"""Tool: system.input.mouse.click

Performs mouse click (Left/Right/Double).
Supports absolute coordinates and context binding.

Category: system
Risk Level: medium
Side Effects: input_event, changes_focus, changes_ui_state
"""

import win32gui
from typing import Dict, Any, Optional
from tools.base import Tool
from core.input.manager import get_input_backend


class MouseClick(Tool):
    """Safe mouse click"""
    
    @property
    def name(self) -> str:
        return "system.input.mouse.click"
    
    @property
    def description(self) -> str:
        return "Clicks mouse at coordinates. Supports left/right/double clicks and safety checks."
    
    @property
    def risk_level(self) -> str:
        return "medium"
        
    @property
    def side_effects(self) -> list[str]:
        return ["input_event", "changes_focus", "triggers_ui_action"]
        
    @property
    def stabilization_time_ms(self) -> int:
        return 200  # Clicks trigger UI changes
        
    @property
    def reversible(self) -> bool:
        return False # Clicks change state

    @property
    def requires_visual_confirmation(self) -> bool:
        return True # Should usually verify effect

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "minimum": 0},
                "y": {"type": "integer", "minimum": 0},
                "button": {
                    "type": "string",
                    "enum": ["left", "right", "middle"],
                    "default": "left"
                },
                "double_click": {
                    "type": "boolean",
                    "default": False
                },
                "window_title": {
                    "type": "string",
                    "description": "Fail if active window title does not match"
                }
            },
            "required": [] # Defaults to current pos
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute safe mouse click"""
        if not self.validate_args(args):
            return {"status": "error", "error": "Invalid arguments"}
            
        x = args.get("x")
        y = args.get("y")
        button = args.get("button", "left")
        double_click = args.get("double_click", False)
        window_title = args.get("window_title")
        
        # 1. Safety Check: Context
        if window_title:
            hwnd = win32gui.GetForegroundWindow()
            active_title = win32gui.GetWindowText(hwnd)
            if window_title.lower() not in active_title.lower():
                return {
                    "status": "error",
                    "error": f"Context mismatch: Goal='{window_title}', Active='{active_title}'"
                }
        
        # 2. Execution
        try:
            backend = get_input_backend()
            
            # Click
            final_pos = backend.click(x, y, button, double_click)
            
            return {
                "status": "success",
                "x": final_pos[0],
                "y": final_pos[1],
                "action": f"{button}_{'double_' if double_click else ''}click"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": f"Click failed: {str(e)}"
            }
