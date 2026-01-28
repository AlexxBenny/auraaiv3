"""Tool: system.audio.mute

Mutes the system audio.

Category: action
Risk Level: low
Side Effects: audio_changed

Dependencies: pycaw (optional - graceful failure)
"""

from typing import Dict, Any
from ...base import Tool


class Mute(Tool):
    """Mute system audio"""
    
    @property
    def name(self) -> str:
        return "system.audio.mute"
    
    @property
    def description(self) -> str:
        return "Mutes the system audio"
    
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
        return True  # Can unmute
    
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
        """Execute mute"""
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
            
            # Check if already muted
            was_muted = bool(volume_interface.GetMute())
            
            # Mute
            volume_interface.SetMute(1, None)
            
            return {
                "status": "success",
                "was_already_muted": was_muted,
                "is_muted": True
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": f"Failed to mute: {str(e)}"
            }
