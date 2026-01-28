"""Tool: system.audio.get_volume

Returns current system volume level.

Category: query
Risk Level: none
Side Effects: none

Dependencies: pycaw (optional - graceful failure)
"""

from typing import Dict, Any
from ...base import Tool


class GetVolume(Tool):
    """Get current system volume level"""
    
    @property
    def name(self) -> str:
        return "system.audio.get_volume"
    
    @property
    def description(self) -> str:
        return "Returns the current system volume level (0-100)"
    
    @property
    def risk_level(self) -> str:
        return "none"  # Pure read operation
    
    @property
    def side_effects(self) -> list[str]:
        return []  # No side effects
    
    @property
    def stabilization_time_ms(self) -> int:
        return 0  # Instantaneous
    
    @property
    def reversible(self) -> bool:
        return True  # Nothing to reverse
    
    @property
    def requires_visual_confirmation(self) -> bool:
        return False  # No visual change
    
    @property
    def requires_focus(self) -> bool:
        return False  # No window needed
    
    @property
    def requires_unlocked_screen(self) -> bool:
        return False  # Works even if locked
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute volume query"""
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
            # Get default speakers device
            speakers = AudioUtilities.GetSpeakers()
            if speakers is None:
                return {
                    "status": "error",
                    "error": "No default speakers device found"
                }
            
            volume_interface = speakers.EndpointVolume
            
            # Get volume as percentage (0-100)
            volume_level = int(volume_interface.GetMasterVolumeLevelScalar() * 100)
            is_muted = bool(volume_interface.GetMute())
            
            return {
                "status": "success",
                "volume": volume_level,
                "is_muted": is_muted
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": f"Failed to get volume: {str(e)}"
            }
