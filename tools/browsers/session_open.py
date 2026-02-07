"""Tool: browsers.session.open

Opens or attaches to a browser session for automation.

Category: browser_control
Risk Level: medium
Side Effects: launches_process, changes_focus

GUARDRAIL: session_id is explicit from Phase 1 onward.
"""

import logging
from typing import Dict, Any, Optional
from tools.base import Tool


class SessionOpen(Tool):
    """Open or attach to a browser session."""
    
    @property
    def name(self) -> str:
        return "browsers.session.open"
    
    @property
    def description(self) -> str:
        return (
            "Opens a new browser session or attaches to an existing one. "
            "Returns session_id for use in subsequent browser operations."
        )
    
    @property
    def risk_level(self) -> str:
        return "medium"
    
    @property
    def side_effects(self) -> list[str]:
        return ["launches_process", "changes_focus"]
    
    @property
    def stabilization_time_ms(self) -> int:
        return 3000  # Browser launch can be slow
    
    @property
    def reversible(self) -> bool:
        return True  # Can close session
    
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
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "string",
                    "description": "Optional browser session identifier. If omitted, uses/creates default session."
                },
                "browser": {
                    "type": "string",
                    "enum": ["chromium", "chrome", "edge", "firefox"],
                    "description": "Browser to launch. Defaults to config value."
                },
                "url": {
                    "type": "string",
                    "description": "Optional URL to navigate to after opening."
                }
            },
            "required": []
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Open browser session."""
        session_id = args.get("session_id")
        browser_type = args.get("browser")
        url = args.get("url")
        
        try:
            from core.browser_session_manager import BrowserSessionManager
            
            manager = BrowserSessionManager.get()
            session = manager.get_or_create(
                session_id=session_id,
                browser_type=browser_type
            )
            
            # Navigate if URL provided
            if url:
                from tools.browsers._engine.playwright import PlaywrightEngine
                engine = PlaywrightEngine()
                engine.navigate(session.page, url)
            
            return {
                "status": "success",
                "session_id": session.session_id,
                "browser_type": session.browser_type,
                "headless": session.headless,
                "content": f"Browser session opened: {session.session_id}"
            }
            
        except RuntimeError as e:
            return {
                "status": "error",
                "error": str(e),
                "error_type": "dependency",
                "failure_class": "environmental",  # Browser engine dependency issue (retryable)
                "content": ""
            }
        except Exception as e:
            logging.error(f"Session open failed: {e}")
            error_str = str(e).lower()
            # Determine failure class based on error type
            if "permission" in error_str or "access" in error_str:
                failure_class = "permission"
            elif "timeout" in error_str or "connection" in error_str:
                failure_class = "environmental"
            else:
                failure_class = "environmental"  # Default to environmental for browser ops
            return {
                "status": "error",
                "error": f"Failed to open browser session: {e}",
                "failure_class": failure_class,
                "content": ""
            }
