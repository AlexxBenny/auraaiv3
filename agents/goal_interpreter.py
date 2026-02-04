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
    parent_target: Optional[str] = None # Explicit parent by name ("inside X")
    
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
                        "parent_target": {
                            "type": "string",
                            "description": "Explicit parent folder name for 'inside X' patterns"
                        },
                        "object_type": {
                            "type": "string",
                            "enum": ["folder", "file"],
                            "description": "For file_operation: whether target is folder or file"
                        }
                    },
                    "required": ["goal_type"]
                }
            },
            "dependencies": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "goal_idx": {"type": "integer"},
                        "depends_on": {
                            "type": "array",
                            "items": {"type": "integer"}
                        }
                    }
                }
            },
            "reasoning": {"type": "string"}
        },
        "required": ["meta_type", "goals"]
    }
    
    FEW_SHOT_EXAMPLES = """
## SEMANTIC GOAL EXTRACTION

### independent_multi (truly independent goals)

User: "open chrome and open spotify"
→ {
    "meta_type": "independent_multi",
    "goals": [
        {"goal_type": "app_launch", "target": "chrome"},
        {"goal_type": "app_launch", "target": "spotify"}
    ],
    "dependencies": [],
    "reasoning": "Two independent app launches"
}

User: "increase volume and take a screenshot"
→ {
    "meta_type": "independent_multi", 
    "goals": [
        {"goal_type": "system_control", "action": "volume_up"},
        {"goal_type": "system_control", "action": "screenshot"}
    ],
    "dependencies": [],
    "reasoning": "Two independent system control operations"
}

User: "unmute and set brightness to 50"
→ {
    "meta_type": "independent_multi", 
    "goals": [
        {"goal_type": "system_control", "action": "unmute"},
        {"goal_type": "system_control", "action": "set_brightness", "target": "50"}
    ],
    "dependencies": [],
    "reasoning": "Two independent system control: audio unmute and display brightness"
}

User: "mute volume and lower brightness"
→ {
    "meta_type": "independent_multi", 
    "goals": [
        {"goal_type": "system_control", "action": "mute"},
        {"goal_type": "system_control", "action": "lower_brightness"}
    ],
    "dependencies": [],
    "reasoning": "Two independent system control: audio mute and display"
}

User: "open notepad and open calculator"
→ {
    "meta_type": "independent_multi",
    "goals": [
        {"goal_type": "app_launch", "target": "notepad"},
        {"goal_type": "app_launch", "target": "calculator"}
    ],
    "dependencies": [],
    "reasoning": "Two independent app launches"
}

User: "play music and open spotify"
→ {
    "meta_type": "independent_multi",
    "goals": [
        {"goal_type": "media_control", "action": "play"},
        {"goal_type": "app_launch", "target": "spotify"}
    ],
    "dependencies": [],
    "reasoning": "Media playback control and app launch are independent"
}

User: "pause the music and next track"
→ {
    "meta_type": "independent_multi",
    "goals": [
        {"goal_type": "media_control", "action": "pause"},
        {"goal_type": "media_control", "action": "next_track"}
    ],
    "dependencies": [],
    "reasoning": "Two media control operations"
}

User: "take a screenshot and mute"
→ {
    "meta_type": "independent_multi",
    "goals": [
        {"goal_type": "system_control", "action": "screenshot"},
        {"goal_type": "system_control", "action": "mute"}
    ],
    "dependencies": [],
    "reasoning": "Screenshot and mute are independent system control operations"
}

### dependent_multi (goals with dependencies)
### CRITICAL: targets must be RAW names only, NEVER include parent paths!
### PathResolver will combine parent + child at resolution time.

User: "create a folder called alex in D drive and create a ppt inside it"
→ {
    "meta_type": "dependent_multi",
    "goals": [
        {"goal_type": "file_operation", "action": "create", "object_type": "folder", "target": "alex"},
        {"goal_type": "file_operation", "action": "create", "object_type": "file", "target": "presentation.pptx"}
    ],
    "dependencies": [{"goal_idx": 1, "depends_on": [0]}],
    "reasoning": "File creation depends on folder existing. Target is just the name, not the full path."
}

User: "create folder space and inside it folder galaxy and inside it file milkyway"
→ {
    "meta_type": "dependent_multi",
    "goals": [
        {"goal_type": "file_operation", "action": "create", "object_type": "folder", "target": "space"},
        {"goal_type": "file_operation", "action": "create", "object_type": "folder", "target": "galaxy"},
        {"goal_type": "file_operation", "action": "create", "object_type": "file", "target": "milkyway.txt"}
    ],
    "dependencies": [
        {"goal_idx": 1, "depends_on": [0]},
        {"goal_idx": 2, "depends_on": [1]}
    ],
    "reasoning": "Each item is inside the most recently created container. Targets are raw names only!"
}

User: "create folder X, create folder Y, create folder Z inside X"
→ {
    "meta_type": "dependent_multi",
    "goals": [
        {"goal_type": "file_operation", "action": "create", "object_type": "folder", "target": "X"},
        {"goal_type": "file_operation", "action": "create", "object_type": "folder", "target": "Y"},
        {"goal_type": "file_operation", "action": "create", "object_type": "folder", "target": "Z", "parent_target": "X"}
    ],
    "dependencies": [
        {"goal_idx": 2, "depends_on": [0]}
    ],
    "reasoning": "Z explicitly refers to X by name, not the most recent folder Y. Use parent_target for explicit references."
}

User: "create two folders named X and Y. Inside X create folder Z"
→ {
    "meta_type": "dependent_multi",
    "goals": [
        {"goal_type": "file_operation", "action": "create", "object_type": "folder", "target": "X"},
        {"goal_type": "file_operation", "action": "create", "object_type": "folder", "target": "Y"},
        {"goal_type": "file_operation", "action": "create", "object_type": "folder", "target": "Z", "parent_target": "X"}
    ],
    "dependencies": [
        {"goal_idx": 2, "depends_on": [0]}
    ],
    "reasoning": "X and Y are SIBLINGS (no dependency between them). Z is inside X via parent_target. 'Inside X' only applies to Z, not Y."
}

User: "download the file and then open it"
→ {
    "meta_type": "dependent_multi",
    "goals": [
        {"goal_type": "file_operation", "action": "download"},
        {"goal_type": "app_action", "action": "open"}
    ],
    "dependencies": [{"goal_idx": 1, "depends_on": [0]}],
    "reasoning": "Opening depends on download completing"
}

### IMPORTANT: Single goals should rarely come here
### QueryClassifier should route most to single path directly
### But if they do arrive, handle gracefully:

User: "open youtube and search nvidia"
→ {
    "meta_type": "single",
    "goals": [
        {"goal_type": "browser_search", "platform": "youtube", "query": "nvidia"}
    ],
    "dependencies": [],
    "reasoning": "One semantic goal: search nvidia on youtube"
}
"""
    
    def __init__(self):
        self.model = get_model_manager().get_planner_model()
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
    
    def _detect_explicit_anchor(self, user_input: str, goal_idx: int) -> Optional[str]:
        """Detect explicit location anchor from user's LINGUISTIC input.
        
        CRITICAL: Only use user text, NOT LLM-generated paths.
        LLMs sometimes emit absolute paths without user intent.
        
        An explicit anchor exists only if linguistically grounded:
        - "in D drive", "on desktop", "in documents"
        
        Args:
            user_input: Original user command text
            goal_idx: Index of goal being processed (for future position-based logic)
            
        Returns:
            Anchor name if explicit location found, None otherwise
        """
        text = user_input.lower()
        
        # Drive letters (most common explicit anchors)
        if "d drive" in text or "drive d" in text:
            return "DRIVE_D"
        if "c drive" in text or "drive c" in text:
            return "DRIVE_C"
        if "e drive" in text or "drive e" in text:
            return "DRIVE_E"
        
        # Common user directories
        if "desktop" in text:
            return "DESKTOP"
        if "documents" in text or "my documents" in text:
            return "DOCUMENTS"
        if "downloads" in text:
            return "DOWNLOADS"
        
        # Root folder / workspace
        if "root folder" in text or "root directory" in text:
            return "WORKSPACE"
        
        return None
    
    def _fix_container_dependencies(
        self, 
        goals_data: List[Dict[str, Any]], 
        deps_data: List[Dict[str, Any]],
        user_input: str
    ) -> List[Dict[str, Any]]:
        """Fix container dependencies with multi-scope support.
        
        Handles two distinct concepts:
        1. Container Stack: "inside it" nesting within a scope
        2. Scope Segments: "in D drive", "on desktop" location switches
        
        An explicit location (linguistically grounded) starts a new scope.
        "inside it" binds to most recent container within current scope.
        
        INVARIANT: Only language can change scope, not LLM-generated paths.
        
        Args:
            goals_data: List of goal dicts from LLM
            deps_data: List of dependency dicts from LLM
            user_input: Original user command (for anchor detection)
            
        Returns:
            Corrected dependency list
        """
        # Build initial dependency map: goal_idx → parent_idx
        dep_map: Dict[int, int] = {}
        for d in deps_data:
            goal_idx = d.get("goal_idx")
            depends_on = d.get("depends_on", [])
            if goal_idx is not None and depends_on:
                dep_map[goal_idx] = depends_on[0]
        
        # Scope tracking
        # Each scope has: base_anchor, container_stack (list of goal indices)
        current_scope_anchor: Optional[str] = None
        current_container_stack: List[int] = []
        
        # Detect if user mentioned any explicit anchors
        explicit_anchor = self._detect_explicit_anchor(user_input, 0)
        
        corrected: Dict[int, List[int]] = {}
        
        for idx, goal in enumerate(goals_data):
            goal_type = goal.get("goal_type")
            object_type = goal.get("object_type")
            
            # Only process file_operation goals
            if goal_type != "file_operation":
                continue
            
            # NEW: Explicit parent_target overrides stack behavior
            # "inside X" → binds to goal named X
            parent_target = goal.get("parent_target")
            if parent_target:
                # Build name → idx map
                name_to_idx = {g.get("target"): i for i, g in enumerate(goals_data)}
                if parent_target in name_to_idx:
                    corrected[idx] = [name_to_idx[parent_target]]
                    logging.debug(
                        f"ExplicitParent: g{idx} bound to g{name_to_idx[parent_target]} "
                        f"(parent_target='{parent_target}')"
                    )
                    # Still push folders to stack for future "inside it"
                    if object_type == "folder":
                        current_container_stack.append(idx)
                    continue
            
            # Check if this goal's target suggests a NEW scope
            # We detect scope change by looking at LLM's target AND user text
            target = goal.get("target", "")
            goal_anchor = None
            
            # If target looks like it's in a different drive, check if user mentioned it
            if target and len(target) >= 2 and target[1] == ":":
                drive_letter = target[0].upper()
                expected_anchor = f"DRIVE_{drive_letter}"
                # Only treat as scope switch if user linguistically mentioned this drive
                if expected_anchor == explicit_anchor and current_scope_anchor != expected_anchor:
                    goal_anchor = expected_anchor
            
            # If we found a linguistic scope switch, start new scope
            if goal_anchor is not None:
                current_scope_anchor = goal_anchor
                current_container_stack = []  # Reset stack for new scope
                logging.debug(f"ScopeSwitch: New scope {goal_anchor} at goal {idx}")
            elif current_scope_anchor is None:
                # Default scope: WORKSPACE
                current_scope_anchor = "WORKSPACE"
            
            # Get LLM-chosen parent
            llm_parent = dep_map.get(idx)
            
            # Determine correct parent within current scope
            # KEY RULE: If LLM says no parent (llm_parent is None), respect that (sibling)
            # Only apply stack logic when LLM explicitly chose a parent
            if llm_parent is not None:
                if current_container_stack:
                    top_container = current_container_stack[-1]
                    first_container = current_container_stack[0]
                    
                    # Rewrite if LLM bound to first but newer exists in this scope
                    if (
                        llm_parent == first_container
                        and top_container != first_container
                    ):
                        corrected[idx] = [top_container]
                        logging.debug(
                            f"ContainerStack: Fixed g{idx} from g{llm_parent} to g{top_container} "
                            f"(scope={current_scope_anchor})"
                        )
                    elif llm_parent in current_container_stack:
                        # LLM parent is valid within current scope
                        corrected[idx] = [llm_parent]
                    else:
                        # LLM parent not in scope, keep LLM's choice (trust LLM)
                        corrected[idx] = [llm_parent]
                else:
                    # No container stack, use LLM's choice
                    corrected[idx] = [llm_parent]
            # ELSE: llm_parent is None → sibling (no dependency), don't add to corrected
            
            # Folder → push onto current scope's container stack
            if object_type == "folder":
                current_container_stack.append(idx)
        
        return [
            {"goal_idx": idx, "depends_on": parents}
            for idx, parents in corrected.items()
        ]
    
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

Your job: Understand what the user is trying to achieve and extract structured goals.
{qc_context}
{self.FEW_SHOT_EXAMPLES}

---

INTERPRET THIS INPUT:
User: "{user_input}"

RULES:
1. Extract SEMANTIC GOALS, not actions
2. independent_multi = goals that don't depend on each other
3. dependent_multi = later goals need earlier goals to complete first
4. Use correct goal_type from the closed set
5. If goals are related to same context, consider if they're really ONE goal
6. CRITICAL: Targets must be RAW names only, NOT full paths

Return JSON with:
- meta_type: "single" | "independent_multi" | "dependent_multi"
- goals: list of goal objects with goal_type and relevant fields
- dependencies: list of {{goal_idx, depends_on: [...]}} for dependent_multi
- reasoning: brief explanation
"""
        
        try:
            result = self.model.generate(prompt, schema=self.INTERPRETER_SCHEMA)
            
            meta_type = result.get("meta_type", "single")
            goals_data = result.get("goals", [])
            deps_data = result.get("dependencies", [])
            reasoning = result.get("reasoning", "")
            
            # AUTHORITY CONTRACT: Enforce QC topology when confident
            self._enforce_topology(qc_output, goals_data)
            
            # FIX: Correct container scope for dependent_multi goals
            # LLMs often bind "inside it" to first container instead of most recent
            # Also handles multi-scope commands with different explicit locations
            if meta_type == "dependent_multi" and deps_data:
                deps_data = self._fix_container_dependencies(goals_data, deps_data, user_input)
            
            # Build Goal objects with unique IDs
            goals = tuple(
                Goal(
                    goal_type=g.get("goal_type", "app_launch"),
                    platform=g.get("platform"),
                    query=g.get("query"),
                    target=g.get("target"),
                    action=g.get("action"),
                    content=g.get("content"),
                    object_type=g.get("object_type"),
                    goal_id=f"g{i}"  # Unique ID for action linking
                )
                for i, g in enumerate(goals_data)
            )
            
            # Build dependencies tuple
            dependencies = tuple(
                (d.get("goal_idx", 0), tuple(d.get("depends_on", [])))
                for d in deps_data
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
                f"({len(goals)} goal(s))"
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
