"""Tool: browsers.get_text

Reads text content of an element by CSS selector.

Category: browser_control
Risk Level: none
Side Effects: none

ARCHITECTURAL CONSTRAINTS (Phase 3):
- Tool is READ-ONLY (observe capability_class)
- Tool does NOT wait for elements (fail-fast)
- Tool does NOT trigger navigation
- Tool does NOT mutate page state
- If waiting is needed, use browsers.wait_for (Phase 3.1)
"""

import logging
from typing import Dict, Any
from tools.base import Tool


class GetText(Tool):
    """Get text content of an element.
    
    CONSTRAINT: Read-only operation. Fails fast if element not found.
    Does NOT use wait_for_selector - that belongs to wait_for tool.
    """
    
    @property
    def name(self) -> str:
        return "browsers.get_text"
    
    @property
    def description(self) -> str:
        return "Gets the text content of an element using a CSS selector. Read-only operation."
    
    @property
    def capability_class(self) -> str:
        return "observe"  # CRITICAL: This is a read-only observer
    
    @property
    def risk_level(self) -> str:
        return "none"
    
    @property
    def side_effects(self) -> list[str]:
        return []  # Pure read operation
    
    @property
    def stabilization_time_ms(self) -> int:
        return 0  # No state change
    
    @property
    def reversible(self) -> bool:
        return True  # No mutation
    
    @property
    def requires_visual_confirmation(self) -> bool:
        return False
    
    @property
    def requires_focus(self) -> bool:
        return False
    
    @property
    def requires_unlocked_screen(self) -> bool:
        return True
    
    @property
    def requires_session(self) -> bool:
        """GetText requires a session-backed page to query DOM."""
        return True
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector for the element to read (e.g., '#result', '.message')"
                },
                "session_id": {
                    "type": "string",
                    "description": "Optional browser session identifier. Uses default if omitted."
                }
            },
            "required": ["selector"]
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get text content of element.
        
        INVARIANT: Read-only. No waiting. Fail fast.
        Does NOT call wait_for_selector (architectural constraint).
        """
        if not self.validate_args(args):
            return {"status": "error", "error": "Invalid arguments", "content": ""}
        
        selector = args.get("selector")
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
                return {"status": "error", "error": "No active browser session", "failure_class": "logical", "content": ""}

            # Ensure page is live (heal if needed)
            if not getattr(session, "ensure_page", lambda: False)():
                return {"status": "error", "error": "Browser session unrecoverable", "failure_class": "environmental", "content": ""}
            page = session.page
            
            # FAIL FAST: No waiting. Use query_selector, not wait_for_selector.
            element = page.query_selector(selector)
            
            if element is None:
                return {
                    "status": "error",
                    "error": f"Element not found: {selector}",
                    "selector": selector,
                    "failure_class": "logical",  # Element doesn't exist (not retryable)
                    "content": ""
                }
            
            text = element.text_content() or ""
            
            logging.info(f"Got text from element: {selector} ({len(text)} chars)")
            return {
                "status": "success",
                "selector": selector,
                "text": text,
                "text_length": len(text),
                "session_id": session.session_id,
                "content": text
            }
            
        except Exception as e:
            logging.error(f"Get text failed for '{selector}': {e}")
            return {
                "status": "error",
                "error": f"Get text failed: {e}",
                "selector": selector,
                "failure_class": "logical",  # Read operation failure (not retryable)
                "content": ""
            }
