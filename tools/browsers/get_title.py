"""Tool: browsers.get_title

Returns the current page title.

Category: browser_control
Risk Level: none
Side Effects: none

GUARDRAIL: Returns content key for coordinator compatibility.
"""

import logging
from typing import Dict, Any
from tools.base import Tool


class GetTitle(Tool):
    """Get current browser page title."""
    
    @property
    def name(self) -> str:
        return "browsers.get_title"
    
    @property
    def description(self) -> str:
        return "Returns the current page title from the browser."
    
    @property
    def risk_level(self) -> str:
        return "none"
    
    @property
    def side_effects(self) -> list[str]:
        return []
    
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
    def capability_class(self) -> str:
        """Observer tool - reads state without modification."""
        return "observe"
    
    @property
    def requires_focus(self) -> bool:
        return False
    
    @property
    def requires_unlocked_screen(self) -> bool:
        return False
    
    @property
    def requires_session(self) -> bool:
        """Reads require an active session to query page state."""
        return True
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Optional browser session identifier. Uses default if omitted."
                }
            },
            "required": []
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get current page title."""
        session_id = args.get("session_id")
        
        try:
            from core.browser_session_manager import BrowserSessionManager
            
            manager = BrowserSessionManager.get()
            
            # Get existing session
            if session_id:
                session = manager.get_or_create(session_id=session_id)
            else:
                session = manager.get_or_create()
            
            if not session or not session.is_active():
                return {
                    "status": "error",
                    "error": "No active browser session",
                    "failure_class": "logical",  # Session doesn't exist (not retryable)
                    "content": ""
                }
            
            from tools.browsers._engine.playwright import PlaywrightEngine
            engine = PlaywrightEngine()
            
            title = engine.get_title(session.page)
            
            return {
                "status": "success",
                "title": title,
                "session_id": session.session_id,
                "content": title
            }
            
        except Exception as e:
            logging.error(f"Get title failed: {e}")
            return {
                "status": "error",
                "error": f"Failed to get title: {e}",
                "failure_class": "environmental",  # Browser state issue (potentially retryable)
                "content": ""
            }
