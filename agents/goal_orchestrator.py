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

Phase 1 Scope: single + independent_multi only
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Literal

from agents.goal_interpreter import Goal, MetaGoal
from agents.goal_planner import GoalPlanner, Plan, PlannedAction, PlanResult


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
    """A goal that could not be planned."""
    goal_idx: int
    goal: Goal
    reason: str
    blocker: Optional[str] = None


@dataclass
class OrchestrationResult:
    """Result of orchestrating multiple goals."""
    status: Literal["success", "partial", "blocked", "no_capability"]
    plan_graph: Optional[PlanGraph] = None
    failed_goals: List[FailedGoal] = field(default_factory=list)
    reason: Optional[str] = None


# =============================================================================
# GOAL ORCHESTRATOR
# =============================================================================

class GoalOrchestrator:
    """Multi-goal coordination via per-goal planning.
    
    RESPONSIBILITY:
    - Accept MetaGoal
    - Call GoalPlanner.plan() per goal
    - Combine plans into PlanGraph
    
    DOES NOT:
    - Parse user input (GoalInterpreter's job)
    - Merge within a goal (GoalPlanner's job)
    - Execute anything (Executor's job)
    """
    
    def __init__(self):
        self.goal_planner = GoalPlanner()
        logging.info("GoalOrchestrator initialized (multi-goal coordination)")
    
    def orchestrate(
        self,
        meta_goal: MetaGoal,
        world_state: Optional[Dict[str, Any]] = None,
        capabilities: Optional[List[Dict]] = None
    ) -> OrchestrationResult:
        """Orchestrate planning for multi-goal MetaGoal.
        
        Args:
            meta_goal: MetaGoal with one or more goals
            world_state: Current world state (read-only)
            capabilities: Available tool capabilities
            
        Returns:
            OrchestrationResult with PlanGraph or failure info
        """
        world_state = world_state or {}
        
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
        result = self.goal_planner.plan(goal, world_state, capabilities)
        
        if result.status != "success" or result.plan is None:
            return OrchestrationResult(
                status=result.status,
                failed_goals=[FailedGoal(0, goal, result.reason or "Planning failed")],
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
        
        for idx, goal in enumerate(meta_goal.goals):
            result = self.goal_planner.plan(goal, world_state, capabilities)
            
            if result.status == "success" and result.plan is not None:
                plans.append((idx, result.plan))
            else:
                failed.append(FailedGoal(
                    goal_idx=idx,
                    goal=goal,
                    reason=result.reason or "Planning failed"
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
        for idx, goal in enumerate(meta_goal.goals):
            # Check if dependencies failed
            deps = meta_goal.get_dependencies(idx)
            if any(d in failed_indices for d in deps):
                failed.append(FailedGoal(
                    goal_idx=idx,
                    goal=goal,
                    reason="Dependency failed"
                ))
                failed_indices.add(idx)
                continue
            
            result = self.goal_planner.plan(goal, world_state, capabilities)
            
            if result.status == "success" and result.plan is not None:
                plans.append((idx, result.plan))
            else:
                failed.append(FailedGoal(
                    goal_idx=idx,
                    goal=goal,
                    reason=result.reason or "Planning failed"
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
                tool=action.tool,
                args=action.args,
                expected_effect=action.expected_effect,
                depends_on=[f"g{goal_idx}_{d}" for d in action.depends_on]
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
                    tool=action.tool,
                    args=action.args,
                    expected_effect=action.expected_effect,
                    depends_on=[f"g{goal_idx}_{d}" for d in action.depends_on]
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
                    tool=action.tool,
                    args=action.args,
                    expected_effect=action.expected_effect,
                    depends_on=[f"g{goal_idx}_{d}" for d in action.depends_on]
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
