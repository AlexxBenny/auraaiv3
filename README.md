# 🤖 AURA - Agentic Desktop Assistant

A goal-oriented AI assistant for Windows desktop automation with **semantic goal extraction**, **dependency-aware execution**, and **deterministic tool safety**.

---

## 🌟 What Makes AURA Different

### 🎯 Goal-Oriented Architecture
User commands are parsed as **semantic goals**, not verb sequences:

```
User: "open youtube and search nvidia"
→ QueryClassifier: SINGLE (one goal)
→ Merged into: ONE action (youtube.com/results?search_query=nvidia)
```

### 🔗 Dependency-Aware Multi-Goal Execution
Dependent actions are automatically sequenced:

```
User: "create folder nvidia and put a file inside it"
→ QueryClassifier: MULTI (dependency detected: "inside it")
→ GoalInterpreter: 2 goals with dependency edge
→ Execute: folder first → file second
```

### 🛡️ Domain-Locked Safety
Tools are constrained by domain to prevent hallucinated execution:

```
Intent: file_operation
→ Stage 1: files.* tools only
→ Stage 2: ONLY files.* fallback (no system.input.mouse!)
→ No match? → Hard fail (safe abort)
```

---

## 🧠 Architecture

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
│ Executor          │ GoalOrchestrator       │
│                   │ PlanGraph → Executor   │
└───────────────────┴────────────────────────┘
    ↓
Result
```

### Core Agents

| Agent | Role |
|-------|------|
| **QueryClassifier** | Route single vs multi-goal queries |
| **GoalInterpreter** | Extract semantic goals with dependencies |
| **GoalPlanner** | Transform goal → minimal executable plan |
| **GoalOrchestrator** | Combine plans into dependency graph |
| **IntentAgent** | Fast intent classification (single path) |

### Core Principles
1. **LLMs decide, Python executes** - LLMs never run code
2. **Goals, not verbs** - Parse intent semantically
3. **Deterministic tools** - Same input → same output
4. **Schema validation** - All LLM outputs validated

---

## 🛠️ Tool Categories

| Category | Examples |
|----------|----------|
| `files.*` | Create folder, create file, delete, rename |
| `system/apps` | Launch, close, focus applications |
| `system/audio` | Volume control, mute |
| `system/display` | Screenshot, brightness |
| `system/input` | Mouse click, keyboard type |
| `system/power` | Sleep, shutdown, lock |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Windows 10/11
- API key (Gemini recommended)

### Installation
```bash
git clone <repo-url>
cd AURA
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

# Set API key
$env:GEMINI_API_KEY="your_key_here"

# Run CLI
python main.py

# Run Web GUI
python main_gui.py
```

---

## 📖 Usage Examples

### Single Goal (Merged Automatically)
```
You: "open youtube and search nvidia"
→ 1 action: Launch Chrome with youtube.com/results?search_query=nvidia
```

### Multi Goal (Independent)
```
You: "open chrome and open spotify"
→ 2 parallel actions
```

### Multi Goal (Dependent)
```
You: "create folder nvidia and create a file inside it"
→ 2 sequential actions (folder first, then file)
```

### System Control
```
You: "mute the volume"
You: "take a screenshot"
You: "increase brightness"
```

---

## 🔌 Model Support

| Provider | Use Case |
|----------|----------|
| **Gemini** | Fast inference (recommended) |
| **Ollama** | Local models, privacy |
| **OpenRouter** | Model variety |

```yaml
# config/models/local.yaml
intent:
  provider: gemini
  model: gemini-2.0-flash
planner:
  provider: gemini
  model: gemini-2.0-flash
```

---

## 📁 Directory Structure

```
AURA/
├── agents/                    # AI agents
│   ├── query_classifier.py   # Single vs multi routing
│   ├── goal_interpreter.py   # Semantic goal extraction
│   ├── goal_planner.py       # Goal → plan transformation
│   ├── goal_orchestrator.py  # Multi-goal coordination
│   └── intent_agent.py       # Intent classification
├── core/
│   ├── orchestrator.py       # Main entry point
│   ├── tool_resolver.py      # Tool selection + safety
│   └── intent_router.py      # Intent → pipeline routing
├── tools/
│   ├── base.py               # Tool base class
│   ├── registry.py           # Central tool registry
│   ├── files/                # File tools
│   └── system/               # System tools
├── models/
│   ├── model_manager.py      # Model routing
│   └── providers/            # LLM adapters
├── config/
│   ├── runtime.yaml          # Runtime mode
│   └── models/               # Per-mode model configs
├── docs/                     # Documentation
├── tests/                    # Test suite
├── main.py                   # CLI entry point
└── main_gui.py               # Web GUI entry point
```

---

## 🛡️ Safety

### Execution Safety
- **No `exec()` calls** - Pure Python tools
- **Schema validation** - All LLM outputs validated
- **Domain lock** - Stage 2 fallback restricted by intent
- **Multi-JSON rejection** - Prevents tool hallucination

### Tool Contract
```python
class MyTool(Tool):
    @property
    def name(self) -> str:
        return "category.tool_name"
    
    def execute(self, args: dict) -> dict:
        # Deterministic Python only
        return {"status": "success", ...}
```

---

## 🧪 Testing

```bash
# Run all tests
python -m pytest tests/

# Run specific test
python -m pytest tests/test_file_operation.py -v
```

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture |
| [CODE_FLOW.md](docs/CODE_FLOW.md) | Execution flow |
| [QUERY_CLASSIFIER_CONTRACT.md](docs/QUERY_CLASSIFIER_CONTRACT.md) | Routing logic |
| [GOAL_PLANNER_CONTRACT.md](docs/GOAL_PLANNER_CONTRACT.md) | Planning contract |
| [GOAL_INTERPRETER_CONTRACT.md](docs/GOAL_INTERPRETER_CONTRACT.md) | Goal extraction |
| [GOAL_ORCHESTRATOR_CONTRACT.md](docs/GOAL_ORCHESTRATOR_CONTRACT.md) | Multi-goal coordination |

---

## ⚠️ Disclaimer

AURA executes actions on your Windows system. While safety measures are in place:
- Test in controlled environments
- Monitor system changes
- Keep backups of important data

---

## 📄 License

MIT License - See LICENSE file for details.
