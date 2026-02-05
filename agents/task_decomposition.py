"""Task Decomposition Agent - LLM-based decomposition of complex queries

This agent decomposes complex, multi-goal user queries into atomic subtasks
that can be processed independently by PlannerAgent.

LOCKED INVARIANTS (from v3 design):
- Outputs ONLY natural-language subtasks
- MUST NOT reference tools, effects, or execution
- MUST NOT reference intent categories
- Falls back to passthrough on any error

See: task_decomposition_agent_design_v3_final.md
"""

import logging
from typing import Dict, Any, List
from models.model_manager import get_model_manager


class TDAValidationError(Exception):
    """Raised when TDA output contains forbidden fields."""
    pass


class TaskDecompositionAgent:
    """
    LLM-based task decomposition.
    
    INVARIANTS (DO NOT VIOLATE):
    - Uses LLM reasoning only (no heuristics)
    - Outputs ONLY natural language subtasks
    - Does NOT reference tools, effects, or execution
    - Does NOT reference intent categories
    """
    
    TDA_SCHEMA = {
        "type": "object",
        "properties": {
            "decomposition_applied": {
                "type": "boolean",
                "description": "True if query was decomposed, False if atomic"
            },
            "original_goal": {
                "type": "string",
                "description": "Restatement of user's overall objective"
            },
            "subtasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "description": {"type": "string"},
                        "depends_on": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "is_optional": {"type": "boolean"}
                    },
                    "required": ["id", "description"]
                }
            },
            "ambiguity_detected": {"type": "boolean"},
            "ambiguity_notes": {"type": "string"}
        },
        "required": ["decomposition_applied", "original_goal", "subtasks"]
    }
    
    # Fields that MUST NOT appear in TDA output
    FORBIDDEN_FIELDS = {
        "tool", "tools", "effects", "steps", "args", 
        "confidence", "execute", "retry", "action_type",
        "intent", "postcondition", "precondition"
    }
    
    def __init__(self):
        # Role-based model access (config-driven)
        self.model = get_model_manager().get("tda")
        logging.info("TaskDecompositionAgent initialized")
    
    def decompose(self, user_input: str, intent: str = None) -> Dict[str, Any]:
        """
        Decompose user input into atomic subtasks.
        
        Args:
            user_input: Original user command
            intent: Initial intent classification (advisory only, not used in prompt)
            
        Returns:
            TDA output conforming to TDA_SCHEMA
        """
        prompt = f"""You are a task decomposition agent. Your job is to determine whether a user request needs to be broken down into smaller, atomic subtasks.

USER REQUEST: "{user_input}"

RULES:
1. If the request is already simple and atomic (single goal), set decomposition_applied = false and return empty subtasks array
2. If the request contains multiple goals, set decomposition_applied = true and list subtasks
3. Each subtask must be:
   - Self-contained (understandable in isolation)
   - Atomic (one goal only)
   - Natural language description only
4. Mark truly optional subtasks with is_optional = true

DEPENDENCY RULES (CRITICAL):
- Only add depends_on when the later subtask is LOGICALLY IMPOSSIBLE without the earlier one completing first
- Do NOT add dependencies merely because tasks appear sequential in language
- Do NOT assume that earlier tasks "enable" later tasks unless strictly required
- Independent tasks must have NO dependencies, even if listed later in the sentence
- When in doubt, DO NOT add a dependency

FORBIDDEN — DO NOT INCLUDE:
- Tool names or technical identifiers
- Implementation details
- System capabilities or limitations
- Execution steps or strategies
- Intent categories
- Effects or postconditions

OUTPUT JSON:
{{
  "decomposition_applied": true/false,
  "original_goal": "restatement of what user wants",
  "subtasks": [
    {{
      "id": "subtask_001",
      "description": "atomic natural language goal",
      "depends_on": [],  // ONLY if logically required
      "is_optional": false
    }}
  ],
  "ambiguity_detected": false,
  "ambiguity_notes": ""
}}

EXAMPLES:

Example 1 - Simple atomic request:
Input: "take a screenshot"
Output: {{ "decomposition_applied": false, "original_goal": "capture the current screen", "subtasks": [], "ambiguity_detected": false, "ambiguity_notes": "" }}

Example 2 - TRUE dependency (navigate requires browser open):
Input: "open chrome and go to gmail"
Output: {{
  "decomposition_applied": true,
  "original_goal": "access Gmail in Chrome browser",
  "subtasks": [
    {{ "id": "subtask_001", "description": "open the Chrome browser" }},
    {{ "id": "subtask_002", "description": "navigate to the Gmail website", "depends_on": ["subtask_001"] }}
  ],
  "ambiguity_detected": false,
  "ambiguity_notes": ""
}}

Example 3 - INDEPENDENT tasks (NO dependencies):
Input: "open chrome, delete system32, take a screenshot"
Output: {{
  "decomposition_applied": true,
  "original_goal": "perform three independent actions",
  "subtasks": [
    {{ "id": "subtask_001", "description": "open the Chrome browser" }},
    {{ "id": "subtask_002", "description": "delete the system32 folder" }},
    {{ "id": "subtask_003", "description": "take a screenshot" }}
  ],
  "ambiguity_detected": false,
  "ambiguity_notes": ""
}}
NOTE: These are INDEPENDENT. Screenshot does NOT depend on Chrome. Delete does NOT depend on Chrome.

Example 4 - Mixed dependencies:
Input: "open notepad, type hello, and set volume to 50%"
Output: {{
  "decomposition_applied": true,
  "original_goal": "type in notepad and adjust volume",
  "subtasks": [
    {{ "id": "subtask_001", "description": "open Notepad" }},
    {{ "id": "subtask_002", "description": "type the word hello", "depends_on": ["subtask_001"] }},
    {{ "id": "subtask_003", "description": "set system volume to 50 percent" }}
  ],
  "ambiguity_detected": false,
  "ambiguity_notes": ""
}}
NOTE: Typing depends on Notepad being open. Volume is INDEPENDENT.
"""
        
        try:
            result = self.model.generate(prompt, schema=self.TDA_SCHEMA)
            
            # Validate output does not contain forbidden fields
            self._validate_output(result)
            
            # Ensure required fields have defaults
            if "decomposition_applied" not in result:
                result["decomposition_applied"] = False
            if "original_goal" not in result:
                result["original_goal"] = user_input
            if "subtasks" not in result:
                result["subtasks"] = []
            if "ambiguity_detected" not in result:
                result["ambiguity_detected"] = False
            if "ambiguity_notes" not in result:
                result["ambiguity_notes"] = ""
            
            # Ensure subtask IDs are unique and properly formatted
            for i, subtask in enumerate(result.get("subtasks", [])):
                if "id" not in subtask:
                    subtask["id"] = f"subtask_{i+1:03d}"
                if "depends_on" not in subtask:
                    subtask["depends_on"] = []
                if "is_optional" not in subtask:
                    subtask["is_optional"] = False
            
            logging.info(f"TDA decomposed '{user_input[:50]}...' into {len(result.get('subtasks', []))} subtasks")
            return result
            
        except TDAValidationError as e:
            logging.error(f"TDA validation failed: {e}")
            # Hard fallback to passthrough
            return self._passthrough_result(user_input, f"Validation failed: {e}")
            
        except Exception as e:
            logging.error(f"TDA decomposition failed: {e}")
            # Hard fallback to passthrough
            return self._passthrough_result(user_input, str(e))
    
    def _validate_output(self, result: Dict[str, Any]) -> None:
        """
        Validate TDA output does not contain forbidden fields.
        
        Raises TDAValidationError if invalid.
        """
        def check_dict(d: Dict, path: str = ""):
            if not isinstance(d, dict):
                return
            for key, value in d.items():
                if key.lower() in self.FORBIDDEN_FIELDS:
                    raise TDAValidationError(f"Forbidden field '{key}' at {path}")
                if isinstance(value, dict):
                    check_dict(value, f"{path}.{key}")
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        if isinstance(item, dict):
                            check_dict(item, f"{path}.{key}[{i}]")
        
        check_dict(result, "root")
    
    def _passthrough_result(self, user_input: str, reason: str) -> Dict[str, Any]:
        """Create a passthrough result (no decomposition)."""
        return {
            "decomposition_applied": False,
            "original_goal": user_input,
            "subtasks": [],
            "ambiguity_detected": False,
            "ambiguity_notes": f"Passthrough: {reason}"
        }
