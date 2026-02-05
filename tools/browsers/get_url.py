"""Tool: browsers.get_url

Returns the current page URL.

Category: browser_control
Risk Level: none
Side Effects: none

GUARDRAIL: Returns content key for coordinator compatibility.
"""

import logging
from typing import Dict, Any
from tools.base import Tool


class GetUrl(Tool):
    """Get current browser URL."""
    
    @property
    def name(self) -> str:
        return "browsers.get_url"
    
    @property
    def description(self) -> str:
        return "Returns the current page URL from the browser."
    
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
        """Get current URL."""
        session_id = args.get("session_id")
        
        try:
            from core.browser_session_manager import BrowserSessionManager
            
            manager = BrowserSessionManager.get()
            
            # Get existing session (don't create new one for read)
            if session_id:
                session = manager.get_session(session_id)
            else:
                session = manager.get_or_create()
            
            if not session or not session.is_active():
                return {
                    "status": "error",
                    "error": "No active browser session",
                    "content": ""
                }
            
            from tools.browsers._engine.playwright import PlaywrightEngine
            engine = PlaywrightEngine()
            
            url = engine.get_url(session.page)
            
            return {
                "status": "success",
                "url": url,
                "session_id": session.session_id,
                "content": url
            }
            
        except Exception as e:
            logging.error(f"Get URL failed: {e}")
            return {
                "status": "error",
                "error": f"Failed to get URL: {e}",
                "content": ""
            }
