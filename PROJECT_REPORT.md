# 📊 AURA v3 - Complete Project Report

> **Generated:** February 3, 2026  
> **Project:** AURA - Agentic Desktop Assistant  
> **Platform:** Windows 10/11  
> **Language:** Python 3.11+

---

## 1. Executive Summary

**AURA** (Agentic Universal Reasoning Assistant) is a sophisticated AI-powered desktop automation system designed for Windows. It distinguishes itself from traditional voice assistants and automation tools through its **goal-oriented architecture**, where user commands are semantically parsed into goals rather than verb sequences. The system enforces a strict separation between AI reasoning and deterministic execution, ensuring safety and predictability.

### Key Differentiators

| Feature | Description |
|---------|-------------|
| **Goal-Oriented Parsing** | "Open YouTube and search nvidia" becomes ONE action, not two |
| **Dependency-Aware Execution** | Automatic sequencing of dependent operations (e.g., create folder then file inside) |
| **Domain-Locked Safety** | Tools are constrained by intent domain to prevent hallucinated execution |
| **LLM-Free Tools** | All tools are deterministic Python—no AI inside execution |
| **Multi-Provider Support** | Ollama (local), Gemini (cloud), OpenRouter, Hybrid modes |

---

## 2. Architecture Overview

### 2.1 Three-Layer Architecture

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
│  ToolResolver → ToolExecutor                        │
│  (No reasoning, just execution)                     │
└─────────────────────────────────────────────────────┘
```

### 2.2 Dual-Path Flow

```
User Input
    ↓
QueryClassifier (single vs multi)
    ↓
┌───────────────────┬────────────────────────┐
│   SINGLE PATH     │      MULTI PATH        │
├───────────────────┼────────────────────────┤
│ IntentAgent       │ GoalInterpreter        │
│ ToolResolver      │ GoalPlanner (per goal) │
│ ActionPipeline    │ GoalOrchestrator       │
│ Executor          │ PlanGraph → Executor   │
└───────────────────┴────────────────────────┘
    ↓
Result with Response
```

---

## 3. Core Components

### 3.1 Agents (`agents/`)

| Agent | File | Purpose |
|-------|------|---------|
| **QueryClassifier** | `query_classifier.py` | Lightweight router: single vs multi goal classification |
| **IntentAgent** | `intent_agent.py` | Classifies user intent into 14+ categories with few-shot examples |
| **GoalInterpreter** | `goal_interpreter.py` | Extracts semantic goals from user input for multi-path |
| **GoalPlanner** | `goal_planner.py` | Transforms single goal → minimal executable plan |
| **GoalOrchestrator** | `goal_orchestrator.py` | Combines multiple plans into PlanGraph with dependency edges |
| **PlannerAgent** | `planner_agent.py` | Fallback reasoning for low-confidence cases |
| **TaskDecompositionAgent** | `task_decomposition.py` | Decomposes complex queries into subtasks (legacy) |

#### Intent Categories (IntentAgent)

```python
INTENT_CATEGORIES = [
    "application_launch",      # Launch apps (chrome, spotify)
    "application_control",     # Focus, close apps
    "window_management",       # Maximize, minimize, snap
    "system_query",            # Get time, battery, disk usage
    "screen_capture",          # Screenshot
    "screen_perception",       # OCR text search
    "input_control",           # Mouse/keyboard automation
    "system_control",          # Volume, brightness, mute
    "clipboard_operation",     # Read/write clipboard
    "memory_recall",           # Query stored facts
    "file_operation",          # Create, delete, rename files/folders
    "browser_control",         # Browser actions with URL/search
    "office_operation",        # Office app automation (future)
    "information_query"        # Pure LLM response, no tools
]
```

#### Goal Types (GoalInterpreter)

```python
GOAL_TYPES = [
    "browser_search",      # Search on a platform (youtube, google)
    "browser_navigate",    # Open URL directly
    "app_launch",          # Launch application
    "app_action",          # Action within app
    "file_operation",      # File/folder CRUD
    "system_query"         # Get information
]
```

#### MetaGoal Structure

```python
@dataclass(frozen=True)
class MetaGoal:
    meta_type: Literal["single", "independent_multi", "dependent_multi"]
    goals: Tuple[Goal, ...]
    dependencies: Tuple[Tuple[int, Tuple[int, ...]], ...]  # DAG edges
```

---

### 3.2 Core (`core/`)

| Module | File | Purpose |
|--------|------|---------|
| **Orchestrator** | `orchestrator.py` | Main entry point, routes single/multi paths |
| **ToolResolver** | `tool_resolver.py` | Two-stage intent-aware tool resolution |
| **IntentRouter** | `intent_router.py` | Routes intents to appropriate pipelines |
| **Runtime** | `runtime.py` | Loads runtime mode (local/hosted/hybrid) |
| **SanityChecks** | `sanity_checks.py` | Prerequisite validation before execution |
| **Context** | `context.py` | Context management |

#### Two-Stage Tool Resolution

```python
# Stage 1: Preferred domains for intent
INTENT_TOOL_DOMAINS = {
    "application_launch": ["system.apps.launch"],
    "file_operation": ["files"],
    "browser_control": ["system.apps.launch"],
    "system_control": ["system.audio", "system.display", "system.power"],
    ...
}

# Stage 2: Domain-locked fallback (safety)
INTENT_STAGE2_ALLOWED_DOMAINS = {
    "file_operation": ["files"],           # ONLY files.*
    "browser_control": ["system.apps.launch"],  # ONLY launch
    ...
}
```

> **Safety Invariant:** Stage 2 fallback is domain-locked. A `file_operation` intent can NEVER fallback to `system.input.mouse`.

---

### 3.3 Pipelines (`core/pipelines/`)

| Pipeline | File | Purpose |
|----------|------|---------|
| **ActionPipeline** | `action_pipeline.py` | Single action: resolve → execute → response |
| **MultiPipeline** | `multi_pipeline.py` | Multi-action with dependency handling |
| **InfoPipeline** | `info_pipeline.py` | Pure LLM response (no tools) |
| **FallbackPipeline** | `fallback_pipeline.py` | Low-confidence reasoning |

---

### 3.4 Response System (`core/response/`)

| Module | Purpose |
|--------|---------|
| **pipeline.py** | `generate_response()` entry point |
| **fact_extractor.py** | Extract memory-safe facts from tool results |
| **base_response.py** | Default response templates per tool |
| **llm_polisher.py** | Optional LLM polish for natural language |
| **user_response.py** | User-facing response formatting |

---

### 3.5 Vision & Input (`core/vision/`, `core/input/`)

**Vision:**
- OCR engine abstraction (`ocr_engine.py`)
- Backends: Tesseract, Windows OCR

**Input:**
- Input backend abstraction
- Backends: PyAutoGUI, Windows API

---

## 4. Tools System

### 4.1 Tool Base Class (`tools/base.py`)

All tools inherit from the `Tool` ABC with these properties:

```python
class Tool(ABC):
    # Required
    @property
    def name(self) -> str: ...
    @property
    def description(self) -> str: ...
    @property
    def schema(self) -> Dict[str, Any]: ...
    
    # Metadata
    @property
    def risk_level(self) -> str: ...           # "low" | "medium" | "high"
    @property
    def side_effects(self) -> list[str]: ...
    @property
    def stabilization_time_ms(self) -> int: ...
    @property
    def reversible(self) -> bool: ...
    
    # Preconditions (enforced by Executor, NOT LLM)
    @property
    def requires_focus(self) -> bool: ...
    @property
    def requires_active_app(self) -> Optional[str]: ...
    @property
    def requires_unlocked_screen(self) -> bool: ...
    @property
    def is_destructive(self) -> bool: ...
    
    # Execution
    @abstractmethod
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]: ...
```

### 4.2 Tool Registry (`tools/registry.py`)

Singleton registry for all tools:
- `get_registry().has(name)` - Check if tool exists
- `get_registry().get(name)` - Get tool instance
- `get_registry().get_tools_for_llm()` - Get all tools for LLM prompts

### 4.3 Tool Categories (~50+ Tools)

#### Files (`tools/files/`)

| Tool | Purpose |
|------|---------|
| `files.create_file` | Create file with optional content |
| `files.create_folder` | Create directory (with parent creation) |
| `files.delete_file` | Delete file |
| `files.delete_folder` | Delete directory |
| `files.read_file` | Read file content |
| `files.write_file` | Write content to file |
| `files.append_file` | Append content to file |
| `files.copy` | Copy file or folder |
| `files.move` | Move file or folder |
| `files.rename` | Rename file or folder |
| `files.list_directory` | List directory contents |
| `files.get_info` | Get file/folder metadata |
| `safety.py` | Path safety validation |

#### System Apps (`tools/system/apps/`)

| Tool | Purpose |
|------|---------|
| `system.apps.launch.shell` | Launch apps with URL/search support |
| `system.apps.launch.path` | Launch by executable path |
| `system.apps.focus` | Focus running application |
| `system.apps.request_close` | Request app close |
| `app_resolver.py` | Multi-strategy app resolution |
| `app_handle.py` | Handle tracking registry |

#### System Window (`tools/system/window/`)

| Tool | Purpose |
|------|---------|
| `system.window.maximize` | Maximize window |
| `system.window.minimize` | Minimize window |
| `system.window.minimize_all` | Win+D |
| `system.window.close` | Close window |
| `system.window.snap_left/right` | Snap windows |
| `system.window.switch` | Alt+Tab to window |
| `system.window.task_view` | Open task view |

#### System Audio (`tools/system/audio/`)

| Tool | Purpose |
|------|---------|
| `system.audio.set_volume` | Set volume level |
| `system.audio.get_volume` | Get current volume |
| `system.audio.set_mute` | Mute audio |
| `system.audio.set_unmute` | Unmute audio |
| `system.audio.media_play_pause` | Play/pause media |
| `system.audio.media_next/previous` | Skip tracks |

#### System Display (`tools/system/display/`)

| Tool | Purpose |
|------|---------|
| `system.display.take_screenshot` | Capture screen |
| `system.display.set_brightness` | Adjust brightness |
| `system.display.find_text` | OCR text search |

#### System State (`tools/system/state/`)

| Tool | Purpose |
|------|---------|
| `system.state.get_time` | Current time |
| `system.state.get_date` | Current date |
| `system.state.get_datetime` | Date and time |
| `system.state.get_battery` | Battery status |
| `system.state.get_disk_usage` | Disk space |
| `system.state.get_memory_usage` | RAM usage |
| `system.state.get_network_status` | Network info |
| `system.state.get_active_window` | Active window info |
| `system.state.get_execution_context` | Full context |

#### System Power (`tools/system/power/`)

| Tool | Purpose |
|------|---------|
| `system.power.shutdown` | Shutdown/restart |
| `system.power.sleep` | Sleep |
| `system.power.lock` | Lock screen |

#### System Input (`tools/system/input/`)

| Tool | Purpose |
|------|---------|
| `system.input.keyboard.type` | Type text |
| `system.input.keyboard.press` | Press key/hotkey |
| `system.input.mouse.click` | Click at coordinates |
| `system.input.mouse.move` | Move cursor |

#### Other Domains

| Domain | Tools |
|--------|-------|
| `system.clipboard/` | `read`, `write` |
| `system.desktop/` | `toggle_icons`, `empty_recycle_bin`, `restart_explorer`, `set_night_light` |
| `system.virtual_desktop/` | `get_current`, `switch_desktop`, `move_window_to_desktop` |
| `system.network/` | Network utilities |
| `tools/memory/` | `get_recent_facts` |
| `tools/browsers/` | Browser stub (future) |
| `tools/apps/` | App creator |
| `tools/automation/` | Automation utilities |
| `tools/knowledge/` | Knowledge base |

---

## 5. Memory Systems

### 5.1 AmbientMemory (`memory/ambient.py`)

**Purpose:** Background system state tracker (every 5 seconds)

**Tracks:**
- Active window (handle, title, process, bounds)
- Running apps list
- Recent activity (last N snapshots)
- History deque (max 100 snapshots)

**Interface:**
```python
class AmbientMemory:
    POLL_INTERVAL = 5.0
    
    def get_context(self) -> Dict[str, Any]: ...
    def get_recent_activity(self, minutes: int = 5) -> List[Dict]: ...
```

**Storage:** `~/.aura/ambient_state.json`

### 5.2 FactsMemory (`memory/facts.py`)

**Purpose:** Episodic memory for tool-derived facts

**Features:**
- Stores `ExtractedFacts` with full provenance (tool, query, session_id)
- Query by keys, tool, recency
- Daily rotation with 7-day retention
- Thread-safe, non-blocking

**Interface:**
```python
class FactsMemory:
    def store(self, extracted: ExtractedFacts, query: str, session_id: str) -> str: ...
    def query_by_keys(self, keys: List[str], tool: str = None, limit: int = 20) -> List[StoredFact]: ...
    def query_by_tool(self, tool_name: str, max_age_minutes: int = None, limit: int = 10) -> List[StoredFact]: ...
    def query_recent(self, minutes: int = 30, limit: int = 20) -> List[StoredFact]: ...
```

**Storage:** `~/.aura/facts/` (daily JSON files)

---

## 6. Execution System

### 6.1 ToolExecutor (`execution/executor.py`)

**Purpose:** Execute tools deterministically with safety enforcement

**Safety Features:**
- Modifier key kill-switch (`pressed_keys` tracking)
- Executor cooldown support
- Key release on any failure
- Precondition enforcement (NOT by LLM)

**Preconditions Enforced:**
```python
requires_focus          # Window must be focused
requires_active_app     # Specific app must be focused
requires_unlocked_screen # Screen must be unlocked
is_destructive          # Requires confirmation
```

**Interface:**
```python
class ToolExecutor:
    def execute_plan(self, plan: Dict[str, Any]) -> Dict[str, Any]: ...
    def execute_step(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]: ...
    def set_cooldown(self, duration_ms: int): ...
    def register_key_press(self, key: str): ...
    def register_key_release(self, key: str): ...
```

---

## 7. Model Management

### 7.1 ModelManager (`models/model_manager.py`)

**Purpose:** Single source of truth for all model routing

**Roles:**
| Role | Purpose |
|------|---------|
| `intent` | Intent classification (cheap, fast) |
| `planner` | Planning/reasoning |
| `critic` | Post-execution analysis |
| `gate` | Single/multi decomposition |
| `tda` | Task decomposition |

### 7.2 Providers (`models/providers/`)

| Provider | File | Purpose |
|----------|------|---------|
| **Ollama** | `ollama.py` | Local models via Ollama |
| **Gemini** | `gemini.py` | Google Gemini API |
| **OpenRouter** | `openrouter.py` | OpenRouter API |
| **Hybrid** | `hybrid.py` | Local-first with cloud fallback |

### 7.3 Runtime Modes

**Local Mode** (`config/models/local.yaml`):
```yaml
intent:
  provider: ollama
  model: phi3:mini
planner:
  provider: ollama
  model: mistral:7b-instruct
```

**Hybrid Mode** (`config/models/hybrid.yaml`):
```yaml
intent:
  primary:
    provider: ollama
    model: phi3:mini
  fallback:
    provider: gemini
    model: gemini-2.0-flash-lite
```

> **Hybrid Contract:** Local-first, cloud only on infrastructure failure (ProviderUnavailableError). Never "cloud when local output is bad."

---

## 8. GUI System

### 8.1 Web Interface (`gui/web/`)

| File | Purpose |
|------|---------|
| `server.py` | aiohttp WebSocket server |
| `index.html` | Modern web interface |
| `style.css` | Styling (~25KB) |
| `app.js` | Frontend logic (~22KB) |

### 8.2 GUIAdapter (`gui/adapter.py`)

Bridges web interface with Orchestrator:
- Routes all commands through Orchestrator
- GUI only sees `UserResponse`, never internal logs
- Real-time progress streaming via WebSocket

### 8.3 ProgressEmitter (`gui/progress.py`)

Streams human-readable progress messages to frontend:
```python
class ProgressEmitter:
    def __init__(self, callback: Callable[[str], None] = None): ...
    def emit(self, message: str): ...
```

---

## 9. Configuration

### 9.1 Runtime Configuration (`config/runtime.yaml`)

```yaml
runtime:
  mode: local  # local | hosted | hybrid
```

### 9.2 Application Configuration (`config/apps.yaml`)

Browser configs, search engines:
```yaml
search:
  default_browser: chrome
  engines:
    google: "https://www.google.com/search?q={query}"
    youtube: "https://www.youtube.com/results?search_query={query}"
    ...

browsers:
  chrome:
    executable_patterns: ["chrome.exe", "Google Chrome"]
    default_args: ["--profile-directory=Default"]
  ...
```

### 9.3 Settings (`config/settings.yaml`)

```yaml
evolution:
  autonomy_mode: manual  # manual | assisted | sandboxed | autonomous
  max_risk_level: medium
  forbidden_categories:
    - system_destruction
    - network_exploit

safety:
  require_description_min_length: 10
  validate_tool_names: true
  check_name_conflicts: true
```

---

## 10. Entry Points

### 10.1 CLI (`main.py`)

```bash
python main.py
```

Starts terminal interface with text input loop.

### 10.2 Web GUI (`main_gui.py`)

```bash
python main_gui.py              # Opens browser
python main_gui.py --no-browser # No auto-open
python main_gui.py --port 3000  # Custom port
```

Starts modern web interface at `http://localhost:8080`.

---

## 11. Safety Guarantees

| Guarantee | Mechanism |
|-----------|-----------|
| **No hallucinated execution** | Stage 2 domain lock |
| **No multi-tool ambiguity** | Multi-JSON detection |
| **Dependent goals ordered** | Dependency graph |
| **Single path isolation** | No goal components touched |
| **No `exec()` calls** | Pure Python tools |
| **Schema validation** | All LLM outputs validated |
| **Tool argument validation** | `validate_args()` method |
| **Path normalization** | File operations safety |

### Safety Invariants

1. **LLMs do NOT execute code** - They only decide what to do
2. **Python owns execution** - All execution is deterministic
3. **Tools are deterministic** - No AI inside tools
4. **Preconditions are enforced by Executor, NOT LLM prompts**

---

## 12. Testing

### 12.1 Test Suite (`tests/`)

| Test File | Purpose |
|-----------|---------|
| `test_goal_architecture.py` | Goal-oriented architecture tests |
| `test_file_operation.py` | File operation tools |
| `test_dependent_multi_fix.py` | Dependent multi-goal execution |
| `test_browser_control_fix.py` | Browser control safety |
| `test_deterministic_safety_trace.py` | Safety trace verification |
| `test_e2e_safety_trace.py` | End-to-end safety |
| `test_app_resolver.py` | Application resolution |
| `test_phase2_readiness.py` | Phase 2 features |
| `test_semantic_indexing.py` | Semantic search |
| `verify_agent_behavior.py` | Agent behavior verification |

### 12.2 Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run specific test
python -m pytest tests/test_file_operation.py -v
```

---

## 13. Project Statistics

| Metric | Value |
|--------|-------|
| **Total Agents** | 7 |
| **Total Pipelines** | 4 |
| **Memory Systems** | 2 |
| **Model Providers** | 4 |
| **Tool Domains** | 12 |
| **Total Tools** | ~50+ |
| **Intent Categories** | 14 |
| **Goal Types** | 6 |
| **Test Files** | 15+ |
| **Documentation Files** | 12 |

---

## 14. Future Roadmap

### Self-Evolution System (Planned)

From `docs/SELF_EVOLUTION_PLAN.md`:

1. **Limitation Detection** - Planner explicitly aware of missing capabilities
2. **Skill Proposal System** - Generate tool proposals (metadata only, no code)
3. **Procedural Memory** - Store learned capabilities
4. **Validation Gates** - Policy enforcement before registration
5. **Safe Evolution** - No `exec()`, no automatic file mutation

### Key Planned Features

- **Dependent Multi Goals** - Full dependency graph execution
- **Simulated State Effects** - Pre-execution state prediction
- **Clarification Loops** - Handle ambiguous requests
- **Neo4j Integration** - Knowledge graph for planning
- **App Action Goals** - In-app automation beyond launch

---

## 15. Known Limitations

1. **Windows Only** - Designed for Windows 10/11
2. **Browser Stub** - Full browser automation is placeholder
3. **Office Operations** - Future domain, not implemented
4. **Physical Input Safety** - Mouse/keyboard tools are opt-in only
5. **Single Session** - No multi-user or distributed execution

---

## 16. Dependencies

From `requirements.txt`:
```
aiohttp          # Web server
pyautogui        # Input automation
pycaw            # Windows audio control
pillow           # Image processing
psutil           # System monitoring
pyyaml           # Configuration
screen_brightness_control  # Display control
google-generativeai  # Gemini API
ollama           # Local LLM
pytest           # Testing
```

---

## 17. Conclusion

AURA represents a sophisticated approach to desktop automation that prioritizes:

1. **Semantic Understanding** - Goals over verbs
2. **Safety** - Deterministic execution with domain locks
3. **Flexibility** - Multi-provider LLM support
4. **Extensibility** - Clean tool architecture
5. **Transparency** - Comprehensive documentation and contracts

The architecture is designed for controlled evolution, where new capabilities are proposed as metadata, validated through policy gates, and only implemented through deterministic Python code—never through AI-generated executable code.

---

*This report was generated through comprehensive analysis of the AURA codebase, including all source files, documentation, configuration, and test suites.*
