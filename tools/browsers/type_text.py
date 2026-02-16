"""Tool: browsers.type_text

Types text into an input element by CSS selector.

Category: browser_control
Risk Level: low
Side Effects: page_state_change

ARCHITECTURAL CONSTRAINTS (Phase 3):
- Tool accepts selector from user/planner
- Tool does NOT infer or guess selectors
- Tool performs exactly ONE attempt (no retries)
- timeout = max wait for Playwright, NOT a retry mechanism
"""

import logging
from typing import Dict, Any
from tools.base import Tool


class TypeText(Tool):
    """Type text into an input element.
    
    CONSTRAINT: Selector must be provided by user or planner.
    This tool does NOT search the DOM or guess elements.
    """
    
    @property
    def name(self) -> str:
        return "browsers.type_text"
    
    @property
    def description(self) -> str:
        return "Types text into an input element using a CSS selector."
    
    @property
    def capability_class(self) -> str:
        return "actuate"
    
    @property
    def risk_level(self) -> str:
        return "low"
    
    @property
    def side_effects(self) -> list[str]:
        return ["page_state_change"]
    
    @property
    def stabilization_time_ms(self) -> int:
        return 300
    
    @property
    def reversible(self) -> bool:
        return True  # Can clear and retype
    
    @property
    def requires_visual_confirmation(self) -> bool:
        return True
    
    @property
    def requires_focus(self) -> bool:
        return False
    
    @property
    def requires_unlocked_screen(self) -> bool:
        return True
    
    @property
    def requires_session(self) -> bool:
        """Typing requires a session-backed page."""
        return True
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector for the input element (e.g., '#search-input', 'input[name=q]')"
                },
                "text": {
                    "type": "string",
                    "description": "Text to type into the element"
                },
                "clear_first": {
                    "type": "boolean",
                    "description": "Clear existing content before typing",
                    "default": True
                },
                "timeout": {
                    "type": "integer",
                    "description": "Max wait time in ms for element. NOT a retry mechanism - exactly one attempt.",
                    "default": 5000
                },
                "session_id": {
                    "type": "string",
                    "description": "Optional browser session identifier. Uses default if omitted."
                }
            },
            "required": ["selector", "text"]
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Type text into element.
        
        INVARIANT: Performs exactly one type attempt. No retries.
        """
        if not self.validate_args(args):
            return {"status": "error", "error": "Invalid arguments", "content": ""}
        
        selector = args.get("selector")
        text = args.get("text", "")
        clear_first = args.get("clear_first", True)
        timeout = args.get("timeout", 5000)
        session_id = args.get("session_id")
        
        if not selector:
            return {"status": "error", "error": "Selector is required", "content": ""}
        
        try:
            from core.browser_session_manager import BrowserSessionManager
            
            manager = BrowserSessionManager.get()
            if session_id:
                session = manager.get_or_create(session_id=session_id)
            else:
                session = manager.get_or_create()
            if not session:
                return {"status": "error", "error": "No active browser session", "content": ""}

            # Ensure page is live (heal if needed)
            if not getattr(session, "ensure_page", lambda: False)():
                return {"status": "error", "error": "Browser session unrecoverable", "failure_class": "environmental", "content": ""}
            page = session.page
            
            # Single attempt - no retries (architectural constraint)
            if clear_first:
                page.fill(selector, text, timeout=timeout)
            else:
                page.type(selector, text, timeout=timeout)
            
            logging.info(f"Typed into element: {selector}")
            return {
                "status": "success",
                "selector": selector,
                "text_length": len(text),
                "session_id": session.session_id,
                "content": f"Typed {len(text)} chars into {selector}"
            }
            
        except TimeoutError as e:
            logging.error(f"Type timeout for '{selector}': {e}")
            return {
                "status": "error",
                "error": f"Type timeout: {e}",
                "selector": selector,
                "failure_class": "environmental",  # Element not found yet (transient)
                "content": ""
            }
        except Exception as e:
            logging.error(f"Type failed for '{selector}': {e}")
            error_str = str(e).lower()
            # Determine failure class based on error type
            if "timeout" in error_str or "waiting" in error_str:
                failure_class = "environmental"  # Transient - element may appear later
            elif "not found" in error_str or "no element" in error_str:
                failure_class = "logical"  # Element doesn't exist (not retryable)
            else:
                failure_class = "environmental"  # Default to environmental for browser ops
            return {
                "status": "error",
                "error": f"Type failed: {e}",
                "selector": selector,
                "failure_class": failure_class,
                "content": ""
            }
