"""Tool: system.audio.get_media_state

Detects active audio sessions and their playback state.

Category: query (read-only)
Risk Level: none
Side Effects: none

Uses Windows Audio Session API via pycaw.
Returns: active sessions, playing state, source application.
"""

import logging
from typing import Dict, Any, List

from ...base import Tool


# Audio session states (from Windows API)
AUDIO_SESSION_STATES = {
    0: "inactive",  # AudioSessionStateInactive
    1: "active",    # AudioSessionStateActive  
    2: "expired"    # AudioSessionStateExpired
}


class GetMediaState(Tool):
    """Get current media playback state across all audio sessions."""
    
    @property
    def name(self) -> str:
        return "system.audio.get_media_state"
    
    @property
    def description(self) -> str:
        return "Detects if media is playing, paused, or inactive across all apps"
    
    @property
    def risk_level(self) -> str:
        return "none"  # Pure read operation
    
    @property
    def side_effects(self) -> list[str]:
        return []
    
    @property
    def stabilization_time_ms(self) -> int:
        return 0  # Instantaneous
    
    @property
    def reversible(self) -> bool:
        return True  # Nothing to reverse
    
    @property
    def requires_visual_confirmation(self) -> bool:
        return False
    
    @property
    def requires_focus(self) -> bool:
        return False
    
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
        """Query audio session state.
        
        Returns:
            {
                "status": "success",
                "active": true/false,      # Any session active?
                "playing": true/false,     # Any session actually playing?
                "source": "Spotify.exe",   # Primary active source
                "sessions": [...]          # All audio sessions
            }
        """
        try:
            from pycaw.pycaw import AudioUtilities
        except ImportError:
            return {
                "status": "error",
                "error": "Dependency not available: pycaw"
            }
        
        try:
            sessions_info: List[Dict[str, Any]] = []
            active_source = None
            any_active = False
            any_playing = False
            
            # Get all audio sessions
            sessions = AudioUtilities.GetAllSessions()
            
            for session in sessions:
                try:
                    # Get process info
                    process = session.Process
                    if process is None:
                        continue
                    
                    process_name = process.name()
                    
                    # Get session state
                    # State: 0=inactive, 1=active, 2=expired
                    state_code = session.State
                    state_name = AUDIO_SESSION_STATES.get(state_code, "unknown")
                    
                    is_active = state_code == 1  # AudioSessionStateActive
                    
                    session_info = {
                        "name": process_name,
                        "state": state_name,
                        "active": is_active
                    }
                    sessions_info.append(session_info)
                    
                    if is_active:
                        any_active = True
                        any_playing = True  # Active session = audio flowing
                        if active_source is None:
                            active_source = process_name
                            
                except Exception as e:
                    logging.debug(f"Failed to get session info: {e}")
                    continue
            
            result = {
                "status": "success",
                "active": any_active,
                "playing": any_playing,
                "source": active_source,
                "session_count": len(sessions_info),
                "sessions": sessions_info[:5]  # Limit to top 5
            }
            
            logging.debug(f"Media state: active={any_active}, playing={any_playing}, source={active_source}")
            return result
            
        except Exception as e:
            logging.error(f"Failed to get media state: {e}")
            return {
                "status": "error",
                "error": f"Failed to get media state: {str(e)}"
            }
