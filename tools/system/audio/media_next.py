"""Tool: system.audio.media_next

Skip to next track using the media key.

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


class MediaNext(Tool):
    """Skip to next track using media key"""
    
    @property
    def name(self) -> str:
        return "system.audio.media_next"
    
    @property
    def description(self) -> str:
        return "Skip to next track - works with any media app"
    
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
        return True  # Can go back with previous
    
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
        """Execute next track"""
        if not PYAUTOGUI_AVAILABLE:
            return {
                "status": "error",
                "error": "Dependency not available: pyautogui"
            }
        
        try:
            pyautogui.press('nexttrack')
            
            logging.info("Skipped to next track")
            return {
                "status": "success",
                "action": "media_next"
            }
            
        except Exception as e:
            logging.error(f"Failed to skip track: {e}")
            return {
                "status": "error",
                "error": f"Failed to skip track: {str(e)}"
            }
