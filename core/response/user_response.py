"""UserResponse - The GUI contract.

This is the ONLY output format the GUI consumes.
Orchestrator → from_orchestrator_result() → UserResponse → GUI

INVARIANT: No raw logs, traces, or internal messages leak through this layer.
INVARIANT: All text passes through _safe_text() before reaching GUI.
"""

from dataclasses import dataclass, field
from typing import Literal, Dict, Any, List, Optional


@dataclass
class UserResponse:
    """GUI-consumable response - the ONLY thing the GUI sees.
    
    Attributes:
        type: Response category for UI rendering
        content: Human-readable, curated text (never internal debug)
        confidence: 0.0-1.0 for optional UI indicators
        actions: Future: button actions for interactive responses
    """
    type: Literal["message", "progress", "clarification", "error"]
    content: str
    confidence: float = 1.0
    actions: List[Dict[str, str]] = field(default_factory=list)
    
    def to_websocket(self) -> Dict[str, Any]:
        """Format for WebSocket transmission."""
        return {
            "type": self.type,
            "message": self.content,
            "confidence": self.confidence,
            "actions": self.actions
        }


def _safe_text(text: str) -> str:
    """Sanitize text before sending to GUI.
    
    This is a choke point for future-proofing:
    - Strip whitespace
    - Filter debug patterns (if they ever leak)
    - Normalize formatting
    
    Currently minimal, but provides a single place to add guards.
    """
    if not text:
        return ""
    
    text = text.strip()
    
    # Future guards can be added here:
    # - Filter [DEBUG], [TRACE], etc.
    # - Truncate extremely long responses
    # - Escape problematic characters
    
    return text


def from_orchestrator_result(result: Dict[str, Any]) -> UserResponse:
    """Convert Orchestrator.process() output to UserResponse.
    
    This is the adapter layer that curates internal results for GUI consumption.
    
    Args:
        result: Raw output from Orchestrator.process()
        
    Returns:
        UserResponse safe for GUI display
        
    Contract:
        - Never expose stack traces
        - Never expose internal tool names directly
        - Always return valid UserResponse (no exceptions)
    """
    status = result.get("status", "unknown")
    result_type = result.get("type", "unknown")
    
    # === SUCCESS PATHS ===
    
    # Action success
    if result_type == "action" and status == "success":
        return UserResponse(
            type="message",
            content=_safe_text(result.get("response", "Done.")),
            confidence=result.get("confidence", 1.0)
        )
    
    # Information response
    if result_type == "information":
        return UserResponse(
            type="message",
            content=_safe_text(result.get("response", "")),
            confidence=result.get("confidence", 1.0)
        )
    
    # Fallback success
    if result_type == "fallback" and status == "success":
        return UserResponse(
            type="message",
            content=_safe_text(result.get("response", "Request processed.")),
            confidence=result.get("confidence", 0.8)
        )
    
    # Multi-action success
    if result_type == "multi" and status == "success":
        return UserResponse(
            type="message",
            content=_safe_text(result.get("response", "All actions completed.")),
            confidence=1.0
        )
    
    # === CLARIFICATION PATHS ===
    
    # Blocked or refused - needs clarification
    if status in ("blocked", "refused"):
        actions = []
        suggestion = result.get("suggestion")
        if suggestion:
            actions.append({"label": "Suggestion", "value": suggestion})
        
        return UserResponse(
            type="clarification",
            content=_safe_text(result.get("response") or result.get("reason", "Action blocked.")),
            actions=actions
        )
    
    # Explicit clarification needed
    if status == "clarification_needed":
        return UserResponse(
            type="clarification",
            content=_safe_text(result.get("response", "Could you please clarify?"))
        )
    
    # Partial success (multi-action)
    if status == "partial":
        return UserResponse(
            type="clarification",
            content=_safe_text(result.get("response", "Some actions completed, others failed."))
        )
    
    # === ERROR PATHS ===
    
    # Goal pipeline errors - respond maturely, don't hallucinate capabilities
    if result_type in ("goal_blocked", "unsupported_goal", "planning_failed"):
        reason = result.get("error", "")
        return UserResponse(
            type="clarification",
            content=_safe_text(
                f"I understand what you want, but I can't do that yet. {reason}" 
                if reason else 
                "I understand what you want, but I don't have the capability to do that yet."
            )
        )
    
    if status == "error":
        # CRITICAL: Never expose raw stack traces or internal errors
        # result.get("error") might contain Traceback - use response instead
        safe_message = result.get("response")
        if not safe_message:
            # Generate generic error, don't expose internals
            safe_message = "Something went wrong. Please try again."
        
        return UserResponse(
            type="error",
            content=_safe_text(safe_message)
        )
    
    # === FALLBACK ===
    
    # Unknown status/type - be safe
    return UserResponse(
        type="message",
        content=_safe_text(result.get("response", "Request processed.")),
        confidence=result.get("confidence", 0.5)
    )
