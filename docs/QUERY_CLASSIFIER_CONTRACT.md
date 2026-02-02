# QueryClassifier Contract

> **Semantic routing: single vs multi-goal queries**

---

## Purpose

`QueryClassifier.classify()` determines whether a user request contains:
- **SINGLE**: One atomic goal
- **MULTI**: Multiple goals (independent OR dependent)

```
User Input → "single" | "multi"
```

---

## Classification Rules

| Pattern | Classification | Example |
|---------|----------------|---------|
| One goal, multiple verbs | `single` | "open youtube and search nvidia" |
| Independent goals | `multi` | "open chrome and open spotify" |
| Dependent sequence | `multi` | "create folder and file inside it" |

---

## Syntactic Heuristics (Deterministic)

Before LLM classification, the classifier applies fast pattern matching:

### Dependency Patterns → `multi`

```python
DEPENDENCY_PATTERNS = [
    r'\b(inside|into|in)\s+(it|that|the)\b',
    r'\b(to|from)\s+(it|that|the)\b',
    r'\bthen\b',
    r'\bafter\s+that\b',
]
```

### Independent Multi Patterns → `multi`

```python
INDEPENDENT_MULTI_PATTERNS = [
    r'\bopen\s+\w+\s+and\s+open\s+\w+\b',
]
```

---

## Critical Distinction

```
"open youtube and search nvidia"
    → SINGLE (search IS the goal, youtube is context)

"create folder X and put file inside it"
    → MULTI (file depends on folder existing)
```

**Key invariant:** If action B references output/state of action A → `multi`

---

## LLM Fallback

When syntactic patterns don't match, the LLM classifies with few-shot examples:

```python
if self._has_dependency_pattern(user_input):
    return "multi"  # Fast, deterministic
if self._has_independent_multi_pattern(user_input):
    return "multi"  # Fast, deterministic
# Fall through to LLM
return self._llm_classify(user_input)
```

---

## Guarantees

| ID | Guarantee |
|----|-----------|
| G1 | Outputs ONLY "single" or "multi" |
| G2 | NEVER extracts actions (GoalInterpreter's job) |
| G3 | Dependent sequences → multi |
| G4 | Deterministic for syntactic patterns |

---

## What QueryClassifier Does NOT Do

| Responsibility | Who Handles It |
|----------------|----------------|
| Extract goals | GoalInterpreter |
| Plan actions | GoalPlanner |
| Execute | Executor |
