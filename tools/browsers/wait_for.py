"""Tool: browsers.wait_for

Waits for an element to reach a specific state.

Category: browser_control
Risk Level: none
Side Effects: none (but blocks execution)

ARCHITECTURAL CONSTRAINTS (Phase 3.1):
- Tool performs exactly ONE wait (no loops, no retries)
- Tool fails loud on timeout
- Tool does NOT auto-retry
- Tool exists to make timing EXPLICIT
- This is the ONLY place implicit waiting is allowed
"""

import logging
from typing import Dict, Any
from tools.base import Tool


class WaitFor(Tool):
    """Wait for an element to reach a specific state.
    
    CONSTRAINT: Single wait, no retries.
    Fails loud on timeout. Makes timing explicit.
    """
    
    @property
    def name(self) -> str:
        return "browsers.wait_for"
    
    @property
    def description(self) -> str:
        return "Waits for an element to reach a specific state (attached, visible, hidden, detached)."
    
    @property
    def capability_class(self) -> str:
        return "actuate"  # Blocks execution until state change
    
    @property
    def risk_level(self) -> str:
        return "none"
    
    @property
    def side_effects(self) -> list[str]:
        return []  # No mutation, just waits
    
    @property
    def stabilization_time_ms(self) -> int:
        return 0
    
    @property
    def reversible(self) -> bool:
        return True
    
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
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector for the element to wait for"
                },
                "state": {
                    "type": "string",
                    "enum": ["attached", "visible", "hidden", "detached"],
                    "description": "State to wait for: attached (exists in DOM), visible, hidden, or detached (removed from DOM)",
                    "default": "visible"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Max wait time in ms. Fails loud on timeout. NOT a retry mechanism.",
                    "default": 5000
                },
                "session_id": {
                    "type": "string",
                    "description": "Optional browser session identifier. Uses default if omitted."
                }
            },
            "required": ["selector"]
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Wait for element state.
        
        INVARIANT: Single wait. No loops. No retries. Fail loud.
        """
        if not self.validate_args(args):
            return {"status": "error", "error": "Invalid arguments", "content": ""}
        
        selector = args.get("selector")
        state = args.get("state", "visible")
        timeout = args.get("timeout", 5000)
        session_id = args.get("session_id")
        
        if not selector:
            return {"status": "error", "error": "Selector is required", "content": ""}
        
        if state not in ("attached", "visible", "hidden", "detached"):
            return {"status": "error", "error": f"Invalid state: {state}", "content": ""}
        
        try:
            from core.browser_session_manager import BrowserSessionManager
            
            manager = BrowserSessionManager.get()
            session = manager.get_or_create(session_id=session_id)
            page = session.page
            
            # Single wait - no loops, no retries (architectural constraint)
            page.wait_for_selector(selector, state=state, timeout=timeout)
            
            logging.info(f"Wait complete: {selector} is {state}")
            return {
                "status": "success",
                "selector": selector,
                "state": state,
                "session_id": session.session_id,
                "content": f"Element {selector} is now {state}"
            }
            
        except Exception as e:
            # FAIL LOUD - no fallback, no retry
            logging.error(f"Wait timeout for '{selector}' state='{state}': {e}")
            return {
                "status": "error",
                "error": f"Wait timeout: {e}",
                "selector": selector,
                "state": state,
                "content": ""
            }
