# AURA Codebase Inventory

> **Complete inventory of all existing components for goal-oriented evolution planning.**

## Directory Structure Overview

```
AURA/
├── agents/              # LLM agents (intent, decomposition, planner, TDA)
├── config/              # YAML configurations
├── core/                # Orchestration, pipelines, response, vision, input
├── execution/           # ToolExecutor
├── gui/                 # Web GUI adapter and progress streaming
├── memory/              # AmbientMemory, FactsMemory
├── models/              # LLM provider abstraction (Ollama, Gemini, OpenRouter)
├── tools/               # 50+ deterministic tools across 12 domains
```

---

## 1. Agents (`agents/`)

| Agent | File | Purpose | Used By |
|-------|------|---------|---------|
| **IntentAgent** | `intent_agent.py` | Classifies user input into 10 intent categories | Orchestrator, MultiPipeline |
| **DecompositionGate** | `decomposition_gate.py` | Detects single vs multi-action requests | Orchestrator |
| **TaskDecompositionAgent** | `task_decomposition.py` | Decomposes into natural language subtasks | MultiPipeline (fallback) |
| **PlannerAgent** | `planner_agent.py` | **Fallback reasoning** for low-confidence | Orchestrator (fallback only) |

### Agent Capabilities

**IntentAgent:**
- 10 intent categories: `application_launch`, `application_control`, `window_management`, `system_query`, `screen_capture`, `screen_perception`, `input_control`, `system_control`, `clipboard_operation`, `memory_recall`, `file_operation`, `browser_control`, `office_operation`, `information_query`
- Few-shot examples for reliable classification
- Confidence scoring (0.0-1.0)

**DecompositionGate:**
- Single/multi classification
- Action extraction with `depends_on_previous` flag
- Syntactic verb counting (NOT semantic goal understanding)

**PlannerAgent:**
- Reasoning for ambiguous requests
- NOT goal-oriented planning
- Only called when confidence < 0.75

---

## 2. Core (`core/`)

### 2.1 Orchestrator (`orchestrator.py`)

Main entry point. Flow:
1. `DecompositionGate.classify_with_actions()` → single/multi
2. Single: `IntentAgent.classify()` → `IntentRouter.route()` → pipeline
3. Multi: Per-action intent + resolution → `MultiPipeline`

### 2.2 Pipelines (`core/pipelines/`)

| Pipeline | File | Purpose |
|----------|------|---------|
| **ActionPipeline** | `action_pipeline.py` | Single action: resolve → execute |
| **MultiPipeline** | `multi_pipeline.py` | Multi-action: upfront resolution → dependency execution |
| **InfoPipeline** | `info_pipeline.py` | Pure LLM response (no tools) |
| **FallbackPipeline** | `fallback_pipeline.py` | Low-confidence reasoning |

### 2.3 Tool Resolution (`tool_resolver.py`)

Two-stage resolution:
1. Stage 1: Intent-preferred domains
2. Stage 2: Global fallback

Domain mappings (`INTENT_TOOL_DOMAINS`):
```python
"application_launch": ["system.apps"],
"application_control": ["system.apps", "system.window"],
"window_management": ["system.window", "system.virtual_desktop"],
"system_query": ["system.state"],
"screen_capture": ["system.display"],
"screen_perception": ["system.display"],
"input_control": ["system.input"],
"system_control": ["system.audio", "system.display", "system.power"],
"clipboard_operation": ["system.clipboard"],
"memory_recall": ["memory"],
"file_operation": ["files"],
"browser_control": ["system.apps.launch"],
"office_operation": ["office"],
```

### 2.4 Response Pipeline (`core/response/`)

| Component | Purpose |
|-----------|---------|
| `fact_extractor.py` | Extracts memory-safe facts from tool results |
| `base_response.py` | Default response templates per tool |
| `llm_polisher.py` | Optional LLM polish for natural language |
| `pipeline.py` | `generate_response()` entry point |

### 2.5 Vision (`core/vision/`)

- `ocr_engine.py` - OCR abstraction
- `backends/` - Tesseract, Windows OCR

### 2.6 Input (`core/input/`)

- `backend.py` - Input abstraction
- `backends/` - PyAutoGUI, Windows API

---

## 3. Execution (`execution/`)

### ToolExecutor (`executor.py`)

**Responsibilities:**
- Execute tool with precondition enforcement
- Safety: pressed_keys tracking, cooldown support
- Key release on failure

**Preconditions (enforced by executor, NOT LLM):**
- `requires_focus` - Window must be focused
- `requires_active_app` - Specific app must be focused
- `requires_unlocked_screen` - Screen must be unlocked
- `is_destructive` - Requires confirmation

---

## 4. Memory (`memory/`)

### AmbientMemory (`ambient.py`)

**Purpose:** Background system state tracker (every 5s)

**Tracks:**
- Active window (handle, title, process, bounds)
- Running apps list
- Recent activity (last N snapshots)
- History deque (max 100 snapshots)

**Interface:**
- `get_context()` → Current state for LLM
- `get_recent_activity(minutes)` → Recent activity

### FactsMemory (`facts.py`)

**Purpose:** Episodic memory for tool-derived facts

**Features:**
- Stores ExtractedFacts with provenance (tool, query, session_id)
- Query by keys, tool, recency
- Daily rotation, 7-day retention
- Persisted to `.aura/facts/`

**Interface:**
- `store(extracted, query, session_id)`
- `query_by_keys(keys, tool, max_age, limit)`
- `query_by_tool(tool_name, max_age, limit)`
- `query_recent(minutes, limit)`

---

## 5. Models (`models/`)

### ModelManager (`model_manager.py`)

Provides LLM abstraction:
- `get_tool_model()` - For tool resolution
- `get_planner_model()` - For intent/planning
- `get_assistant_model()` - For responses

### Providers (`models/providers/`)

| Provider | Purpose |
|----------|---------|
| `ollama.py` | Local Ollama models |
| `gemini.py` | Google Gemini API |
| `openrouter.py` | OpenRouter API |
| `hybrid.py` | Hybrid (Ollama + cloud fallback) |

---

## 6. Tools (`tools/`)

### 6.1 Tool Base (`tools/base.py`)

All tools inherit from `Tool` ABC:
- `name`, `description`, `schema` (required)
- `risk_level`, `side_effects`, `stabilization_time_ms`
- `reversible`, `requires_visual_confirmation`
- **Preconditions:** `requires_focus`, `requires_active_app`, `requires_unlocked_screen`, `is_destructive`

### 6.2 Tool Registry (`tools/registry.py`)

Singleton registry for all tools:
- `get_registry().has(name)` - Check tool exists
- `get_registry().get(name)` - Get tool instance
- `get_registry().get_tools_for_llm()` - Get all tools for LLM

### 6.3 Tool Domains

#### `tools/system/apps/` (Application Management)

| Tool | Purpose |
|------|---------|
| `launch_shell.py` | Launch apps with URL/search support |
| `launch_path.py` | Launch by executable path |
| `focus.py` | Focus running application |
| `request_close.py` | Request app close |
| `app_resolver.py` | Multi-strategy app resolution |
| `app_handle.py` | Handle tracking registry |

#### `tools/system/window/` (Window Management)

| Tool | Purpose |
|------|---------|
| `maximize.py` | Maximize window |
| `minimize.py` | Minimize window |
| `minimize_all.py` | Win+D |
| `close.py` | Close window |
| `snap_left.py` / `snap_right.py` | Snap windows |
| `switch.py` | Alt+Tab to window |
| `task_view.py` | Open task view |

#### `tools/system/input/keyboard/` (Keyboard)

| Tool | Purpose |
|------|---------|
| `type.py` | Type text |
| `press.py` | Press key/hotkey |

#### `tools/system/input/mouse/` (Mouse)

| Tool | Purpose |
|------|---------|
| `click.py` | Click at coordinates |
| `move.py` | Move cursor |

#### `tools/system/audio/` (Audio)

| Tool | Purpose |
|------|---------|
| `set_volume.py` | Set volume level |
| `get_volume.py` | Get current volume |
| `mute.py` / `unmute.py` | Toggle mute |
| `media_play_pause.py` | Play/pause media |
| `media_next.py` / `media_previous.py` | Skip tracks |

#### `tools/system/display/` (Display)

| Tool | Purpose |
|------|---------|
| `take_screenshot.py` | Capture screen |
| `set_brightness.py` | Adjust brightness |
| `find_text.py` | OCR text search |

#### `tools/system/state/` (System Queries)

| Tool | Purpose |
|------|---------|
| `get_time.py` | Current time |
| `get_date.py` | Current date |
| `get_datetime.py` | Date and time |
| `get_battery.py` | Battery status |
| `get_disk_usage.py` | Disk space |
| `get_memory_usage.py` | RAM usage |
| `get_network_status.py` | Network info |
| `get_active_window.py` | Active window info |
| `get_execution_context.py` | Full context |

#### `tools/system/power/` (Power)

| Tool | Purpose |
|------|---------|
| `shutdown.py` | Shutdown/restart |
| `sleep.py` | Sleep |
| `lock.py` | Lock screen |

#### `tools/system/clipboard/` (Clipboard)

| Tool | Purpose |
|------|---------|
| `read.py` | Read clipboard |
| `write.py` | Write to clipboard |

#### `tools/system/desktop/` (Desktop)

| Tool | Purpose |
|------|---------|
| `toggle_icons.py` | Show/hide icons |
| `empty_recycle_bin.py` | Empty recycle bin |
| `restart_explorer.py` | Restart explorer |
| `set_night_light.py` | Night light toggle |

#### `tools/system/virtual_desktop/` (Virtual Desktops)

| Tool | Purpose |
|------|---------|
| `get_current.py` | Get current desktop |
| `switch_desktop.py` | Switch desktop |
| `move_window_to_desktop.py` | Move window |

#### `tools/files/` (File Operations)

| Tool | Purpose |
|------|---------|
| `create_file.py` | Create file with content |
| `create_folder.py` | Create directory |
| `write_file.py` | Write to file |
| `append_file.py` | Append to file |
| `read_file.py` | Read file content |
| `delete_file.py` | Delete file |
| `delete_folder.py` | Delete directory |
| `copy.py` | Copy file/folder |
| `move.py` | Move file/folder |
| `rename.py` | Rename file/folder |
| `list_directory.py` | List directory |
| `get_info.py` | File/folder info |
| `safety.py` | Path safety checks |

#### `tools/memory/` (Memory)

| Tool | Purpose |
|------|---------|
| `get_recent_facts.py` | Query FactsMemory |

#### `tools/browsers/` (Browser - STUB)

| Tool | Purpose |
|------|---------|
| `not_implemented.py` | Placeholder for future |

---

## 7. Config (`config/`)

| File | Purpose |
|------|---------|
| `apps.yaml` | Browser configs, search engines |
| `settings.yaml` | General settings |
| `runtime.yaml` | Runtime mode (local/hosted/hybrid) |
| `models/` | Model configurations per runtime |

---

## 8. GUI (`gui/`)

| Component | Purpose |
|-----------|---------|
| `adapter.py` | GUIAdapter for web interface |
| `progress.py` | ProgressEmitter for real-time streaming |
| `web/` | Flask web server and frontend |

---

## Summary Statistics

| Category | Count |
|----------|-------|
| **Agents** | 4 |
| **Pipelines** | 4 |
| **Memory Systems** | 2 |
| **Model Providers** | 4 |
| **Tool Domains** | 12 |
| **Total Tools** | ~50 |
| **Intent Categories** | 10+ |
