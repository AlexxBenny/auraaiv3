"""Goal Planner - Transform single goal into minimal executable plan

RESPONSIBILITY: Given ONE goal + world state, produce optimal action sequence.

Question answered:
"What is the minimal set of actions to achieve this goal?"

INVARIANTS:
- Merging happens HERE (not in interpreter or orchestrator)
- Plan is minimal (no redundant actions)
- All tools exist in capabilities
- Dependencies are explicit
- WorldState is READ-ONLY (never mutated)
- Deterministic for same inputs

Supported goal types: browser_search, browser_navigate, app_launch, file_operation
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Literal, Tuple
from urllib.parse import quote

from agents.goal_interpreter import Goal


# =============================================================================
# GOAL TO INTENT MAPPING (Single Source of Truth)
# =============================================================================

GOAL_TO_INTENT = {
    "browser_search": "browser_control",
    "browser_navigate": "browser_control",
    "app_launch": "application_launch",
    "app_action": "application_control",
    "file_operation": "file_operation",
    "system_query": "system_query",
    "system_control": "system_control",
    "media_control": "system_control",
}

# Guard: GOAL_TO_INTENT must cover all goal types
from agents.goal_interpreter import Goal
_allowed_goal_types = set(Goal.__annotations__["goal_type"].__args__)
assert set(GOAL_TO_INTENT.keys()) == _allowed_goal_types, \
    f"GOAL_TO_INTENT out of sync: missing {_allowed_goal_types - set(GOAL_TO_INTENT.keys())}"
del _allowed_goal_types  # Clean up module namespace


# =============================================================================
# PLAN DATA CONTRACTS (Immutable where possible)
# =============================================================================

@dataclass
class PlannedAction:
    """A single abstract action in a plan.
    
    INVARIANT: This is an ABSTRACT action, not a concrete tool call.
    The intent + description are resolved to a concrete tool by ToolResolver
    in Phase 3 (GoalOrchestrator._resolve_and_execute).
    """
    action_id: str
    intent: str            # Abstract intent (e.g., "system_control", "file_operation")
    description: str       # Structured string for ToolResolver (e.g., "create:folder:X")
    args: Dict[str, Any]   # Semantic args (not tool-specific)
    expected_effect: str
    depends_on: List[str] = field(default_factory=list)


@dataclass
class Plan:
    """A minimal plan to achieve a goal."""
    actions: List[PlannedAction]
    goal_achieved_by: str  # action_id of final action
    total_actions: int
    
    def __post_init__(self):
        assert self.total_actions == len(self.actions), "Action count mismatch"
        action_ids = [a.action_id for a in self.actions]
        assert self.goal_achieved_by in action_ids, f"goal_achieved_by '{self.goal_achieved_by}' not in actions"


@dataclass
class PlanResult:
    """Result of planning attempt."""
    status: Literal["success", "no_capability", "blocked"]
    plan: Optional[Plan] = None
    reason: Optional[str] = None


# =============================================================================
# SEARCH ENGINE CONFIGURATION
# =============================================================================

SEARCH_ENGINES = {
    "youtube": "https://www.youtube.com/results?search_query={query}",
    "google": "https://www.google.com/search?q={query}",
    "bing": "https://www.bing.com/search?q={query}",
    "duckduckgo": "https://duckduckgo.com/?q={query}",
    "github": "https://github.com/search?q={query}",
    "stackoverflow": "https://stackoverflow.com/search?q={query}",
}

DEFAULT_SEARCH_ENGINE = "google"
DEFAULT_BROWSER = "chrome"


# =============================================================================
# FILE OPERATION CONFIGURATION
# =============================================================================

# Action normalization (user language -> canonical action)
ACTION_ALIASES = {
    # Create operations
    "make": "create",
    "new": "create",
    "add": "create",
    "mkdir": "create",  # mkdir + folder = create folder
    
    # Delete operations  
    "remove": "delete",
    "rm": "delete",
    "rmdir": "delete",  # rmdir + folder = delete folder
    
    # Move/rename
    "mv": "move",
    "ren": "rename",
    
    # Copy
    "cp": "copy",
    "duplicate": "copy",
}

# Tool mapping: (action, object_type) -> tool name
# object_type: "folder" | "file" | None (inferred from path)
FILE_OPERATION_TOOLS = {
    ("create", "folder"): "files.create_folder",
    ("create", "file"): "files.create_file",
    ("delete", "folder"): "files.delete_folder",
    ("delete", "file"): "files.delete_file",
    ("rename", None): "files.rename",
    ("move", None): "files.move",
    ("copy", None): "files.copy",
    ("write", None): "files.write_file",
    ("read", None): "files.read_file",
}


# =============================================================================
# GOAL PLANNER
# =============================================================================

class GoalPlanner:
    """Transform single goal into minimal executable plan.
    
    RESPONSIBILITY:
    - Given ONE goal, produce ONE minimal plan
    - This is where merging happens
    - "open youtube and search nvidia" → single URL action
    
    DOES NOT:
    - Handle multiple goals (GoalOrchestrator's job)
    - Parse user input (GoalInterpreter's job)
    - Execute anything (Executor's job)
    
    Supported goal types:
    - browser_search
    - browser_navigate
    - app_launch
    - file_operation
    """
    
    SUPPORTED_GOAL_TYPES = {"browser_search", "browser_navigate", "app_launch", "file_operation"}
    
    def __init__(self):
        logging.info("GoalPlanner initialized (minimal plan generation)")
    
    def plan(
        self,
        goal: Goal,
        world_state: Optional[Dict[str, Any]] = None,
        capabilities: Optional[List[Dict]] = None
    ) -> PlanResult:
        """Generate minimal plan to achieve goal.
        
        Args:
            goal: Single Goal to achieve
            world_state: Current world state (read-only)
            capabilities: Available tool capabilities
            
        Returns:
            PlanResult with status and optional Plan
        """
        world_state = world_state or {}
        
        # Route to appropriate planner
        if goal.goal_type == "browser_search":
            return self._plan_browser_search(goal, world_state)
        elif goal.goal_type == "browser_navigate":
            return self._plan_browser_navigate(goal, world_state)
        elif goal.goal_type == "app_launch":
            return self._plan_app_launch(goal, world_state)
        elif goal.goal_type == "file_operation":
            return self._plan_file_operation(goal, world_state)
        elif goal.goal_type == "system_control":
            return self._plan_system_control(goal, world_state)
        elif goal.goal_type == "media_control":
            return self._plan_media_control(goal, world_state)
        elif goal.goal_type == "system_query":
            return self._plan_system_query(goal, world_state)
        else:
            # All goal types must be handled - fail fast
            raise AssertionError(f"Unplanned goal_type: {goal.goal_type}")
    
    def _plan_browser_search(self, goal: Goal, world_state: Dict) -> PlanResult:
        """Plan browser search - abstract action.
        
        Emits intent + description for ToolResolver to resolve.
        """
        platform = (goal.platform or DEFAULT_SEARCH_ENGINE).lower()
        query = goal.query or ""
        
        if not query:
            return PlanResult(
                status="blocked",
                reason="No search query provided"
            )
        
        # Build search URL for description context
        if platform in SEARCH_ENGINES:
            url_template = SEARCH_ENGINES[platform]
            url = url_template.format(query=quote(query))
        else:
            logging.warning(f"Unknown search platform '{platform}', defaulting to Google")
            url = SEARCH_ENGINES["google"].format(query=quote(f"{platform} {query}"))
        
        # Abstract action
        action = PlannedAction(
            action_id="a1",
            intent=GOAL_TO_INTENT["browser_search"],
            description=f"search:{platform}:{query}",
            args={
                "platform": platform,
                "query": query,
                "url": url  # Pre-computed for ToolResolver
            },
            expected_effect=f"{platform}_search_results_visible"
        )
        
        plan = Plan(
            actions=[action],
            goal_achieved_by="a1",
            total_actions=1
        )
        
        logging.info(f"GoalPlanner: browser_search → abstract action (search:{platform}:{query[:30]})")
        
        return PlanResult(status="success", plan=plan)
    
    def _plan_browser_navigate(self, goal: Goal, world_state: Dict) -> PlanResult:
        """Plan browser navigation - abstract action."""
        url = goal.target
        
        if not url:
            return PlanResult(
                status="blocked",
                reason="No URL target provided"
            )
        
        # Ensure URL has protocol
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        
        action = PlannedAction(
            action_id="a1",
            intent=GOAL_TO_INTENT["browser_navigate"],
            description=f"navigate:{url}",
            args={"url": url},
            expected_effect="url_loaded"
        )
        
        plan = Plan(
            actions=[action],
            goal_achieved_by="a1",
            total_actions=1
        )
        
        logging.info(f"GoalPlanner: browser_navigate → abstract action ({url})")
        
        return PlanResult(status="success", plan=plan)
    
    def _plan_app_launch(self, goal: Goal, world_state: Dict) -> PlanResult:
        """Plan app launch - abstract action."""
        app_name = goal.target
        
        if not app_name:
            return PlanResult(
                status="blocked",
                reason="No app target provided"
            )
        
        action = PlannedAction(
            action_id="a1",
            intent=GOAL_TO_INTENT["app_launch"],
            description=f"launch:{app_name}",
            args={"app_name": app_name},
            expected_effect=f"{app_name}_running"
        )
        
        plan = Plan(
            actions=[action],
            goal_achieved_by="a1",
            total_actions=1
        )
        
        logging.info(f"GoalPlanner: app_launch → abstract action ({app_name})")
        
        return PlanResult(status="success", plan=plan)
    
    def _plan_file_operation(self, goal: Goal, world_state: Dict) -> PlanResult:
        """Plan file/folder operation - abstract action.
        
        Handles:
        - Action normalization (mkdir, make, new -> create)
        - Object type disambiguation (folder vs file)
        - Dynamic action IDs for linking
        
        INVARIANT: goal.resolved_path MUST be set by GoalOrchestrator.
        This planner does NOT resolve paths - that's PathResolver's job.
        """
        from pathlib import Path
        
        # Use resolved_path (AUTHORITY) - set by GoalOrchestrator
        # Fall back to target only for backward compatibility
        target = goal.resolved_path or goal.target
        
        if not target:
            return PlanResult(
                status="blocked",
                reason="No file/folder path provided"
            )
        
        # INVARIANT: Path must be absolute (resolved by PathResolver)
        # If not, something went wrong upstream
        if not Path(target).is_absolute():
            logging.warning(
                f"GoalPlanner: Path not absolute: '{target}'. "
                "This indicates GoalOrchestrator did not resolve paths."
            )
            return PlanResult(
                status="blocked",
                reason=f"Path not resolved by orchestrator: {target}"
            )
        
        # Normalize action
        raw_action = (goal.action or "create").lower()
        action = ACTION_ALIASES.get(raw_action, raw_action)
        
        # Determine object type (folder vs file)
        object_type = goal.object_type
        if not object_type:
            # Infer from path: no extension = folder
            if "." in Path(target).name:
                object_type = "file"
            else:
                object_type = "folder"
        
        # Generate unique action ID from goal_id
        goal_id = goal.goal_id or "g0"
        action_id = f"{goal_id}_a1"
        
        # Build semantic args
        args = {
            "action": action,
            "object_type": object_type,
            "path": target
        }
        
        # Add optional fields
        if goal.content:
            args["content"] = goal.content
        
        # Structured description: action:object_type (NO PATH - stays in args)
        planned_action = PlannedAction(
            action_id=action_id,
            intent=GOAL_TO_INTENT["file_operation"],
            description=f"{action}:{object_type}",
            args=args,
            expected_effect=f"{action}_{object_type}_completed"
        )
        
        plan = Plan(
            actions=[planned_action],
            goal_achieved_by=action_id,
            total_actions=1
        )
        
        logging.info(f"GoalPlanner: file_operation → abstract action ({action}:{object_type}:{Path(target).name})")
        
        return PlanResult(status="success", plan=plan)
    
    def _plan_system_control(self, goal: Goal, world_state: Dict) -> PlanResult:
        """Plan system control action (audio, display, power) - abstract action."""
        action = goal.action or "unknown"
        value = goal.target  # e.g., "60" for brightness
        
        # Structured description
        if value:
            description = f"{action}:{value}"
        else:
            description = action
        
        planned_action = PlannedAction(
            action_id="a0",
            intent=GOAL_TO_INTENT["system_control"],
            description=description,
            args={"action": action, "value": value},
            expected_effect=f"{action}_complete"
        )
        
        plan = Plan(
            actions=[planned_action],
            goal_achieved_by="a0",
            total_actions=1
        )
        
        logging.info(f"GoalPlanner: system_control → abstract action ({description})")
        
        return PlanResult(status="success", plan=plan)
    
    def _plan_media_control(self, goal: Goal, world_state: Dict) -> PlanResult:
        """Plan media control action (play, pause, next, previous) - abstract action."""
        action = goal.action or "play"
        
        planned_action = PlannedAction(
            action_id="a0",
            intent=GOAL_TO_INTENT["media_control"],
            description=action,
            args={"action": action},
            expected_effect=f"{action}_complete"
        )
        
        plan = Plan(
            actions=[planned_action],
            goal_achieved_by="a0",
            total_actions=1
        )
        
        logging.info(f"GoalPlanner: media_control → abstract action ({action})")
        
        return PlanResult(status="success", plan=plan)
    
    def _plan_system_query(self, goal: Goal, world_state: Dict) -> PlanResult:
        """Plan system query (battery, time, disk usage) - abstract action."""
        query_type = goal.action or goal.query or "status"
        
        planned_action = PlannedAction(
            action_id="a0",
            intent=GOAL_TO_INTENT["system_query"],
            description=f"query:{query_type}",
            args={"query_type": query_type},
            expected_effect=f"{query_type}_retrieved"
        )
        
        plan = Plan(
            actions=[planned_action],
            goal_achieved_by="a0",
            total_actions=1
        )
        
        logging.info(f"GoalPlanner: system_query → abstract action (query:{query_type})")
        
        return PlanResult(status="success", plan=plan)
