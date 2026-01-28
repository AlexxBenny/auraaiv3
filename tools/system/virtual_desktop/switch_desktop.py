"""Tool: system.virtual_desktop.switch

Switches to a specified virtual desktop.

Category: action
Risk Level: low
Side Effects: virtual_desktop_changed

Uses VirtualDesktopAccessor.dll or pyvda with capability probe.
"""

import time
import logging
from typing import Dict, Any

from ...base import Tool
from .accessor import switch_to_desktop, get_desktop_count, is_capability_available


class SwitchDesktop(Tool):
    """Switch to a virtual desktop"""
    
    @property
    def name(self) -> str:
        return "system.virtual_desktop.switch"
    
    @property
    def description(self) -> str:
        return "Switches to specified virtual desktop (1-indexed)"
    
    @property
    def risk_level(self) -> str:
        return "low"
    
    @property
    def side_effects(self) -> list[str]:
        return ["virtual_desktop_changed"]
    
    @property
    def stabilization_time_ms(self) -> int:
        return 200  # Desktop switch animation
    
    @property
    def reversible(self) -> bool:
        return True
    
    @property
    def requires_visual_confirmation(self) -> bool:
        return True
    
    @property
    def requires_focus(self) -> bool:
        return False
    
    @property
    def requires_unlocked_screen(self) -> bool:
        return True
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "desktop_number": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Target desktop number (1-indexed)"
                }
            },
            "required": ["desktop_number"]
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute switch desktop"""
        # Capability probe
        if not is_capability_available():
            return {
                "status": "unsupported",
                "error": "Virtual desktop control not available on this system"
            }
        
        desktop_number = args.get("desktop_number")
        
        if desktop_number is None:
            return {
                "status": "error",
                "error": "Required argument 'desktop_number' not provided"
            }
        
        try:
            # Validate desktop exists
            total = get_desktop_count()
            if total and desktop_number > total:
                return {
                    "status": "error",
                    "error": f"Desktop {desktop_number} does not exist. Only {total} desktops available."
                }
            
            success = switch_to_desktop(desktop_number)
            
            if success:
                time.sleep(self.stabilization_time_ms / 1000.0)
                logging.info(f"Switched to virtual desktop {desktop_number}")
                return {
                    "status": "success",
                    "action": "switch_desktop",
                    "desktop_number": desktop_number
                }
            else:
                return {
                    "status": "error",
                    "error": f"Failed to switch to desktop {desktop_number}"
                }
            
        except Exception as e:
            logging.error(f"Failed to switch desktop: {e}")
            return {
                "status": "error",
                "error": f"Failed to switch desktop: {str(e)}"
            }
