# AURA Execution Flow Reference

> **Purpose**: Complete reference of all modules a user query passes through.  
> **Use this when**: Making updates to ensure all affected paths are modified.

---

## Quick Reference: Query Classification

```
User Input
    ↓
QueryClassifier.classify()
    ↓
┌───────────────────┬────────────────────┐
│    "single"       │      "multi"       │
│                   │                    │
│ _process_single() │  _process_goal()   │
└───────────────────┴────────────────────┘
```

---

## Entry Point

**File**: [`core/orchestrator.py`](file:///d:/aura/AURA/core/orchestrator.py)  
**Class**: `Orchestrator`  
**Method**: `process(user_input, progress)`

```
Orchestrator.process()
    ├─► SessionContext.start_task()
    ├─► _get_context() → AmbientMemory state for LLM reasoning
    ├─► QueryClassifier.classify() (syntactic, NO context)
    │       └─► Returns "single" or "multi"
    │
    ├─► _get_execution_mode()  ← NEW: Conservative gate
    │       └─► Returns "direct" or "orchestrated"
    │
    ├─► IF "direct": _process_single(context) → IntentAgent WITH context
    └─► IF "orchestrated": ExecutionCoordinator.execute()
            └─► LLM decides structure, dispatches to pipelines
```

---

## Execution Modes (NEW)

**Gate**: `_get_execution_mode()` - Conservative, dumb routing for cost control.

| Mode | Meaning | When |
|------|---------|------|
| `direct` | Single pipeline, LLM exits | Clearly atomic, no conjunctions |
| `orchestrated` | Coordinator takes over | Everything else |

> [!IMPORTANT]
> The gate is NOT the intelligence. It only answers:
> "Is this so trivial that waking the conductor would be wasteful?"
> When in doubt, it returns "orchestrated" and lets the LLM decide.

---

## Path 1: Single Query (`_process_single`)

**When**: Simple, atomic commands (one action)  
**Examples**: "open chrome", "what time is it", "take a screenshot"

```
_process_single(context)
    │
    ├─► IntentAgent.classify(user_input, context)  ◄── LLM-CENTRIC
    │       ├─► ContextSnapshot.build(context) injected into prompt
    │       └─► Returns {decision, intent, confidence, question?}
    │
    ├─► IF decision == "ask": RETURN {type: "clarification", question}
    │       └─► TERMINAL: No tool resolution or execution  ◄── CRITICAL
    │
    ├─► IntentRouter.route(intent_result)
    │       └─► Passes intent to handler via kwargs (intent=...)
    │
    └─► Pipeline handles execution (receives intent, may not re-classify)
```

### Intent Categories & Pipelines

| Intent | Pipeline | Handler |
|--------|----------|---------|
| `information_query` | info_pipeline | `_handle_info()` |
| `application_launch` | action_pipeline | `_handle_action()` |
| `application_control` | action_pipeline | `_handle_action()` |
| `window_management` | action_pipeline | `_handle_action()` |
| `system_query` | action_pipeline | `_handle_action()` |
| `screen_capture` | action_pipeline | `_handle_action()` |
| `screen_perception` | action_pipeline | `_handle_action()` |
| `input_control` | action_pipeline | `_handle_action()` |
| `file_operation` | action_pipeline | `_handle_action()` |
| `browser_control` | action_pipeline | `_handle_action()` |
| `office_operation` | action_pipeline | `_handle_action()` |
| `unknown` / low confidence | fallback_pipeline | `_handle_fallback()` |

### Action Pipeline Detail

```
_handle_action(intent=...)  ◄── Intent passed from router (NEVER re-classified)
    │
    ├─► ToolResolver.resolve(intent, args)
    │       ├─► Stage 1: Direct registry lookup
    │       ├─► Stage 2: Domain-locked similarity (whitelist)
    │       └─► Returns {tool, args, confidence}
    │
    ├─► ToolExecutor.execute_tool(tool_name, args)
    │       ├─► ToolRegistry.get(tool_name)
    │       └─► tool.execute(args)
    │
    └─► Return result
```

> [!IMPORTANT]
> **Invariant**: Intent is classified ONCE per request (in `_process_single`) and passed immutably.
> Handlers may NOT re-classify intent. This prevents silent overrides of LLM decisions.

---

## Path 2: Multi Query (`_process_goal`)

**When**: Complex, multi-step commands  
**Examples**: "create folder and file inside it", "open youtube and search nvidia"

```
_process_goal()
    │
    ├─► GoalInterpreter.interpret()
    │       ├─► LLM extracts goals + dependencies
    │       ├─► _fix_container_dependencies()  ◄── Container Stack Fix
    │       │       └─► Corrects "inside it" anaphora binding
    │       └─► Returns MetaGoal {meta_type, goals[], dependencies[]}
    │
    ├─► GoalOrchestrator.orchestrate()
    │       │
    │       ├─► _resolve_goal_paths()  ◄── PathResolver (NEW)
    │       │       └─► Resolves all file_operation paths
    │       │
    │       ├─► FOR each goal:
    │       │       └─► GoalPlanner.plan(goal)
    │       │               └─► Returns Plan {actions[]}
    │       │
    │       └─► Returns OrchestrationResult {plan_graph}
    │
    ├─► FOR each action in plan_graph:
    │       └─► ToolExecutor.execute_tool()
    │
    └─► Return aggregated results
```

### MetaGoal Types

| Type | Description | Dependencies |
|------|-------------|--------------|
| `single` | Just one goal | None |
| `independent_multi` | Multiple unrelated goals | None |
| `dependent_multi` | Goals depend on each other | Yes (DAG) |

### GoalPlanner Supported Types

| Goal Type | Method | Tools |
|-----------|--------|-------|
| `browser_search` | `_plan_browser_search()` | `browsers.chrome.navigate` |
| `browser_navigate` | `_plan_browser_navigate()` | `browsers.chrome.navigate` |
| `app_launch` | `_plan_app_launch()` | `system.apps.launch` |
| `file_operation` | `_plan_file_operation()` | `files.create_folder`, `files.create_file`, etc. |

---

## Component Reference

### Agents (`agents/`)

| File | Class | Responsibility |
|------|-------|----------------|
| [`query_classifier.py`](file:///d:/aura/AURA/agents/query_classifier.py) | `QueryClassifier` | Classify "single" vs "multi" |
| [`intent_agent.py`](file:///d:/aura/AURA/agents/intent_agent.py) | `IntentAgent` | Context-aware intent + act vs ask |
| [`goal_interpreter.py`](file:///d:/aura/AURA/agents/goal_interpreter.py) | `GoalInterpreter` | Extract semantic goals from multi queries |
| [`goal_planner.py`](file:///d:/aura/AURA/agents/goal_planner.py) | `GoalPlanner` | Plan single goal → executable actions |
| [`goal_orchestrator.py`](file:///d:/aura/AURA/agents/goal_orchestrator.py) | `GoalOrchestrator` | Combine multiple goal plans |
| [`task_decomposition.py`](file:///d:/aura/AURA/agents/task_decomposition.py) | `TaskDecomposer` | Legacy decomposition (fallback) |
| [`planner_agent.py`](file:///d:/aura/AURA/agents/planner_agent.py) | `PlannerAgent` | Legacy planner (fallback) |

### Core (`core/`)

| File | Class | Responsibility |
|------|-------|----------------|
| [`orchestrator.py`](file:///d:/aura/AURA/core/orchestrator.py) | `Orchestrator` | Main entry point, routing |
| [`execution_coordinator.py`](file:///d:/aura/AURA/core/execution_coordinator.py) | `ExecutionCoordinator` | LLM-driven orchestration over pipelines |
| [`context_snapshot.py`](file:///d:/aura/AURA/core/context_snapshot.py) | `ContextSnapshot` | Format ambient state for LLM |
| [`intent_router.py`](file:///d:/aura/AURA/core/intent_router.py) | `IntentRouter` | Route intents to pipelines |
| [`tool_resolver.py`](file:///d:/aura/AURA/core/tool_resolver.py) | `ToolResolver` | Map intents to tools |
| [`path_resolver.py`](file:///d:/aura/AURA/core/path_resolver.py) | `PathResolver` | Centralized path resolution |
| [`context.py`](file:///d:/aura/AURA/core/context.py) | `SessionContext` | Session state, cwd |
| [`runtime.py`](file:///d:/aura/AURA/core/runtime.py) | - | Runtime configuration |

### Pipelines (`core/pipelines/`)

| File | Responsibility |
|------|----------------|
| [`action_pipeline.py`](file:///d:/aura/AURA/core/pipelines/action_pipeline.py) | Execute tool-based actions |
| [`info_pipeline.py`](file:///d:/aura/AURA/core/pipelines/info_pipeline.py) | LLM-based information queries |
| [`fallback_pipeline.py`](file:///d:/aura/AURA/core/pipelines/fallback_pipeline.py) | Handle unknown intents |
| [`multi_pipeline.py`](file:///d:/aura/AURA/core/pipelines/multi_pipeline.py) | Legacy multi-action |

### Execution (`execution/`)

| File | Class | Responsibility |
|------|-------|----------------|
| [`executor.py`](file:///d:/aura/AURA/execution/executor.py) | `ToolExecutor` | Execute tools, aggregate results |

### Tools (`tools/`)

| Domain | Directory | Examples |
|--------|-----------|----------|
| Files | `tools/files/` | `create_folder`, `create_file`, `delete_file`, `move`, `copy` |
| Apps | `tools/apps/` | App-specific tools |
| Browsers | `tools/browsers/` | `chrome.navigate`, `chrome.search` |
| System | `tools/system/` | Input, audio, clipboard, display, power, network |
| Memory | `tools/memory/` | Fact storage/retrieval |
| Automation | `tools/automation/` | Screen automation |
| Knowledge | `tools/knowledge/` | Knowledge queries |

---

## Data Contracts

### Goal (from GoalInterpreter)

```python
@dataclass(frozen=True)
class Goal:
    goal_type: Literal["browser_search", "browser_navigate", "app_launch", 
                       "app_action", "file_operation", "system_query"]
    platform: Optional[str]      # youtube, google
    query: Optional[str]         # search query
    target: Optional[str]        # semantic path/URL/app name
    action: Optional[str]        # create, delete, move
    content: Optional[str]       # file content
    object_type: Optional[str]   # folder, file
    goal_id: Optional[str]       # g0, g1, g2
    base_anchor: Optional[str]   # WORKSPACE, DESKTOP, DRIVE_D
    resolved_path: Optional[str] # AUTHORITY after resolution
```

### MetaGoal (from GoalInterpreter)

```python
@dataclass(frozen=True)
class MetaGoal:
    meta_type: Literal["single", "independent_multi", "dependent_multi"]
    goals: Tuple[Goal, ...]
    dependencies: Tuple[Tuple[int, Tuple[int, ...]], ...]
```

### Plan (from GoalPlanner)

```python
@dataclass
class Plan:
    actions: List[PlannedAction]
    goal_achieved_by: str
    total_actions: int

@dataclass
class PlannedAction:
    action_id: str       # g0_a1
    tool: str            # files.create_folder
    args: Dict[str, Any] # {path: "...", parents: True}
    expected_effect: str
```

### PlanGraph (from GoalOrchestrator)

```python
@dataclass
class PlanGraph:
    actions: List[PlannedAction]
    edges: List[Tuple[str, str]]  # (a1, a2) = a2 depends on a1
    total_actions: int
```

---

## Container Stack & Scope Switching

**File:** [`agents/goal_interpreter.py`](file:///d:/aura/AURA/agents/goal_interpreter.py)  
**Methods:** `_fix_container_dependencies()`, `_detect_explicit_anchor()`

### Two Concepts

| Concept | What It Controls | Trigger |
|---------|------------------|---------|
| **Container Stack** | "inside it" nesting | Folder creation |
| **Scope Switching** | Location changes | Explicit anchor in user text |

### Container Stack

Fixes "inside it" binding to first container instead of most recent.

```
g0: mkdir space        → stack = [0]
g1: mkdir galaxy       → stack = [0, 1], parent = 0 (correct)
g2: create milkyway    → stack = [0, 1], parent = 1 (FIXED from 0)
```

### Scope Switching

Explicit location (linguistically grounded) starts a new scope.

```
User: "create space in root folder, galaxy in d drive, milkyway inside it"

Scope 0: WORKSPACE      Scope 1: DRIVE_D
   └─ space                └─ galaxy
                               └─ milkyway
```

### Explicit Anchor Detection

**CRITICAL:** Only user text, NOT LLM-generated paths.

```python
# Detected from user_input.lower()
"d drive" / "drive d" → DRIVE_D
"desktop"            → DESKTOP
"documents"          → DOCUMENTS
"downloads"          → DOWNLOADS
"root folder"        → WORKSPACE
```

### Key Invariant

> **Only language can change scope, not paths.**
> 
> LLM-generated absolute paths are NOT treated as scope switches.

### Path Resolution Invariant

> **Targets describe identity. Dependencies describe structure.**
> **Only PathResolver combines them.**

| Invariant | Meaning |
|-----------|---------|
| **Raw Until Resolution** | Targets are names only (no parent paths) until PathResolver |
| **Single Combiner** | PathResolver is the ONLY place that does `parent / child` |
| **No Double-Application** | Container logic NEVER modifies target, only dependencies |

---

## Path Resolution Flow

**SINGLE AUTHORITY**: [`core/path_resolver.py`](file:///d:/aura/AURA/core/path_resolver.py)

```
User: "create folder space and file inside it"
    │
    ▼
GoalInterpreter → Goal(target="space"), Goal(target="file.txt")
    │
    ▼
GoalOrchestrator._resolve_goal_paths()
    │
    ├─► Goal 0: PathResolver.resolve("space", base=WORKSPACE)
    │       → D:\aura\AURA\space
    │
    └─► Goal 1: PathResolver.resolve("file.txt", parent=above)
            → D:\aura\AURA\space\file.txt
    │
    ▼
GoalPlanner uses goal.resolved_path (AUTHORITY)
    │
    ▼
Tool receives absolute path
```

### Base Anchors

| Anchor | Resolves To |
|--------|-------------|
| `WORKSPACE` | Session's cwd (captured once) |
| `DESKTOP` | `Path.home() / "Desktop"` |
| `DOCUMENTS` | `Path.home() / "Documents"` |
| `DOWNLOADS` | `Path.home() / "Downloads"` |
| `DRIVE_C` | `C:/` |
| `DRIVE_D` | `D:/` |

---

## File Operation Tools

| Tool | File | Args |
|------|------|------|
| `files.create_folder` | [`create_folder.py`](file:///d:/aura/AURA/tools/files/create_folder.py) | `path`, `parents`, `exist_ok` |
| `files.create_file` | [`create_file.py`](file:///d:/aura/AURA/tools/files/create_file.py) | `path`, `content`, `create_parents` |
| `files.delete_file` | [`delete_file.py`](file:///d:/aura/AURA/tools/files/delete_file.py) | `path` |
| `files.delete_folder` | [`delete_folder.py`](file:///d:/aura/AURA/tools/files/delete_folder.py) | `path`, `recursive` |
| `files.move` | [`move.py`](file:///d:/aura/AURA/tools/files/move.py) | `source`, `destination`, `overwrite` |
| `files.copy` | [`copy.py`](file:///d:/aura/AURA/tools/files/copy.py) | `source`, `destination` |
| `files.rename` | [`rename.py`](file:///d:/aura/AURA/tools/files/rename.py) | `path`, `new_name` |
| `files.read_file` | [`read_file.py`](file:///d:/aura/AURA/tools/files/read_file.py) | `path` |
| `files.write_file` | [`write_file.py`](file:///d:/aura/AURA/tools/files/write_file.py) | `path`, `content` |
| `files.append_file` | [`append_file.py`](file:///d:/aura/AURA/tools/files/append_file.py) | `path`, `content` |
| `files.list_directory` | [`list_directory.py`](file:///d:/aura/AURA/tools/files/list_directory.py) | `path` |
| `files.get_info` | [`get_info.py`](file:///d:/aura/AURA/tools/files/get_info.py) | `path` |

### Safety Checks

**File**: [`tools/files/safety.py`](file:///d:/aura/AURA/tools/files/safety.py)

- `normalize_path()` - Convert string to Path (no .resolve())
- `validate_write_path()` - Check if path is writable
- `validate_delete_path()` - Check if path can be deleted
- `is_protected_path()` - Check against PROTECTED_DIRECTORIES
- `is_protected_extension()` - Check against PROTECTED_EXTENSIONS

---

## Checklist: Updating File Operations

When modifying file operation behavior, check:

1. [ ] `agents/goal_interpreter.py` - Goal extraction schema
2. [ ] `agents/goal_planner.py` - `_plan_file_operation()` 
3. [ ] `agents/goal_orchestrator.py` - `_resolve_goal_paths()`
4. [ ] `core/path_resolver.py` - Path resolution logic
5. [ ] `tools/files/*.py` - Individual tool implementations
6. [ ] `tools/files/safety.py` - Safety validation
7. [ ] `execution/executor.py` - Tool execution
8. [ ] `core/tool_resolver.py` - Tool mapping

---

## Checklist: Updating Intent Handling

When adding/modifying intents:

1. [ ] `agents/intent_agent.py` - Intent detection
2. [ ] `core/orchestrator.py` - `_register_pipelines()`
3. [ ] `core/intent_router.py` - Intent routing
4. [ ] `core/tool_resolver.py` - Tool resolution
5. [ ] Corresponding pipeline in `core/pipelines/`

---

## Checklist: Updating Goal Architecture

When modifying goal handling:

1. [ ] `agents/query_classifier.py` - Query classification
2. [ ] `agents/goal_interpreter.py` - Goal extraction
3. [ ] `agents/goal_planner.py` - Goal planning
4. [ ] `agents/goal_orchestrator.py` - Multi-goal coordination
5. [ ] `core/path_resolver.py` - Path resolution (file ops)
6. [ ] `core/orchestrator.py` - `_process_goal()`

---

## Fallback Paths

```
IF GoalPlanner returns "no_capability"
    └─► Fall back to _process_multi_legacy()
            └─► TaskDecomposer → PlannerAgent → ToolExecutor

IF ToolResolver returns no match
    └─► _handle_fallback()
            └─► LLM generates conversational response
```

---

## Visual Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INPUT                                  │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    QueryClassifier.classify()                       │
│                   "single" │ "multi"                                │
└─────────────────────────────────────────────────────────────────────┘
           │                                    │
           ▼                                    ▼
┌─────────────────────┐              ┌─────────────────────────────────┐
│  _process_single()  │              │      _process_goal()            │
│                     │              │                                 │
│  ┌───────────────┐  │              │  ┌───────────────────────────┐  │
│  │  IntentAgent  │  │              │  │    GoalInterpreter        │  │
│  └───────────────┘  │              │  └───────────────────────────┘  │
│         │           │              │              │                  │
│         ▼           │              │              ▼                  │
│  ┌───────────────┐  │              │  ┌───────────────────────────┐  │
│  │ IntentRouter  │  │              │  │    GoalOrchestrator       │  │
│  └───────────────┘  │              │  │    ├─ PathResolver        │  │
│         │           │              │  │    └─ GoalPlanner         │  │
│         ▼           │              │  └───────────────────────────┘  │
│  ┌───────────────┐  │              │              │                  │
│  │  Pipeline     │  │              │              ▼                  │
│  └───────────────┘  │              │  ┌───────────────────────────┐  │
│         │           │              │  │     PlanGraph             │  │
│         ▼           │              │  └───────────────────────────┘  │
│  ┌───────────────┐  │              │              │                  │
│  │ ToolResolver  │  │              │              ▼                  │
│  └───────────────┘  │              │  ┌───────────────────────────┐  │
└─────────────────────┘              │  │     FOR each action       │  │
           │                         │  └───────────────────────────┘  │
           │                         └─────────────────────────────────┘
           │                                        │
           ▼                                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        ToolExecutor.execute_tool()                  │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Tool.execute(args)                             │
│                                                                     │
│   files.*  │  browsers.*  │  system.*  │  apps.*  │  memory.*       │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           RESULT                                    │
└─────────────────────────────────────────────────────────────────────┘
```
