# AURA Execution Flow (Authoritative)

This document is the **single source of truth** for how a user query is
interpreted, planned, and executed in AURA.

Any code change that violates the invariants described here is an
**architectural regression**, not a feature.

---

## Core Architectural Invariants

1. **Single Authority per Concern**
   - Paths → PathResolver
   - Semantic tokens → SemanticResolver
   - Sessions → Session Managers (e.g. BrowserSessionManager)
   - Planning → GoalPlanner
   - Execution state → ToolExecutor

2. **Determinism**
   - Same input + same config ⇒ same plan & behavior
   - LLM output is normalized early

3. **No Hardcoding**
   - No branching on tool names, app names, OS paths
   - All behavior is metadata- or config-driven

4. **One Execution Model**
   - “single” vs “multi” is a routing optimization
   - There is ONE execution pipeline

---

## High-Level Pipeline

User Input
↓
QueryClassifier (syntactic only)
↓
Orchestrator
↓
GoalInterpreter
↓
SemanticResolver
↓
PathResolver
↓
GoalPlanner
↓
PlanGraph
↓
Plan-Scoped ToolExecutor
↓
Tools


---

## Phase 1: Query Classification

**Component:** QueryClassifier

- Purely syntactic
- Returns: `single` or `multi`
- No context
- No semantics

**Invariant**
> Classification does NOT decide execution logic.
> It only selects the entry path.

---

## Phase 2: Goal Interpretation

**Component:** GoalInterpreter

- Converts user intent into semantic Goals:
  - domain
  - verb
  - params
  - scope
- No execution logic
- No path resolution
- No session logic

**Dependency Derivation**
- Dependencies are derived **only** from `scope`
- LLM does not emit DAGs

---

## Phase 3: Semantic Token Resolution

**Component:** SemanticResolver

- Resolves explicit semantic tokens (e.g. `"default"`)
- Config-driven
- Deterministic

**Resolution Order**
1. Explicit user value
2. Semantic token
3. Planner default (if param missing)

**Invariant**
> Planner NEVER resolves semantic tokens.

---

## Phase 4: Path Resolution

**Component:** PathResolver

- Converts raw user paths → absolute filesystem paths
- Applies containment via dependencies
- Uses explicit base anchors (WORKSPACE, DESKTOP, DRIVE_D, etc.)

**Invariants**
- Planner NEVER sees raw paths
- Tools NEVER resolve paths
- PathResolver is the ONLY combiner of parent/child paths

---

## Phase 5: Planning

**Component:** GoalPlanner

- Table-driven planning via PLANNER_RULES
- Input: ONE Goal
- Output: ONE minimal Plan

**Characteristics**
- No per-domain planner methods
- No branching on goal type
- Fail-fast param validation
- Explicit context consumption & production

**Invariant**
> Goals describe WHAT.
> Planner maps WHAT → abstract actions.
> Tools decide HOW.

---

## Phase 6: Plan Graph Construction

**Component:** GoalOrchestrator

- Combines multiple single-goal plans
- Applies dependency DAG
- Produces PlanGraph

No execution occurs here.

---

## Phase 7: Plan-Scoped Execution

**Components:** Orchestrator, ExecutionCoordinator, ToolExecutor

### Executor Scoping

**Rule**
> Exactly ONE ToolExecutor per Plan execution.

- Executor is created at plan start
- Executor is discarded at plan end
- Executor is never reused across plans

---

### Session Acquisition

**Rule**
> Sessions are acquired ONCE per plan, NEVER per action.

**Mechanism**
- Orchestrator pre-scans planned actions
- If any tool declares `requires_session = True`:
  - Acquire session via SessionManager
  - Bind `session_id` to executor

**Per-Action Behavior**
- Tools attach to existing session via `session_id`
- Tools must NOT create sessions mid-plan

**Fallback**
- Only when executor is absent (standalone / test usage)

---

## Phase 8: Tool Resolution & Execution

**Components:** ToolResolver, ToolExecutor

- Abstract actions resolved to concrete tools
- `action_class` enforces side-effect class
- Executor injects execution-scoped metadata
- Tools are procedural only

---

## Repair & Retry

**Component:** ExecutionCoordinator

- Failures produce new Plans
- Each Plan gets a NEW executor
- Repair is bounded and explicit

---

## Summary of Non-Negotiable Rules

- One plan → one executor
- One executor → bounded execution state
- One concern → one authority
- No tool-level guessing
- No hidden resource creation
- Deterministic behavior always

Violating these rules is an **architectural error**.