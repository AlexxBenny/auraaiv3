"""Tool: system.window.close

Closes the active window.

Category: action
Risk Level: medium
Side Effects: window_closed, potential_data_loss

Uses Alt+F4 hotkey.
"""

import time
import logging
from typing import Dict, Any

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

from ...base import Tool


class Close(Tool):
    """Close the active window"""
    
    @property
    def name(self) -> str:
        return "system.window.close"
    
    @property
    def description(self) -> str:
        return "Closes the active window (Alt+F4). May prompt to save unsaved work."
    
    @property
    def risk_level(self) -> str:
        return "medium"  # Could close unsaved work
    
    @property
    def side_effects(self) -> list[str]:
        return ["window_closed", "potential_data_loss"]
    
    @property
    def stabilization_time_ms(self) -> int:
        return 200
    
    @property
    def reversible(self) -> bool:
        return False  # Window is closed
    
    @property
    def requires_visual_confirmation(self) -> bool:
        return True
    
    @property
    def requires_focus(self) -> bool:
        return True  # Needs a window to close
    
    @property
    def requires_unlocked_screen(self) -> bool:
        return True
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute close window"""
        if not PYAUTOGUI_AVAILABLE:
            return {
                "status": "error",
                "error": "Dependency not installed: pyautogui"
            }
        
        try:
            pyautogui.hotkey('alt', 'F4')
            
            time.sleep(self.stabilization_time_ms / 1000.0)
            
            logging.info("Executed close window (Alt+F4)")
            return {
                "status": "success",
                "action": "close",
                "hotkey": "Alt+F4",
                "warning": "Window may have prompted for save confirmation"
            }
            
        except Exception as e:
            logging.error(f"Failed to close window: {e}")
            return {
                "status": "error",
                "error": f"Failed to close: {str(e)}"
            }
