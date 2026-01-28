"""Tool: system.window.switch

Switches to the next window (Alt+Tab).

Category: action
Risk Level: medium
Side Effects: window_state_changed

CRITICAL SAFETY: This tool uses a kill-switch pattern with finally block
to ensure modifier keys are ALWAYS released, even on failure.

Uses Alt+Tab hotkey with explicit keydown/keyup management.
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


class Switch(Tool):
    """Switch to the next window (Alt+Tab)
    
    SAFETY: Uses kill-switch pattern to prevent stuck Alt key.
    """
    
    @property
    def name(self) -> str:
        return "system.window.switch"
    
    @property
    def description(self) -> str:
        return "Switches to the next window using Alt+Tab"
    
    @property
    def risk_level(self) -> str:
        return "medium"  # Stateful modal operation
    
    @property
    def side_effects(self) -> list[str]:
        return ["window_state_changed"]
    
    @property
    def stabilization_time_ms(self) -> int:
        return 300  # Alt+Tab needs more time
    
    @property
    def reversible(self) -> bool:
        return True
    
    @property
    def requires_visual_confirmation(self) -> bool:
        return True
    
    @property
    def requires_focus(self) -> bool:
        return False  # Works from anywhere
    
    @property
    def requires_unlocked_screen(self) -> bool:
        return True  # MANDATORY for Alt+Tab
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute window switch with kill-switch safety pattern
        
        CRITICAL: Uses finally block to ALWAYS release Alt key.
        """
        if not PYAUTOGUI_AVAILABLE:
            return {
                "status": "error",
                "error": "Dependency not installed: pyautogui"
            }
        
        # =====================================================================
        # KILL-SWITCH PATTERN: Ensure Alt is ALWAYS released
        # =====================================================================
        pressed_keys = set()
        
        try:
            # Press Alt
            pyautogui.keyDown('alt')
            pressed_keys.add('alt')
            
            # Brief pause to ensure Alt is registered
            time.sleep(0.05)
            
            # Press Tab
            pyautogui.press('tab')
            
            # Wait for window switch animation
            time.sleep(0.1)
            
        finally:
            # CRITICAL: Always release all pressed keys
            for key in pressed_keys:
                try:
                    pyautogui.keyUp(key)
                    logging.debug(f"Released key: {key}")
                except Exception as e:
                    logging.error(f"Failed to release {key}: {e}")
        
        # Wait for stabilization after key release
        time.sleep(self.stabilization_time_ms / 1000.0)
        
        logging.info("Executed window switch (Alt+Tab) with kill-switch safety")
        return {
            "status": "success",
            "action": "switch",
            "hotkey": "Alt+Tab",
            "safety": "kill_switch_pattern"
        }
