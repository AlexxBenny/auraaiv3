# Goal Interpreter Contract (Phase 4)

> **Contract for Semantic Goal Extraction & Scope Resolution**

---

## 1. Purpose

`GoalInterpreter.interpret()` transforms raw user input into a **MetaGoal** containing structured **Parametric Goals** and a deterministically derived **Dependency DAG**.

```
User Input → LLM → Parametric Goals + Scopes → Dependency Resolver → MetaGoal
```

---

## 2. Parametric Goal Structure

Goals are no longer typed (e.g. `browser_search`). They are **domain-verb tuples**.

```python
@dataclass(frozen=True)
class Goal:
    domain: str                  # "browser", "file", "system"
    verb: str                    # "navigate", "wait", "click"
    params: Dict[str, Any]       # {"url": "...", "selector": "..."}
    object: Optional[str] = None # "title"
    scope: str = "root"          # "after:navigate", "inside:docs"
    
    # Internal
    goal_id: str                 # "g0", "g1" (Auto-assigned)
```

### 2.1 Domain/Verb Open Set
The interpreter allows **any** domain/verb pair that the Planner supports.
Common examples:
- `browser.navigate`
- `browser.wait`
- `browser.click`
- `file.create`
- `system.launch`

---

## 3. Scope Resolution & Dependencies

The interpreter is the **Single Authority** for dependencies. The LLM outputs `scope` strings, which are deterministically resolved to integer dependencies.

### 3.1 Supported Scopes

| Scope Format | Resolution Strategy | Example |
|--------------|---------------------|---------|
| `root` | Independent | `browser.navigate` |
| `after:<verb>` | Depends on **first goal** with this verb | `scope="after:navigate"` |
| `after:<id>` | Depends on goal with this ID | `scope="after:g0"` |
| `inside:<target>` | Depends on file op creating this target | `scope="inside:my_folder"` |
| `drive:<D>` | Sets base anchor (no logic dependency) | `scope="drive:C"` |

### 3.2 Resolution Algorithm

1. **Assign IDs**: `g0`, `g1`, `g2` assigned sequentially.
2. **Build Maps**:
   - `id_map`: `{"g0": 0, "g1": 1}`
   - `verb_map`: `{"navigate": 0, "wait": 1}` (First win)
   - `target_map`: `{"my_folder": 0}`
3. **Resolve**:
   - `after:navigate` → Look up "navigate" in `verb_map` → Index 0
   - `after:g0` → Look up "g0" in `id_map` → Index 0

### 3.3 Graph Validation
- **No Forward References**: A goal can only depend on previous goals ($i > j$).
- **No Self-References**: A goal cannot depend on itself.
- **DAG Guarantee**: The resulting graph is guaranteed to be acyclic.

---

## 4. Output Contract (MetaGoal)

```python
@dataclass
class MetaGoal:
    meta_type: Literal["single", "independent_multi", "dependent_multi"]
    goals: Tuple[Goal, ...]
    dependencies: FrozenDict[int, Tuple[int, ...]]
```

### Example Output
**Input:** `"go to google and wait for the search box"`

```python
MetaGoal(
    meta_type="dependent_multi",
    goals=(
        Goal(id="g0", domain="browser", verb="navigate", params={url: "google.com"}),
        Goal(id="g1", domain="browser", verb="wait", scope="after:navigate")
    ),
    dependencies={
        1: (0,)  # g1 depends on g0
    }
)
```

---

## 5. Safety & Errors

| Condition | Response |
|-----------|----------|
| **Unknown Verb** | Accepted by Interpreter (Planner will reject if unsupported) |
| **Invalid Scope** | Logged as warning, dependency dropped (Soft Fail) |
| **Forward Dependency** | Logged as error, dependency dropped (Cycle prevention) |

---

## 6. What Changed in Phase 4?

- **Removed `goal_type`**: Replaced by `domain` + `verb`.
- **Flexible Scopes**: Supports `after:verb` (natural LLM output) alongside `after:ID`.
- **Internal IDs**: `g0`, `g1` automatically managed.
