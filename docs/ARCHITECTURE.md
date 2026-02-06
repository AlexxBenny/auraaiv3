# AURA System Architecture (Phase 4)

> **Goal-Oriented, Parametric, Deterministic**

---

## 1. High-Level Design

AURA is a **hybrid** desktop automation system that combines:
1. **Classical Code**: Deterministic tools, DAG execution, safety enforcement.
2. **Modern AI**: Semantic goal extraction, dependency reasoning.

It avoids the "black box agent" problem by enforcing a strict separation between **Reasoning** (LLM) and **Execution** (Python).

---

## 2. Core Data Flow

```
User Input
    ↓
[QueryClassifier] → (Single vs Multi)
    ↓
    ├── If SINGLE:
    │   [IntentAgent] → Intent (e.g. "browser_control")
    │         ↓
    │   [ToolResolver] → Tool Selection (Legacy Path)
    │         ↓
    │   [Executor] → Tool Execution
    │
    └── If MULTI (Parametric Engine):
        [GoalInterpreter] → MetaGoal (Parametric Goals + Scopes)
              ↓
        [GoalOrchestrator] → Dependency Graph Construction
              ↓
        [GoalPlanner] → PlannedActions (per goal)
              ↓
        [PlanGraph] → Topological Execution
              ↓
        [ToolResolver] → Concrete Tool Mapping
              ↓
        [Executor] → Tool Execution
```

---

## 3. The Parametric Goal Engine (Phase 4)

The core innovation in Phase 4 is the move from "Typed Goals" to **Parametric Goals**.

### 3.1 Parametric Goal Structure
A goal is defined by `(domain, verb, params)`.
- **Domain**: Broad category (`browser`, `file`).
- **Verb**: Specific action (`navigate`, `create`).
- **Params**: Arguments strictly defined by schema (`url`, `selector`).

### 3.2 Planner Authority
The **GoalPlanner** is the single source of truth for action parameters. 
- The Planner defines `selector="input[name='q']"`.
- The Orchestrator injects this into the tool.
- The LLM in ToolResolver is **bypassed** for these critical parameters to prevent hallucination.

---

## 4. Safety Architecture

Safety is enforced at multiple layers:

### Layer 1: Schema Validation
- All LLM outputs are validated against Pydantic models.
- Invalid intent/goals cause immediate failure.

### Layer 2: Domain Locking
- Tools are segmented by domain.
- A `file_operation` intent can **only** access `files.*` tools.
- Fallback logic is strictly constrained.

### Layer 3: Deterministic Tools
- Tools are "dumb". They perform one atomic action.
- No retries, no loops within tools.
- Complexity is lifted to the Orchestrator.

---

## 5. Technology Stack

- **Language**: Python 3.11+
- **Browser Control**: Playwright (Headless/Headful)
- **LLM Provider**: Abstracted (Gemini, Ollama, OpenRouter)
- **Architecture**: Modular Monolith

---

## 6. Key Components

### QueryClassifier
Fast router that decides if a query is simple (single goal) or complex (multi goal).

### GoalInterpreter
The "Brain" of the multi-goal path. Translates natural language into structured Parametric Goals and Scope-based dependencies.

### GoalPlanner
The "Architect". Converts a high-level goal into a concrete, minimal action plan using table-driven rules.

### GoalOrchestrator
The "Conductor". Manages the dependency graph and executes plans in correct order.
