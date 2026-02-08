"""Goal Interpreter - Semantic goal extraction from user input

RESPONSIBILITY: Transform user input into structured MetaGoal.

Question answered:
"What is the user trying to achieve, semantically?"

Called ONLY when QueryClassifier returns "multi".
Single queries bypass this entirely.

INVARIANTS:
- Goal types are from a CLOSED set (no dynamic types)
- MetaGoal is immutable once created
- Dependencies form a DAG (no cycles)
- Context is read-only
"""

import logging
import re
from core.location_config import LocationConfig
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Literal, Tuple, FrozenSet
from models.model_manager import get_model_manager


# =============================================================================
# DATA CONTRACTS (Immutable)
# =============================================================================

@dataclass(frozen=True)
class Goal:
    """A single semantic goal.
    
    PARAMETRIC SCHEMA (Phase 4):
    - domain: What system/subsystem (browser, file, system, app, memory, media)
    - verb: What action (from closed taxonomy in core/verbs.py)
    - object: What the verb applies to (optional)
    - params: Additional parameters
    
    This schema is future-proof:
    - New tools map to existing verbs
    - New params extend without changing verbs
    - Planner uses (domain, verb) lookup, not branching
    """
    domain: Literal["browser", "file", "system", "app", "memory", "media"]
    verb: str  # From closed taxonomy in core/verbs.py
    
    # Optional semantic object (what the verb applies to)
    object: Optional[str] = None
    
    # Parameters for the goal (varies by domain/verb)
    params: Dict[str, Any] = field(default_factory=dict)
    
    # SCOPE-BASED DEPENDENCY (single source of truth)
    # Allowed forms: "root", "inside:<target>", "drive:<letter>", "after:<target>"
    scope: str = "root"
    
    # Path resolution fields (set by GoalOrchestrator, NOT by interpreter)
    base_anchor: Optional[str] = None   # WORKSPACE, DESKTOP, DRIVE_D, etc.
    resolved_path: Optional[str] = None # Authoritative absolute path (planner MUST use this)
    
    # Unique ID for action linking
    goal_id: Optional[str] = None
    
    def __post_init__(self):
        # Validate domain and verb against taxonomy
        from core.verbs import is_valid_verb, ALL_DOMAINS
        if self.domain not in ALL_DOMAINS:
            raise ValueError(f"Invalid domain: {self.domain}")
        if not is_valid_verb(self.domain, self.verb):
            raise ValueError(f"Invalid verb '{self.verb}' for domain '{self.domain}'")


@dataclass(frozen=True)
class MetaGoal:
    """A goal tree that may contain multiple sub-goals.
    
    INVARIANTS:
    - meta_type determines structure
    - goals is immutable tuple
    - dependencies form a DAG (validated at construction)
    """
    meta_type: Literal["single", "independent_multi", "dependent_multi"]
    goals: Tuple[Goal, ...]
    dependencies: Tuple[Tuple[int, Tuple[int, ...]], ...]  # (goal_idx, (depends_on...))
    
    def __post_init__(self):
        # Validate invariants
        if self.meta_type == "single":
            assert len(self.goals) == 1, "Single meta_type must have exactly 1 goal"
            assert len(self.dependencies) == 0, "Single meta_type cannot have dependencies"
        
        if self.meta_type == "independent_multi":
            assert len(self.dependencies) == 0, "Independent multi cannot have dependencies"
        
        # Validate no cycles in dependencies
        if self.dependencies:
            visited = set()
            for goal_idx, deps in self.dependencies:
                for dep in deps:
                    if dep >= goal_idx:
                        raise ValueError(f"Goal {goal_idx} depends on later goal {dep}")
    
    def get_dependencies(self, goal_idx: int) -> Tuple[int, ...]:
        """Get dependencies for a specific goal."""
        for idx, deps in self.dependencies:
            if idx == goal_idx:
                return deps
        return ()


# =============================================================================
# TOPOLOGY VIOLATION ERROR
# =============================================================================

class TopologyViolationError(Exception):
    """Raised when LLM violates QC authority contract.
    
    INVARIANT: When QC confidence >= 0.85, GI MUST respect topology:
    - QC says "single" → GI must return exactly 1 goal
    - QC says "multi" → GI must return ≥ 2 goals
    
    This error indicates a contract violation that should NOT be auto-corrected.
    """
    pass


# =============================================================================
# GOAL INTERPRETER
# =============================================================================

class GoalInterpreter:
    """Semantic goal extraction from user input.
    
    RESPONSIBILITY:
    - Understand what the user wants, semantically
    - Produce a structured MetaGoal
    
    DOES NOT:
    - Plan how to achieve goals (GoalPlanner's job)
    - Execute anything (Executor's job)
    - Extract actions (that's the old, wrong approach)
    """
    
    INTERPRETER_SCHEMA = {
        "type": "object",
        "properties": {
            "meta_type": {
                "type": "string",
                "enum": ["single", "independent_multi", "dependent_multi"]
            },
            "goals": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "domain": {
                            "type": "string",
                            "enum": ["browser", "file", "system", "app", "memory", "media"],
                            "description": "What system/subsystem the goal applies to"
                        },
                        "verb": {
                            "type": "string",
                            "description": "What action from closed taxonomy (navigate, wait, click, type, read, create, delete, launch, etc.)"
                        },
                        "object": {
                            "type": "string",
                            "description": "What the verb applies to (optional)"
                        },
                        "params": {
                            "type": "object",
                            "description": "Additional parameters for the goal"
                        },
                        "scope": {
                            "type": "string",
                            "description": "Semantic scope: 'root', 'inside:<target>', 'drive:<letter>', 'after:<target>'"
                        }
                    },
                    "required": ["domain", "verb"]
                }
            },
            "reasoning": {"type": "string"}
        },
        "required": ["meta_type", "goals"]
    }
    
    FEW_SHOT_EXAMPLES = """
## SEMANTIC GOAL EXTRACTION - PARAMETRIC SCHEMA (Phase 4)

### CORE PRINCIPLE
Goals describe WHAT, not HOW. Use domain + verb + params.

### VERB TAXONOMY (CLOSED SET - DO NOT INVENT NEW VERBS)
- browser: navigate, search, wait, click, type, read, scroll, select
- file: create, delete, move, copy, read, write, rename, list
- system: set, get, toggle, query
- app: launch, focus, close
- media: play, pause, stop, next, previous
- memory: store, recall

### SCOPE SEMANTICS (CRITICAL)
- "root" = no parent dependency (default)
- "inside:<target>" = this goal goes inside the named container
- "drive:<letter>" = this goal is in a specific drive (no dependency, just location)
- "after:<target>" = this goal runs after the named goal completes

### DO NOT output dependencies array. DO NOT use goal indices.
### Express ordering ONLY via scope field.

### independent_multi (truly independent goals - all scope: "root")


User: "increase volume and take a screenshot"
→ {
    "meta_type": "independent_multi", 
    "goals": [
        {"domain": "system", "verb": "set", "params": {"target": "volume", "value": "up"}, "scope": "root"},
        {"domain": "system", "verb": "get", "params": {"target": "screenshot"}, "scope": "root"}
    ],
    "reasoning": "Two independent system operations"
}

User: "mute volume and lower brightness"
→ {
    "meta_type": "independent_multi", 
    "goals": [
        {"domain": "system", "verb": "toggle", "params": {"target": "mute"}, "scope": "root"},
        {"domain": "system", "verb": "set", "params": {"target": "brightness", "value": "down"}, "scope": "root"}
    ],
    "reasoning": "Two independent system control: audio mute and display"
}

### dependent_multi (goals with scope-based dependencies)
### CRITICAL: Use scope to express containment and ordering!

User: "create a folder called alex in D drive and create a ppt inside it"
→ {
    "meta_type": "dependent_multi",
    "goals": [
        {"domain": "file", "verb": "create", "params": {"object_type": "folder", "name": "alex"}, "scope": "drive:D"},
        {"domain": "file", "verb": "create", "params": {"object_type": "file", "name": "presentation.pptx"}, "scope": "inside:alex"}
    ],
    "reasoning": "File goes inside alex folder. scope:inside:alex expresses containment."
}

User: "create folder space and inside it folder galaxy and inside it file milkyway"
→ {
    "meta_type": "dependent_multi",
    "goals": [
        {"domain": "file", "verb": "create", "params": {"object_type": "folder", "name": "space"}, "scope": "root"},
        {"domain": "file", "verb": "create", "params": {"object_type": "folder", "name": "galaxy"}, "scope": "inside:space"},
        {"domain": "file", "verb": "create", "params": {"object_type": "file", "name": "milkyway.txt"}, "scope": "inside:galaxy"}
    ],
    "reasoning": "Nested containment: galaxy inside space, milkyway inside galaxy."
}

User: "go to google.com and wait for the search box and read the title"
→ {
    "meta_type": "dependent_multi",
    "goals": [
        {"domain": "browser", "verb": "navigate", "params": {"url": "https://google.com"}, "scope": "root"},
        {"domain": "browser", "verb": "wait", "params": {"selector": "input[name='q']", "state": "visible"}, "scope": "after:navigate"},
        {"domain": "browser", "verb": "read", "object": "title", "scope": "after:wait"}
    ],
    "reasoning": "Sequential browser interaction: navigate, wait for element, read title."
}

### Single goals

User: "search nvidia"
→ {
    "meta_type": "single",
    "goals": [
        {"domain": "browser", "verb": "search", "params": {"query": "nvidia"}, "scope": "root"}
    ],
    "reasoning": "Search query without explicit platform - platform will use default"
}

User: "open youtube and search nvidia"
→ {
    "meta_type": "single",
    "goals": [
        {"domain": "browser", "verb": "search", "params": {"platform": "youtube", "query": "nvidia"}, "scope": "root"}
    ],
    "reasoning": "One semantic goal: search nvidia on youtube"
}

User: "go to google.com"
→ {
    "meta_type": "single",
    "goals": [
        {"domain": "browser", "verb": "navigate", "params": {"url": "https://google.com"}, "scope": "root"}
    ],
    "reasoning": "Single navigation goal"
}

User: "create a folder named space in D drive"
→ {
    "meta_type": "single",
    "goals": [
        {"domain": "file", "verb": "create", "params": {"object_type": "folder", "name": "space"}, "scope": "drive:D"}
    ],
    "reasoning": "Single file operation with explicit location via scope."
}

User: "play music"
→ {
    "meta_type": "single",
    "goals": [
        {"domain": "media", "verb": "play", "scope": "root"}
    ],
    "reasoning": "Single media control operation"
}

### CONTEXTUAL INTENT RESOLUTION (CRITICAL FOR SESSION-BASED OPERATIONS)
### When user mentions an app followed by operations WITHIN that app's domain,
### the user's intent is the operation, not app visibility.
### Only use app.launch when user wants the application window itself.

# User intent is browser operation, not app visibility
User: "open chrome and go to youtube"
→ {
    "meta_type": "single",
    "goals": [
        {"domain": "browser", "verb": "navigate", "params": {"url": "https://youtube.com"}, "scope": "root"}
    ],
    "reasoning": "User intent is to visit YouTube. 'Open chrome' is instrumental, not the goal."
}

# User intent is search, browser is just the medium
User: "open chrome, go to youtube, search nvidia"
→ {
    "meta_type": "single",
    "goals": [
        {"domain": "browser", "verb": "search", "params": {"platform": "youtube", "query": "nvidia"}, "scope": "root"}
    ],
    "reasoning": "User intent is to search for nvidia on YouTube. Express terminal goal only."
}

# User intent is search, not app launch
User: "open chrome and search for cats"
→ {
    "meta_type": "single",
    "goals": [
        {"domain": "browser", "verb": "search", "params": {"query": "cats"}, "scope": "root"}
    ],
    "reasoning": "User intent is to search for cats. Browser is just the medium."
}

# User intent is platform search
User: "go to github and search pytorch"
→ {
    "meta_type": "single",
    "goals": [
        {"domain": "browser", "verb": "search", "params": {"platform": "github", "query": "pytorch"}, "scope": "root"}
    ],
    "reasoning": "User intent is to find pytorch on GitHub."
}

# User intent IS app visibility (standalone request)
User: "open chrome"
→ {
    "meta_type": "single",
    "goals": [
        {"domain": "app", "verb": "launch", "params": {"app_name": "chrome"}, "scope": "root"}
    ],
    "reasoning": "User wants the Chrome window visible. No further operation follows."
}

# Two separate user intents - both want app visibility
User: "open chrome and open spotify"
→ {
    "meta_type": "independent_multi",
    "goals": [
        {"domain": "app", "verb": "launch", "params": {"app_name": "chrome"}, "scope": "root"},
        {"domain": "app", "verb": "launch", "params": {"app_name": "spotify"}, "scope": "root"}
    ],
    "reasoning": "User wants both apps visible. Neither has a follow-up operation."
}
"""
    
    def __init__(self):
        # Role-based model access (config-driven)
        self.model = get_model_manager().get("goal_interpreter")
        logging.info("GoalInterpreter initialized (semantic goal extraction)")
    
    def _enforce_topology(
        self, 
        qc_output: Optional[Dict[str, Any]], 
        goals: List[Dict[str, Any]]
    ) -> None:
        """Enforce QC authority contract.
        
        AUTHORITY CONTRACT:
        - When confidence >= 0.85, LLM MUST respect QC topology
        - QC="single" → exactly 1 goal
        - QC="multi" → at least 2 goals
        
        FAIL FAST on violations. Do NOT auto-correct.
        
        Args:
            qc_output: QueryClassifier result with classification + confidence
            goals: Goals extracted by LLM
            
        Raises:
            TopologyViolationError: When LLM contradicts high-confidence QC
        """
        if not qc_output:
            return  # No QC output, LLM is free
        
        confidence = qc_output.get("confidence", 0.0)
        if confidence < 0.85:
            return  # Low confidence, LLM is free to reason
        
        qc_class = qc_output.get("classification", "unknown")
        goal_count = len(goals)
        
        if qc_class == "single" and goal_count != 1:
            raise TopologyViolationError(
                f"QC authority violated: QC='single' (confidence={confidence}) "
                f"but LLM returned {goal_count} goal(s). "
                f"High-confidence QC cannot be overridden."
            )
        
        if qc_class == "multi" and goal_count < 2:
            raise TopologyViolationError(
                f"QC authority violated: QC='multi' (confidence={confidence}) "
                f"but LLM returned only {goal_count} goal(s). "
                f"High-confidence QC requires multi-goal output."
            )
    
    
    def _derive_dependencies_from_scope(
        self, 
        goals_data: List[Dict[str, Any]]
    ) -> List[Tuple[int, Tuple[int, ...]]]:
        """Derive dependencies deterministically from scope annotations.
        
        THIS IS THE SINGLE AUTHORITY FOR DEPENDENCY CREATION.
        No LLM dependencies. No repair logic. Pure scope → DAG conversion.
        
        PHASE 4 UPDATE: Supports multiple resolution strategies:
        - after:g0, after:g1 → goal ID based (preferred)
        - after:navigate, after:wait → verb based (LLM natural output)
        - inside:folder_name → target based (legacy file operations)
        
        Rules:
        - scope="root" → no dependency
        - scope="inside:<ref>" → depends on goal matching <ref>
        - scope="drive:<letter>" → no dependency (just location)
        - scope="after:<ref>" → depends on goal matching <ref>
        
        Args:
            goals_data: List of goal dicts with scope annotations
            
        Returns:
            Dependencies as tuple of (goal_idx, (depends_on...))
        """
        # Build multiple resolution maps for flexibility
        # 1. Goal ID map: g0 → 0, g1 → 1
        id_to_idx: Dict[str, int] = {f"g{idx}": idx for idx in range(len(goals_data))}
        
        # 2. Verb map: navigate → 0, wait → 1 (first occurrence wins)
        verb_to_idx: Dict[str, int] = {}
        for idx, g in enumerate(goals_data):
            verb = g.get("verb")
            if verb and verb not in verb_to_idx:
                verb_to_idx[verb] = idx
        
        # 3. Target/object map: folder_name → idx (for file operations)
        target_to_idx: Dict[str, int] = {}
        for idx, g in enumerate(goals_data):
            # Try object field (parametric) then target (legacy)
            target = g.get("object") or g.get("target") or g.get("params", {}).get("name")
            if target and target not in target_to_idx:
                # First occurrence wins for target → map to earliest defining goal
                target_to_idx[target] = idx
        
        logging.debug(f"ScopeResolver: id_map={id_to_idx}, verb_map={verb_to_idx}, target_map={target_to_idx}")
        
        def resolve_ref(ref: str) -> Optional[int]:
            """Resolve a reference to a goal index using multiple strategies."""
            # Try goal ID first (g0, g1, etc.)
            if ref in id_to_idx:
                return id_to_idx[ref]
            # Try verb (navigate, wait, etc.)
            if ref in verb_to_idx:
                return verb_to_idx[ref]
            # Try target/object name
            if ref in target_to_idx:
                return target_to_idx[ref]
            return None
        
        dependencies: List[Tuple[int, Tuple[int, ...]]] = []
        
        for idx, goal in enumerate(goals_data):
            scope = goal.get("scope", "root")
            
            if scope == "root" or scope.startswith("drive:"):
                # No dependency
                continue
            
            ref_type = None
            ref_name = None
            
            if scope.startswith("inside:"):
                ref_type = "inside"
                ref_name = scope[7:]  # Remove "inside:"
            elif scope.startswith("after:"):
                ref_type = "after"
                ref_name = scope[6:]  # Remove "after:"
            else:
                logging.warning(f"ScopeError: Unknown scope format '{scope}' for g{idx}")
                continue
            
            resolved_idx = resolve_ref(ref_name)
            
            if resolved_idx is not None:
                if resolved_idx < idx:  # Forward reference only
                    dependencies.append((idx, (resolved_idx,)))
                    logging.info(
                        f"ScopeDerived: g{idx} depends on g{resolved_idx} "
                        f"({ref_type}:{ref_name})"
                    )
                else:
                    logging.warning(
                        f"ScopeError: g{idx} references future/self goal '{ref_name}' - skipped"
                    )
            else:
                logging.warning(
                    f"ScopeError: g{idx} references unknown '{ref_name}' "
                    f"(tried: id, verb, target)"
                )
        
        return dependencies

    
    def _suppress_redundant_app_launches(
        self, 
        goals_data: List[Dict[str, Any]], 
        dependencies: Tuple[Tuple[int, Tuple[int, ...]], ...]
    ) -> List[Dict[str, Any]]:
        """Suppress app.launch if its substrate is bootstrapped by another goal.
        
        SEMANTIC SUPPRESSION RULE (SUBSTRATE-SPECIFIC, ORDER-AGNOSTIC):
        Suppress app.launch(A) only if:
        1. There exists a goal G with session_bootstraps=True and provides_substrate=S
        2. app_name A maps to substrate S (via SubstrateConfig)
        3. app.launch contributes no unique semantic data
        
        IMPORTANT: Dependency direction is IGNORED because LLM may emit goals
        in inconsistent order. Substrate match is the sole criterion.
        
        ASSUMPTION: Suppression assumes app.launch does not contribute semantic
        data required by other goals. If app.launch carries semantic data
        (e.g., profile selection), this rule must be revisited.
        
        This happens BEFORE MetaGoal finalization, not during execution.
        Suppressed goals never reach the Planner.
        
        Args:
            goals_data: Raw goal dicts from LLM
            dependencies: Derived dependencies (unused - order-agnostic)
            
        Returns:
            Filtered goals_data with redundant app.launch removed
        """
        from core.planner_rules import PLANNER_RULES
        from core.substrate_config import SubstrateConfig
        
        # Step 1: Find substrates bootstrapped by goals in this block
        bootstrapped_substrates: set = set()
        for goal in goals_data:
            domain = goal.get("domain")
            verb = goal.get("verb")
            rule = PLANNER_RULES.get((domain, verb), {})
            
            if rule.get("session_bootstraps", False):
                # Use explicit provides_substrate, or fall back to domain
                substrate = rule.get("provides_substrate", domain)
                bootstrapped_substrates.add(substrate)
                
                # Guardrail: warn if session_bootstraps but no provides_substrate
                if "provides_substrate" not in rule:
                    logging.warning(
                        f"Planner rule ({domain}, {verb}) bootstraps a session but "
                        f"does not declare provides_substrate - using domain as fallback"
                    )
        
        if not bootstrapped_substrates:
            # No self-bootstrapping goals - nothing to suppress
            return goals_data
        
        # Step 2: Suppress app.launch only if its substrate is bootstrapped
        substrate_config = SubstrateConfig.get()
        suppressed: set = set()
        suppressed_app_names: set = set()
        
        for idx, goal in enumerate(goals_data):
            if goal.get("domain") != "app" or goal.get("verb") != "launch":
                continue
            
            app_name = goal.get("params", {}).get("app_name", "")
            target_substrate = substrate_config.get_substrate(app_name)
            
            if target_substrate and target_substrate in bootstrapped_substrates:
                suppressed.add(idx)
                suppressed_app_names.add(app_name.lower())
                logging.info(
                    f"SEMANTIC_SUPPRESSION: app.launch({app_name}) suppressed - "
                    f"substrate '{target_substrate}' bootstrapped by another goal"
                )
            elif target_substrate is None:
                # Unknown app - do NOT suppress (safe default)
                logging.debug(
                    f"SEMANTIC_SUPPRESSION: app.launch({app_name}) kept - "
                    f"unknown substrate (not in config)"
                )
        
        if suppressed:
            logging.info(
                f"SEMANTIC_SUPPRESSION: Removed {len(suppressed)} redundant "
                f"app.launch goal(s) (substrate-specific)"
            )
        
        # =====================================================================
        # Step 3: Clean leaked substrate params from remaining goals
        # =====================================================================
        # INVARIANT: Only remove parameters whose value is a direct semantic
        # reference to a suppressed goal. Do NOT remove params just because
        # domain matches or substrate matches.
        #
        # Example: browser.search(platform="chrome") → delete platform
        #          Planner will apply default_params: {platform: "google"}
        # =====================================================================
        if suppressed_app_names:
            for goal in goals_data:
                domain = goal.get("domain")
                
                # Check if goal's domain matches any suppressed app's substrate
                domain_matches_substrate = False
                for app_name in suppressed_app_names:
                    substrate = substrate_config.get_substrate(app_name)
                    if substrate == domain:
                        domain_matches_substrate = True
                        break
                
                if domain_matches_substrate:
                    # Clean params that equal suppressed app names
                    params = goal.get("params", {})
                    keys_to_delete = []
                    
                    for key, value in params.items():
                        if isinstance(value, str) and value.lower() in suppressed_app_names:
                            keys_to_delete.append(key)
                            logging.info(
                                f"SEMANTIC_CLEANUP: Removed {domain}.{goal.get('verb')}.{key}='{value}' "
                                f"(leaked from suppressed app.launch)"
                            )
                    
                    for key in keys_to_delete:
                        del params[key]
        
        # Return filtered goals (preserves order)
        return [g for i, g in enumerate(goals_data) if i not in suppressed]

    
    def interpret(
        self, 
        user_input: str, 
        qc_output: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> MetaGoal:
        """Extract semantic goals from user input.
        
        Args:
            user_input: Raw user command
            qc_output: QueryClassifier output with classification + confidence
            context: Optional world state (read-only)
            
        Returns:
            MetaGoal with structured goals
        """
        # Build QC authority context for prompt
        qc_context = ""
        if qc_output:
            qc_class = qc_output.get("classification", "unknown")
            qc_conf = qc_output.get("confidence", 0.5)
            qc_reason = qc_output.get("reasoning", "")
            qc_context = f"""
## QUERY CLASSIFIER OUTPUT (AUTHORITATIVE)
Classification: {qc_class}
Confidence: {qc_conf}
Reasoning: {qc_reason}

AUTHORITY RULES:
- If confidence >= 0.85, you MUST respect the classification
- "single" → return exactly 1 goal
- "multi" → return 2+ goals
- Do NOT contradict high-confidence QC judgments
"""
        
        prompt = f"""You are a semantic goal interpreter.

Your job: Understand what the user is trying to achieve and extract structured goals with scope annotations.
{qc_context}
{self.FEW_SHOT_EXAMPLES}

---

INTERPRET THIS INPUT:
User: "{user_input}"

RULES:
1. Extract SEMANTIC GOALS using domain + verb + params, not procedural actions
2. independent_multi = goals that don't depend on each other (all scope: "root")
3. dependent_multi = later goals have containment/ordering (use scope: "inside:<target>" or "after:<target>")
4. Use ONLY verbs from the closed taxonomy (see above)
5. CRITICAL: Targets must be RAW names only, NOT full paths
6. DO NOT output dependencies array - use scope field instead
7. Express ordering and containment ONLY via scope

Return JSON with:
- meta_type: "single" | "independent_multi" | "dependent_multi"
- goals: list of goal objects with domain, verb, params, scope
- reasoning: brief explanation
"""
        
        try:
            result = self.model.generate(prompt, schema=self.INTERPRETER_SCHEMA)
            
            meta_type = result.get("meta_type", "single")
            goals_data = result.get("goals", [])
            reasoning = result.get("reasoning", "")
            
            # AUTHORITY CONTRACT: Enforce QC topology when confident
            self._enforce_topology(qc_output, goals_data)
            
            # DEBUG: Log raw LLM output
            logging.info(f"DEBUG: LLM goals (with scope): {goals_data}")
            
            # DETERMINISTIC DEPENDENCY DERIVATION (single authority)
            # No LLM dependencies. Pure scope → DAG conversion.
            dependencies = tuple(self._derive_dependencies_from_scope(goals_data))
            
            logging.info(f"DEBUG: Derived dependencies: {dependencies}")
            
            # =================================================================
            # SEMANTIC SUPPRESSION: Remove redundant app.launch goals
            # =================================================================
            # If a goal depends on app.launch AND can self-bootstrap, suppress app.launch.
            # This happens BEFORE MetaGoal finalization - suppressed goals never reach Planner.
            goals_data = self._suppress_redundant_app_launches(goals_data, dependencies)
            
            # Re-derive dependencies after suppression (indices may have shifted)
            dependencies = tuple(self._derive_dependencies_from_scope(goals_data))
            logging.info(f"DEBUG: Dependencies after suppression: {dependencies}")
            # =================================================================
            
            # =================================================================
            # AUTO-CORRECT meta_type BASED ON STRUCTURAL FACTS
            # =================================================================
            # LLM may output inconsistent meta_type (e.g., "single" with 2 goals).
            # Derived dependencies are authoritative. Correct meta_type accordingly.
            # This is structural normalization, NOT semantic rewriting.
            goal_count = len(goals_data)
            
            if goal_count == 1:
                # Single goal - force single regardless of what LLM said
                meta_type = "single"
                dependencies = ()  # Single cannot have deps
            elif dependencies:
                # Multiple goals WITH dependencies → dependent_multi
                meta_type = "dependent_multi"
            else:
                # Multiple goals, NO dependencies → independent_multi
                meta_type = "independent_multi"
            
            logging.info(f"DEBUG: Auto-corrected meta_type: {meta_type}")
            # =================================================================
            
            # Build Goal objects with unique IDs and scope (PARAMETRIC SCHEMA)
            goals = tuple(
                Goal(
                    domain=g.get("domain", "app"),
                    verb=g.get("verb", "launch"),
                    object=g.get("object"),
                    params=g.get("params", {}),
                    goal_id=f"g{i}",  # Unique ID for action linking
                    scope=g.get("scope", "root"),  # SCOPE-BASED: single source of truth
                    # INVARIANT: base_anchor derived ONLY from scope, not global detection
                    base_anchor=self._derive_anchor_from_scope(g.get("scope", "root"))
                        if g.get("domain") == "file" else None
                )
                for i, g in enumerate(goals_data)
            )
            
            # DEBUG: Log constructed goals
            for i, g in enumerate(goals):
                logging.info(
                    f"DEBUG: Goal[{i}] domain={g.domain}, verb={g.verb}, "
                    f"params={g.params}, scope={g.scope}, base_anchor={g.base_anchor}"
                )
            
            # Handle edge case: no goals extracted
            if not goals:
                logging.warning(f"GoalInterpreter: No goals extracted from '{user_input}'")
                # Fallback to safe browser.search
                goals = (Goal(domain="browser", verb="search", params={"query": user_input}),)
                meta_type = "single"
                dependencies = ()
            
            meta_goal = MetaGoal(
                meta_type=meta_type,
                goals=goals,
                dependencies=dependencies
            )
            
            logging.info(
                f"GoalInterpreter: '{user_input[:50]}...' → {meta_type} "
                f"({len(goals)} goal(s), {len(dependencies)} dep(s))"
            )
            logging.debug(f"Goals: {goals}")
            
            return meta_goal
            
        except Exception as e:
            # =================================================================
            # FIX C: SAFE PASSTHROUGH FALLBACK
            # =================================================================
            # Never create app.launch(entire_input) - that's always wrong.
            # browser.search is universally safe: informational, no side effects.
            logging.error(f"GoalInterpreter failed: {e}, returning safe search fallback")
            return MetaGoal(
                meta_type="single",
                goals=(Goal(domain="browser", verb="search", params={"query": user_input}),),
                dependencies=()
            )
    
    def _derive_anchor_from_scope(self, scope: str) -> Optional[str]:
        """Derive base_anchor from scope annotation.
        
        Delegates to LocationConfig for scope→anchor conversion.
        
        INVARIANT: Anchors do NOT leak across scopes.
        - drive:X → DRIVE_X (explicit from scope)
        - inside:X → None (inherit via dependency in orchestrator)
        - root → None (default to WORKSPACE in orchestrator)
        - after:X → None (ordering only, no anchor)
        
        Args:
            scope: The scope string (e.g., "drive:D", "root")
            
        Returns:
            Anchor name (DRIVE_D, etc.) or None for inheritance/default
        """
        return LocationConfig.get().get_anchor_from_scope(scope)
