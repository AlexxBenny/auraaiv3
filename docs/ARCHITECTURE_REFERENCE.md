# AURA Architecture Reference

> **Purpose**: Complete reference of AURA's architecture, intent categories, tool domains, and data flows.  
> **Use this**: Before making any changes, to understand what components are affected.  
> **Last Updated**: 2026-02-04

---

## Table of Contents

1. [Intent Categories](#intent-categories)
2. [Query Paths](#query-paths)
3. [Tool Domains](#tool-domains)
4. [Data Contracts](#data-contracts)
5. [Path Resolution Architecture](#path-resolution-architecture)
6. [Component Dependencies](#component-dependencies)
7. [Invariants](#invariants)

---

## Intent Categories

The `IntentAgent` classifies user input into one of 15 categories:

| Intent | Description | Tool Domain | Uses Paths? |
|--------|-------------|-------------|-------------|
| `information_query` | Pure LLM answer | None | ❌ |
| `application_launch` | Open/start apps | `system.apps.launch` | ❌ |
| `application_control` | Focus, close windows | `system.apps` | ❌ |
| `window_management` | Snap, minimize, maximize | `system.window`, `system.virtual_desktop` | ❌ |
| `system_query` | Time, battery, disk (read-only) | `system.state` | ❌ |
| `system_control` | Volume, brightness (write) | `system.audio`, `system.display`, `system.power` | ❌ |
| `screen_capture` | Screenshots | `system.display` | ⚠️ Save path |
| `screen_perception` | OCR, find UI elements | `system.display` | ❌ |
| `input_control` | Keyboard, mouse actions | `system.input` | ❌ |
| **`file_operation`** | Create, read, delete files | `files.*` | ✅ **Primary** |
| `browser_control` | Web navigation | `system.apps.launch` (Phase 0) | ❌ URLs |
| `office_operation` | Excel, Word, PowerPoint | `office` | ⚠️ File paths |
| `clipboard_operation` | Copy, paste | `system.clipboard` | ❌ |
| `memory_recall` | Previous queries/facts | `memory` | ❌ |
| `unknown` | Cannot determine | All (fallback) | ❌ |

### Files

- **Definition**: [`agents/intent_agent.py`](file:///d:/aura/AURA/agents/intent_agent.py)
- **Schema**: `IntentAgent.INTENT_SCHEMA`
- **Few-shot examples**: `IntentAgent.FEW_SHOT_EXAMPLES`

---

## Query Paths

### Classification

```
User Input → QueryClassifier.classify() → "single" | "multi"
```

**File**: [`agents/query_classifier.py`](file:///d:/aura/AURA/agents/query_classifier.py)

### Single Query Path

```
_process_single()
    ├─► IntentAgent.analyze_simple() → {intent, confidence, args}
    ├─► IntentRouter.route() → dispatches to pipeline
    └─► Pipeline handles execution
```

**When**: Simple, atomic commands (one action)  
**Examples**: "open chrome", "what time is it", "take a screenshot"

### Multi Query Path (Goal-Oriented)

```
_process_goal()
    ├─► GoalInterpreter.interpret()
    │       ├─► LLM extracts goals + dependencies
    │       ├─► LLM extracts goals + dependencies (scope-based)
    │       ├─► _derive_dependencies_from_scope()  ◄── Deterministic DAG
    │       └─► Returns MetaGoal
    │
    ├─► GoalOrchestrator.orchestrate()
    │       ├─► _resolve_goal_paths()  ◄── PathResolver
    │       └─► GoalPlanner.plan() for each goal
    │
    └─► ToolExecutor.execute_tool() for each action
```

**When**: Complex, multi-step commands  
**Examples**: "create folder and file inside", "open youtube and search nvidia"

### Files

| File | Class | Responsibility |
|------|-------|----------------|
| [`core/orchestrator.py`](file:///d:/aura/AURA/core/orchestrator.py) | `Orchestrator` | Main entry point |
| [`agents/query_classifier.py`](file:///d:/aura/AURA/agents/query_classifier.py) | `QueryClassifier` | single vs multi |
| [`agents/goal_interpreter.py`](file:///d:/aura/AURA/agents/goal_interpreter.py) | `GoalInterpreter` | Semantic goal extraction |
| [`agents/goal_orchestrator.py`](file:///d:/aura/AURA/agents/goal_orchestrator.py) | `GoalOrchestrator` | Multi-goal coordination |
| [`agents/goal_planner.py`](file:///d:/aura/AURA/agents/goal_planner.py) | `GoalPlanner` | Single goal → actions |
| [`core/intent_router.py`](file:///d:/aura/AURA/core/intent_router.py) | `IntentRouter` | Intent → pipeline |
| [`core/tool_resolver.py`](file:///d:/aura/AURA/core/tool_resolver.py) | `ToolResolver` | Intent → tool |

---

## Tool Domains

### Directory Structure

```
tools/
├── files/           # File operations (13 tools)
├── browsers/        # Browser automation (placeholder)
├── apps/            # App-specific tools
├── automation/      # Screen automation
├── knowledge/       # Knowledge queries
├── memory/          # Fact storage/retrieval
└── system/          # System tools
    ├── apps/        # Launch, focus, close (8 files)
    ├── audio/       # Volume control (7 files)
    ├── clipboard/   # Copy, paste (2 files)
    ├── desktop/     # Icons, night light (4 files)
    ├── display/     # Screenshot, brightness (3 files)
    ├── input/       # Keyboard, mouse (6 files)
    ├── network/     # Airplane mode (1 file)
    ├── power/       # Lock, shutdown (3 files)
    ├── state/       # Battery, disk, RAM (9 files)
    ├── virtual_desktop/  # Desktop switching (5 files)
    └── window/      # Snap, minimize (8 files)
```

### File Tools

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

### Safety Module

**File**: [`tools/files/safety.py`](file:///d:/aura/AURA/tools/files/safety.py)

- `normalize_path()` - String to Path (no .resolve())
- `validate_write_path()` - Check writable
- `validate_delete_path()` - Check deletable
- `is_protected_path()` - System directories
- `is_protected_extension()` - .exe, .dll, etc.

---

## Data Contracts

### Goal

```python
@dataclass(frozen=True)
class Goal:
    goal_type: Literal["browser_search", "browser_navigate", "app_launch", 
                       "app_action", "file_operation", "system_query"]
    scope: str = "root"          # "root", "inside:X", "drive:D"
    target: Optional[str]        # semantic path/URL/app name
    action: Optional[str]        # create, delete, move
    content: Optional[str]       # file content
    object_type: Optional[str]   # folder, file
    goal_id: Optional[str]       # g0, g1, g2
    base_anchor: Optional[str]   # WORKSPACE, DESKTOP, DRIVE_D (derived from scope)
    resolved_path: Optional[str] # AUTHORITY after resolution
```

### MetaGoal

```python
@dataclass(frozen=True)
class MetaGoal:
    meta_type: Literal["single", "independent_multi", "dependent_multi"]
    goals: Tuple[Goal, ...]
    dependencies: Tuple[Tuple[int, Tuple[int, ...]], ...]
```

### Plan

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

---

## Path Resolution Architecture

### Components

| Component | Responsibility |
|-----------|----------------|
| `PathResolver` | Single authority for path resolution |
| `SessionContext.cwd` | Session's working directory (captured once) |
| `Goal.resolved_path` | Authoritative absolute path |
| `Goal.base_anchor` | WORKSPACE, DESKTOP, DRIVE_D, etc. |

### Base Anchors

| Anchor | Resolves To |
|--------|-------------|
| `WORKSPACE` | Session's cwd |
| `DESKTOP` | `Path.home() / "Desktop"` |
| `DOCUMENTS` | `Path.home() / "Documents"` |
| `DOWNLOADS` | `Path.home() / "Downloads"` |
| `DRIVE_C` | `C:/` |
| `DRIVE_D` | `D:/` |

### Resolution Flow

```
User Input
    ↓
GoalInterpreter → Goal(target="space"), Goal(target="galaxy")
    ↓
GoalOrchestrator._resolve_goal_paths()
    ├─► PathResolver.resolve() for each goal
    └─► Sets goal.resolved_path
    ↓
GoalPlanner uses goal.resolved_path (AUTHORITY)
    ↓
Tool receives absolute path
```

### Scope-Based Dependency Architecture

**File**: [`agents/goal_interpreter.py`](file:///d:/aura/AURA/agents/goal_interpreter.py)  
**Method**: `_derive_dependencies_from_scope()`

Dependency generation is now **deterministic based on scope**:
- **"root"**: Independent goal
- **"inside:X"**: Depends on goal X (inherits anchor)
- **"drive:D"**: Explicit anchor (no dependency)
- **"after:X"**: Explicit ordering dependency

**Invariant**:
> **Scopes define dependencies; dependencies define inheritance; nothing else leaks.**

---

## Component Dependencies

### Import Graph (Key Modules)

```
core/orchestrator.py
    ├── agents/query_classifier.py
    ├── agents/intent_agent.py
    ├── agents/goal_interpreter.py
    ├── agents/goal_orchestrator.py
    │       ├── agents/goal_planner.py
    │       └── core/path_resolver.py
    ├── core/intent_router.py
    ├── core/tool_resolver.py
    └── execution/executor.py
            └── tools/registry.py
                    └── tools/**/*.py
```

### Modification Checklists

#### When Modifying File Operations

1. [ ] `agents/goal_interpreter.py` - Goal schema, container logic
2. [ ] `agents/goal_planner.py` - `_plan_file_operation()`
3. [ ] `agents/goal_orchestrator.py` - `_resolve_goal_paths()`
4. [ ] `core/path_resolver.py` - Resolution logic
5. [ ] `tools/files/*.py` - Tool implementations
6. [ ] `tools/files/safety.py` - Safety validation

#### When Modifying Intents

1. [ ] `agents/intent_agent.py` - Intent detection, few-shot
2. [ ] `core/orchestrator.py` - `_register_pipelines()`
3. [ ] `core/intent_router.py` - Routing
4. [ ] `core/tool_resolver.py` - Tool domains

#### When Modifying Goal Architecture

1. [ ] `agents/query_classifier.py` - Classification
2. [ ] `agents/goal_interpreter.py` - Extraction
3. [ ] `agents/goal_planner.py` - Planning
4. [ ] `agents/goal_orchestrator.py` - Coordination

---

## Invariants

### Path Resolution Invariants

1. **Single Authority**: Only `PathResolver` resolves paths
2. **No cwd Leaks**: Use `context.cwd`, never `Path.cwd()` at runtime
3. **Absolute After Resolution**: `goal.resolved_path` is always absolute
4. **Planner Trusts Resolver**: `GoalPlanner` never calls `.resolve()`

### Scope-Based Invariants

1. **Scope is Authority**: Containment is defined ONLY by `scope` field
2. **Anchors Don't Leak**: `drive:D` applies only to that goal (and children via inheritance)
3. **Root Resets**: `scope="root"` always implies WORKSPACE anchor
4. **Deterministic Derivation**: No LLM "repair" steps; dependencies are derived purely from scope annotations

### Safety Invariants

1. **Protected Paths**: System directories never written
2. **Protected Extensions**: .exe, .dll never deleted
3. **Input Domain Lock**: `system.input` never auto-resolved

---

## Configuration Files

| File | Purpose |
|------|---------|
| [`config/apps.yaml`](file:///d:/aura/AURA/config/apps.yaml) | App launch mappings |
| [`config/runtime_local.yaml`](file:///d:/aura/AURA/config/runtime_local.yaml) | Local mode config |

---

## Test Files

| File | Tests |
|------|-------|
| [`tests/test_path_resolver.py`](file:///d:/aura/AURA/tests/test_path_resolver.py) | PathResolver (16 tests) |
| [`tests/test_container_stack.py`](file:///d:/aura/AURA/tests/test_container_stack.py) | Container dependencies (7 tests) |

---

## Quick Reference: What Uses Paths?

| Category | Uses Filesystem Paths? |
|----------|------------------------|
| `file_operation` | ✅ Primary |
| `screen_capture` | ⚠️ Optional save path |
| `office_operation` | ⚠️ Open/save paths |
| All other intents | ❌ No |

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
│  IntentAgent        │              │  GoalInterpreter                │
│       ↓             │              │       ↓                         │
│  IntentRouter       │              │  GoalOrchestrator               │
│       ↓             │              │    ├─ PathResolver              │
│  Pipeline           │              │    └─ GoalPlanner               │
│       ↓             │              │       ↓                         │
│  ToolResolver       │              │  PlanGraph                      │
└─────────────────────┘              └─────────────────────────────────┘
           │                                        │
           ▼                                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        ToolExecutor.execute_tool()                  │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           RESULT                                    │
└─────────────────────────────────────────────────────────────────────┘
```
