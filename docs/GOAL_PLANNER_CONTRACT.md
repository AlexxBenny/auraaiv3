# GoalPlanner Contract

> **Strict contract defining inputs, outputs, guarantees, and failure modes.**  
> No code until this contract is locked.

---

## 1. Purpose

`GoalPlanner.plan()` transforms a **semantic goal** + **world state** into an **executable plan**.

```
(Goal, WorldState, Capabilities) → Plan
```

This is the **only** place where:
- Action merging happens
- Optimal action count is determined
- Tool selection is finalized

---

## 2. Function Signature

```python
def plan(
    self,
    goal: Goal,
    world_state: WorldState,
    capabilities: List[ToolCapability]
) -> PlanResult:
```

---

## 3. Input Contracts

### 3.1 Goal (Immutable)

```python
@dataclass(frozen=True)
class Goal:
    goal_type: Literal[
        "browser_search",      # Search on a platform
        "browser_navigate",    # Open URL directly
        "app_launch",          # Launch application
        "file_operation",      # File CRUD
        "system_query",        # Get information
    ]
    platform: Optional[str] = None   # youtube, google, notepad
    query: Optional[str] = None      # nvidia, weather
    target: Optional[str] = None     # URL, file path, app name
    action: Optional[str] = None     # mkdir, create, delete
    object_type: Optional[str] = None  # folder, file
    goal_id: Optional[str] = None    # Unique ID for action linking
```

**Invariants:**
- `goal_type` is from a **closed set** (no dynamic types)
- Goal is **immutable** (frozen dataclass)
- `sub_goals` only populated for `independent_multi`

### 3.2 WorldState (Read-Only Snapshot)

```python
@dataclass(frozen=True)
class WorldState:
    browser_running: bool
    browser_last_url: Optional[str]
    active_window: Optional[str]
    running_apps: FrozenSet[str]
    recent_facts: Tuple[Fact, ...]
```

**Invariants:**
- WorldState is **frozen** (immutable during planning)
- Planner **NEVER** mutates WorldState
- Only Executor updates memory after execution

### 3.3 Capabilities (Tool Metadata)

```python
@dataclass(frozen=True)
class ToolCapability:
    name: str                    # system.apps.launch.shell
    can_achieve: Set[str]        # {"browser_open", "browser_search"}
    requires: Set[str]           # {"browser_running"} or empty
    effects: Set[str]            # {"browser_open", "url_loaded"}
```

**Invariants:**
- Capabilities are derived from tool registry
- No dynamic capability discovery during planning

---

## 4. Output Contract

### 4.1 PlanResult

```python
@dataclass
class PlanResult:
    status: Literal["success", "no_capability", "blocked"]
    plan: Optional[Plan]
    reason: Optional[str]  # If not success
```

### 4.2 Plan

```python
@dataclass
class Plan:
    actions: List[PlannedAction]
    goal_achieved_by: str  # action_id of final action
    total_actions: int
    
    def __post_init__(self):
        assert self.total_actions == len(self.actions)
        assert self.goal_achieved_by in [a.action_id for a in self.actions]
```

### 4.3 PlannedAction

```python
@dataclass
class PlannedAction:
    action_id: str                    # "a1", "a2"
    tool: str                         # "system.apps.launch.shell"
    args: Dict[str, Any]              # Tool arguments
    expected_effect: str              # "youtube_search_visible"
    depends_on: List[str] = field(default_factory=list)
```

---

## 5. Guarantees (MUST Hold)

| ID | Guarantee | Enforcement |
|----|-----------|-------------|
| G1 | **Merging happens here** | "open youtube and search nvidia" → 1 action |
| G2 | **Plan is minimal** | No redundant actions |
| G3 | **Plan is executable** | All tools exist in capabilities |
| G4 | **Dependencies are explicit** | No implicit ordering |
| G5 | **WorldState is unchanged** | Read-only, never mutated |
| G6 | **Deterministic for same inputs** | Same (goal, state, caps) → same plan |

---

## 6. Failure Modes

| Mode | Condition | Response |
|------|-----------|----------|
| `no_capability` | No tool can achieve goal | Return with reason |
| `blocked` | WorldState prevents goal | Return with blocker |
| `ambiguous` | Goal type unclear | **Reject** (GoalInterpreter's job) |
| `partial` | Can achieve part of goal | Return partial plan + unmet parts |

**Critical:** Planner does NOT:
- Ask for clarification (GoalInterpreter does)
- Execute anything (Executor does)
- Modify any state (immutable contract)

---

## 7. Supported Goal Types

GoalPlanner currently handles:

```python
SUPPORTED_GOAL_TYPES = {"browser_search", "browser_navigate", "app_launch", "file_operation"}
```

**Rule-based, not LLM-based:**

```python
def plan(self, goal: Goal, world_state: WorldState, capabilities: List) -> PlanResult:
    if goal.goal_type == "browser_search":
        return self._plan_browser_search(goal, world_state)
    elif goal.goal_type == "browser_navigate":
        return self._plan_browser_navigate(goal, world_state)
    elif goal.goal_type == "app_launch":
        return self._plan_app_launch(goal, world_state)
    elif goal.goal_type == "file_operation":
        return self._plan_file_operation(goal, world_state)
    else:
        return PlanResult(status="no_capability", reason="Not supported")
```

### File Operation Planning

```python
ACTION_ALIASES = {"mkdir": "create", "make": "create", "rm": "delete"}
FILE_OPERATION_TOOLS = {
    ("create", "folder"): "files.create_folder",
    ("create", "file"): "files.create_file",
    ("delete", "folder"): "files.delete_folder",
    ("delete", "file"): "files.delete_file",
}
```

### Browser Search Planning (Phase 1)

```python
def _plan_browser_search(self, goal: Goal, world_state: WorldState) -> PlanResult:
    # Merging logic: platform + query → single URL
    url = self._build_search_url(goal.platform, goal.query)
    
    return PlanResult(
        status="success",
        plan=Plan(
            actions=[
                PlannedAction(
                    action_id="a1",
                    tool="system.apps.launch.shell",
                    args={"app_name": "chrome", "url": url},
                    expected_effect="search_results_visible"
                )
            ],
            goal_achieved_by="a1",
            total_actions=1
        )
    )
```

---

## 8. What GoalPlanner Does NOT Do

| Responsibility | Who Handles It |
|----------------|----------------|
| Parse user input | GoalInterpreter |
| Classify intent | IntentAgent |
| Execute plan | Executor |
| Update memory | Executor + FactsMemory |
| Handle ambiguity | GoalInterpreter + Fallback |
| Manage context between actions | PlanExecutor |

---

## 9. Litmus Test

**Input:**
```python
goal = Goal(goal_type="browser_search", platform="youtube", query="nvidia")
world_state = WorldState(browser_running=False, ...)
```

**Expected Output:**
```python
PlanResult(
    status="success",
    plan=Plan(
        actions=[
            PlannedAction(
                action_id="a1",
                tool="system.apps.launch.shell",
                args={"app_name": "chrome", "url": "https://youtube.com/results?search_query=nvidia"},
                expected_effect="youtube_search_visible"
            )
        ],
        goal_achieved_by="a1",
        total_actions=1  # NOT 2
    )
)
```

If `total_actions > 1` for this case, **the planner is broken**.

---

## 10. Contract Violations (Hard Errors)

These are bugs, not edge cases:

| Violation | Severity |
|-----------|----------|
| Plan with 0 actions + status="success" | CRITICAL |
| Mutating WorldState | CRITICAL |
| Returning tool not in capabilities | CRITICAL |
| `goal_achieved_by` not in actions | CRITICAL |
| Circular dependencies in plan | CRITICAL |

---

## Summary

```
┌─────────────────────────────────────────────────────┐
│                   GoalPlanner.plan()                │
├─────────────────────────────────────────────────────┤
│  INPUTS (all immutable):                            │
│    - Goal (frozen, typed)                           │
│    - WorldState (frozen, read-only)                 │
│    - Capabilities (tool metadata)                   │
├─────────────────────────────────────────────────────┤
│  OUTPUTS:                                           │
│    - PlanResult with status                         │
│    - Plan (actions, dependencies, effects)          │
├─────────────────────────────────────────────────────┤
│  GUARANTEES:                                        │
│    - Merging happens here                           │
│    - Minimal action count                           │
│    - Deterministic                                  │
│    - No side effects                                │
├─────────────────────────────────────────────────────┤
│  DOES NOT:                                          │
│    - Execute anything                               │
│    - Mutate state                                   │
│    - Handle ambiguity                               │
└─────────────────────────────────────────────────────┘
```
