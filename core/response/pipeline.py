"""Response Pipeline - Coordinates fact extraction, base response, and optional polish

REFINEMENT 2: Side-effect free
- No logging, memory storage, or I/O
- Pure function: (tool_name, result) → ResponseResult
- Memory storage lives outside this pipeline

This is the unified response layer for both action and query results.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass

from .fact_extractor import extract_facts, ExtractedFacts
from .base_response import generate_base_response
from .llm_polisher import get_polish_provider, PolishResult


@dataclass
class ResponseResult:
    """Complete response pipeline result
    
    Attributes:
        facts: Extracted facts (memory-safe, source of truth)
        base_response: Deterministic template response
        final_response: User-facing response (base or polished)
        polish_applied: Whether LLM polish was used
        polish_fallback_reason: If polish failed, why
    """
    facts: ExtractedFacts
    base_response: str
    final_response: str
    polish_applied: bool = False
    polish_fallback_reason: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for serialization."""
        return {
            "facts": {
                "facts": self.facts.facts,
                "summary": self.facts.summary,
                "tool": self.facts.tool,
                "status": self.facts.status
            },
            "base_response": self.base_response,
            "final_response": self.final_response,
            "polish_applied": self.polish_applied,
            "polish_fallback_reason": self.polish_fallback_reason
        }


class ResponsePipeline:
    """Coordinates fact extraction, base response, and optional polish.
    
    PURE - No side effects. Memory storage is caller's responsibility.
    
    Usage:
        pipeline = ResponsePipeline(polish_enabled=False)
        result = pipeline.generate("system.state.get_memory_usage", tool_result)
        print(result.final_response)
    """
    
    def __init__(self, polish_enabled: bool = False, polish_model_role: str = "polisher"):
        """Initialize response pipeline.
        
        Args:
            polish_enabled: Whether to use LLM polish (default: False)
            polish_model_role: Model role for LLM polisher
        """
        self.polish_enabled = polish_enabled
        self.polish_provider = get_polish_provider(
            enabled=polish_enabled,
            model_role=polish_model_role
        )
    
    def generate(self, tool_name: str, result: Dict[str, Any]) -> ResponseResult:
        """Generate response from tool result.
        
        PURE FUNCTION - No side effects.
        
        Args:
            tool_name: Full tool name (e.g., "system.state.get_memory_usage")
            result: Raw tool execution result
            
        Returns:
            ResponseResult with facts and responses
        """
        # Step 1: Extract facts (deterministic)
        extracted = extract_facts(tool_name, result)
        
        # Step 2: Generate base response (templates)
        base = generate_base_response(extracted)
        
        # Step 3: Optional polish (guarded LLM)
        if self.polish_enabled:
            polish_result = self.polish_provider.polish(base, extracted.facts)
            final = polish_result.polished
            polish_applied = polish_result.used_polish
            fallback_reason = polish_result.fallback_reason
        else:
            final = base
            polish_applied = False
            fallback_reason = "Polish disabled"
        
        return ResponseResult(
            facts=extracted,
            base_response=base,
            final_response=final,
            polish_applied=polish_applied,
            polish_fallback_reason=fallback_reason
        )
    
    def generate_for_status(self, tool_name: str, status: str, 
                           reason: Optional[str] = None) -> ResponseResult:
        """Generate response for non-success statuses without full result.
        
        Useful for blocked, refused, or error statuses.
        
        Args:
            tool_name: Tool that was attempted
            status: Status code (blocked, refused, error, etc.)
            reason: Optional reason for the status
            
        Returns:
            ResponseResult with appropriate message
        """
        # Create minimal result dict for extraction
        result = {
            "status": status,
            "reason": reason,
            "error": reason  # For error status
        }
        
        return self.generate(tool_name, result)


# Module-level singleton for convenience
_default_pipeline: Optional[ResponsePipeline] = None


def get_response_pipeline(polish_enabled: bool = False) -> ResponsePipeline:
    """Get or create default response pipeline.
    
    Args:
        polish_enabled: Whether to enable LLM polish
        
    Returns:
        ResponsePipeline instance
    """
    global _default_pipeline
    
    # Always create new if polish setting changed
    if _default_pipeline is None or _default_pipeline.polish_enabled != polish_enabled:
        _default_pipeline = ResponsePipeline(polish_enabled=polish_enabled)
    
    return _default_pipeline


def generate_response(tool_name: str, result: Dict[str, Any], 
                      polish_enabled: bool = False) -> ResponseResult:
    """Convenience function for one-shot response generation.
    
    Args:
        tool_name: Full tool name
        result: Tool execution result
        polish_enabled: Whether to use LLM polish
        
    Returns:
        ResponseResult
    """
    pipeline = get_response_pipeline(polish_enabled)
    return pipeline.generate(tool_name, result)
