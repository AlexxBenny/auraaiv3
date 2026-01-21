"""Tool: system.input.mouse.move

Moves mouse to ABSOLUTE coordinates.
Supports safety context (window binding).

Category: system
Risk Level: medium
Side Effects: changes_focus, input_event
"""

import win32gui
from typing import Dict, Any
from tools.base import Tool
from core.input.manager import get_input_backend


class MouseMove(Tool):
    """Move mouse to absolute coordinates safely"""
    
    @property
    def name(self) -> str:
        return "system.input.mouse.move"
    
    @property
    def description(self) -> str:
        return "Moves mouse to specific ABSOLUTE coordinates. Can verify active window first."
    
    @property
    def risk_level(self) -> str:
        return "medium"
        
    @property
    def side_effects(self) -> list[str]:
        return ["input_event", "may_change_focus"]
        
    @property
    def stabilization_time_ms(self) -> int:
        return 100
        
    @property
    def reversible(self) -> bool:
        return True

    @property
    def requires_visual_confirmation(self) -> bool:
        return False  # Move itself is usually reliable, clicks need check

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "minimum": 0},
                "y": {"type": "integer", "minimum": 0},
                "window_title": {
                    "type": "string",
                    "description": "If provided, fails if active window doesn't contain this"
                },
                "require_focus": {
                    "type": "boolean",
                    "default": False,
                    "description": "If true, enforces window check"
                }
            },
            "required": ["x", "y"]
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute safe mouse move"""
        if not self.validate_args(args):
            return {"status": "error", "error": "Invalid arguments"}
            
        x = args["x"]
        y = args["y"]
        window_title = args.get("window_title")
        require_focus = args.get("require_focus", False)
        
        # 1. Safety Check: Context binding
        if window_title or require_focus:
            hwnd = win32gui.GetForegroundWindow()
            active_title = win32gui.GetWindowText(hwnd)
            
            if window_title:
                if window_title.lower() not in active_title.lower():
                    return {
                        "status": "error",
                        "error": f"Context mismatch: Goal='{window_title}', Active='{active_title}'"
                    }
        
        # 2. Execution
        try:
            backend = get_input_backend()
            # Bounds check is now handled in backend, but we can catch it here or let it bubble up
            # (Backend raises ValueError for bounds)
            
            final_pos = backend.move_to(x, y)
            
            return {
                "status": "success",
                "x": final_pos[0],
                "y": final_pos[1],
                "context_verified": bool(window_title)
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": f"Mouse move failed: {str(e)}"
            }
