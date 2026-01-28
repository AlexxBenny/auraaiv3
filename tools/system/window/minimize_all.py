"""Tool: system.window.minimize_all

Minimizes all windows, showing the desktop.

Category: action
Risk Level: low
Side Effects: window_state_changed

Uses Win+D hotkey.
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


class MinimizeAll(Tool):
    """Minimize all windows (show desktop)"""
    
    @property
    def name(self) -> str:
        return "system.window.minimize_all"
    
    @property
    def description(self) -> str:
        return "Minimizes all windows to show the desktop (Win+D)"
    
    @property
    def risk_level(self) -> str:
        return "low"  # Non-destructive, reversible
    
    @property
    def side_effects(self) -> list[str]:
        return ["window_state_changed"]
    
    @property
    def stabilization_time_ms(self) -> int:
        return 200  # Windows need time to animate
    
    @property
    def reversible(self) -> bool:
        return True  # Win+D again restores
    
    @property
    def requires_visual_confirmation(self) -> bool:
        return True  # Desktop should be visible
    
    @property
    def requires_focus(self) -> bool:
        return False  # Works from anywhere
    
    @property
    def requires_unlocked_screen(self) -> bool:
        return True  # Screen must be unlocked
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute minimize all windows"""
        if not PYAUTOGUI_AVAILABLE:
            return {
                "status": "error",
                "error": "Dependency not installed: pyautogui"
            }
        
        try:
            # Win+D to show desktop
            pyautogui.hotkey('win', 'd')
            
            # Wait for stabilization
            time.sleep(self.stabilization_time_ms / 1000.0)
            
            logging.info("Executed minimize all windows (Win+D)")
            return {
                "status": "success",
                "action": "minimize_all",
                "hotkey": "Win+D"
            }
            
        except Exception as e:
            logging.error(f"Failed to minimize all windows: {e}")
            return {
                "status": "error",
                "error": f"Failed to minimize windows: {str(e)}"
            }
