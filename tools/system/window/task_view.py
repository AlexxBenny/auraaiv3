"""Tool: system.window.task_view

Opens Windows Task View (virtual desktop overview).

Category: action
Risk Level: low
Side Effects: window_state_changed

Uses Win+Tab hotkey.
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


class TaskView(Tool):
    """Open Windows Task View"""
    
    @property
    def name(self) -> str:
        return "system.window.task_view"
    
    @property
    def description(self) -> str:
        return "Opens Windows Task View showing all windows and virtual desktops (Win+Tab)"
    
    @property
    def risk_level(self) -> str:
        return "low"
    
    @property
    def side_effects(self) -> list[str]:
        return ["window_state_changed"]
    
    @property
    def stabilization_time_ms(self) -> int:
        return 300  # Task View has longer animation
    
    @property
    def reversible(self) -> bool:
        return True  # Escape or click to exit
    
    @property
    def requires_visual_confirmation(self) -> bool:
        return True
    
    @property
    def requires_focus(self) -> bool:
        return False  # Works from anywhere
    
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
        """Execute open task view"""
        if not PYAUTOGUI_AVAILABLE:
            return {
                "status": "error",
                "error": "Dependency not installed: pyautogui"
            }
        
        try:
            pyautogui.hotkey('win', 'tab')
            
            time.sleep(self.stabilization_time_ms / 1000.0)
            
            logging.info("Opened Task View (Win+Tab)")
            return {
                "status": "success",
                "action": "task_view",
                "hotkey": "Win+Tab"
            }
            
        except Exception as e:
            logging.error(f"Failed to open task view: {e}")
            return {
                "status": "error",
                "error": f"Failed to open task view: {str(e)}"
            }
