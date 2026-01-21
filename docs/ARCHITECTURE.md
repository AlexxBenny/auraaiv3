# AURA Agentic Architecture

## Core Principles

1. **LLMs do NOT execute code** - They only decide what to do
2. **Python owns execution** - All execution is deterministic
3. **Tools are deterministic** - No AI inside tools
4. **Model abstraction** - Switch models via config
5. **Schema validation** - All LLM outputs validated

## Architecture Flow

```
User Input
    ↓
Intent Agent (cheap model)
    ↓
Planner Agent (reasoning model)
    ↓
Tool Router (deterministic)
    ↓
Tool Executor (NO AI)
    ↓
Critic Agent (evaluation)
    ↓
Result
```

## Component Responsibilities

### Models (`models/`)
- **ModelManager**: Single source of truth for model routing
- **Providers**: Abstract LLM interfaces (Gemini, OpenRouter, Ollama)
- **Rules**: Always return JSON, never code

### Agents (`agents/`)
- **IntentAgent**: Classifies user intent (fast, cheap)
- **PlannerAgent**: Creates execution plans (reasoning)
- **CriticAgent**: Evaluates results (post-execution)

### Tools (`tools/`)
- **Tool**: Base class for all tools
- **Registry**: Central tool registry
- **System Tools**: Screenshot, Volume, Brightness, etc.

### Execution (`execution/`)
- **ToolExecutor**: Executes tools deterministically
- **NO AI**: Pure Python execution only
- **NO retries**: Single execution per step

### Core (`core/`)
- **AgentLoop**: Main orchestration
- **Context**: Session context (working memory)
- **Assistant**: User-facing interface

## Tool Contract

Every tool must:
1. Inherit from `Tool` base class
2. Define `name`, `description`, `schema`
3. Implement `execute(args)` method
4. Return structured result with `status` key
5. Be deterministic (no randomness, no AI)

## Model Configuration

Edit `config/models.yaml` to change models:

```yaml
intent:
  provider: ollama
  model: phi-3-mini

planner:
  provider: openrouter
  model: mistralai/mistral-7b-instruct
```

No code changes needed!

## Adding New Tools

1. Create tool class in `tools/system/`
2. Inherit from `Tool`
3. Implement required methods
4. Register in `core/assistant.py`

Example:
```python
class MyTool(Tool):
    @property
    def name(self) -> str:
        return "my_tool"
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        # Deterministic Python only
        return {"status": "success", "result": ...}
```

## Memory System (Future)

- **Working**: Current task (in `core/context.py`)
- **Episodic**: What happened (SQLite)
- **Procedural**: What can be done (tool metadata)
- **Semantic**: Similar past tasks (vector DB)

## Security

- No `exec()` calls
- Schema validation on all LLM outputs
- Tool argument validation
- Deterministic execution only

---

*This architecture replaces the old code-generation approach*

