# AURA Code Flow

## Main Entry Points

| Entry | File | Purpose |
|-------|------|---------|
| CLI | `main.py` | Terminal interface |
| GUI | `main_gui.py` | Web interface |

---

## Complete Flow (Current Architecture)

```
User Input: "create folder nvidia and file inside it"
    ↓
┌─────────────────────────────────────────────────────────┐
│ STEP 1: QueryClassifier.classify()                       │
│   - Syntactic heuristics: "inside it" = dependency       │
│   - Result: "multi"                                       │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│ STEP 2: GoalInterpreter.interpret()                      │
│   - Extract semantic goals                                │
│   - Result: MetaGoal(dependent_multi, 2 goals)           │
│     Goal 0: file_operation, folder, "nvidia"             │
│     Goal 1: file_operation, file, "nvidia/test.txt"      │
│     Dependencies: [(1, [0])]                              │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│ STEP 3: GoalOrchestrator.orchestrate()                   │
│   - For each goal: GoalPlanner.plan()                    │
│   - Combine: PlanGraph with dependency edges             │
└─────────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│ STEP 4: Execute PlanGraph                                │
│   - Respect dependency order                              │
│   - Execute: folder first → file second                  │
└─────────────────────────────────────────────────────────┘
    ↓
Result
```

---

## Single Path Flow (Simple Commands)

```
User Input: "mute the volume"
    ↓
QueryClassifier: "single"
    ↓
IntentAgent.classify() → system_control
    ↓
IntentRouter → _handle_action()
    ↓
ToolResolver.resolve() → system.audio.set_mute
    ↓
ToolExecutor.execute()
    ↓
Result
```

---

## Multi Path Flow (Independent Goals)

```
User Input: "open chrome and open spotify"
    ↓
QueryClassifier: "multi" (independent pattern)
    ↓
GoalInterpreter → independent_multi
    ↓
GoalOrchestrator → parallel execution
    ↓
Both apps launch
```

---

## Key Files

| File | Responsibility |
|------|----------------|
| `core/orchestrator.py` | Main routing logic |
| `agents/query_classifier.py` | Single vs multi detection |
| `agents/goal_interpreter.py` | Goal extraction |
| `agents/goal_planner.py` | Goal → Plan transformation |
| `agents/goal_orchestrator.py` | Multi-goal coordination |
| `core/tool_resolver.py` | Tool selection + safety |

---

## Safety Mechanisms

```
Stage 1 ToolResolver: Preferred domains
    ↓ (if no match)
Stage 2 ToolResolver: Domain-locked fallback
    ↓ (if still no match)
Hard fail (no hallucination)
```
