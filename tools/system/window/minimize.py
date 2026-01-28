"""Tool: system.window.minimize

Minimizes the active window.

Category: action
Risk Level: low
Side Effects: window_state_changed

Uses Win+Down hotkey.
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


class Minimize(Tool):
    """Minimize the active window"""
    
    @property
    def name(self) -> str:
        return "system.window.minimize"
    
    @property
    def description(self) -> str:
        return "Minimizes the active window (Win+Down)"
    
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
        """Execute minimize window"""
        if not PYAUTOGUI_AVAILABLE:
            return {
                "status": "error",
                "error": "Dependency not installed: pyautogui"
            }
        
        try:
            pyautogui.hotkey('win', 'down')
            
            time.sleep(self.stabilization_time_ms / 1000.0)
            
            logging.info("Executed minimize window (Win+Down)")
            return {
                "status": "success",
                "action": "minimize",
                "hotkey": "Win+Down"
            }
            
        except Exception as e:
            logging.error(f"Failed to minimize window: {e}")
            return {
                "status": "error",
                "error": f"Failed to minimize: {str(e)}"
            }
