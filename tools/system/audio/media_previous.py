"""Tool: system.audio.media_previous

Skip to previous track using the media key.

Category: action
Risk Level: low
Side Effects: media_state_changed

Works with any media app (Spotify, YouTube, VLC, etc.)
"""

import logging
from typing import Dict, Any

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

from ...base import Tool


class MediaPrevious(Tool):
    """Skip to previous track using media key"""
    
    @property
    def name(self) -> str:
        return "system.audio.media_previous"
    
    @property
    def description(self) -> str:
        return "Skip to previous track - works with any media app"
    
    @property
    def risk_level(self) -> str:
        return "low"
    
    @property
    def side_effects(self) -> list[str]:
        return ["media_state_changed"]
    
    @property
    def stabilization_time_ms(self) -> int:
        return 50
    
    @property
    def reversible(self) -> bool:
        return True
    
    @property
    def requires_visual_confirmation(self) -> bool:
        return False
    
    @property
    def requires_focus(self) -> bool:
        return False
    
    @property
    def requires_unlocked_screen(self) -> bool:
        return False
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute previous track"""
        if not PYAUTOGUI_AVAILABLE:
            return {
                "status": "error",
                "error": "Dependency not available: pyautogui"
            }
        
        try:
            pyautogui.press('prevtrack')
            
            logging.info("Skipped to previous track")
            return {
                "status": "success",
                "action": "media_previous"
            }
            
        except Exception as e:
            logging.error(f"Failed to skip track: {e}")
            return {
                "status": "error",
                "error": f"Failed to skip track: {str(e)}"
            }
