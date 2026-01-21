# 🤖 AURA - Agentic Desktop Assistant

A multi-agent AI system for Windows desktop automation with **effect-based planning**, **deterministic execution**, and **self-evolution capabilities**.

---

## 🌟 What Makes AURA Different

### ♻️ Idempotent Effect Execution
Plans are expressed as **observable effects** (not imperative commands). Before execution:
- **Preconditions** are validated
- **Already-satisfied effects** are detected and skipped
- Re-running the same command won't repeat completed work

```
User: "Mute the volume"
→ Effect: {type: "audio.muted", target: "master"}
→ Check: Is master already muted? → YES → Skip execution
```

### 🔍 Two-Tier Effect Verification
Execution results are verified in two tiers:
1. **Tier 1 (Deterministic)**: Fast Python checks (file exists? volume level?)
2. **Tier 2 (LLM Fallback)**: For custom effects without deterministic verifiers

No blind trust in tool return values—effects are independently verified.

### 🧭 Semantic Tool Discovery (Qdrant)
Tools are found via **semantic similarity**, not string matching:
- Tool descriptions are embedded and indexed in Qdrant
- Planner queries find relevant tools even with novel phrasing
- No brittle keyword mapping required

### 🚧 Ontology-Based Plan Validation (Neo4j)
Before execution, plans are validated against a **constraint graph**:
- **Blocked tools** based on context (e.g., "don't send emails during DND")
- **Prerequisite checks** (e.g., "app must be open before clicking")
- Plans failing eligibility are refused with explanation

### 🔄 Evolution Modes
Self-evolution with configurable autonomy:

| Mode | Behavior |
|------|----------|
| `manual` | Human approves all new tools |
| `assisted` | System proposes, human decides |
| `sandboxed` | Auto-test in isolated environment |
| `autonomous` | Full auto-evolution (high trust) |

---

## 🧠 Multi-Agent Architecture

| Agent | Role | Model Type |
|-------|------|------------|
| **Intent Agent** | Fast intent classification | Cheap/fast |
| **Planner Agent** | Effect-based plan generation | Reasoning |
| **Critic Agent** | Two-tier effect verification | Evaluation |
| **Task Decomposition Agent** | Complex query → atomic subtasks | Reasoning |
| **Limitation Agent** | Propose new tools for gaps | Reasoning |

### Core Principles
1. **LLMs decide, Python executes** - LLMs never run code
2. **Deterministic tools** - Same input → same output
3. **Schema validation** - All LLM outputs validated
4. **Model abstraction** - Switch providers via YAML config

---

## 🔌 Multi-Provider Model Support

| Provider | Use Case |
|----------|----------|
| **Gemini** | Google AI, fast inference |
| **OpenRouter** | Aggregator, model variety |
| **Ollama** | Local models, privacy |

```yaml
# config/models/local.yaml
intent:
  provider: gemini
  model: gemini-2.5-flash
planner:
  provider: gemini
  model: gemini-2.5-flash
critic:
  provider: gemini
  model: gemini-2.5-flash
```

---

## 🛠️ Tool Categories

| Category | Examples |
|----------|----------|
| `system/apps` | Launch, close, focus applications |
| `system/audio` | Volume control, mute |
| `system/display` | Screenshot, brightness |
| `system/input` | Mouse click, keyboard type |
| `system/power` | Sleep, shutdown, lock |
| `system/state` | Query running processes |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Windows 10/11
- API key (Gemini, OpenRouter, or Ollama running locally)

### Installation
```bash
git clone <repo-url>
cd AURA
pip install -r requirements.txt

# Set API key
$env:GEMINI_API_KEY="your_key_here"

# Run
python main.py
```

---

## 🏗️ Architecture

```
User Input
    ↓
┌─────────────────────────────────────────┐
│  SubtaskOrchestrator (top-level)        │
│    ├─ Decomposition Gate                │
│    └─ Task Decomposition Agent          │
└─────────────────────────────────────────┘
    ↓ (per subtask)
┌─────────────────────────────────────────┐
│  AgentLoop                              │
│    ├─ Intent Agent (classification)     │
│    ├─ Planner Agent (effect planning)   │
│    ├─ Effect Router (deterministic)     │
│    ├─ Tool Executor (NO AI)             │
│    └─ Critic Agent (evaluation)         │
└─────────────────────────────────────────┘
    ↓
Result
```

### Directory Structure

```
AURA/
├── agents/                    # AI agents
│   ├── intent_agent.py       # Fast intent classification
│   ├── planner_agent.py      # Effect-based planning
│   ├── critic_agent.py       # Execution evaluation
│   ├── task_decomposition.py # TDA v3
│   ├── limitation_agent.py   # Skill proposals
│   └── decomposition_gate.py # Single/multi routing
├── core/
│   ├── orchestrator.py       # SubtaskOrchestrator (entry point)
│   ├── agent_loop.py         # Per-subtask execution
│   ├── assistant.py          # User-facing interface
│   ├── effects/              # Effect schemas & verification
│   │   ├── schema.py         # Effect type definitions
│   │   └── verification.py   # Deterministic verifiers
│   ├── semantic/             # Semantic search (Qdrant)
│   │   ├── qdrant_client.py  # Vector store client
│   │   ├── tool_index.py     # Tool embeddings
│   │   └── tool_search.py    # Semantic tool matching
│   └── ontology/             # Constraint checking (Neo4j)
│       ├── neo4j_client.py   # Graph DB client
│       └── eligibility.py    # Plan eligibility checks
├── tools/
│   ├── base.py               # Tool base class
│   ├── registry.py           # Central tool registry
│   ├── loader.py             # Dynamic tool loading
│   └── system/               # System tools by category
├── models/
│   ├── model_manager.py      # Model routing singleton
│   └── providers/            # LLM provider adapters
│       ├── gemini.py
│       ├── openrouter.py
│       └── ollama.py
├── memory/
│   ├── procedural.py         # Tool proposals & skills
│   └── postmortem.py         # Execution outcomes
├── execution/
│   └── executor.py           # Deterministic tool executor
├── config/
│   ├── settings.yaml         # General settings
│   └── models/               # Per-runtime model configs
│       ├── local.yaml
│       ├── hosted.yaml
│       └── hybrid.yaml
├── tests/                    # Test suite
│   ├── test_e2e_*.py         # End-to-end tests
│   └── test_*_integration.py # Integration tests
├── docs/                     # Documentation
│   ├── ARCHITECTURE.md       # Detailed architecture
│   └── *.md                  # Design docs
├── main.py                   # Entry point
└── requirements.txt
```

---

## 🛡️ Security & Safety

### Execution Safety
- **No `exec()` calls** - Tools are pure Python
- **Schema validation** - All LLM outputs validated before use
- **Argument validation** - Tool inputs checked against JSON Schema
- **Risk levels** - Tools declare `low`, `medium`, `high` risk
- **Side effect tracking** - Tools declare their side effects

### Self-Evolution Safety
```yaml
# config/settings.yaml
evolution:
  autonomy_mode: manual    # manual | assisted | sandboxed | autonomous
  max_risk_level: medium
  require_manual_approval: true
  forbidden_categories:
    - system_destruction
    - network_exploit
```

### Tool Contract
Every tool must:
1. Inherit from `Tool` base class
2. Define `name`, `description`, `schema`
3. Implement `execute(args)` → `{"status": "success", ...}`
4. Be deterministic (no randomness, no AI)

---

## ⚙️ Configuration

### Runtime Modes
AURA supports multiple runtime modes configured in `config/runtime.yaml`:
- **local** - All models run locally or via personal API keys
- **hosted** - Cloud-hosted models (future)
- **hybrid** - Mixed local/cloud (future)

### Model Configuration
Edit `config/models/<runtime>.yaml` to customize models per agent role:

```yaml
intent:
  provider: ollama
  model: phi-3-mini

planner:
  provider: openrouter
  model: mistralai/mistral-7b-instruct

critic:
  provider: gemini
  model: gemini-2.5-flash
```

---

## 🧪 Testing

```bash
# Run full test suite
python -m pytest tests/

# Run specific test
python -m pytest tests/test_e2e_safety_trace.py -v

# Run integration tests
python -m pytest tests/test_planner_qdrant_integration.py -v
```

---

## 📖 Usage Examples

```
You: "Take a screenshot"
→ Intent: system_control
→ Plan: effects=[{type: "screenshot.captured", ...}]
→ Execute: ScreenshotTool.execute()
→ Critic: verified ✓
→ Result: Screenshot saved

You: "Mute the volume and open notepad"
→ Decomposition Gate: MULTI
→ TDA: subtask_1="mute volume", subtask_2="open notepad"
→ Execute each subtask through AgentLoop
→ Aggregate results
```

### Special Commands
- `help` - Show available commands
- `status` - Show system status
- `exit` / `quit` - Exit AURA

---

## 🔮 Self-Evolution

When AURA encounters an unknown capability:
1. **Detection** - Planner reports `requires_new_tool: true`
2. **Proposal** - LimitationAgent proposes tool specification
3. **Validation** - SkillGate validates proposal
4. **Storage** - ProceduralMemory stores proposal
5. **Human Review** - User approves/rejects
6. **Implementation** - Tool scaffold generated for development

> **Note**: Self-evolution currently requires human approval for new tools.

---

## 📝 Development

### Adding New Tools

1. Create tool in `tools/system/<category>/`:
   ```python
   from tools.base import Tool

   class MyTool(Tool):
       @property
       def name(self) -> str:
           return "my_tool"
       
       @property
       def description(self) -> str:
           return "Does something useful"
       
       @property
       def schema(self) -> dict:
           return {
               "type": "object",
               "properties": {
                   "param": {"type": "string"}
               },
               "required": ["param"]
           }
       
       def execute(self, args: dict) -> dict:
           # Deterministic Python only
           return {"status": "success", "result": "..."}
   ```

2. Tool is auto-discovered via `ToolLoader`

### Key Design Principles
- **Effect-first**: Think in terms of observable state changes
- **Determinism**: Tools must produce same output for same input
- **Separation**: LLMs reason, Python executes
- **Validation**: Schema-first, always validate

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Detailed system architecture |
| [SELF_EVOLUTION_PLAN.md](docs/SELF_EVOLUTION_PLAN.md) | Self-evolution design |
| [IMPLEMENTATION_ORDER.md](docs/IMPLEMENTATION_ORDER.md) | Build order guide |

---

## ⚠️ Disclaimer

AURA executes actions on your Windows system. While safety measures are in place:
- Review tool proposals before approval
- Use in controlled environments for testing
- Monitor system changes
- Keep backups of important data

---

## 📄 License

MIT License - See LICENSE file for details.
