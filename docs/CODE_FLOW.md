# Execution Code Flow (Phase 4)

> **Trace of a request from User Input to Result**

---

## 1. Entry Point (`main.py`)

1. User enters text.
2. `Orchestrator.process_command(user_input)` is called.

---

## 2. Classification Layer

**`core/orchestrator.py`**

```python
classification = self.query_classifier.classify(user_input)
# Returns: "single" or "multi"
```

---

## 3. Path A: Single Goal (Legacy/Fast)

If `classification == "single"`, the legacy path is taken.

**`core/orchestrator.py`**
1. **Intent Classification**: `self.intent_router.route(user_input)`
   - Takes: "open youtube"
   - Returns: `Intent(name="browser_control", confidence=0.9)`

2. **Pipeline Execution**: `self.execution_coordinator.execute(...)`
   - **`ToolResolver.resolve()`**: Maps intent ("browser_control") + input ("open youtube") → `browsers.navigate`
   - **`ToolExecutor.execute()`**: Runs the tool.

---

## 4. Path B: Multi Goal (Parametric Engine)

If `classification == "multi"`, the new Phase 4 path is taken.

### 4.1 Goal Interpretation
**`agents/goal_interpreter.py`**
1. **LLM Call**: "go to google and read title" → JSON Goals
2. **Scope Resolution**: 
   - `after:navigate` → Resolved to dependency ID `0`
3. **MetaGoal Creation**: Returns `MetaGoal` with parametric goals and dependency DAG.

### 4.2 Orchestration
**`agents/goal_orchestrator.py`**
1. **Orchestrate**:
   - Iterates through DAG in topological order.
   - Maintains `WorldState` context.

2. **Planning (Per Goal)**:
   - **`GoalPlanner.plan(goal)`**: 
     - Lookups `PLANNER_RULES[(domain, verb)]`.
     - Validates params.
     - Returns `PlannedAction`.

### 4.3 Execution (Per Action)
1. **Context Injection**:
   - Orchestrator injects resolved paths (`path`) or selectors (`selector`) from `PlannedAction` into params.
   
2. **Resolution & Run**:
   - **`ToolResolver.resolve()`**: Maps `PlannedAction` → Tool.
   - **`ToolExecutor`**: Executes tool. 
   - Result stored in `PlanGraph`.

---

## 5. Summary of Key Files

| File | Phase | Role |
|------|-------|------|
| `core/orchestrator.py` | 1-4 | Routes between Single/Multi paths |
| `agents/query_classifier.py` | 2 | Decides Single vs Multi |
| `agents/goal_interpreter.py` | 4 | Creates Parametric Goals |
| `agents/goal_planner.py` | 4 | Validates & Creates Actions |
| `agents/goal_orchestrator.py` | 4 | Manages Dependencies |
