"""Tool: system.audio.set_volume

Sets the system volume to a specific level.

Category: action
Risk Level: low
Side Effects: audio_changed

Dependencies: pycaw (optional - graceful failure)
"""

from typing import Dict, Any
from ...base import Tool


class SetVolume(Tool):
    """Set system volume to a specific level"""
    
    @property
    def name(self) -> str:
        return "system.audio.set_volume"
    
    @property
    def description(self) -> str:
        return "Sets the system volume to a specific level (0-100)"
    
    @property
    def risk_level(self) -> str:
        return "low"  # Easily reversible, non-destructive
    
    @property
    def side_effects(self) -> list[str]:
        return ["audio_changed"]
    
    @property
    def stabilization_time_ms(self) -> int:
        return 100  # Audio changes are near-instant
    
    @property
    def reversible(self) -> bool:
        return True  # Can set volume back
    
    @property
    def requires_visual_confirmation(self) -> bool:
        return False  # Audio change, not visual
    
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
            "properties": {
                "level": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Volume level (0-100)"
                }
            },
            "required": ["level"]
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute volume change"""
        if not self.validate_args(args):
            raise ValueError(f"Invalid arguments for {self.name}")
        
        level = args.get("level")
        if level is None:
            return {
                "status": "error",
                "error": "Required argument 'level' not provided"
            }
        
        # Validate range
        if not 0 <= level <= 100:
            return {
                "status": "error",
                "error": f"Volume must be 0-100, got {level}"
            }
        
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
            
            # Get previous volume for logging
            previous_volume = int(volume_interface.GetMasterVolumeLevelScalar() * 100)
            
            # Set volume (0.0 to 1.0)
            volume_interface.SetMasterVolumeLevelScalar(level / 100, None)
            
            return {
                "status": "success",
                "previous_volume": previous_volume,
                "new_volume": level
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": f"Failed to set volume: {str(e)}"
            }
