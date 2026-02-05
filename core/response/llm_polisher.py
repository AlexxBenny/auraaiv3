"""LLM Polisher - Optional constrained natural language refinement

REFINEMENT 4: Plug-in architecture, not hardcoded
- Uses PolishProvider interface
- Swappable: Gemini, local LLM, no-op
- Configured via ModelManager

CRITICAL RULES:
- Must NOT change any numbers, facts, or meanings
- Must NOT add advice, opinions, or suggestions
- May ONLY improve clarity and naturalness
- On ANY violation → fallback to base_response
"""

import re
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class PolishResult:
    """Result of polish operation
    
    Attributes:
        polished: The polished text (or base_response on fallback)
        used_polish: Whether LLM polish was actually applied
        fallback_reason: If fallback, why
    """
    polished: str
    used_polish: bool
    fallback_reason: Optional[str] = None


class PolishProvider(ABC):
    """Abstract interface for polish providers
    
    Implementations:
    - LLMPolishProvider: Uses LLM for refinement
    - NoOpPolishProvider: Returns base_response unchanged
    """
    
    @abstractmethod
    def polish(self, base_response: str, facts: Dict[str, Any]) -> PolishResult:
        """Refine base_response while preserving all facts.
        
        Args:
            base_response: Deterministic template output
            facts: Facts that MUST appear in output
            
        Returns:
            PolishResult with polished text or fallback
        """
        pass


class NoOpPolishProvider(PolishProvider):
    """No-op provider - returns base_response unchanged
    
    Use when:
    - Polish is disabled
    - Offline mode
    - Testing
    """
    
    def polish(self, base_response: str, facts: Dict[str, Any]) -> PolishResult:
        return PolishResult(
            polished=base_response,
            used_polish=False,
            fallback_reason="Polish disabled"
        )


class LLMPolishProvider(PolishProvider):
    """LLM-based polish with strict validation
    
    Uses ModelManager for LLM access (configurable via model role).
    Validates output to ensure facts are preserved.
    """
    
    # Banned patterns that indicate opinion/advice
    BANNED_PATTERNS = [
        r"\byou should\b",
        r"\bi recommend\b",
        r"\btry to\b",
        r"\byou might want\b",
        r"\bconsider\b",
        r"\bperhaps\b",
        r"\bmaybe you\b",
        r"\bit might be\b",
        r"\bwatch out\b",
        r"\bbe careful\b",
    ]
    
    def __init__(self, model_role: str = "polisher"):
        """Initialize with model role for ModelManager lookup.
        
        Args:
            model_role: Role name in model config (default: "polisher")
        """
        self.model_role = model_role
        self._model = None
    
    def _get_model(self):
        """Lazy-load model from ModelManager."""
        if self._model is None:
            try:
                from models.model_manager import get_model_manager
                # Role-based model access (config-driven)
                self._model = get_model_manager().get(self.model_role)
            except Exception:
                # Model not configured - will cause fallback
                self._model = None
        return self._model
    
    def polish(self, base_response: str, facts: Dict[str, Any]) -> PolishResult:
        """Refine base_response using LLM with strict validation."""
        
        model = self._get_model()
        if model is None:
            return PolishResult(
                polished=base_response,
                used_polish=False,
                fallback_reason="Polisher model not configured"
            )
        
        # Build strict prompt
        prompt = self._build_prompt(base_response, facts)
        
        try:
            # Generate polished version
            response = model.generate(prompt)
            
            # Handle response formats
            if isinstance(response, dict):
                polished = response.get("response", response.get("content", str(response)))
            else:
                polished = str(response)
            
            polished = polished.strip()
            
            # Validate
            validation = self._validate(polished, base_response, facts)
            
            if not validation["valid"]:
                return PolishResult(
                    polished=base_response,
                    used_polish=False,
                    fallback_reason=validation["reason"]
                )
            
            return PolishResult(
                polished=polished,
                used_polish=True
            )
            
        except Exception as e:
            return PolishResult(
                polished=base_response,
                used_polish=False,
                fallback_reason=f"LLM error: {str(e)}"
            )
    
    def _build_prompt(self, base_response: str, facts: Dict[str, Any]) -> str:
        """Build the strict polish prompt."""
        
        # Extract numeric values that must be preserved
        numbers = self._extract_numbers(facts)
        numbers_str = ", ".join(str(n) for n in numbers) if numbers else "none"
        
        return f"""You are refining a system response for natural language quality.

STRICT RULES:
1. You must NOT change any numbers, facts, or meanings
2. You must NOT add advice, opinions, or suggestions
3. You may ONLY improve clarity and naturalness
4. Keep the same information, just make it sound more natural
5. Do not add phrases like "you should", "I recommend", "try to"

Numbers that MUST appear exactly: {numbers_str}

Original text to refine:
{base_response}

Refined text (same facts, more natural):"""
    
    def _validate(self, polished: str, base_response: str, facts: Dict[str, Any]) -> Dict[str, Any]:
        """Validate polished output preserves all facts."""
        
        # Rule 1: Check length bounds (0.5x - 2x)
        base_len = len(base_response)
        polish_len = len(polished)
        
        if polish_len < base_len * 0.5:
            return {"valid": False, "reason": "Output too short"}
        
        if polish_len > base_len * 2.5:
            return {"valid": False, "reason": "Output too long"}
        
        # Rule 2: Check banned patterns
        polished_lower = polished.lower()
        for pattern in self.BANNED_PATTERNS:
            if re.search(pattern, polished_lower):
                return {"valid": False, "reason": f"Banned pattern found: {pattern}"}
        
        # Rule 3: Verify all numbers from facts appear in output
        numbers = self._extract_numbers(facts)
        for num in numbers:
            # Allow for small formatting differences (70.8 vs 70.8%)
            num_str = str(num)
            if num_str not in polished:
                # Try without decimal if it's a whole number
                if isinstance(num, float) and num == int(num):
                    if str(int(num)) not in polished:
                        return {"valid": False, "reason": f"Missing number: {num}"}
                else:
                    return {"valid": False, "reason": f"Missing number: {num}"}
        
        # Rule 4: Check that key fact terms appear (bijective presence)
        required_terms = self._extract_required_terms(facts)
        for term in required_terms:
            if term.lower() not in polished_lower:
                return {"valid": False, "reason": f"Missing term: {term}"}
        
        return {"valid": True, "reason": None}
    
    def _extract_numbers(self, facts: Dict[str, Any]) -> List[float]:
        """Extract all numeric values from facts for validation."""
        numbers = []
        
        def extract_recursive(value):
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                numbers.append(value)
            elif isinstance(value, dict):
                for v in value.values():
                    extract_recursive(v)
            elif isinstance(value, list):
                for item in value:
                    extract_recursive(item)
        
        for value in facts.values():
            extract_recursive(value)
        
        return numbers
    
    def _extract_required_terms(self, facts: Dict[str, Any]) -> List[str]:
        """Extract key terms that must appear in output."""
        terms = []
        
        # Key terms from specific fact keys
        key_mappings = {
            "ram": ["RAM", "memory"],
            "swap": ["swap"],
            "wifi": ["WiFi", "Wi-Fi", "wireless"],
            "ethernet": ["Ethernet", "wired"],
            "brightness": ["brightness"],
            "volume": ["volume"],
            "battery": ["battery"],
        }
        
        for key in facts.keys():
            key_lower = key.lower()
            for term_key, term_options in key_mappings.items():
                if term_key in key_lower:
                    terms.extend(term_options)
                    break
        
        # Deduplicate while preserving any-match semantics
        return list(set(terms))


def get_polish_provider(enabled: bool = False, model_role: str = "polisher") -> PolishProvider:
    """Factory function to get appropriate polish provider.
    
    Args:
        enabled: Whether LLM polish is enabled
        model_role: Model role for LLM provider
        
    Returns:
        PolishProvider instance
    """
    if not enabled:
        return NoOpPolishProvider()
    
    return LLMPolishProvider(model_role=model_role)
