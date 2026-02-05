# Adding New Goal Types to AURA

## Checklist

When adding a new goal type (e.g., `window_management`), follow this exact sequence:

### Step 1: Goal.goal_type Literal
**File**: `agents/goal_interpreter.py` (line 42-51)

```python
goal_type: Literal[
    ...existing types...,
    "window_management"  # ADD HERE
]
```

Update docstring above it (line 32-40).

### Step 2: INTERPRETER_SCHEMA enum
**File**: `agents/goal_interpreter.py` (line 152-161)

```python
"enum": [
    ...existing types...,
    "window_management"  # ADD HERE
]
```

### Step 3: GOAL_TO_INTENT mapping
**File**: `agents/goal_planner.py` (line 31-40)

```python
GOAL_TO_INTENT = {
    ...existing mappings...,
    "window_management": "window_management",  # ADD HERE
}
```

The assertion guard (line 44-46) will fail at import if this is missing.

### Step 4: Add planner method
**File**: `agents/goal_planner.py`

```python
def _plan_window_management(self, goal: Goal, world_state: Dict) -> PlanResult:
    """Plan window management action."""
    action = goal.action or "unknown"
    target = goal.target  # app name or window identifier
    
    planned_action = PlannedAction(
        action_id="a0",
        intent=GOAL_TO_INTENT["window_management"],
        description=f"{action}:{target}" if target else action,
        args={"action": action, "target": target},
        expected_effect=f"{action}_complete"
    )
    
    return PlanResult(
        status="success",
        plan=Plan(actions=[planned_action], goal_achieved_by="a0", total_actions=1)
    )
```

### Step 5: Update router in plan()
**File**: `agents/goal_planner.py` (around line 204)

```python
elif goal.goal_type == "window_management":
    return self._plan_window_management(goal, world_state)
```

### Step 6: Add FEW_SHOT_EXAMPLES
**File**: `agents/goal_interpreter.py` (around line 245)

```python
User: "snap chrome to left and minimize notepad"
→ {
    "meta_type": "independent_multi",
    "goals": [
        {"goal_type": "window_management", "action": "snap_left", "target": "chrome", "scope": "root"},
        {"goal_type": "window_management", "action": "minimize", "target": "notepad", "scope": "root"}
    ],
    "reasoning": "Two independent window operations"
}
```

### Step 7: Update ToolResolver (if needed)
**File**: `core/tool_resolver.py`

Ensure ToolResolver can resolve the description format to actual tools.

### Step 8: Syntax check
```bash
python -m py_compile agents/goal_interpreter.py
python -m py_compile agents/goal_planner.py
```

---

## Current Goal Types

| goal_type | intent | Planner | Status |
|-----------|--------|---------|--------|
| browser_search | browser_control | ✅ | Active |
| browser_navigate | browser_control | ✅ | Active |
| app_launch | application_launch | ✅ | Active |
| app_action | application_control | ✅ | Active |
| file_operation | file_operation | ✅ | Active |
| system_query | system_query | ✅ | Active |
| system_control | system_control | ✅ | Active |
| media_control | system_control | ✅ | Active |

## Intentionally Deferred Goal Types

| goal_type | Reason for deferral |
|-----------|---------------------|
| window_management | No planner semantics, ambiguous targets |
| screen_capture | Treat as system_control instead |
| input_control | Timing semantics, race conditions |
| clipboard_operation | Transient state, security |
| memory_recall | LLM reasoning, not OS action |
