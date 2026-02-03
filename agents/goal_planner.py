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
# PLAN DATA CONTRACTS (Immutable where possible)
# =============================================================================

@dataclass
class PlannedAction:
    """A single action in a plan."""
    action_id: str
    tool: str
    args: Dict[str, Any]
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
        else:
            # Unsupported goal type
            logging.info(f"GoalPlanner: goal_type '{goal.goal_type}' not supported")
            return PlanResult(
                status="no_capability",
                reason=f"Goal type '{goal.goal_type}' not supported"
            )
    
    def _plan_browser_search(self, goal: Goal, world_state: Dict) -> PlanResult:
        """Plan browser search - THE MERGING HAPPENS HERE.
        
        "open youtube and search nvidia" becomes:
        - ONE action
        - ONE URL: youtube.com/results?search_query=nvidia
        - ONE tab
        """
        platform = (goal.platform or DEFAULT_SEARCH_ENGINE).lower()
        query = goal.query or ""
        
        if not query:
            return PlanResult(
                status="blocked",
                reason="No search query provided"
            )
        
        # Build search URL
        if platform in SEARCH_ENGINES:
            url_template = SEARCH_ENGINES[platform]
            url = url_template.format(query=quote(query))
        else:
            # Unknown platform - default to google search
            logging.warning(f"Unknown search platform '{platform}', defaulting to Google")
            url = SEARCH_ENGINES["google"].format(query=quote(f"{platform} {query}"))
        
        # Single action plan
        action = PlannedAction(
            action_id="a1",
            tool="system.apps.launch.shell",
            args={
                "app_name": DEFAULT_BROWSER,
                "url": url
            },
            expected_effect=f"{platform}_search_results_visible"
        )
        
        plan = Plan(
            actions=[action],
            goal_achieved_by="a1",
            total_actions=1
        )
        
        logging.info(f"GoalPlanner: browser_search → 1 action (URL: {url[:50]}...)")
        
        return PlanResult(status="success", plan=plan)
    
    def _plan_browser_navigate(self, goal: Goal, world_state: Dict) -> PlanResult:
        """Plan browser navigation to URL."""
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
            tool="system.apps.launch.shell",
            args={
                "app_name": DEFAULT_BROWSER,
                "url": url
            },
            expected_effect="url_loaded"
        )
        
        plan = Plan(
            actions=[action],
            goal_achieved_by="a1",
            total_actions=1
        )
        
        logging.info(f"GoalPlanner: browser_navigate → 1 action (URL: {url})")
        
        return PlanResult(status="success", plan=plan)
    
    def _plan_app_launch(self, goal: Goal, world_state: Dict) -> PlanResult:
        """Plan simple app launch."""
        app_name = goal.target
        
        if not app_name:
            return PlanResult(
                status="blocked",
                reason="No app target provided"
            )
        
        action = PlannedAction(
            action_id="a1",
            tool="system.apps.launch.shell",
            args={"app_name": app_name},
            expected_effect=f"{app_name}_running"
        )
        
        plan = Plan(
            actions=[action],
            goal_achieved_by="a1",
            total_actions=1
        )
        
        logging.info(f"GoalPlanner: app_launch → 1 action ({app_name})")
        
        return PlanResult(status="success", plan=plan)
    
    def _plan_file_operation(self, goal: Goal, world_state: Dict) -> PlanResult:
        """Plan file/folder operation with action normalization.
        
        Handles:
        - Action normalization (mkdir, make, new -> create)
        - Object type disambiguation (folder vs file)
        - Dynamic action IDs for linking
        - Safe defaults (create_parents=True, exist_ok=True)
        
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
            # Fail explicitly rather than silently resolving wrong
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
        
        # Look up tool
        tool = FILE_OPERATION_TOOLS.get((action, object_type))
        if not tool:
            # Try action without object_type (for move, copy, etc.)
            tool = FILE_OPERATION_TOOLS.get((action, None))
        
        if not tool:
            return PlanResult(
                status="no_capability",
                reason=f"No tool for action '{action}' on {object_type}"
            )
        
        # Build args based on tool
        args = {"path": target}
        
        if tool == "files.create_folder":
            args["parents"] = True
            args["exist_ok"] = True
        elif tool == "files.create_file":
            args["create_parents"] = True
            if goal.content:
                args["content"] = goal.content
        
        # Generate unique action ID from goal_id
        goal_id = goal.goal_id or "g0"
        action_id = f"{goal_id}_a1"
        
        planned_action = PlannedAction(
            action_id=action_id,
            tool=tool,
            args=args,
            expected_effect=f"{action}_{object_type}_completed"
        )
        
        plan = Plan(
            actions=[planned_action],
            goal_achieved_by=action_id,
            total_actions=1
        )
        
        logging.info(f"GoalPlanner: file_operation → {tool} ({target})")
        
        return PlanResult(status="success", plan=plan)
