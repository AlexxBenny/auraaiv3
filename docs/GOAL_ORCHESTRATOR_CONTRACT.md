# Goal Orchestrator Contract

> **The layer above GoalPlanner. Handles multi-goal queries by orchestrating per-goal planning.**

---

## 1. Architectural Position

```
User Query
    ↓
GoalInterpreter
    ↓
MetaGoal (goal tree with dependencies)
    ↓
GoalOrchestrator  ← THIS CONTRACT
    ↓
GoalPlanner.plan() (called per goal)
    ↓
OrchestratedPlan (plan graph)
    ↓
Executor
```

**Key Insight:**
- `GoalPlanner` handles ONE goal → ONE plan
- `GoalOrchestrator` handles MANY goals → combined plan graph

---

## 2. Input Contracts

### 2.1 MetaGoal

```python
@dataclass(frozen=True)
class MetaGoal:
    """A goal tree that may contain multiple sub-goals."""
    
    meta_type: Literal["single", "independent_multi", "dependent_multi"]
    goals: Tuple[Goal, ...]  # Immutable tuple
    dependencies: FrozenDict[int, Tuple[int, ...]]  # goal_idx → depends_on[]
    
    def __post_init__(self):
        # Invariants
        if self.meta_type == "single":
            assert len(self.goals) == 1
            assert len(self.dependencies) == 0
        
        # No circular dependencies
        assert not self._has_cycles()
```

**MetaGoal Types:**

| Type | Meaning | Example |
|------|---------|---------|
| `single` | One goal | "open youtube and search nvidia" |
| `independent_multi` | Multiple unrelated goals | "open spotify and open chrome" |
| `dependent_multi` | Goals with dependencies | "create folder X, then create file in X" |

### 2.2 Goal (from GoalPlanner contract)

```python
@dataclass(frozen=True)
class Goal:
    goal_type: Literal[
        "browser_search",
        "browser_navigate", 
        "app_launch",
        "app_action",
        "file_operation",
        "system_query"
    ]
    # ... (same as GoalPlanner contract)
```

---

## 3. Function Signature

```python
def orchestrate(
    self,
    meta_goal: MetaGoal,
    world_state: WorldState,
    capabilities: List[ToolCapability]
) -> OrchestrationResult:
```

---

## 4. Output Contract

### 4.1 OrchestrationResult

```python
@dataclass
class OrchestrationResult:
    status: Literal["success", "partial", "blocked", "no_capability"]
    plan_graph: Optional[PlanGraph]
    failed_goals: List[FailedGoal]  # Which goals couldn't be planned
    reason: Optional[str]
```

### 4.2 PlanGraph

```python
@dataclass
class PlanGraph:
    """Combined plan from multiple goals."""
    
    nodes: Dict[str, PlannedAction]  # action_id → action
    edges: Dict[str, List[str]]       # action_id → depends_on[]
    goal_map: Dict[int, List[str]]    # goal_idx → action_ids
    execution_order: List[str]        # Topologically sorted
    
    def __post_init__(self):
        # Invariants
        assert self._is_acyclic()
        assert self._all_deps_exist()
        assert len(self.execution_order) == len(self.nodes)
```

### 4.3 FailedGoal

```python
@dataclass
class FailedGoal:
    goal_idx: int
    goal: Goal
    reason: str
    blocker: Optional[str]  # What blocked it
```

---

## 5. Orchestration Logic

### 5.1 Single Goal (Passthrough)

```python
if meta_goal.meta_type == "single":
    plan_result = self.goal_planner.plan(
        meta_goal.goals[0], world_state, capabilities
    )
    return self._wrap_single(plan_result)
```

### 5.2 Independent Multi

```python
if meta_goal.meta_type == "independent_multi":
    plans = []
    failed = []
    
    for idx, goal in enumerate(meta_goal.goals):
        result = self.goal_planner.plan(goal, world_state, capabilities)
        
        if result.status == "success":
            plans.append((idx, result.plan))
        else:
            failed.append(FailedGoal(idx, goal, result.reason))
    
    if not plans:
        return OrchestrationResult(status="blocked", failed_goals=failed)
    elif failed:
        return OrchestrationResult(
            status="partial",
            plan_graph=self._merge_independent(plans),
            failed_goals=failed
        )
    else:
        return OrchestrationResult(
            status="success",
            plan_graph=self._merge_independent(plans)
        )
```

### 5.3 Dependent Multi

```python
if meta_goal.meta_type == "dependent_multi":
    # Topological sort of goals
    goal_order = self._topo_sort(meta_goal.dependencies)
    
    plans = []
    failed = []
    simulated_state = world_state  # Track expected state changes
    
    for goal_idx in goal_order:
        goal = meta_goal.goals[goal_idx]
        
        # Check if dependencies failed
        deps = meta_goal.dependencies.get(goal_idx, ())
        if any(d in [f.goal_idx for f in failed] for d in deps):
            failed.append(FailedGoal(goal_idx, goal, "Dependency failed"))
            continue
        
        result = self.goal_planner.plan(goal, simulated_state, capabilities)
        
        if result.status == "success":
            plans.append((goal_idx, result.plan))
            # Update simulated state with expected effects
            simulated_state = self._apply_effects(simulated_state, result.plan)
        else:
            failed.append(FailedGoal(goal_idx, goal, result.reason))
    
    return self._build_result(plans, failed, meta_goal.dependencies)
```

---

## 6. Guarantees

| ID | Guarantee |
|----|-----------|
| O1 | **Single goals pass through unchanged** |
| O2 | **Independent goals produce parallel-safe plan** |
| O3 | **Dependencies become edges in plan graph** |
| O4 | **Execution order is topologically valid** |
| O5 | **Partial success returns what succeeded** |
| O6 | **WorldState never mutated** |

---

## 7. Edge Cases

### 7.1 All Goals Fail

```python
OrchestrationResult(
    status="blocked",
    plan_graph=None,
    failed_goals=[...all...],
    reason="No goals could be planned"
)
```

### 7.2 Dependency Chain Breaks

```python
# Goal 1 fails, Goal 2 depends on Goal 1
→ Goal 2 automatically fails with reason="Dependency failed"
→ Status becomes "partial" if Goal 0 succeeded
```

### 7.3 Circular Dependencies in Input

```python
# MetaGoal validation rejects this at construction time
# GoalOrchestrator never sees circular dependencies
```

---

## 8. Examples

### Example A: Single Merged Goal

**Input:**
```python
MetaGoal(
    meta_type="single",
    goals=(Goal(goal_type="browser_search", platform="youtube", query="nvidia"),),
    dependencies={}
)
```

**Output:**
```python
OrchestrationResult(
    status="success",
    plan_graph=PlanGraph(
        nodes={"a1": PlannedAction(tool="launch_shell", args={url: "youtube.com/..."})}),
        edges={},
        execution_order=["a1"]
    )
)
```

### Example B: Independent Multi

**Input:**
```python
MetaGoal(
    meta_type="independent_multi",
    goals=(
        Goal(goal_type="app_action", target="spotify", action="play"),
        Goal(goal_type="browser_search", platform="google", query="nvidia")
    ),
    dependencies={}
)
```

**Output:**
```python
OrchestrationResult(
    status="success",
    plan_graph=PlanGraph(
        nodes={
            "g0_a1": PlannedAction(...spotify...),
            "g1_a1": PlannedAction(...chrome...)
        },
        edges={},  # No dependencies
        execution_order=["g0_a1", "g1_a1"]  # Can be parallel
    )
)
```

### Example C: Dependent Multi

**Input:**
```python
MetaGoal(
    meta_type="dependent_multi",
    goals=(
        Goal(goal_type="file_operation", action="mkdir", path="D:\\alex"),
        Goal(goal_type="file_operation", action="create", path="D:\\alex\\cars.pptx")
    ),
    dependencies={1: (0,)}  # Goal 1 depends on Goal 0
)
```

**Output:**
```python
OrchestrationResult(
    status="success",
    plan_graph=PlanGraph(
        nodes={
            "g0_a1": PlannedAction(tool="files.create_folder", args={path: "D:\\alex"}),
            "g1_a1": PlannedAction(tool="files.create_file", args={path: "D:\\alex\\cars.pptx"})
        },
        edges={"g1_a1": ["g0_a1"]},  # Explicit dependency
        execution_order=["g0_a1", "g1_a1"]  # Sequential
    )
)
```

---

## 9. What GoalOrchestrator Does NOT Do

| Responsibility | Who Handles It |
|----------------|----------------|
| Parse user input | GoalInterpreter |
| Plan single goal | GoalPlanner |
| Merge actions within a goal | GoalPlanner |
| Execute plan | Executor |
| Handle ambiguity | GoalInterpreter |

---

## 10. Phase 1 Scope

For initial implementation:

```python
PHASE_1_META_TYPES = {"single", "independent_multi"}
```

- `dependent_multi` deferred to Phase 2
- Simulated state effects deferred to Phase 2

---

## Summary

```
┌─────────────────────────────────────────────────────┐
│              GoalOrchestrator.orchestrate()         │
├─────────────────────────────────────────────────────┤
│  INPUTS (all immutable):                            │
│    - MetaGoal (goal tree with dependencies)         │
│    - WorldState (frozen, read-only)                 │
│    - Capabilities (tool metadata)                   │
├─────────────────────────────────────────────────────┤
│  OUTPUTS:                                           │
│    - OrchestrationResult with status                │
│    - PlanGraph (nodes, edges, execution_order)      │
│    - FailedGoals for partial/blocked                │
├─────────────────────────────────────────────────────┤
│  GUARANTEES:                                        │
│    - Single goals pass through                      │
│    - Independent goals parallelizable               │
│    - Dependencies → explicit edges                  │
│    - Execution order is valid                       │
│    - Partial success supported                      │
├─────────────────────────────────────────────────────┤
│  CALLS:                                             │
│    - GoalPlanner.plan() per goal                    │
├─────────────────────────────────────────────────────┤
│  DOES NOT:                                          │
│    - Execute anything                               │
│    - Parse user input                               │
│    - Merge within a goal (GoalPlanner's job)        │
└─────────────────────────────────────────────────────┘
```
