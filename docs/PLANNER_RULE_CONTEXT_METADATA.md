Planner Rule Context Metadata
=============================

This document describes the three new planner rule fields that control semantic
context consumption and production. These fields are authoritative: planner
behavior must be declared in `core/planner_rules.py` and the planner must not
branch on domain/verb to implement context behavior.

- `allow_semantic_only` (bool)
  - Meaning: When true, the planner may accept a semantic goal that is missing
    technical params (for example, `browser.navigate` without a `url`) and
    produce semantic context instead of immediate execution.
  - Validation: Any params that are present must still be validated via
    `validate_params()`. The planner should not accept invalid values.

- `context_consumption` (dict)
  - Type: mapping from planner param name -> (context_domain, context_key)
  - Meaning: If the planner param is missing, the planner MAY fill it from an
    upstream `ContextFrame` whose `domain` == `context_domain` and whose data
    contains `context_key`.
  - Rules:
    - Planner fills only missing params; explicit params provided by the user
      (or interpreter) always win.
    - Planner must only read ContextFrames passed in by the Orchestrator (no
      global lookup).
    - Entries must be declared per rule in `PLANNER_RULES` (no code-side maps).

- `context_production` (object)
  - Type: `{ "domain": str, "keys": [str, ...] }`
  - Meaning: After successful `validate_params()`, the planner SHOULD produce a
    `ContextFrame` with the given `domain` and keys drawn from the validated
    params. Only validated, non-null keys are included.
  - Rules:
    - Production must occur after validation.
    - If no validated keys are available, do NOT produce a ContextFrame.
    - The produced `ContextFrame` must be immutable and include `produced_by`
      metadata (action/goal id) to support provenance.

Invariant (must be enforced)
----------------------------
Planner MUST NOT branch on domain/verb to implement context consumption or
production. All context behavior must be declared in `PLANNER_RULES` using the
fields above. Planner code should read these fields and act accordingly; it
should not contain ad-hoc domain-specific context logic.

Example (browser.search)
------------------------
```yaml
("browser","search"):
  intent: browser_control
  description_template: "search:{platform}:{query}"
  required_params: ["query"]
  default_params: {"platform": "google"}
  context_consumption:
    platform: ["browser", "platform"]
  context_production:
    domain: "browser"
    keys: ["platform"]
```

Governance note
---------------
- When adding new planner rules that need context semantics, add `context_consumption`
  and/or `context_production` to the rule rather than changing planner code.
- Keep context keys small and typed (scalars or small structured values). Avoid
  free-form text blobs.


