"""Tool: system.window.snap_left

Snaps the active window to the left half of the screen.

Category: action
Risk Level: low
Side Effects: window_state_changed

Uses Win+Left hotkey.
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


class SnapLeft(Tool):
    """Snap active window to left half of screen"""
    
    @property
    def name(self) -> str:
        return "system.window.snap_left"
    
    @property
    def description(self) -> str:
        return "Snaps the active window to the left half of the screen (Win+Left)"
    
    @property
    def risk_level(self) -> str:
        return "low"
    
    @property
    def side_effects(self) -> list[str]:
        return ["window_state_changed"]
    
    @property
    def stabilization_time_ms(self) -> int:
        return 150  # Window snap animation
    
    @property
    def reversible(self) -> bool:
        return True
    
    @property
    def requires_visual_confirmation(self) -> bool:
        return True
    
    @property
    def requires_focus(self) -> bool:
        return True  # Needs a window to snap
    
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
        """Execute snap left"""
        if not PYAUTOGUI_AVAILABLE:
            return {
                "status": "error",
                "error": "Dependency not installed: pyautogui"
            }
        
        try:
            # Win+Left to snap left
            pyautogui.hotkey('win', 'left')
            
            time.sleep(self.stabilization_time_ms / 1000.0)
            
            logging.info("Executed snap left (Win+Left)")
            return {
                "status": "success",
                "action": "snap_left",
                "hotkey": "Win+Left"
            }
            
        except Exception as e:
            logging.error(f"Failed to snap left: {e}")
            return {
                "status": "error",
                "error": f"Failed to snap left: {str(e)}"
            }
