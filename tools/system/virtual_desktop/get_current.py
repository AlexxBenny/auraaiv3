"""Tool: system.virtual_desktop.get_current

Gets the current virtual desktop number.

Category: query
Risk Level: low
Side Effects: none

Uses VirtualDesktopAccessor.dll or pyvda with capability probe.
"""

import logging
from typing import Dict, Any

from ...base import Tool
from .accessor import get_current_desktop_number, is_capability_available


class GetCurrentDesktop(Tool):
    """Get current virtual desktop number"""
    
    @property
    def name(self) -> str:
        return "system.virtual_desktop.get_current"
    
    @property
    def description(self) -> str:
        return "Gets the current virtual desktop number (1-indexed)"
    
    @property
    def risk_level(self) -> str:
        return "low"  # Read-only
    
    @property
    def side_effects(self) -> list[str]:
        return []  # No side effects
    
    @property
    def stabilization_time_ms(self) -> int:
        return 0  # Read-only, instant
    
    @property
    def reversible(self) -> bool:
        return True  # No change to revert
    
    @property
    def requires_visual_confirmation(self) -> bool:
        return False
    
    @property
    def requires_focus(self) -> bool:
        return False
    
    @property
    def requires_unlocked_screen(self) -> bool:
        return False  # Can query even when locked
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute get current desktop"""
        # Capability probe
        if not is_capability_available():
            return {
                "status": "unsupported",
                "error": "Virtual desktop control not available on this system"
            }
        
        try:
            desktop_number = get_current_desktop_number()
            
            if desktop_number is None:
                return {
                    "status": "error",
                    "error": "Failed to get current desktop number"
                }
            
            logging.info(f"Current virtual desktop: {desktop_number}")
            return {
                "status": "success",
                "action": "get_current_desktop",
                "desktop_number": desktop_number
            }
            
        except Exception as e:
            logging.error(f"Failed to get current desktop: {e}")
            return {
                "status": "error",
                "error": f"Failed to get current desktop: {str(e)}"
            }
