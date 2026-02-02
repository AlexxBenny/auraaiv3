"""Hybrid Provider - Local-first with cloud fallback on infrastructure failures

INVARIANT: Fallback occurs ONLY on ProviderUnavailableError.
All other exceptions (ValueError, semantic errors) propagate normally.

This preserves:
- Determinism
- Reproducibility  
- Debuggability
"""

import logging
from typing import Dict, Any, Optional
from .base import BaseLLMProvider
from ..exceptions import ProviderUnavailableError


class HybridProvider(BaseLLMProvider):
    """Wrapper: tries primary provider, falls back ONLY on infrastructure failures.
    
    MODE CONTRACT:
    - hybrid = local-first, cloud ONLY on infra failure
    - Never "cloud when local output is bad" - that would be adaptive AI
    - AURA is deterministic automation
    """
    
    def __init__(self, primary: BaseLLMProvider, fallback: BaseLLMProvider, role: str):
        """Initialize HybridProvider.
        
        Args:
            primary: Primary provider (typically local/Ollama)
            fallback: Fallback provider (typically hosted/Gemini)
            role: Role name for logging (e.g., 'planner', 'intent')
        """
        super().__init__(api_key=None)
        self.primary = primary
        self.fallback = fallback
        self.role = role
        self.model = f"{primary.model}→{fallback.model}"  # For identification
    
    def generate(self, prompt: str, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate response, falling back ONLY on infrastructure failures.
        
        Fallback triggers:
        - ProviderUnavailableError (connection, timeout, 5xx, missing key)
        
        NO fallback:
        - ValueError (malformed output, schema failure)
        - RuntimeError (4xx errors, client errors)
        - Any other exception (logic bugs)
        """
        try:
            return self.primary.generate(prompt, schema)
        except ProviderUnavailableError as e:
            logging.warning(
                f"[HYBRID][{self.role}] Primary {self.primary.model} unavailable: {e} "
                f"→ falling back to {self.fallback.model}"
            )
            return self.fallback.generate(prompt, schema)
        # All other exceptions propagate - no silent model switching
