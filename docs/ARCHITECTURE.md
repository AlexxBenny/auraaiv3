# AURA Agentic Architecture

## Core Principles

1. **LLMs do NOT execute code** - They only decide what to do
2. **Python owns execution** - All execution is deterministic
3. **Tools are deterministic** - No AI inside tools
4. **Goal-oriented reasoning** - Semantic goals, not verb counting
5. **Schema validation** - All LLM outputs validated
6. **LLM-centric decisions** - Context surfaces to LLM, not coded as rules

---

## Architecture Flow

```
User Input
    ↓
QueryClassifier (single vs multi)
    ↓
┌───────────────────┬────────────────────────┐
│   SINGLE PATH     │      MULTI PATH        │
├───────────────────┼────────────────────────┤
│ IntentAgent       │ GoalInterpreter        │
│ ToolResolver      │ GoalOrchestrator       │
│ Executor          │ GoalPlanner (per goal) │
│                   │ PlanGraph → Executor   │
└───────────────────┴────────────────────────┘
    ↓
Result
```

---

## Component Responsibilities

### Context Layer (`core/`)

| Component | Responsibility |
|-----------|----------------|
| **ContextSnapshot** | Format ambient state for LLM consumption |
| **AmbientMemory** | Background system state tracking |

### Routing Layer (`agents/`)

| Component | Responsibility |
|-----------|----------------|
| **QueryClassifier** | Syntactic routing (single vs multi) - NO context |
| **IntentAgent** | Intent classification WITH context - decides act vs ask |

### Reasoning Layer (`agents/`)

| Component | Responsibility |
|-----------|----------------|
| **GoalInterpreter** | Extract semantic goals from user input |
| **GoalPlanner** | Transform goal → minimal executable plan |
| **GoalOrchestrator** | Combine plans into dependency graph |

### Execution Layer (`core/`, `execution/`)

| Component | Responsibility |
|-----------|----------------|
| **ToolResolver** | Map intent → tool with domain safety |
| **Orchestrator** | Main entry point, path routing |
| **ToolExecutor** | Execute tools deterministically |

### Tools (`tools/`)

- **Tool**: Base class for all tools
- **Registry**: Central tool registry
- **Categories**: files, system, office, memory

---

## Goal Architecture (Key Innovation)

```
"create folder nvidia and file inside it"
    ↓
QueryClassifier: "multi" (syntactic: "inside it")
    ↓
GoalInterpreter: dependent_multi, 2 goals
    ↓
GoalPlanner: 2 plans (files.create_folder, files.create_file)
    ↓
GoalOrchestrator: PlanGraph with dependency edges
    ↓
Execute: folder first → file second
```

### Merging Principle

```
"open youtube and search nvidia"
    ↓
QueryClassifier: "single" (one semantic goal)
    ↓
Single path: IntentAgent → browser_control
    ↓
One action: youtube.com/results?search_query=nvidia
```

---

## Tool Contract

Every tool must:
1. Inherit from `Tool` base class
2. Define `name`, `description`, `schema`
3. Implement `execute(args)` method
4. Return structured result with `status` key
5. Be deterministic (no randomness, no AI)

---

## Safety Guarantees

| Guarantee | Mechanism |
|-----------|-----------|
| No hallucinated execution | Stage 2 domain lock |
| No multi-tool ambiguity | Multi-JSON detection |
| Dependent goals ordered | Dependency graph |
| Single path isolation | No goal components touched |

---

## Model Configuration

Edit `config/models.yaml`:

```yaml
intent:
  provider: ollama
  model: phi-3-mini

planner:
  provider: ollama
  model: phi-3-mini
```

---

## Security

- No `exec()` calls
- Schema validation on all LLM outputs
- Tool argument validation
- Deterministic execution only
- Path normalization for file operations
