# Adding a New Intent to AURA

This checklist ensures all components are updated when adding a new intent.

---

## Checklist

### 1. Intent Agent (`agents/intent_agent.py`)

- [ ] Add intent to `INTENT_SCHEMA.properties.intent.enum` list
- [ ] Add comment describing the intent's purpose
- [ ] Add 2-3 few-shot examples in `FEW_SHOT_EXAMPLES`

```python
# Example:
"system_control",  # Volume, brightness, lock, power (actions)

# Few-shot example:
### system_control (NOT system_query - these CHANGE system state!)
User: "set volume to 50"
→ {"intent": "system_control", "confidence": 0.95, "reasoning": "Changing system volume"}
```

---

### 2. Tool Resolver (`core/tool_resolver.py`)

- [ ] Add intent to `INTENT_TOOL_DOMAINS` dict
- [ ] Map intent to appropriate tool domain prefixes

```python
# Example:
"system_control": ["system.audio", "system.display", "system.power"],
"clipboard_operation": ["system.clipboard"],
```

---

### 3. Orchestrator (`core/orchestrator.py`)

- [ ] Register handler in `_register_pipelines()` method
- [ ] Most intents use `self._handle_action`

```python
# Example:
self.router.register("system_control", self._handle_action)
self.router.register("clipboard_operation", self._handle_action)
```

---

### 4. Create Tools (if needed)

- [ ] Create tool files in appropriate directory
- [ ] Follow atomic tool structure (one action per tool)
- [ ] Declare all preconditions explicitly

---

## Intent-to-Handler Mapping

| Intent | Handler | Tool Domains |
|--------|---------|--------------|
| `application_launch` | `_handle_action` | `system.apps.launch` |
| `application_control` | `_handle_action` | `system.apps` |
| `window_management` | `_handle_action` | `system.window`, `system.virtual_desktop` |
| `system_query` | `_handle_action` | `system.state` |
| `system_control` | `_handle_action` | `system.audio`, `system.display`, `system.power`, `system.desktop`, `system.network` |
| `screen_capture` | `_handle_action` | `system.display` |
| `screen_perception` | `_handle_action` | `system.display` |
| `input_control` | `_handle_action` | `system.input` |
| `clipboard_operation` | `_handle_action` | `system.clipboard` |
| `file_operation` | `_handle_action` | `files` |
| `browser_control` | `_handle_action` | `system.apps.launch`, `browsers` |
| `office_operation` | `_handle_action` | `office` |
| `information_query` | `_handle_info` | (none - pure LLM) |
| `unknown` | `_handle_action` | (all domains - Stage 2) |

---

## Tool-Class Constraints (Safety Invariants)

Some intents must **NEVER** fallback to certain tool classes, even in Stage 2 global search.
This prevents dangerous "guessing" where input tools are executed for unrelated intents.

These constraints are defined in `INTENT_DISALLOWED_DOMAINS` in `core/tool_resolver.py`.

| Intent | Disallowed Domains | Rationale |
|--------|-------------------|-----------|
| `browser_control` | `system.input.*` | Browser automation ≠ raw mouse/keyboard |
| `file_operation` | `system.input.*` | File ops use file tools, not input |
| `office_operation` | `system.input.*` | Office ops use office tools, not input |
| `application_launch` | `system.input.*` | App launch uses shell, not input |
| `application_control` | `system.input.*` | App control uses window APIs |
| `window_management` | `system.input.*` | Window ops use system APIs |
| `screen_capture` | `system.input.*` | Screenshots don't need input |
| `screen_perception` | `system.input.*` | OCR/visual search doesn't need input |
| `information_query` | `system.input.*`, `system.apps.*`, `system.power.*` | Knowledge queries don't execute actions |

**Safety Invariant**: Physical input tools (`system.input.*`) are **opt-in only**, never guessed.
The only way to trigger input tools is via the `input_control` intent.

---

## Verification

After adding a new intent:

1. **Syntax check**: `python -m py_compile agents/intent_agent.py core/tool_resolver.py core/orchestrator.py`
2. **Test classification**: Run AURA and test a command that should trigger the new intent
3. **Check logs for**:
   - `Intent classified: <new_intent> (confidence)`
   - `ActionPipeline: processing...` (NOT FallbackPipeline)
   - `Stage 1 success` with `domain_match=True`

---

## Common Mistakes

| Symptom | Cause | Fix |
|---------|-------|-----|
| `No handler for intent 'X' -> fallback` | Missing Orchestrator handler | Add `router.register()` call |
| `Intent classified: unknown` | Missing few-shot examples | Add examples to `FEW_SHOT_EXAMPLES` |
| `Stage 2 domain mismatch` | Missing domain mapping | Add to `INTENT_TOOL_DOMAINS` |
| `No preferred domains for intent` | Intent not in domain map | Add intent key to `INTENT_TOOL_DOMAINS` |
| `Stage 2 aborted: all tools disallowed` | Safety constraint blocking | Check `INTENT_DISALLOWED_DOMAINS` |

---

## Files to Update (Summary)

```
agents/intent_agent.py      # Intent enum + few-shot examples
core/tool_resolver.py       # INTENT_TOOL_DOMAINS + INTENT_DISALLOWED_DOMAINS
core/orchestrator.py        # router.register() call
tools/<domain>/<tool>.py    # New tool files (if needed)
```

