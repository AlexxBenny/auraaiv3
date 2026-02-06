# Goal Orchestrator Contract (Phase 4)

> **Contract for Multi-Goal Coordination & Context Injection**

---

## 1. Purpose

`GoalOrchestrator` is the **Execution Engine** for the Parametric Goal architecture. It manages the lifecycle of `MetaGoal` → `PlanGraph` -> `Execution`.

**Primary Responsibilities:**
1. **Dependency Resolution**: Converts `MetaGoal` dependencies into a `PlanGraph` DAG.
2. **Context Injection**: Injects resolved paths and planner-authoritative parameters (`selectors`) into tool parameters.
3. **Execution Management**: Topological execution of the graph.

---

## 2. Architecture

```
MetaGoal (Interpreter)
    ↓
GoalOrchestrator (Dependency Resolution)
    ↓
GoalPlanner (per goal) → PlannedAction
    ↓
PlanGraph (DAG of Actions)
    ↓
PlanExecutor (Topological Sort)
    ↓
ToolResolver (Action → Tool)
```

---

## 3. Param Injection & Context Logic

The Orchestrator is responsible for ensuring **Planner Authority** over critical parameters.

### 3.1 Selector Injection (Browser)
To prevent LLM hallucinations (e.g. adding `.` to selectors), the Orchestrator injects `selector` and `state` directly from `PlannedAction.args` into the tool parameters.

```python
# Logic
if action.intent == "browser_control" and "selector" in action.args:
    params["selector"] = action.args["selector"]  # OVERRIDE LLM
```

### 3.2 Path Injection (File)
To handle Windows paths and anchor resolution deterministically:

```python
# Logic
if action.intent == "file_operation" and "path" in action.args:
    params["path"] = action.args["path"]  # OVERRIDE LLM
```

---

## 4. Input/Output Contracts

### 4.1 Input: MetaGoal
- Contains parametric goals (`domain, verb, params`)
- Contains dependency map `{child_idx: (parent_idx, ...)}`

### 4.2 Output: PlanGraph
```python
@dataclass
class PlanGraph:
    nodes: Dict[str, PlannedAction]  # action_id -> Action
    adjacency: Dict[str, Set[str]]   # parent_id -> children_ids
    results: Dict[str, Any]          # action_id -> ToolResult
```

---

## 5. Execution Logic

1. **Topological Sort**: Flatten DAG into layers (e.g. `[g0, g1], [g2]`).
2. **Parallel Execution**: Execute independent items in parallel (future capability).
3. **Context Propagation**:
   - `g0` (navigate) executes.
   - `g1` (wait) inherits browser session from `g0`.
   - `g2` (open folder) inherits resolved path from `g0`.

---

## 6. What Changed in Phase 4?

- **Removed `goal_type` Logic**: Orchestrator no longer switches on `goal_type`. It inspects `domain`.
- **Param Injection**: Formalized injection of `selector`, `url`, `path` to enforce Planner Authority.
- **DAG Construction**: Uses Scope-Resolved dependencies exclusively.
