# GoalPlanner Contract (Phase 4)

> **Strict contract defining inputs, outputs, guarantees, and failure modes.**  
> Implementation is now **Table-Driven** via `PLANNER_RULES`.

---

## 1. Purpose

`GoalPlanner.plan()` transforms a **parametric goal** + **world state** into a minimal **executable plan**.

```
(ParametricGoal, WorldState) → (domain, verb) → PLANNER_RULES → PlanResult
```

 This is the **only** place where:
- Abstract goals become concrete actions (`navigate:url` → `browsers.navigate`)
- Parameter validation occurs (fail-fast)
- Description strings are formatted for ToolResolver

---

## 2. Input Contracts

### 2.1 Parametric Goal (Immutable)

```python
@dataclass(frozen=True)
class Goal:
    domain: str        # "browser", "file", "system", "audio"
    verb: str          # "navigate", "click", "create", "mute"
    params: Dict[str, Any]       # {"url": "...", "selector": "..."}
    object: Optional[str] = None # "title", "file.txt" (if applicable)
    
    # Metadata
    goal_id: str                 # "g0", "g1"
    scope: str                   # "root", "after:g0"
    resolved_path: Optional[str] # Injected by GoalOrchestrator
```

**Invariants:**
- `domain` and `verb` are **open strings** (validated against rules table)
- `params` must match the rule's schema
- Goal is **immutable** during planning

---

## 3. The `PLANNER_RULES` Table

Planning is no longer logic-based (`if type == ...`). It is **data-driven**:

```python
PLANNER_RULES = {
    ("browser", "navigate"): {
        "intent": "browser_control",
        "action_class": "actuate",
        "description_template": "navigate:{url}",
        "required_params": ["url"],
    },
    ("browser", "wait"): {
        "intent": "browser_control",
        "action_class": "actuate",
        "description_template": "wait:{selector}:{state}",
        "required_params": ["selector"],
        "default_params": {"state": "visible"},
    }
}
```

### 3.1 Validation Logic
For each goal, the planner:
1. Lookups rule `(domain, verb)`
2. Validates `required_params` are present
3. Validates `allowed_values` (if defined in rule)
4. Applies `default_params`
5. Formats `description` using the template

---

## 4. Output Contract

### 4.1 PlanResult
```python
@dataclass
class PlanResult:
    status: Literal["success", "rule_not_found", "validation_failed", "blocked"]
    plan: Optional[Plan]
    reason: Optional[str]
```

### 4.2 PlannedAction
```python
@dataclass
class PlannedAction:
    action_id: str          # "g0_navigate_1"
    intent: str             # "browser_control" (for ToolResolver)
    description: str        # "navigate:google.com" (for LLM context)
    args: Dict[str, Any]    # Validated params (AUTHORITATIVE)
    action_class: str       # "actuate" | "observe"
```

**Safety Invariant:**
`args` are the **single source of truth** for tool execution. The ToolResolver LLM **must not** hallucinate new parameters.

---

## 5. Failure Modes

| Mode | Condition | Response |
|------|-----------|----------|
| `rule_not_found` | `(domain, verb)` not in rules | Return failure (Interpreter hallucination) |
| `validation_failed` | Missing required param | Fail fast (don't guess) |
| `blocked` | Invalid param value (e.g. unknown direction) | Fail fast |

---

## 6. What GoalPlanner Does NOT Do

| Responsibility | Who Handles It |
|----------------|----------------|
| **Resolve Dependencies** | `GoalOrchestrator` (Scope Resolution) |
| **Pick Concrete Tool** | `ToolResolver` (Abstract Action → Tool) |
| **Execute Code** | `ToolExecutor` / Playwright |
| **Guess Selectors** | **NOBODY** (Must be in params) |
