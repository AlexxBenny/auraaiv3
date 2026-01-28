"""Tool: system.window.snap_right

Snaps the active window to the right half of the screen.

Category: action
Risk Level: low
Side Effects: window_state_changed

Uses Win+Right hotkey.
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


class SnapRight(Tool):
    """Snap active window to right half of screen"""
    
    @property
    def name(self) -> str:
        return "system.window.snap_right"
    
    @property
    def description(self) -> str:
        return "Snaps the active window to the right half of the screen (Win+Right)"
    
    @property
    def risk_level(self) -> str:
        return "low"
    
    @property
    def side_effects(self) -> list[str]:
        return ["window_state_changed"]
    
    @property
    def stabilization_time_ms(self) -> int:
        return 150
    
    @property
    def reversible(self) -> bool:
        return True
    
    @property
    def requires_visual_confirmation(self) -> bool:
        return True
    
    @property
    def requires_focus(self) -> bool:
        return True
    
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
        """Execute snap right"""
        if not PYAUTOGUI_AVAILABLE:
            return {
                "status": "error",
                "error": "Dependency not installed: pyautogui"
            }
        
        try:
            pyautogui.hotkey('win', 'right')
            
            time.sleep(self.stabilization_time_ms / 1000.0)
            
            logging.info("Executed snap right (Win+Right)")
            return {
                "status": "success",
                "action": "snap_right",
                "hotkey": "Win+Right"
            }
            
        except Exception as e:
            logging.error(f"Failed to snap right: {e}")
            return {
                "status": "error",
                "error": f"Failed to snap right: {str(e)}"
            }
