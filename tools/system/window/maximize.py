"""Tool: system.window.maximize

Maximizes the active window.

Category: action
Risk Level: low
Side Effects: window_state_changed

Uses Win+Up hotkey.
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


class Maximize(Tool):
    """Maximize the active window"""
    
    @property
    def name(self) -> str:
        return "system.window.maximize"
    
    @property
    def description(self) -> str:
        return "Maximizes the active window to fill the screen (Win+Up)"
    
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
        """Execute maximize window"""
        if not PYAUTOGUI_AVAILABLE:
            return {
                "status": "error",
                "error": "Dependency not installed: pyautogui"
            }
        
        try:
            pyautogui.hotkey('win', 'up')
            
            time.sleep(self.stabilization_time_ms / 1000.0)
            
            logging.info("Executed maximize window (Win+Up)")
            return {
                "status": "success",
                "action": "maximize",
                "hotkey": "Win+Up"
            }
            
        except Exception as e:
            logging.error(f"Failed to maximize window: {e}")
            return {
                "status": "error",
                "error": f"Failed to maximize: {str(e)}"
            }
