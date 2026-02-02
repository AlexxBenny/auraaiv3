"""Stub tool for unsupported browser operations

Returns a helpful error explaining the capability gap.
This prevents Stage 2 from "guessing" with input tools.

Category: browsers
Risk Level: none (information only)
Side Effects: none
"""

from typing import Dict, Any
from tools.base import Tool


class BrowserNotImplemented(Tool):
    """Placeholder for unimplemented browser operations
    
    This tool is selected when browser automation is requested
    but no specific browser tools are available yet.
    
    It provides clear feedback instead of:
    - Silent failures
    - Random mouse movements
    - Confusing error messages
    """
    
    @property
    def name(self) -> str:
        return "browsers.not_implemented"
    
    @property
    def description(self) -> str:
        return (
            "Placeholder for browser automation features not yet implemented. "
            "Use this when user requests tab control, navigation, or DOM interaction. "
            "For launching browsers, use system.apps.launch.shell instead."
        )
    
    @property
    def risk_level(self) -> str:
        return "none"
    
    @property
    def side_effects(self) -> list[str]:
        return []
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "description": "The browser operation that was requested"
                },
                "details": {
                    "type": "string",
                    "description": "Additional context about what the user wanted"
                }
            },
            "required": ["operation"]
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Return a helpful capability gap message"""
        operation = args.get("operation", "unknown")
        details = args.get("details", "")
        
        # Map common operations to suggestions
        suggestions = {
            "tab": "Tab control is coming in Phase 1. For now, use keyboard shortcuts (Ctrl+T, Ctrl+W).",
            "navigation": "URL navigation is coming in Phase 1. For now, manually enter the URL.",
            "close_tab": "Use 'close this tab' with input_control intent, or Ctrl+W.",
            "new_tab": "Use 'open new tab' with input_control intent, or Ctrl+T.",
            "scrape": "Web scraping is not supported. Consider using dedicated tools.",
            "click": "DOM clicking requires browser automation (Phase 2+).",
        }
        
        # Find matching suggestion
        suggestion = None
        for key, msg in suggestions.items():
            if key in operation.lower():
                suggestion = msg
                break
        
        if suggestion is None:
            suggestion = "Use 'open chrome' or 'open edge' to launch a browser."
        
        return {
            "status": "not_implemented",
            "error_type": "capability_missing",
            "operation": operation,
            "details": details if details else None,
            "message": (
                f"Browser automation ('{operation}') is not yet implemented. "
                f"{suggestion}"
            ),
            "supported_now": [
                "Launching browsers: 'open chrome', 'open edge', 'open brave'",
                "Opening URLs: 'open google.com' (launches default browser with URL)"
            ],
            "coming_soon": [
                "Tab management (Phase 1)",
                "URL navigation (Phase 1)",
                "Multi-tab orchestration (Phase 2)",
            ]
        }
