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
    
    CLOSED SET of goal types (do not expand without design review):
    - browser_search: Search on a platform (youtube, google)
    - browser_navigate: Open a URL directly
    - app_launch: Launch an application
    - app_action: Perform action within an app
    - file_operation: File/folder CRUD
    - system_query: Get system information
    - system_control: Control system state (audio, display, power)
    - media_control: Control media playback (play, pause, next, previous)
    """
    goal_type: Literal[
        "browser_search",
        "browser_navigate",
        "app_launch",
        "app_action",
        "file_operation",
        "system_query",
        "system_control",
        "media_control"
    ]
    
    # Optional fields based on goal_type
    platform: Optional[str] = None      # youtube, google, spotify
    query: Optional[str] = None         # nvidia, weather
    target: Optional[str] = None        # URL, file path, app name (semantic)
    action: Optional[str] = None        # play, mkdir, create
    content: Optional[str] = None       # File content, etc.
    object_type: Optional[str] = None   # "folder" | "file" for file_operation
    goal_id: Optional[str] = None       # Unique ID for action linking
    
    # SCOPE-BASED DEPENDENCY (single source of truth)
    # Allowed forms: "root", "inside:<target>", "drive:<letter>", "after:<target>"
    scope: str = "root"
    
    # Path resolution fields (set by GoalOrchestrator, NOT by interpreter)
    base_anchor: Optional[str] = None   # WORKSPACE, DESKTOP, DRIVE_D, etc.
    resolved_path: Optional[str] = None # Authoritative absolute path (planner MUST use this)


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
                        "goal_type": {
                            "type": "string",
                            "enum": [
                                "browser_search",
                                "browser_navigate",
                                "app_launch",
                                "app_action",
                                "file_operation",
                                "system_query",
                                "system_control",
                                "media_control"
                            ]
                        },
                        "platform": {"type": "string"},
                        "query": {"type": "string"},
                        "target": {"type": "string"},
                        "action": {"type": "string"},
                        "content": {"type": "string"},
                        "object_type": {
                            "type": "string",
                            "enum": ["folder", "file"],
                            "description": "For file_operation: whether target is folder or file"
                        },
                        "scope": {
                            "type": "string",
                            "description": "Semantic scope: 'root', 'inside:<target>', 'drive:<letter>', 'after:<target>'"
                        }
                    },
                    "required": ["goal_type"]
                }
            },
            "reasoning": {"type": "string"}
        },
        "required": ["meta_type", "goals"]
    }
    
    FEW_SHOT_EXAMPLES = """
## SEMANTIC GOAL EXTRACTION WITH SCOPE-BASED DEPENDENCIES

### SCOPE SEMANTICS (CRITICAL)
- "root" = no parent dependency (default)
- "inside:<target>" = this goal goes inside the named container
- "drive:<letter>" = this goal is in a specific drive (no dependency, just location)
- "after:<target>" = this goal runs after the named goal completes

### DO NOT output dependencies array. DO NOT use goal indices.
### Express ordering ONLY via scope field.

### independent_multi (truly independent goals - all scope: "root")

User: "open chrome and open spotify"
→ {
    "meta_type": "independent_multi",
    "goals": [
        {"goal_type": "app_launch", "target": "chrome", "scope": "root"},
        {"goal_type": "app_launch", "target": "spotify", "scope": "root"}
    ],
    "reasoning": "Two independent app launches, no ordering needed"
}

User: "increase volume and take a screenshot"
→ {
    "meta_type": "independent_multi", 
    "goals": [
        {"goal_type": "system_control", "action": "volume_up", "scope": "root"},
        {"goal_type": "system_control", "action": "screenshot", "scope": "root"}
    ],
    "reasoning": "Two independent system control operations"
}

User: "unmute and set brightness to 50"
→ {
    "meta_type": "independent_multi", 
    "goals": [
        {"goal_type": "system_control", "action": "unmute", "scope": "root"},
        {"goal_type": "system_control", "action": "set_brightness", "target": "50", "scope": "root"}
    ],
    "reasoning": "Two independent system control: audio unmute and display brightness"
}

User: "mute volume and lower brightness"
→ {
    "meta_type": "independent_multi", 
    "goals": [
        {"goal_type": "system_control", "action": "mute", "scope": "root"},
        {"goal_type": "system_control", "action": "lower_brightness", "scope": "root"}
    ],
    "reasoning": "Two independent system control: audio mute and display"
}

### dependent_multi (goals with scope-based dependencies)
### CRITICAL: Use scope to express containment and ordering!

User: "create a folder called alex in D drive and create a ppt inside it"
→ {
    "meta_type": "dependent_multi",
    "goals": [
        {"goal_type": "file_operation", "action": "create", "object_type": "folder", "target": "alex", "scope": "drive:D"},
        {"goal_type": "file_operation", "action": "create", "object_type": "file", "target": "presentation.pptx", "scope": "inside:alex"}
    ],
    "reasoning": "File goes inside alex folder. scope:inside:alex expresses containment."
}

User: "create folder space and inside it folder galaxy and inside it file milkyway"
→ {
    "meta_type": "dependent_multi",
    "goals": [
        {"goal_type": "file_operation", "action": "create", "object_type": "folder", "target": "space", "scope": "root"},
        {"goal_type": "file_operation", "action": "create", "object_type": "folder", "target": "galaxy", "scope": "inside:space"},
        {"goal_type": "file_operation", "action": "create", "object_type": "file", "target": "milkyway.txt", "scope": "inside:galaxy"}
    ],
    "reasoning": "Nested containment: galaxy inside space, milkyway inside galaxy. Each scope references its parent."
}

User: "create folder X, create folder Y, create folder Z inside X"
→ {
    "meta_type": "dependent_multi",
    "goals": [
        {"goal_type": "file_operation", "action": "create", "object_type": "folder", "target": "X", "scope": "root"},
        {"goal_type": "file_operation", "action": "create", "object_type": "folder", "target": "Y", "scope": "root"},
        {"goal_type": "file_operation", "action": "create", "object_type": "folder", "target": "Z", "scope": "inside:X"}
    ],
    "reasoning": "X and Y are SIBLINGS (both root). Z explicitly goes inside X. Enumeration = same scope."
}

User: "create two folders named X and Y. Inside X create folder Z"
→ {
    "meta_type": "dependent_multi",
    "goals": [
        {"goal_type": "file_operation", "action": "create", "object_type": "folder", "target": "X", "scope": "root"},
        {"goal_type": "file_operation", "action": "create", "object_type": "folder", "target": "Y", "scope": "root"},
        {"goal_type": "file_operation", "action": "create", "object_type": "folder", "target": "Z", "scope": "inside:X"}
    ],
    "reasoning": "X and Y are SIBLINGS - enumeration means same scope. 'Inside X' only applies to Z."
}

User: "Create folder A. Create folder B in D drive. Inside A create C."
→ {
    "meta_type": "dependent_multi",
    "goals": [
        {"goal_type": "file_operation", "action": "create", "object_type": "folder", "target": "A", "scope": "root"},
        {"goal_type": "file_operation", "action": "create", "object_type": "folder", "target": "B", "scope": "drive:D"},
        {"goal_type": "file_operation", "action": "create", "object_type": "folder", "target": "C", "scope": "inside:A"}
    ],
    "reasoning": "A at root, B in D drive (different location), C inside A. drive:D is location, not dependency."
}

### Single goals

User: "open youtube and search nvidia"
→ {
    "meta_type": "single",
    "goals": [
        {"goal_type": "browser_search", "platform": "youtube", "query": "nvidia", "scope": "root"}
    ],
    "reasoning": "One semantic goal: search nvidia on youtube"
}

User: "create a folder named space in D drive"
→ {
    "meta_type": "single",
    "goals": [
        {"goal_type": "file_operation", "action": "create", "object_type": "folder", "target": "space", "scope": "drive:D"}
    ],
    "reasoning": "Single file operation with explicit location via scope."
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
        
        Rules:
        - scope="root" → no dependency
        - scope="inside:<target>" → depends on goal where target=<target>
        - scope="drive:<letter>" → no dependency (just location)
        - scope="after:<target>" → depends on goal where target=<target>
        
        Args:
            goals_data: List of goal dicts with scope annotations
            
        Returns:
            Dependencies as tuple of (goal_idx, (depends_on...))
        """
        # Build target → idx map
        name_to_idx: Dict[str, int] = {}
        for idx, g in enumerate(goals_data):
            target = g.get("target")
            if target:
                name_to_idx[target] = idx
        
        dependencies: List[Tuple[int, Tuple[int, ...]]] = []
        
        for idx, goal in enumerate(goals_data):
            scope = goal.get("scope", "root")
            
            if scope == "root" or scope.startswith("drive:"):
                # No dependency
                continue
            
            if scope.startswith("inside:"):
                parent_name = scope[7:]  # Remove "inside:"
                if parent_name in name_to_idx:
                    parent_idx = name_to_idx[parent_name]
                    if parent_idx < idx:  # Forward reference only
                        dependencies.append((idx, (parent_idx,)))
                        logging.debug(
                            f"ScopeDerived: g{idx} depends on g{parent_idx} "
                            f"(inside:{parent_name})"
                        )
                    else:
                        logging.warning(
                            f"ScopeError: g{idx} references future goal '{parent_name}' - skipped"
                        )
                else:
                    logging.warning(
                        f"ScopeError: g{idx} references unknown target '{parent_name}'"
                    )
            
            elif scope.startswith("after:"):
                prereq_name = scope[6:]  # Remove "after:"
                if prereq_name in name_to_idx:
                    prereq_idx = name_to_idx[prereq_name]
                    if prereq_idx < idx:  # Forward reference only
                        dependencies.append((idx, (prereq_idx,)))
                        logging.debug(
                            f"ScopeDerived: g{idx} depends on g{prereq_idx} "
                            f"(after:{prereq_name})"
                        )
                    else:
                        logging.warning(
                            f"ScopeError: g{idx} references future goal '{prereq_name}' - skipped"
                        )
                else:
                    logging.warning(
                        f"ScopeError: g{idx} references unknown target '{prereq_name}'"
                    )
        
        return dependencies
    
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
1. Extract SEMANTIC GOALS, not actions
2. independent_multi = goals that don't depend on each other (all scope: "root")
3. dependent_multi = later goals have containment/ordering (use scope: "inside:<target>" or "after:<target>")
4. Use correct goal_type from the closed set
5. CRITICAL: Targets must be RAW names only, NOT full paths
6. DO NOT output dependencies array - use scope field instead
7. Express ordering and containment ONLY via scope

Return JSON with:
- meta_type: "single" | "independent_multi" | "dependent_multi"
- goals: list of goal objects with goal_type, scope, and relevant fields
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
            
            # Build Goal objects with unique IDs and scope
            goals = tuple(
                Goal(
                    goal_type=g.get("goal_type", "app_launch"),
                    platform=g.get("platform"),
                    query=g.get("query"),
                    target=g.get("target"),
                    action=g.get("action"),
                    content=g.get("content"),
                    object_type=g.get("object_type"),
                    goal_id=f"g{i}",  # Unique ID for action linking
                    scope=g.get("scope", "root"),  # SCOPE-BASED: single source of truth
                    # INVARIANT: base_anchor derived ONLY from scope, not global detection
                    base_anchor=self._derive_anchor_from_scope(g.get("scope", "root"))
                        if g.get("goal_type") == "file_operation" else None
                )
                for i, g in enumerate(goals_data)
            )
            
            # DEBUG: Log constructed goals
            for i, g in enumerate(goals):
                logging.info(
                    f"DEBUG: Goal[{i}] type={g.goal_type}, target={g.target}, "
                    f"scope={g.scope}, base_anchor={g.base_anchor}"
                )
            
            # Handle edge case: no goals extracted
            if not goals:
                logging.warning(f"GoalInterpreter: No goals extracted from '{user_input}'")
                goals = (Goal(goal_type="app_launch", target=user_input),)
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
            logging.error(f"GoalInterpreter failed: {e}, returning passthrough")
            # Passthrough: treat as single goal
            return MetaGoal(
                meta_type="single",
                goals=(Goal(goal_type="app_launch", target=user_input),),
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
