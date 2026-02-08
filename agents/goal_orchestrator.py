"""Goal Orchestrator - Multi-goal coordination via per-goal planning

RESPONSIBILITY: Handle multi-goal MetaGoals by orchestrating GoalPlanner.

Question answered:
"Given multiple goals, how do I combine their plans?"

INVARIANTS:
- Single goals pass through to GoalPlanner
- Independent goals produce parallel-safe plan
- Dependencies become edges in plan graph
- Execution order is topologically valid
- Partial success returns what succeeded
- WorldState never mutated
- All file_operation paths resolved BEFORE planning (single authority)

Phase 1 Scope: single + independent_multi only
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, List, Optional, Literal, Tuple

from agents.goal_interpreter import Goal, MetaGoal
from agents.goal_planner import GoalPlanner, Plan, PlannedAction, PlanResult
from core.path_resolver import PathResolver
from core.semantic_resolver import SemanticResolver
from core.context_frame import ContextFrame


# =============================================================================
# ORCHESTRATION DATA CONTRACTS
# =============================================================================

@dataclass
class PlanGraph:
    """Combined plan from multiple goals."""
    nodes: Dict[str, PlannedAction]       # action_id → action
    edges: Dict[str, List[str]]           # action_id → depends_on[]
    goal_map: Dict[int, List[str]]        # goal_idx → action_ids
    execution_order: List[str]            # Topologically sorted
    total_actions: int
    
    def __post_init__(self):
        assert self.total_actions == len(self.nodes), "Node count mismatch"


@dataclass
class FailedGoal:
    """A goal that could not be planned or executed."""
    goal_idx: int
    goal: Goal
    reason: str
    blocker: Optional[str] = None
    failure_class: str = "unknown"  # Phase 5: environmental/logical/permission/unknown


@dataclass
class ExecutionSummary:
    """Summary of plan execution results.
    
    Phase 5: First-class execution results passed to repair logic.
    """
    status: Literal["success", "partial", "failed"]
    failed_goals: List[FailedGoal] = field(default_factory=list)
    completed_goals: List[int] = field(default_factory=list)  # goal_idx of completed goals


@dataclass
class OrchestrationResult:
    """Result of orchestrating multiple goals."""
    status: Literal["success", "partial", "blocked", "no_capability"]
    plan_graph: Optional[PlanGraph] = None
    failed_goals: List[FailedGoal] = field(default_factory=list)
    reason: Optional[str] = None
    # Phase 5: Repair trace
    repair_attempted: bool = False
    repair_reason: Optional[str] = None


# =============================================================================
# GOAL ORCHESTRATOR
# =============================================================================

class GoalOrchestrator:
    """Multi-goal coordination via per-goal planning.
    
    RESPONSIBILITY:
    - Accept MetaGoal
    - Call GoalPlanner.plan() per goal
    - Combine plans into PlanGraph
    - Phase 5: Attempt plan repair for recoverable execution failures
    
    DOES NOT:
    - Parse user input (GoalInterpreter's job)
    - Merge within a goal (GoalPlanner's job)
    - Execute anything (Executor's job)
    
    ARCHITECTURAL CONTRACT (Phase 5):
    =================================
    GoalOrchestrator is repair-aware but execution-agnostic.
    
    - Repair awareness: GoalOrchestrator receives ExecutionSummary from execution
      and can generate alternative plans via _attempt_plan_repair()
    
    - Execution agnosticism: GoalOrchestrator does NOT execute plans. Execution
      happens in Orchestrator._process_goal(), which:
      1. Calls orchestrate() to get PlanGraph
      2. Executes PlanGraph actions
      3. Builds ExecutionSummary from execution results
      4. Calls orchestrate() again with ExecutionSummary to trigger repair
      5. Executes repaired PlanGraph if repair succeeds
    
    This creates bidirectional coupling:
    - Orchestrator must understand repair semantics (passes ExecutionSummary)
    - GoalOrchestrator must understand execution outcomes (receives ExecutionSummary)
    
    This is intentional and correct. Do NOT:
    - Move execution into GoalOrchestrator (violates separation of concerns)
    - Move repair into Orchestrator (violates single responsibility)
    - Remove ExecutionSummary coupling (breaks repair flow)
    """
    
    # Phase 5: Plan repair budget
    MAX_REPAIR_ATTEMPTS = 1  # Conservative: one repair per orchestration
    
    def __init__(self):
        self.goal_planner = GoalPlanner()
        logging.info("GoalOrchestrator initialized (multi-goal coordination)")
    
    # =========================================================================
    # PHASE 5: PLAN REPAIR HELPERS
    # =========================================================================
    
    def _is_recoverable(self, failure_class: str) -> bool:
        """Check if a failure is potentially recoverable via plan repair."""
        return failure_class in {"environmental", "unknown"}
    
    # Browser apps that should trigger the warning
    _BROWSER_APP_NAMES = frozenset({"chrome", "firefox", "edge", "brave", "opera", "chromium", "safari"})
    
    def _warn_if_browser_launch_with_browser_goals(self, meta_goal: MetaGoal) -> None:
        """Log a warning if app.launch(browser) appears alongside browser domain goals.
        
        This pattern indicates the interpreter should have collapsed the request
        into browser domain goals only, since BrowserSessionManager handles session
        bootstrapping automatically.
        
        This is a DIAGNOSTIC ONLY - does not modify execution.
        """
        if len(meta_goal.goals) < 2:
            return
        
        has_browser_app_launch = False
        has_browser_goal = False
        browser_app_name = None
        
        for goal in meta_goal.goals:
            if goal.domain == "app" and goal.verb == "launch":
                app_name = (goal.params or {}).get("app_name", "").lower()
                if app_name in self._BROWSER_APP_NAMES:
                    has_browser_app_launch = True
                    browser_app_name = app_name
            elif goal.domain == "browser":
                has_browser_goal = True
        
        if has_browser_app_launch and has_browser_goal:
            logging.warning(
                f"INTERPRETER_EXAMPLE_GAP: app.launch({browser_app_name}) emitted alongside "
                f"browser domain goals. This likely indicates an interpreter example gap. "
                f"Expected: browser goals only (session bootstraps automatically). "
                f"MetaGoal type: {meta_goal.meta_type}"
            )
    
    def _validate_repair_equivalence(
        self, 
        original: MetaGoal, 
        repaired_goals: List[Dict]
    ) -> bool:
        """Ensure repaired goals preserve terminal intent.
        
        Checks:
        1. No new domains introduced
        2. Same verb distribution (allow fewer, not more)
        3. Terminal expected_effect preserved
        
        Args:
            original: Original MetaGoal
            repaired_goals: List of {domain, verb, params} from repair prompt
            
        Returns:
            True if repair is semantically equivalent
        """
        from collections import Counter
        
        # 1. No new domains
        original_domains = {g.domain for g in original.goals}
        repaired_domains = {g.get("domain") for g in repaired_goals}
        if repaired_domains - original_domains:
            logging.warning(f"Plan repair rejected: new domains {repaired_domains - original_domains}")
            return False
        
        # 2. Same verb distribution (allow fewer, not more)
        original_verbs = Counter((g.domain, g.verb) for g in original.goals)
        repaired_verbs = Counter((g.get("domain"), g.get("verb")) for g in repaired_goals)
        for key in repaired_verbs:
            if repaired_verbs[key] > original_verbs.get(key, 0):
                logging.warning(f"Plan repair rejected: verb inflation for {key}")
                return False
        
        # 3. Terminal intent preserved - terminal verb must appear LAST
        terminal_goal = original.goals[-1]
        
        if not repaired_goals:
            logging.warning("Plan repair rejected: no repaired goals provided")
            return False
        
        # Terminal verb must be the LAST goal in repaired sequence
        if repaired_goals[-1].get("verb") != terminal_goal.verb:
            logging.warning(
                f"Plan repair rejected: terminal verb {terminal_goal.verb} not preserved as last goal "
                f"(got {repaired_goals[-1].get('verb')})"
            )
            return False
        
        return True
    
    def _attempt_plan_repair(
        self,
        original_meta_goal: MetaGoal,
        execution_summary: ExecutionSummary,
        world_state: Dict[str, Any]
    ) -> Optional[OrchestrationResult]:
        """Attempt to repair plan after execution failure.
        
        Phase 5: LLM-based goal recovery for recoverable failures.
        
        Args:
            original_meta_goal: Original MetaGoal that failed
            execution_summary: Execution results showing failures
            world_state: Current world state
            
        Returns:
            OrchestrationResult with repaired plan, or None if repair failed
        """
        from models.model_manager import get_model_manager
        from core.prompts.plan_repair import PLAN_REPAIR_PROMPT, PLAN_REPAIR_SCHEMA
        
        # Get repair LLM
        model_manager = get_model_manager()
        repair_llm = model_manager.get("repair")
        
        # Build prompt context
        original_goals = []
        for goal in original_meta_goal.goals:
            original_goals.append({
                "domain": goal.domain,
                "verb": goal.verb,
                "params": goal.params or {}
            })
        
        # Get completed goals
        completed = execution_summary.completed_goals
        
        # Get failed goals (only recoverable ones)
        failed = []
        for fg in execution_summary.failed_goals:
            if self._is_recoverable(fg.failure_class):
                failed.append({
                    "goal_idx": fg.goal_idx,
                    "domain": fg.goal.domain,
                    "verb": fg.goal.verb,
                    "reason": fg.reason
                })
        
        # Format prompt
        # Note: available_verbs removed - equivalence gate ensures no new domains/verbs
        prompt = PLAN_REPAIR_PROMPT.format(
            original_goals=str(original_goals),
            completed=str(completed),
            failed=str(failed),
            available_verbs="[]"  # Deprecated - equivalence gate enforces constraints
        )
        
        try:
            # Call repair LLM
            response = repair_llm.generate(
                prompt=prompt,
                schema=PLAN_REPAIR_SCHEMA,
                temperature=0.2  # Conservative
            )
            
            if not response or "repaired_goals" not in response:
                logging.warning("Repair LLM returned invalid response")
                return None
            
            skip_remaining = response.get("skip_remaining", False)
            repaired_goals = response.get("repaired_goals", [])
            reasoning = response.get("reasoning", "")
            
            logging.info(f"Plan repair reasoning: {reasoning}")
            
            if skip_remaining:
                # Goal already achieved - return success with existing plan
                logging.info("Repair LLM determined goal already achieved")
                return OrchestrationResult(
                    status="success",
                    reason="Goal already achieved (repair skip)"
                )
            
            if not repaired_goals:
                logging.info("Repair LLM determined failure unrecoverable")
                return None
            
            # Validate equivalence
            if not self._validate_repair_equivalence(original_meta_goal, repaired_goals):
                logging.warning("Repair failed equivalence check")
                return None
            
            # Convert repaired goals to Goal objects
            from agents.goal_interpreter import Goal
            repaired_goal_objects = []
            for rg in repaired_goals:
                goal = Goal(
                    domain=rg["domain"],
                    verb=rg["verb"],
                    object=None,  # Will be inferred
                    params=rg.get("params", {}),
                    goal_id=None,
                    scope="user",
                    base_anchor=None
                )
                repaired_goal_objects.append(goal)
            
            # Create new MetaGoal with repaired goals
            repaired_meta_goal = MetaGoal(
                meta_type=original_meta_goal.meta_type,
                goals=tuple(repaired_goal_objects),
                dependencies=original_meta_goal.dependencies
            )
            
            # Resolve semantic tokens for repaired goals
            resolved_goals = [
                SemanticResolver.resolve_goal(goal)
                for goal in repaired_meta_goal.goals
            ]
            repaired_meta_goal = MetaGoal(
                meta_type=repaired_meta_goal.meta_type,
                goals=tuple(resolved_goals),
                dependencies=repaired_meta_goal.dependencies
            )
            
            # Resolve paths for repaired goals
            repaired_meta_goal = self._resolve_goal_paths(repaired_meta_goal, world_state)
            
            # Re-plan with repaired goals (without execution_summary to avoid loop)
            if repaired_meta_goal.meta_type == "single":
                plan_result = self._handle_single(repaired_meta_goal, world_state, capabilities=None)
            elif repaired_meta_goal.meta_type == "independent_multi":
                plan_result = self._handle_independent_multi(repaired_meta_goal, world_state, capabilities=None)
            elif repaired_meta_goal.meta_type == "dependent_multi":
                plan_result = self._handle_dependent_multi(repaired_meta_goal, world_state, capabilities=None)
            else:
                return None
            
            if plan_result.status == "success" and plan_result.plan_graph:
                return plan_result
            else:
                logging.warning("Repaired goals could not be planned")
                return None
            
        except Exception as e:
            logging.error(f"Plan repair LLM call failed: {e}")
            return None
    
    def _resolve_and_execute(
        self,
        action: PlannedAction,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Resolve abstract PlannedAction → concrete tool → execute.
        
        Invariant: EVERY action goes through ToolResolver.
        No exceptions (including file operations).
        
        Args:
            action: Abstract PlannedAction with intent + description
            context: Current world state (ambient context)
            
        Returns:
            Execution result dict with status and result/error
        """
        from core.tool_resolver import ToolResolver
        from core.context_snapshot import ContextSnapshot
        from execution.executor import ToolExecutor
        
        resolver = ToolResolver()
        executor = ToolExecutor()
        
        # Build structured context snapshot
        context_snapshot = ContextSnapshot.build(context)
        
        resolution = resolver.resolve(
            description=action.description,
            intent=action.intent,
            context=context,
            action_class=action.action_class  # Phase 2: semantic filter
        )
        logging.info(f"DEBUG: _resolve_and_execute: action_class={action.action_class}")
        
        tool_name = resolution.get("tool")
        params = resolution.get("params", {})
        
        # For file_operation: inject path from action.args (not LLM output)
        # This keeps Windows paths out of JSON entirely
        if action.intent == "file_operation" and "path" in action.args:
            params["path"] = action.args["path"]

        if action.intent == "browser_control" and "url" in action.args:
            params["url"] = action.args["url"]
            logging.info(f"DEBUG: Injected browser URL: {action.args['url']}")
            if "browser" in action.args:
                params["app_name"] = action.args["browser"]
                logging.info(f"DEBUG: Injected browser name: {action.args['browser']}")
        
        # PHASE 4: Inject browser selector params from planner (bypass LLM hallucination)
        # LLM was adding "." prefix to selectors - this ensures planner args are authoritative
        if action.intent == "browser_control":
            if "selector" in action.args:
                params["selector"] = action.args["selector"]
                logging.info(f"DEBUG: Injected selector from planner: {action.args['selector']}")
            if "state" in action.args:
                params["state"] = action.args["state"]
                logging.info(f"DEBUG: Injected state from planner: {action.args['state']}")
        
        if not tool_name:
            logging.warning(
                f"GoalOrchestrator: resolution failed for action '{action.description}' "
                f"(intent={action.intent}) - {resolution.get('reason', 'unknown')}"
            )
            return {
                "status": "error",
                "reason": resolution.get("reason", "Tool resolution failed"),
                "action": action.description,
            }
        
        logging.info(
            f"GoalOrchestrator: resolved {action.description} → {tool_name}"
        )
        
        result = executor.execute_tool(tool_name, params)
        
        # Phase 5: Propagate failure_class from tool result
        # If tool didn't provide it, fall back to tool's default property
        if "failure_class" not in result and result.get("status") == "error":
            from tools.registry import get_registry
            registry = get_registry()
            tool_instance = registry.get(tool_name)
            if tool_instance:
                result["failure_class"] = tool_instance.failure_class
            else:
                result["failure_class"] = "unknown"
        
        return result
    
    def _resolve_goal_paths(
        self, 
        meta_goal: MetaGoal, 
        world_state: Dict[str, Any]
    ) -> MetaGoal:
        """Resolve all file_operation paths BEFORE planning.
        
        This is the SINGLE AUTHORITY for path resolution.
        After this method, all file_operation goals have resolved_path set.
        
        Resolution rules:
        1. If user provided absolute path → use as-is
        2. If dependent goal → inherit parent's resolved path
        3. Otherwise → resolve against base_anchor (default: WORKSPACE)
        
        Args:
            meta_goal: MetaGoal with potentially unresolved paths
            world_state: Context containing session info with cwd
        
        Returns:
            New MetaGoal with resolved paths
        """
        # Get session context for WORKSPACE anchor
        context = world_state.get("_session_context")
        
        # Track resolved paths for inheritance
        resolved_paths: Dict[int, Path] = {}  # goal_idx → resolved path
        
        resolved_goals = []
        
        for idx, goal in enumerate(meta_goal.goals):
            # Only resolve file domain goals with paths
            # PHASE 4: Use parametric (domain, verb, params) instead of goal_type
            path_param = goal.params.get("path") or goal.params.get("name") if goal.params else None
            if goal.domain != "file" or not path_param:
                resolved_goals.append(goal)
                continue
            
            # Determine parent path for dependent goals
            parent_path = None
            deps = meta_goal.get_dependencies(idx)
            
            # DEBUG: Log dependency resolution
            logging.info(f"DEBUG: Goal {idx} '{path_param}' - deps={deps}, scope={goal.scope}")
            
            if deps:
                # Use first dependency's resolved path
                parent_idx = deps[0]
                parent_path = resolved_paths.get(parent_idx)
                logging.info(f"DEBUG: Goal {idx} using parent_path from goal {parent_idx}: {parent_path}")
            
            # Determine base anchor (from goal or default)
            base_anchor = goal.base_anchor or "WORKSPACE"
            
            try:
                # Resolve using PathResolver
                # PHASE 4: Use path_param from params
                resolved = PathResolver.resolve(
                    raw_path=path_param,
                    base_anchor=base_anchor,
                    parent_resolved=parent_path,
                    context=context
                )
                
                # Store for children
                resolved_paths[idx] = resolved.absolute_path
                
                # Create new goal with resolved path in params
                # PHASE 4: Goals are parametric (domain, verb, params)
                updated_params = dict(goal.params) if goal.params else {}
                updated_params["resolved_path"] = str(resolved.absolute_path)
                
                new_goal = Goal(
                    domain=goal.domain,
                    verb=goal.verb,
                    object=goal.object,
                    params=updated_params,
                    goal_id=goal.goal_id,
                    scope=goal.scope,
                    base_anchor=resolved.base_anchor,
                    resolved_path=str(resolved.absolute_path)  # THE AUTHORITY
                )
                resolved_goals.append(new_goal)
                
                logging.debug(
                    f"PathResolver: goal {idx} '{path_param}' → "
                    f"'{resolved.absolute_path}' (base={resolved.base_anchor})"
                )
                
            except Exception as e:
                logging.error(f"Path resolution failed for goal {idx}: {e}")
                # Keep original goal, planner will fail with assertion
                resolved_goals.append(goal)
        
        # Create new MetaGoal with resolved goals
        return MetaGoal(
            meta_type=meta_goal.meta_type,
            goals=tuple(resolved_goals),
            dependencies=meta_goal.dependencies
        )
    
    def orchestrate(
        self,
        meta_goal: MetaGoal,
        world_state: Optional[Dict[str, Any]] = None,
        capabilities: Optional[List[Dict]] = None,
        execution_summary: Optional[ExecutionSummary] = None
    ) -> OrchestrationResult:
        """Orchestrate planning for multi-goal MetaGoal.
        
        Phase 5: If execution_summary is provided and shows partial failure,
        attempt plan repair for recoverable failures.
        
        Args:
            meta_goal: MetaGoal with one or more goals
            world_state: Current world state (read-only)
            capabilities: Available tool capabilities
            execution_summary: Optional execution results from previous attempt
            
        Returns:
            OrchestrationResult with PlanGraph or failure info
        """
        world_state = world_state or {}
        
        # Phase 5: Repair logic - triggered after execution failure
        if execution_summary and execution_summary.status == "partial" and execution_summary.failed_goals:
            repair_budget = world_state.get("_repair_attempts", 0)
            
            if repair_budget >= self.MAX_REPAIR_ATTEMPTS:
                logging.info("Repair budget exhausted")
                return OrchestrationResult(
                    status="partial",
                    failed_goals=execution_summary.failed_goals,
                    reason="Repair budget exhausted",
                    repair_attempted=True,
                    repair_reason="Budget limit reached"
                )
            
            # Filter recoverable failures
            recoverable = [
                fg for fg in execution_summary.failed_goals
                if self._is_recoverable(fg.failure_class)
            ]
            
            if recoverable:
                # CONSUME BUDGET BEFORE CALLING LLM
                world_state["_repair_attempts"] = repair_budget + 1
                
                try:
                    repaired = self._attempt_plan_repair(meta_goal, execution_summary, world_state)
                    if repaired:
                        repaired.repair_attempted = True
                        repaired.repair_reason = f"Recovered from {len(recoverable)} environmental failures"
                        return repaired
                    else:
                        # Repair failed - equivalence check rejected
                        return OrchestrationResult(
                            status="partial",
                            failed_goals=execution_summary.failed_goals,
                            reason="Plan repair failed - equivalence check rejected",
                            repair_attempted=True,
                            repair_reason="Repair produced invalid goals"
                        )
                except Exception as e:
                    # Budget consumed even on failure
                    logging.error(f"Plan repair failed: {e}")
                    return OrchestrationResult(
                        status="partial",
                        failed_goals=execution_summary.failed_goals,
                        reason=f"Plan repair exception: {e}",
                        repair_attempted=True,
                        repair_reason=f"Repair exception: {e}"
                    )
        
        # STEP 0: Resolve semantic tokens (like "default") BEFORE planning
        # This is the SINGLE AUTHORITY for semantic token resolution
        logging.info(f"SemanticResolver: Processing {len(meta_goal.goals)} goal(s) for semantic token resolution")
        resolved_goals = []
        for goal in meta_goal.goals:
            logging.debug(f"SemanticResolver: Before resolution - {goal.domain}.{goal.verb} params={goal.params}")
            resolved_goal = SemanticResolver.resolve_goal(goal)
            logging.debug(f"SemanticResolver: After resolution - {resolved_goal.domain}.{resolved_goal.verb} params={resolved_goal.params}")
            resolved_goals.append(resolved_goal)
        meta_goal = MetaGoal(
            meta_type=meta_goal.meta_type,
            goals=tuple(resolved_goals),
            dependencies=meta_goal.dependencies
        )
        
        # DIAGNOSTIC: Detect app.launch(browser) followed by browser goals
        # This pattern suggests an interpreter example gap
        self._warn_if_browser_launch_with_browser_goals(meta_goal)
        
        # STEP 1: Resolve all file_operation paths BEFORE planning
        # This is the SINGLE AUTHORITY for path resolution
        meta_goal = self._resolve_goal_paths(meta_goal, world_state)
        
        if meta_goal.meta_type == "single":
            return self._handle_single(meta_goal, world_state, capabilities)
        elif meta_goal.meta_type == "independent_multi":
            return self._handle_independent_multi(meta_goal, world_state, capabilities)
        elif meta_goal.meta_type == "dependent_multi":
            return self._handle_dependent_multi(meta_goal, world_state, capabilities)
        else:
            return OrchestrationResult(
                status="no_capability",
                reason=f"Unknown meta_type: {meta_goal.meta_type}"
            )
    
    def _handle_single(
        self, 
        meta_goal: MetaGoal, 
        world_state: Dict,
        capabilities: Optional[List[Dict]]
    ) -> OrchestrationResult:
        """Single goal - passthrough to GoalPlanner."""
        goal = meta_goal.goals[0]
        # Log context frames (none for single by default)
        logging.info(f"Planning goal {goal.goal_id or '<no-id>'} with context frames: []")
        result = self.goal_planner.plan(goal, world_state, capabilities, context_frames=[])
        
        if result.status != "success" or result.plan is None:
            return OrchestrationResult(
                status=result.status,
                failed_goals=[FailedGoal(
                    goal_idx=0,
                    goal=goal,
                    reason=result.reason or "Planning failed",
                    failure_class="logical"  # Planning failures are never recoverable
                )],
                reason=result.reason
            )
        
        # Wrap plan in PlanGraph
        plan_graph = self._plan_to_graph(result.plan, goal_idx=0)
        
        return OrchestrationResult(
            status="success",
            plan_graph=plan_graph
        )
    
    def _handle_independent_multi(
        self,
        meta_goal: MetaGoal,
        world_state: Dict,
        capabilities: Optional[List[Dict]]
    ) -> OrchestrationResult:
        """Independent multi - plan each goal, merge parallel."""
        plans: List[tuple] = []  # (goal_idx, Plan)
        failed: List[FailedGoal] = []
        
        produced_contexts: Dict[int, List[ContextFrame]] = {}

        for idx, goal in enumerate(meta_goal.goals):
            # Independent goals have no dependencies: pass no contexts
            logging.info(f"Planning goal {goal.goal_id or '<no-id>'} with context frames: []")
            result = self.goal_planner.plan(goal, world_state, capabilities, context_frames=[])
            
            if result.status == "success" and result.plan is not None:
                plans.append((idx, result.plan))
                # capture produced contexts from plan actions (if any)
                for a in result.plan.actions:
                    if getattr(a, "produced_context", None):
                        produced_contexts.setdefault(idx, []).append(a.produced_context)
            else:
                failed.append(FailedGoal(
                    goal_idx=idx,
                    goal=goal,
                    reason=result.reason or "Planning failed",
                    failure_class="logical"  # Planning failures are never recoverable
                ))
        
        if not plans:
            return OrchestrationResult(
                status="blocked",
                failed_goals=failed,
                reason="No goals could be planned"
            )
        
        # Merge plans into single graph (no dependencies between goals)
        plan_graph = self._merge_independent_plans(plans)
        
        if failed:
            return OrchestrationResult(
                status="partial",
                plan_graph=plan_graph,
                failed_goals=failed,
                reason=f"{len(failed)} goal(s) could not be planned"
            )
        
        return OrchestrationResult(
            status="success",
            plan_graph=plan_graph
        )
    
    def _handle_dependent_multi(
        self,
        meta_goal: MetaGoal,
        world_state: Dict,
        capabilities: Optional[List[Dict]]
    ) -> OrchestrationResult:
        """Dependent multi - plan in order, track dependencies.
        
        Phase 1: Basic implementation, no simulated state.
        """
        plans: List[tuple] = []  # (goal_idx, Plan)
        failed: List[FailedGoal] = []
        failed_indices = set()
        
        # Process goals in order (dependencies are already validated in MetaGoal)
        produced_contexts: Dict[int, List[ContextFrame]] = {}

        def collect_upstream_contexts(goal_idx: int, visited: set | None = None) -> List[ContextFrame]:
            visited = visited or set()
            if goal_idx in visited:
                return []
            visited.add(goal_idx)
            ctxs: List[ContextFrame] = []
            deps = meta_goal.get_dependencies(goal_idx)
            for dep in deps:
                # include contexts produced directly by dependency
                ctxs.extend(produced_contexts.get(dep, []))
                # recurse to transitive dependencies
                ctxs.extend(collect_upstream_contexts(dep, visited))
            return ctxs

        for idx, goal in enumerate(meta_goal.goals):
            # Check if dependencies failed
            deps = meta_goal.get_dependencies(idx)
            if any(d in failed_indices for d in deps):
                failed.append(FailedGoal(
                    goal_idx=idx,
                    goal=goal,
                    reason="Dependency failed",
                    failure_class="logical"  # Planning failures are never recoverable
                ))
                failed_indices.add(idx)
                continue
            # Collect context frames produced by upstream dependencies (transitive closure)
            upstream_contexts = collect_upstream_contexts(idx)
            logging.info(f"Planning goal {goal.goal_id or '<no-id>'} with context frames: {[f'{c.domain}.{list(c.data.keys())} (from {c.produced_by})' for c in upstream_contexts]}")
            result = self.goal_planner.plan(goal, world_state, capabilities, context_frames=upstream_contexts)
            
            if result.status == "success" and result.plan is not None:
                plans.append((idx, result.plan))
                # capture produced contexts from plan actions (if any)
                for a in result.plan.actions:
                    if getattr(a, "produced_context", None):
                        produced_contexts.setdefault(idx, []).append(a.produced_context)
            else:
                failed.append(FailedGoal(
                    goal_idx=idx,
                    goal=goal,
                    reason=result.reason or "Planning failed",
                    failure_class="logical"  # Planning failures are never recoverable
                ))
                failed_indices.add(idx)
        
        if not plans:
            return OrchestrationResult(
                status="blocked",
                failed_goals=failed,
                reason="No goals could be planned"
            )
        
        # Merge with dependencies
        plan_graph = self._merge_dependent_plans(plans, meta_goal.dependencies)
        
        if failed:
            return OrchestrationResult(
                status="partial",
                plan_graph=plan_graph,
                failed_goals=failed
            )
        
        return OrchestrationResult(
            status="success",
            plan_graph=plan_graph
        )
    
    def _plan_to_graph(self, plan: Plan, goal_idx: int) -> PlanGraph:
        """Convert single Plan to PlanGraph."""
        nodes = {}
        edges = {}
        goal_map = {goal_idx: []}
        execution_order = []
        
        for action in plan.actions:
            # Prefix action_id with goal index for uniqueness
            prefixed_id = f"g{goal_idx}_{action.action_id}"
            
            # Update action with prefixed ID
            nodes[prefixed_id] = PlannedAction(
                action_id=prefixed_id,
                intent=action.intent,
                description=action.description,
                args=action.args,
                expected_effect=action.expected_effect,
                depends_on=[f"g{goal_idx}_{d}" for d in action.depends_on],
                action_class=action.action_class  # Phase 2: MUST copy this!
                , produced_context=action.produced_context
            )
            
            edges[prefixed_id] = [f"g{goal_idx}_{d}" for d in action.depends_on]
            goal_map[goal_idx].append(prefixed_id)
            execution_order.append(prefixed_id)
        
        return PlanGraph(
            nodes=nodes,
            edges=edges,
            goal_map=goal_map,
            execution_order=execution_order,
            total_actions=len(nodes)
        )
    
    def _merge_independent_plans(self, plans: List[tuple]) -> PlanGraph:
        """Merge independent plans (no inter-goal dependencies)."""
        nodes = {}
        edges = {}
        goal_map = {}
        execution_order = []
        
        for goal_idx, plan in plans:
            goal_map[goal_idx] = []
            
            for action in plan.actions:
                prefixed_id = f"g{goal_idx}_{action.action_id}"
                
                nodes[prefixed_id] = PlannedAction(
                    action_id=prefixed_id,
                    intent=action.intent,
                    description=action.description,
                    args=action.args,
                    expected_effect=action.expected_effect,
                    depends_on=[f"g{goal_idx}_{d}" for d in action.depends_on],
                    action_class=action.action_class  # Phase 2: MUST copy this!
                    , produced_context=action.produced_context
                )
                
                edges[prefixed_id] = [f"g{goal_idx}_{d}" for d in action.depends_on]
                goal_map[goal_idx].append(prefixed_id)
                execution_order.append(prefixed_id)
        
        return PlanGraph(
            nodes=nodes,
            edges=edges,
            goal_map=goal_map,
            execution_order=execution_order,
            total_actions=len(nodes)
        )
    
    def _merge_dependent_plans(
        self, 
        plans: List[tuple],
        dependencies: tuple
    ) -> PlanGraph:
        """Merge dependent plans with inter-goal edges."""
        nodes = {}
        edges = {}
        goal_map = {}
        
        # First pass: add all nodes
        for goal_idx, plan in plans:
            goal_map[goal_idx] = []
            
            for action in plan.actions:
                prefixed_id = f"g{goal_idx}_{action.action_id}"
                
                nodes[prefixed_id] = PlannedAction(
                    action_id=prefixed_id,
                    intent=action.intent,
                    description=action.description,
                    args=action.args,
                    expected_effect=action.expected_effect,
                    depends_on=[f"g{goal_idx}_{d}" for d in action.depends_on],
                    action_class=action.action_class  # Phase 2: MUST copy this!
                    , produced_context=action.produced_context
                )
                
                edges[prefixed_id] = [f"g{goal_idx}_{d}" for d in action.depends_on]
                goal_map[goal_idx].append(prefixed_id)
        
        # Second pass: add inter-goal dependencies
        for goal_idx, deps in dependencies:
            if goal_idx not in goal_map:
                continue
            
            # First action of this goal depends on last action of dependency goals
            first_action = goal_map[goal_idx][0] if goal_map[goal_idx] else None
            
            for dep_idx in deps:
                if dep_idx in goal_map and goal_map[dep_idx]:
                    last_dep_action = goal_map[dep_idx][-1]
                    if first_action and last_dep_action not in edges.get(first_action, []):
                        edges.setdefault(first_action, []).append(last_dep_action)
                        nodes[first_action].depends_on.append(last_dep_action)
        
        # Topological sort for execution order
        execution_order = self._topological_sort(nodes, edges)
        
        return PlanGraph(
            nodes=nodes,
            edges=edges,
            goal_map=goal_map,
            execution_order=execution_order,
            total_actions=len(nodes)
        )
    
    def _topological_sort(
        self, 
        nodes: Dict[str, PlannedAction],
        edges: Dict[str, List[str]]
    ) -> List[str]:
        """Topological sort of action nodes."""
        in_degree = {node: 0 for node in nodes}
        
        for node, deps in edges.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[node] = in_degree.get(node, 0) + 1
        
        # Start with nodes having no dependencies
        queue = [n for n, d in in_degree.items() if d == 0]
        result = []
        
        while queue:
            node = queue.pop(0)
            result.append(node)
            
            # Reduce in-degree for dependents
            for other_node, deps in edges.items():
                if node in deps:
                    in_degree[other_node] -= 1
                    if in_degree[other_node] == 0:
                        queue.append(other_node)
        
        # If not all nodes processed, there's a cycle (shouldn't happen)
        if len(result) != len(nodes):
            logging.warning("Topological sort incomplete - possible cycle")
            # Add remaining nodes anyway
            for node in nodes:
                if node not in result:
                    result.append(node)
        
        return result
