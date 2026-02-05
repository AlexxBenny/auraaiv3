# TODO: Goal Satisfaction Layer (Deferred)

## Status
🚧 **Deferred – Not implemented yet**  
This is a planned architectural enhancement. Current focus is on stabilizing browser automation and execution correctness.

---

## Problem Statement

AURA currently plans and executes goals correctly but **does not check whether a goal is already satisfied before executing it**.

This can lead to:
- Redundant actions (e.g., creating a folder that already exists)
- Repeated idempotent operations
- Potentially unsafe behavior for non-idempotent actions in the future

At present, this is acceptable because:
- Most file operations are idempotent
- The system prioritizes correctness of execution flow over optimization

However, this will not scale safely as:
- More domains are added
- Non-idempotent actions increase
- Long-running or stateful workflows are introduced

---

## What Is a Goal Satisfaction Layer?

A **Goal Satisfaction Layer** is a deterministic check performed *after planning but before execution*.

It answers a single question:

> **Is the intended outcome of this goal already true in the real world?**

If yes → skip execution  
If no → execute as planned

This layer:
- Does **not** use an LLM
- Does **not** perform reasoning
- Only evaluates real-world state via domain adapters

---

## Why This Is Needed (But Deferred)

LLMs:
- Are good at interpreting intent
- Are **not** reliable sources of truth about real-world state

Only the system (OS, APIs, tools) can determine:
- Whether a file exists
- Whether an app is running
- Whether a setting is already applied

Without a satisfaction layer:
- The system may repeat actions unnecessarily
- Execution correctness depends on idempotency
- Debugging becomes harder as workflows grow

Despite this, implementation is deferred because:
- Current tasks are safe
- Browser automation correctness is higher priority
- This layer introduces architectural surface area that should be added deliberately

---

## Conceptual Design (Future)

### Interface (Conceptual)

```python
class GoalSatisfactionProvider:
    def is_satisfied(goal, context) -> bool:
        ...
