# Goal Interpreter Contract + System Flow

> **The final contract. Includes GoalInterpreter and the complete architectural flow.**

---

## 1. Complete Architecture

```
User Query
    ↓
┌─────────────────────────────────┐
│  QueryClassifier (was Gate)     │  Cheap, fast, rule-based
│  Output: single | multi         │
└─────────────────────────────────┘
    ↓
    ├── single ───────────────────────────────────────┐
    │                                                 ↓
    │   ┌─────────────────────────────────────────────────────┐
    │   │  EXISTING SINGLE PATH (UNCHANGED)                   │
    │   │  IntentAgent → ToolResolver → ActionPipeline        │
    │   └─────────────────────────────────────────────────────┘
    │
    └── multi ────────────────────────────────────────┐
                                                      ↓
        ┌─────────────────────────────────────────────────────┐
        │  NEW GOAL PATH                                      │
        │  GoalInterpreter → MetaGoal                         │
        │       ↓                                             │
        │  GoalOrchestrator                                   │
        │       ↓                                             │
        │  GoalPlanner.plan() (per goal)                      │
        │       ↓                                             │
        │  PlanGraph → PlanExecutor (was MultiPipeline)       │
        └─────────────────────────────────────────────────────┘
```

**Critical Rule:**
- `single` → Existing flow, NO CHANGES
- `multi` → New goal-oriented flow

---

## 2. QueryClassifier (Demoted DecompositionGate)

### 2.1 New Contract

```python
class QueryClassifier:
    """Lightweight router. Single vs multi only.
    
    DOES:
    - Cheap classification (rule-based or small model)
    - Return single or multi
    
    DOES NOT:
    - Extract actions
    - Preserve ordering
    - Infer dependencies
    - Create subtasks
    """
    
    def classify(self, user_input: str) -> Literal["single", "multi"]:
        """Classify query structure.
        
        Returns:
            "single" - One semantic goal (even if multiple verbs)
            "multi" - Potentially multiple independent goals
        """
```

### 2.2 Classification Rules

| Query | Classification | Reason |
|-------|----------------|--------|
| "open chrome" | single | One action |
| "what time is it" | single | One query |
| "open youtube and search nvidia" | single | One goal (search on youtube) |
| "open spotify and play song" | single | One goal (play music) |
| "open chrome and open spotify" | multi | Two independent apps |
| "create folder X and file Y inside" | multi | Two operations |
| "shutdown computer" | single | One action |

### 2.3 Key Insight

```
"open youtube and search nvidia"
```

**Old Gate:** multi (two verbs)  
**New Classifier:** single (one semantic goal)

The classifier errs toward **single** unless clearly independent.

### 2.4 Invariant

> **QueryClassifier NEVER creates actions. Only planners create actions.**

---

## 3. GoalInterpreter Contract

### 3.1 Purpose

Transform user input into a structured `MetaGoal`.

**Only called when:** `QueryClassifier` returns `multi`

### 3.2 Function Signature

```python
def interpret(
    self,
    user_input: str,
    context: WorldState
) -> MetaGoal:
```

### 3.3 Output Contract: MetaGoal

```python
@dataclass(frozen=True)
class MetaGoal:
    meta_type: Literal["single", "independent_multi", "dependent_multi"]
    goals: Tuple[Goal, ...]
    dependencies: FrozenDict[int, Tuple[int, ...]]
```

### 3.4 Goal Types (Closed Set)

```python
class Goal:
    goal_type: Literal[
        "browser_search",      # Search on a platform
        "browser_navigate",    # Open URL
        "app_launch",          # Launch app
        "app_action",          # Do something in app
        "file_operation",      # File CRUD
        "system_query"         # Get information
    ]
```

**No dynamic goal types.** This set is exhaustive for Phase 1.

### 3.5 Examples

**Input:** `"open spotify and open chrome"`
```python
MetaGoal(
    meta_type="independent_multi",
    goals=(
        Goal(goal_type="app_launch", target="spotify"),
        Goal(goal_type="app_launch", target="chrome")
    ),
    dependencies={}
)
```

**Input:** `"create folder alex in D drive and create ppt inside it"`
```python
MetaGoal(
    meta_type="dependent_multi",
    goals=(
        Goal(goal_type="file_operation", action="mkdir", path="D:\\alex"),
        Goal(goal_type="file_operation", action="create", path="D:\\alex\\presentation.pptx")
    ),
    dependencies={1: (0,)}  # Goal 1 depends on Goal 0
)
```

### 3.6 Guarantees

| ID | Guarantee |
|----|-----------|
| I1 | Output is always a valid MetaGoal |
| I2 | Goal types are from closed set |
| I3 | Dependencies form a DAG (no cycles) |
| I4 | Context is read-only |

### 3.7 Failure Modes

| Mode | Handling |
|------|----------|
| Ambiguous | Ask for clarification (via orchestrator) |
| Unsupported goal type | Return with `status="unsupported"` |
| Parse failure | Fall through to legacy multi path |

---

## 4. What Changes vs What Stays

### ✅ Unchanged (Single Path)

| Component | Status |
|-----------|--------|
| IntentAgent | ✅ Same |
| ToolResolver | ✅ Same |
| ActionPipeline | ✅ Same |
| ToolExecutor | ✅ Same |

**Single queries work exactly as before. Zero regression risk.**

### ⚠️ Modified

| Component | Change |
|-----------|--------|
| DecompositionGate | Demoted to QueryClassifier |
| MultiPipeline | Becomes PlanExecutor |
| Orchestrator | Routes to new goal path for multi |

### ✳️ New

| Component | Purpose |
|-----------|---------|
| GoalInterpreter | User input → MetaGoal |
| GoalOrchestrator | MetaGoal → PlanGraph |
| GoalPlanner | Goal → Plan (per goal) |

---

## 5. Phase 1 Implementation Scope

### In Scope

- QueryClassifier (simplified Gate)
- GoalInterpreter (browser + file goals only)
- GoalOrchestrator (single + independent_multi)
- GoalPlanner (browser_search, browser_navigate)

### Out of Scope (Phase 2+)

- `dependent_multi` handling
- Simulated state effects
- `app_action` goals
- Clarification loops

---

## 6. Summary: Three Layers

```
┌─────────────────────────────────────────────────────┐
│  LAYER 1: ROUTING (cheap, fast)                     │
│  QueryClassifier: single | multi                    │
└─────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────┐
│  LAYER 2: REASONING (LLM, semantic)                 │
│  GoalInterpreter → GoalOrchestrator → GoalPlanner   │
│  (Only for multi path)                              │
└─────────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────┐
│  LAYER 3: EXECUTION (deterministic)                 │
│  PlanExecutor / ActionPipeline → ToolExecutor       │
│  (No reasoning, just execution)                     │
└─────────────────────────────────────────────────────┘
```

---

## 7. Contract Files Summary

| File | Purpose |
|------|---------|
| `GOAL_PLANNER_CONTRACT.md` | Goal → Plan |
| `GOAL_ORCHESTRATOR_CONTRACT.md` | MetaGoal → PlanGraph |
| `GOAL_INTERPRETER_CONTRACT.md` | This file: full flow + GoalInterpreter |

All contracts are now defined. Ready for implementation.
