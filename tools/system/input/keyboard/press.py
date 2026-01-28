"""Tool: system.input.keyboard.press

Presses single keys or shortcuts (e.g., 'enter', 'ctrl+c').
Supports context binding.

Category: system
Risk Level: medium
Side Effects: input_event, triggers_ui_action
"""

import win32gui
from typing import Dict, Any
from tools.base import Tool
from core.input.manager import get_input_backend


class KeyboardPress(Tool):
    """Presses specific keys"""
    
    @property
    def name(self) -> str:
        return "system.input.keyboard.press"
    
    @property
    def description(self) -> str:
        return "Presses a key or key combination. E.g. 'enter', 'esc', 'ctrl', 'c'."
    
    @property
    def risk_level(self) -> str:
        return "medium"
        
    @property
    def side_effects(self) -> list[str]:
        return ["input_event", "triggers_ui_action"]
        
    @property
    def stabilization_time_ms(self) -> int:
        return 100
        
    @property
    def reversible(self) -> bool:
        return False # Keypress effects vary wildly

    @property
    def requires_visual_confirmation(self) -> bool:
        return True # Pressing 'enter' often changes screen

    @property
    def requires_focus(self) -> bool:
        """Key presses MUST have a focused window to receive input."""
        return True

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Key name (enter, esc, a, f1) or list of keys for shortcut"
                },
                "modifiers": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["ctrl", "alt", "shift", "win"]},
                    "description": "Keys to hold down while pressing 'key'"
                },
                "window_title": {"type": "string"}
            },
            "required": ["key"]
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute key press"""
        if not self.validate_args(args):
            return {"status": "error", "error": "Invalid arguments"}
            
        key = args["key"]
        modifiers = args.get("modifiers", [])
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
            
            # The tool spec says 'key' can be string or list, but typically one key or list of keys if macro (which we avoid)
            # Backend expects List[str] for keys to press sequentially or simultaneously?
            # Backend signature: press_keys(keys: List[str], modifiers: List[str])
            # If args['key'] is "c", keys=["c"]. If "ctrl+c", modifiers=["ctrl"], keys=["c"]
            
            keys_to_press = key if isinstance(key, list) else [key]
            
            backend.press_keys(keys_to_press, modifiers)
                
            return {
                "status": "success",
                "key": key,
                "modifiers": modifiers
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
