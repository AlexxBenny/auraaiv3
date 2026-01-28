"""Tool: system.audio.media_play_pause

Toggles media playback (play/pause) using the media key.

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


class MediaPlayPause(Tool):
    """Toggle media playback using media key"""
    
    @property
    def name(self) -> str:
        return "system.audio.media_play_pause"
    
    @property
    def description(self) -> str:
        return "Toggles media playback (play/pause) - works with any media app"
    
    @property
    def risk_level(self) -> str:
        return "low"
    
    @property
    def side_effects(self) -> list[str]:
        return ["media_state_changed"]
    
    @property
    def stabilization_time_ms(self) -> int:
        return 50  # Instant media key
    
    @property
    def reversible(self) -> bool:
        return True  # Can toggle back
    
    @property
    def requires_visual_confirmation(self) -> bool:
        return False
    
    @property
    def requires_focus(self) -> bool:
        return False  # Works globally
    
    @property
    def requires_unlocked_screen(self) -> bool:
        return False  # Media keys work on lock screen
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute media play/pause"""
        if not PYAUTOGUI_AVAILABLE:
            return {
                "status": "error",
                "error": "Dependency not available: pyautogui"
            }
        
        try:
            pyautogui.press('playpause')
            
            logging.info("Media play/pause toggled")
            return {
                "status": "success",
                "action": "media_play_pause"
            }
            
        except Exception as e:
            logging.error(f"Failed to toggle media: {e}")
            return {
                "status": "error",
                "error": f"Failed to toggle media: {str(e)}"
            }
