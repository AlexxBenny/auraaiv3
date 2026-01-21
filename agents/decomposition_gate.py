"""Decomposition Gate - Cheap LLM gate for single/multi goal classification

LOCKED INVARIANT: This gate is STRUCTURAL, not SEMANTIC.
It MUST NOT infer intent, feasibility, safety, or complexity.
It only decides: "Does this request contain one goal or multiple goals?"

See: task_decomposition_agent_design_v3_final.md - Invariant 1
"""

import logging
from typing import Dict, Any
from models.model_manager import get_model_manager


class DecompositionGate:
    """
    Cheap LLM gate to decide if full Task Decomposition is needed.
    
    This is NOT a heuristic. It uses LLM reasoning with minimal cost.
    
    INVARIANTS (DO NOT VIOLATE):
    - Decides structure only (single vs multi-goal)
    - MUST NOT infer intent
    - MUST NOT infer feasibility
    - MUST NOT infer safety
    - MUST NOT reference tools or capabilities
    """
    
    GATE_SCHEMA = {
        "type": "object",
        "properties": {
            "classification": {
                "type": "string",
                "enum": ["single", "multi"]
            }
        },
        "required": ["classification"]
    }
    
    def __init__(self):
        self.model = get_model_manager().get_custom_model("gate")
        logging.info("DecompositionGate initialized")
    
    def classify(self, user_input: str) -> str:
        """
        Classify input as single or multi-goal.
        
        Args:
            user_input: Raw user command
            
        Returns:
            "single" or "multi"
        """
        prompt = f"""Classify whether this user request contains a single goal or multiple goals.

USER REQUEST: "{user_input}"

SINGLE = one atomic action or question
MULTI = multiple actions, sequential steps, or compound goals

IMPORTANT: Do not consider feasibility, safety, or system capabilities.
Only judge whether the request contains more than one goal.

Respond with JSON: {{"classification": "single"}} or {{"classification": "multi"}}
"""
        
        try:
            result = self.model.generate(prompt, schema=self.GATE_SCHEMA)
            classification = result.get("classification", "single")
            logging.info(f"DecompositionGate classified: '{user_input[:50]}...' -> {classification}")
            return classification
        except Exception as e:
            # Fallback: assume single (cheaper path, safe default)
            logging.warning(f"DecompositionGate failed: {e}, defaulting to 'single'")
            return "single"
