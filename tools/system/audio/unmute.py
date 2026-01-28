"""Tool: system.audio.unmute

Unmutes the system audio.

Category: action
Risk Level: low
Side Effects: audio_changed

Dependencies: pycaw (optional - graceful failure)
"""

from typing import Dict, Any
from ...base import Tool


class Unmute(Tool):
    """Unmute system audio"""
    
    @property
    def name(self) -> str:
        return "system.audio.unmute"
    
    @property
    def description(self) -> str:
        return "Unmutes the system audio"
    
    @property
    def risk_level(self) -> str:
        return "low"  # Easily reversible
    
    @property
    def side_effects(self) -> list[str]:
        return ["audio_changed"]
    
    @property
    def stabilization_time_ms(self) -> int:
        return 100
    
    @property
    def reversible(self) -> bool:
        return True  # Can mute again
    
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
        """Execute unmute"""
        if not self.validate_args(args):
            raise ValueError(f"Invalid arguments for {self.name}")
        
        try:
            from pycaw.pycaw import AudioUtilities
        except ImportError:
            return {
                "status": "error",
                "error": "Dependency not installed: pycaw"
            }
        
        try:
            speakers = AudioUtilities.GetSpeakers()
            if speakers is None:
                return {
                    "status": "error",
                    "error": "No default speakers device found"
                }
            
            volume_interface = speakers.EndpointVolume
            
            # Check if already unmuted
            was_muted = bool(volume_interface.GetMute())
            
            # Unmute
            volume_interface.SetMute(0, None)
            
            return {
                "status": "success",
                "was_muted": was_muted,
                "is_muted": False
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": f"Failed to unmute: {str(e)}"
            }
