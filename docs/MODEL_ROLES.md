# Model Roles Reference

**SINGLE SOURCE OF TRUTH**: All model assignments are in `config/models/{mode}.yaml`

## Role ↔ Component Map

| Role | Component | Responsibility |
|------|-----------|----------------|
| `intent` | IntentAgent | Strategy selection and routing |
| `classifier` | QueryClassifier | Single/Multi goal topology detection |
| `goal_interpreter` | GoalInterpreter | Semantic goal extraction from queries |
| `coordinator` | ExecutionCoordinator | Block structuring for complex queries |
| `planner` | PlannerAgent, GoalPlanner | Plan synthesis and action generation |
| `tool_resolver` | ToolResolver | Intent → Tool mapping |
| `response` | Orchestrator | Response formatting |
| `critic` | (Future) | Validation and audits |
| `tda` | TaskDecompositionAgent | Deep decomposition of complex goals |

## Configuration Files

- `config/models/local.yaml` - Local Ollama models
- `config/models/hosted.yaml` - Cloud API models (Gemini)
- `config/models/hybrid.yaml` - Local primary + cloud fallback

## Usage

```python
from models.model_manager import get_model_manager

# Canonical access pattern
model = get_model_manager().get("role_name")

# DEPRECATED (will emit warnings)
# get_planner_model(), get_intent_model(), get_custom_model()
```

## Invariants

1. **One role → One model instance** (cached per process)
2. **YAML is the only authority** (no hardcoded model names)
3. **Agents depend on roles** (not on models directly)
4. **Changing a model = YAML edit only** (zero code changes)
