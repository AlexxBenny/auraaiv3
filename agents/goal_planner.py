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
from core.context_frame import ContextFrame


# =============================================================================
# PLANNER RULES (PHASE 4 - PARAMETRIC PLANNING)
# =============================================================================
# Planning is now table-driven via core/planner_rules.py
# No more per-domain planner methods. Just (domain, verb) → rule lookup.

from core.planner_rules import (
    PLANNER_RULES, 
    get_planner_rule, 
    format_description, 
    validate_params,
    ParamValidationError
)


# =============================================================================
# PLAN DATA CONTRACTS (Immutable where possible)
# =============================================================================

@dataclass
class PlannedAction:
    """A single abstract action in a plan.
    
    INVARIANT: This is an ABSTRACT action, not a concrete tool call.
    The intent + description are resolved to a concrete tool by ToolResolver
    in Phase 3 (GoalOrchestrator._resolve_and_execute).
    
    action_class (Phase 2):
        Semantic classification of what kind of side effect this action has.
        MUST be one of: "actuate", "observe", "query"
        - actuate: causes change in world state (navigate, write, click)
        - observe: reads world state (get_title, read_file)
        - query: pure info request (no side effects)
        
        This is a HARD FILTER in ToolResolver - only tools with matching
        capability_class will be considered.
    """
    action_id: str
    intent: str            # Abstract intent (e.g., "system_control", "file_operation")
    description: str       # Structured string for ToolResolver (e.g., "create:folder:X")
    args: Dict[str, Any]   # Semantic args (not tool-specific)
    expected_effect: str
    depends_on: List[str] = field(default_factory=list)
    action_class: Optional[str] = None  # "actuate" | "observe" | "query"
    produced_context: Optional[ContextFrame] = None  # Semantic frame produced by this action


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
# GOAL PLANNER
# =============================================================================

class GoalPlanner:
    """Transform single goal into minimal executable plan.
    
    RESPONSIBILITY:
    - Given ONE goal, produce ONE minimal plan
    - Uses PLANNER_RULES table for (domain, verb) → PlannedAction mapping
    
    PHASE 4 ARCHITECTURE:
    - No per-domain planner methods
    - No if/elif branching on goal type
    - Single table lookup: (goal.domain, goal.verb) → rule
    
    DOES NOT:
    - Handle multiple goals (GoalOrchestrator's job)
    - Parse user input (GoalInterpreter's job)
    - Execute anything (Executor's job)
    """
    
    def __init__(self):
        logging.info("GoalPlanner initialized (parametric table-driven planning)")
    
    def plan(
        self,
        goal: Goal,
        world_state: Optional[Dict[str, Any]] = None,
        capabilities: Optional[List[Dict]] = None
        , context_frames: Optional[List[ContextFrame]] = None
    ) -> PlanResult:
        """Generate minimal plan to achieve goal.
        
        PHASE 4: Table-driven planning via PLANNER_RULES.
        No branching. Just lookup and format.
        
        Args:
            goal: Single Goal to achieve (domain, verb, params)
            world_state: Current world state (read-only)
            capabilities: Available tool capabilities
            
        Returns:
            PlanResult with status and optional Plan
        """
        world_state = world_state or {}
        
        # AGGRESSIVE DEBUG LOGGING
        logging.info(f"=== GoalPlanner.plan() START ===")
        logging.info(f"  Input Goal: domain={goal.domain}, verb={goal.verb}")
        logging.info(f"  Input Goal: object={goal.object}, params={goal.params}")
        logging.info(f"  Input Goal: scope={goal.scope}, resolved_path={goal.resolved_path}")
        
        # TABLE LOOKUP - the heart of parametric planning
        rule = get_planner_rule(goal.domain, goal.verb)
        
        if not rule:
            logging.error(f"PLANNER FAIL: No rule for ({goal.domain}, {goal.verb})")
            return PlanResult(
                status="no_capability",
                reason=f"No planner rule for domain={goal.domain}, verb={goal.verb}"
            )
        
        logging.info(f"  Rule found: intent={rule['intent']}, action_class={rule['action_class']}")
        
        # Build params from goal
        params = {**goal.params}
        if goal.object:
            params["target"] = goal.object
        if goal.resolved_path:
            params["path"] = goal.resolved_path
        
        logging.info(f"  Pre-validation params: {params}")
        
        # PARAM VALIDATION - fail-fast on semantic errors
        try:
            # Read context metadata from rule (table-driven)
            consumption = rule.get("context_consumption", {})
            production = rule.get("context_production")
            allow_semantic_only = bool(rule.get("allow_semantic_only", False))

            # Light-weight schema validation for metadata (log warnings only)
            if consumption and not isinstance(consumption, dict):
                logging.warning(f"PLANNER_RULES: context_consumption for ({goal.domain},{goal.verb}) must be a dict")
                consumption = {}
            if production and not (isinstance(production, dict) and "domain" in production and isinstance(production.get("keys", []), list)):
                logging.warning(f"PLANNER_RULES: context_production for ({goal.domain},{goal.verb}) malformed")
                production = None

            # If allow_semantic_only and required params missing, accept limited semantic plan
            if allow_semantic_only and any(p not in params for p in rule.get("required_params", [])):
                # Validate allowed values for any present params
                allowed = rule.get("allowed_values", {})
                for pname, pset in allowed.items():
                    if pname in params and params[pname] not in pset:
                        raise ParamValidationError(
                            f"({goal.domain}, {goal.verb}): Invalid value '{params[pname]}' for '{pname}'. Allowed: {sorted(pset)}"
                        )
                validated_params = params.copy()
                logging.info(f"GoalPlanner: Semantic-only {goal.domain}.{goal.verb} accepted (no technical params) with params={validated_params}")
            else:
                # Fill missing params from context_frames according to rule metadata
                if context_frames and consumption:
                    for param_name, (ctx_domain, ctx_key) in consumption.items():
                        if param_name not in params or params.get(param_name) is None:
                            for cf in context_frames:
                                if cf.domain == ctx_domain and ctx_key in cf.data:
                                    params[param_name] = cf.data[ctx_key]
                                    logging.info(f"GoalPlanner: Filled param '{param_name}' from ContextFrame(domain={cf.domain}, produced_by={cf.produced_by})")
                                    break

                validated_params = validate_params(goal.domain, goal.verb, params, rule)
            logging.info(f"  Validated params: {validated_params}")
        except ParamValidationError as e:
            logging.error(f"PLANNER FAIL: Param validation failed: {e}")
            return PlanResult(
                status="blocked",
                reason=str(e)
            )
        
        # Generate action ID
        action_id = goal.goal_id or f"{goal.domain}_{goal.verb}_1"
        
        # Construct search URL for browser.search goals
        # Trust validate_params() contract - platform is guaranteed to exist
        if goal.domain == "browser" and goal.verb == "search":
            platform = validated_params["platform"]  # Trust contract, no silent default
            query = validated_params["query"]
            
            if query:
                search_url = self._construct_search_url(platform, query)
                validated_params["url"] = search_url
                logging.info(f"GoalPlanner: Constructed search URL for {platform}: {search_url}")

        # Produce ContextFrame according to rule metadata (after validation)
        produced_ctx: Optional[ContextFrame] = None
        production = rule.get("context_production")
        if production:
            try:
                prod_domain = production.get("domain")
                prod_keys = production.get("keys", [])
                data = {
                    k: validated_params[k]
                    for k in prod_keys
                    if k in validated_params and validated_params[k] is not None
                }
                if data:
                    produced_ctx = ContextFrame(domain=prod_domain, data=data, produced_by=action_id)
                    logging.info(f"GoalPlanner: Produced ContextFrame(domain={prod_domain}, keys={list(data.keys())}, produced_by={action_id})")
            except Exception as e:
                logging.warning(f"GoalPlanner: Failed to produce ContextFrame for {goal.domain}.{goal.verb}: {e}")
                produced_ctx = None
        
        # Format description using rule template
        description = format_description(rule, validated_params)
        
        logging.info(f"  Generated description: {description}")
        
        # Build PlannedAction
        action = PlannedAction(
            action_id=action_id,
            intent=rule["intent"],
            description=description,
            args=validated_params,
            expected_effect=f"{goal.verb} completed",
            action_class=rule["action_class"],
            produced_context=produced_ctx,
        )
        
        logging.info(f"=== GoalPlanner.plan() SUCCESS ===")
        logging.info(f"  Output: {description} [intent={rule['intent']}, action_class={rule['action_class']}]")
        
        return PlanResult(
            status="success",
            plan=Plan(
                actions=[action],
                goal_achieved_by=action_id,
                total_actions=1
            )
        )

    # =========================================================================
    # URL CONSTRUCTION HELPERS
    # =========================================================================
    
    def _construct_search_url(self, platform: str, query: str) -> str:
        """Construct search URL from platform and query.
        
        Uses templates from AppsConfig singleton. This ensures deterministic URL
        construction for browser.search goals, avoiding LLM-dependent URL generation
        in ToolResolver.
        
        NOTE: URL encoding is a layer boundary leak (planner shouldn't know HTTP
        details), but it's tolerable for now. Future: Move to URLBuilder layer.
        
        Args:
            platform: Search platform (google, youtube, bing, etc.)
            query: Search query string
            
        Returns:
            Constructed search URL
        """
        from core.apps_config import AppsConfig
        from urllib.parse import quote
        
        # Get template from singleton config (cached, no disk I/O per call)
        apps_config = AppsConfig.get()
        template = apps_config.get_search_template(platform)
        
        if not template:
            # Config-driven fallback (not hardcoded)
            default_engine = apps_config.get_default_search_engine()
            template = apps_config.get_search_template(default_engine)
            
            if not template:
                # Last resort: use Google template from defaults
                template = "https://www.google.com/search?q={query}"
            
            logging.warning(
                f"GoalPlanner: Unknown search platform '{platform}', "
                f"using default engine '{default_engine}'"
            )
        
        # URL encode query (strict encoding, no safe chars)
        # NOTE: This is a layer boundary leak - planner knows HTTP details
        # Acceptable for now, but consider moving to URLBuilder layer in future
        encoded_query = quote(query, safe='')
        
        # Construct URL
        url = template.format(query=encoded_query)
        logging.debug(f"GoalPlanner: Constructed search URL: {url}")
        
        return url
    
    # =========================================================================
    # DEPRECATED METHODS REMOVED (Phase 4)
    # =========================================================================
    # The following methods were removed as they are now handled by 
    # table-driven planning via PLANNER_RULES:
    # - _plan_browser_search
    # - _plan_browser_navigate
    # - _plan_app_launch
    # - _plan_file_operation
    # - _plan_system_control
    # - _plan_media_control
    # - _plan_system_query
    #
    # All planning is now: (domain, verb) -> PLANNER_RULES lookup -> PlannedAction


 