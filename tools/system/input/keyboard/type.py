"""Tool: system.input.keyboard.type

Types text strings.
Supports context binding.

Category: system
Risk Level: medium
Side Effects: input_event, modifies_content
"""

import win32gui
from typing import Dict, Any
from tools.base import Tool
from core.input.manager import get_input_backend


class KeyboardType(Tool):
    """Types text characters"""
    
    @property
    def name(self) -> str:
        return "system.input.keyboard.type"
    
    @property
    def description(self) -> str:
        return "Types a string of text. Supports window safety check."
    
    @property
    def risk_level(self) -> str:
        return "medium" # Can overwrite data
        
    @property
    def side_effects(self) -> list[str]:
        return ["input_event", "modifies_content"]
        
    @property
    def stabilization_time_ms(self) -> int:
        return 50
        
    @property
    def reversible(self) -> bool:
        return True # Text can be deleted

    @property
    def requires_visual_confirmation(self) -> bool:
        return False

    @property
    def requires_focus(self) -> bool:
        """Typing MUST have a focused window to receive input."""
        return True

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "interval": {
                    "type": "number", 
                    "default": 0.0,
                    "description": "Delay between keys (seconds)"
                },
                "window_title": {"type": "string"}
            },
            "required": ["text"]
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute typing"""
        if not self.validate_args(args):
            return {"status": "error", "error": "Invalid arguments"}
            
        text = args["text"]
        interval = args.get("interval", 0.0)
        window_title = args.get("window_title")
        
        # 1. Safety Check
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
            backend.type_text(text, interval=interval)
            return {
                "status": "success",
                "chars_typed": len(text)
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
