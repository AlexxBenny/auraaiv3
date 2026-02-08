"""Tool: browsers.navigate

Navigates the current page to a URL.

Category: browser_control
Risk Level: low
Side Effects: network_request
"""

import logging
from typing import Dict, Any
from tools.base import Tool


class Navigate(Tool):
    """Navigate browser to URL."""
    
    @property
    def name(self) -> str:
        return "browsers.navigate"
    
    @property
    def description(self) -> str:
        return "Navigates the browser to a specified URL."
    
    @property
    def risk_level(self) -> str:
        return "low"
    
    @property
    def side_effects(self) -> list[str]:
        return ["network_request"]
    
    @property
    def stabilization_time_ms(self) -> int:
        return 2000
    
    @property
    def reversible(self) -> bool:
        return True  # Can navigate back
    
    @property
    def requires_visual_confirmation(self) -> bool:
        return True
    
    @property
    def requires_focus(self) -> bool:
        return False
    
    @property
    def requires_unlocked_screen(self) -> bool:
        return False
    
    @property
    def requires_session(self) -> bool:
        """Navigate operates on a session-backed browser/page."""
        return True

    @property
    def required_semantic_inputs(self) -> set:
        """Navigate requires a planner-provided URL."""
        return {"url"}

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to navigate to (e.g., 'https://google.com' or 'google.com')"
                },
                "session_id": {
                    "type": "string",
                    "description": "Optional browser session identifier. Uses default if omitted."
                }
            },
            "required": ["url"]
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Navigate to URL."""
        if not self.validate_args(args):
            return {"status": "error", "error": "Invalid arguments", "content": ""}
        
        url = args.get("url")
        session_id = args.get("session_id")
        
        if not url:
            return {"status": "error", "error": "URL is required", "content": ""}
        
        try:
            from core.browser_session_manager import BrowserSessionManager
            from core.browser_config import BrowserConfig
            
            manager = BrowserSessionManager.get()
            config = BrowserConfig.get().settings
            
            # Prefer provided session_id (do NOT recreate); otherwise create default
            if session_id:
                session = manager.get_session(session_id)
            else:
                session = manager.get_or_create()
            if not session or not session.is_active():
                return {
                    "status": "error",
                    "error": "No active browser session",
                    "failure_class": "logical",
                    "content": ""
                }
            
            # Navigate using engine
            from tools.browsers._engine.playwright import PlaywrightEngine
            engine = PlaywrightEngine()
            
            success = engine.navigate(
                session.page, 
                url, 
                timeout_ms=config.timeout_ms
            )
            
            if success:
                final_url = engine.get_url(session.page)
                return {
                    "status": "success",
                    "url": final_url,
                    "session_id": session.session_id,
                    "content": final_url
                }
            else:
                return {
                    "status": "error",
                    "error": f"Navigation to {url} failed",
                    "failure_class": "environmental",  # Timeout/network failure
                    "content": ""
                }
                
        except TimeoutError as e:
            return {
                "status": "error",
                "error": str(e),
                "failure_class": "environmental",  # Network timeout
                "content": ""
            }
        except RuntimeError as e:
            return {
                "status": "error",
                "error": str(e),
                "error_type": "dependency",
                "failure_class": "environmental",  # Browser engine issue
                "content": ""
            }
        except Exception as e:
            logging.error(f"Navigation failed: {e}")
            return {
                "status": "error",
                "error": f"Navigation failed: {e}",
                "failure_class": "environmental",  # Default to environmental for browser ops
                "content": ""
            }
