"""Plan Repair Prompt - LLM-based goal recovery for partial failures.

INVARIANTS:
- LLM produces NEW goals, not tool calls
- Goals use existing (domain, verb, params) schema
- No retry-at-tool-level
- Constrained to original domain/verb set
"""


PLAN_REPAIR_PROMPT = """You are a plan repair assistant for a desktop automation system.

Some actions in the original plan failed with recoverable errors. Your job is to determine if the user's goal can still be achieved through alternative actions.

## Original Goals
{original_goals}

## Completed Actions (succeeded)
{completed}

## Failed Actions (recoverable)
{failed}

## Rules
1. You may ONLY use domain/verb pairs from the original goals (no new domains or verbs)
2. You may NOT introduce new domains
3. You may NOT retry the exact same action with same params
4. You may propose alternative approaches (e.g., if wait failed, try without wait)
5. You may skip unnecessary actions if the goal is already achievable
6. Return empty repaired_goals if the failure is unrecoverable
7. The terminal goal must be preserved as the LAST goal (same verb as original terminal goal)

## Response Format
Return JSON with:
- skip_remaining: bool - True if goal is already achieved
- repaired_goals: list of {{domain, verb, params}} - Alternative goals to try
- reasoning: str - Brief explanation of repair strategy
"""


PLAN_REPAIR_SCHEMA = {
    "type": "object",
    "properties": {
        "skip_remaining": {
            "type": "boolean",
            "description": "True if the goal is already achieved and no more actions needed"
        },
        "repaired_goals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "domain": {"type": "string"},
                    "verb": {"type": "string"},
                    "params": {"type": "object"}
                },
                "required": ["domain", "verb"]
            }
        },
        "reasoning": {
            "type": "string",
            "description": "Brief explanation of repair strategy"
        }
    },
    "required": ["skip_remaining", "repaired_goals", "reasoning"]
}
