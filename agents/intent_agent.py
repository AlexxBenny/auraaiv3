"""Intent Agent - Classifies user intent (cheap, fast model)

NO reasoning. NO tools. Just classification.
"""

import logging
from typing import Dict, Any
from models.model_manager import get_model_manager


class IntentAgent:
    """Classifies user intent into categories"""
    
    INTENT_SCHEMA = {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "enum": [
                    "system_control",
                    "file_operation",
                    "web_search",
                    "information_query",
                    "application_launch",
                    "unknown"
                ]
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1
            }
        },
        "required": ["intent", "confidence"]
    }
    
    def __init__(self):
        self.model = get_model_manager().get_intent_model()
        logging.info("IntentAgent initialized")
    
    def classify(self, user_input: str) -> Dict[str, Any]:
        """Classify user intent
        
        Args:
            user_input: Raw user text
            
        Returns:
            {
                "intent": "system_control",
                "confidence": 0.92
            }
        """
        prompt = f"""Classify the user's intent from this input:

"{user_input}"

Respond with JSON containing:
- intent: one of the predefined categories
- confidence: how confident you are (0.0 to 1.0)

Intent categories:
- system_control: Control system settings (volume, brightness, etc.)
- file_operation: Create, read, write, delete files
- web_search: Search the web or fetch information
- information_query: Ask questions or get information
- application_launch: Open or launch applications
- unknown: Cannot determine intent
"""
        
        try:
            result = self.model.generate(prompt, schema=self.INTENT_SCHEMA)
            
            # Ensure confidence is a float
            if "confidence" in result:
                result["confidence"] = float(result["confidence"])
            
            logging.info(f"Intent classified: {result}")
            return result
            
        except Exception as e:
            logging.error(f"Intent classification failed: {e}")
            return {
                "intent": "unknown",
                "confidence": 0.0
            }

