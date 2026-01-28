"""Tool: system.power.lock

Locks the workstation immediately.

Category: action
Risk Level: medium (requires user to re-authenticate)
Side Effects: screen_locked

Dependencies: ctypes (built-in)

CONSTRAINTS:
- Non-reversible: No unlock tool exists.
- No toggle: Lock only.
- No confirmation: Immediate execution.
"""

import ctypes
from typing import Dict, Any
from ...base import Tool


class Lock(Tool):
    """Lock the workstation"""
    
    @property
    def name(self) -> str:
        return "system.power.lock"
    
    @property
    def description(self) -> str:
        return "Locks the workstation immediately"
    
    @property
    def risk_level(self) -> str:
        return "medium"  # Requires re-authentication
    
    @property
    def side_effects(self) -> list[str]:
        return ["screen_locked"]
    
    @property
    def stabilization_time_ms(self) -> int:
        return 500  # Wait for lock animation
    
    @property
    def reversible(self) -> bool:
        return False  # Cannot unlock programmatically
    
    @property
    def requires_visual_confirmation(self) -> bool:
        return False  # Lock screen is self-evident
    
    @property
    def requires_focus(self) -> bool:
        return False
    
    @property
    def requires_unlocked_screen(self) -> bool:
        return True  # Must be unlocked to lock
    
    @property
    def is_destructive(self) -> bool:
        return False  # Not data-destructive, but terminal
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute workstation lock"""
        if not self.validate_args(args):
            raise ValueError(f"Invalid arguments for {self.name}")
        
        try:
            # Windows API call to lock workstation
            result = ctypes.windll.user32.LockWorkStation()
            
            if result:
                return {
                    "status": "success",
                    "action": "locked",
                    "note": "Workstation has been locked"
                }
            else:
                return {
                    "status": "error",
                    "error": "LockWorkStation returned False"
                }
            
        except Exception as e:
            return {
                "status": "error",
                "error": f"Failed to lock workstation: {str(e)}"
            }
