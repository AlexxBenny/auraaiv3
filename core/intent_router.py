"""Intent Router - Deterministic routing based on intent classification

JARVIS Architecture Role:
- Routes to intent-specific pipelines based on IntentAgent output
- AUTHORITATIVE: intent determines execution path, not just context
- Confidence gated: low confidence routes to fallback
"""

import logging
from typing import Dict, Any, Callable


CONFIDENCE_THRESHOLD = 0.75


class IntentRouter:
    """Routes to intent-specific pipelines (AUTHORITATIVE)."""
    
    def __init__(self):
        self.pipelines: Dict[str, Callable] = {}
        self.fallback_handler: Callable = None
        logging.info(f"IntentRouter initialized (threshold={CONFIDENCE_THRESHOLD})")
    
    def register(self, intent: str, handler: Callable):
        """Register a pipeline handler for an intent.
        
        Args:
            intent: Intent name (e.g., "information_query", "application_launch")
            handler: Function(user_input, context) -> dict
        """
        self.pipelines[intent] = handler
        logging.debug(f"Registered pipeline for intent: {intent}")
    
    def set_fallback(self, handler: Callable):
        """Set the fallback handler for unknown/low-confidence intents."""
        self.fallback_handler = handler
    
    def route(self, intent_result: Dict[str, Any], user_input: str, 
              context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Route to appropriate pipeline based on intent.
        
        Args:
            intent_result: Output from IntentAgent.classify()
            user_input: Original user input
            context: Current system context
            **kwargs: Additional args passed to handlers (e.g., progress)
            
        Returns:
            Pipeline result dict
        """
        intent = intent_result.get("intent", "unknown")
        confidence = intent_result.get("confidence", 0.0)
        
        # Confidence gating: low confidence -> fallback
        if confidence < CONFIDENCE_THRESHOLD:
            logging.info(
                f"Low confidence ({confidence:.2f} < {CONFIDENCE_THRESHOLD}) -> fallback"
            )
            if self.fallback_handler:
                return self.fallback_handler(user_input, context, **kwargs)
            return {
                "status": "error",
                "error": "No fallback handler configured",
                "intent": intent,
                "confidence": confidence
            }
        
        # High confidence: route to intent-specific pipeline
        handler = self.pipelines.get(intent)
        
        if handler:
            logging.info(f"Routing to {intent} pipeline (confidence={confidence:.2f})")
            return handler(user_input, context, **kwargs)
        
        # No handler for this intent: try fallback
        logging.warning(f"No handler for intent '{intent}' -> fallback")
        if self.fallback_handler:
            return self.fallback_handler(user_input, context, **kwargs)
        
        return {
            "status": "error",
            "error": f"No handler for intent: {intent}",
            "intent": intent,
            "confidence": confidence
        }
    
    def get_registered_intents(self) -> list:
        """Get list of registered intent handlers."""
        return list(self.pipelines.keys())
