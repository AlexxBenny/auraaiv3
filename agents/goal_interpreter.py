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
    """
    goal_type: Literal[
        "browser_search",
        "browser_navigate",
        "app_launch",
        "app_action",
        "file_operation",
        "system_query"
    ]
    
    # Optional fields based on goal_type
    platform: Optional[str] = None      # youtube, google, spotify
    query: Optional[str] = None         # nvidia, weather
    target: Optional[str] = None        # URL, file path, app name
    action: Optional[str] = None        # play, mkdir, create
    content: Optional[str] = None       # File content, etc.
    object_type: Optional[str] = None   # "folder" | "file" for file_operation
    goal_id: Optional[str] = None       # Unique ID for action linking


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
                                "system_query"
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
        {"goal_type": "system_query", "action": "set_volume"},
        {"goal_type": "system_query", "action": "screenshot"}
    ],
    "dependencies": [],
    "reasoning": "Two independent system operations"
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

### dependent_multi (goals with dependencies)

User: "create a folder called alex in D drive and create a ppt inside it"
→ {
    "meta_type": "dependent_multi",
    "goals": [
        {"goal_type": "file_operation", "action": "create", "object_type": "folder", "target": "D:\\\\alex"},
        {"goal_type": "file_operation", "action": "create", "object_type": "file", "target": "D:\\\\alex\\\\presentation.pptx"}
    ],
    "dependencies": [{"goal_idx": 1, "depends_on": [0]}],
    "reasoning": "File creation depends on folder existing"
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
    
    def interpret(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> MetaGoal:
        """Extract semantic goals from user input.
        
        Args:
            user_input: Raw user command
            context: Optional world state (read-only)
            
        Returns:
            MetaGoal with structured goals
        """
        prompt = f"""You are a semantic goal interpreter.

Your job: Understand what the user is trying to achieve and extract structured goals.

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
