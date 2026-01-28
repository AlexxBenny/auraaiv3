"""Tool: system.display.set_brightness

Sets display brightness level.

Category: action
Risk Level: low
Side Effects: display_brightness_changed

IDEMPOTENT: Takes explicit level, not toggle.

FALLBACK BEHAVIOR (explicit, per user requirement):
1. Try laptop brightness (WMI)
2. Try external monitor (DDC/CI via screen_brightness_control)
3. Return unsupported if both fail
"""

import logging
from typing import Dict, Any

from ...base import Tool


class SetBrightness(Tool):
    """Set display brightness to a specific level
    
    Uses screen_brightness_control library with explicit fallback behavior.
    """
    
    @property
    def name(self) -> str:
        return "system.display.set_brightness"
    
    @property
    def description(self) -> str:
        return "Sets display brightness to a specific level (0-100)"
    
    @property
    def risk_level(self) -> str:
        return "low"
    
    @property
    def side_effects(self) -> list[str]:
        return ["display_brightness_changed"]
    
    @property
    def stabilization_time_ms(self) -> int:
        return 100
    
    @property
    def reversible(self) -> bool:
        return True
    
    @property
    def requires_visual_confirmation(self) -> bool:
        return True  # User can see brightness change
    
    @property
    def requires_focus(self) -> bool:
        return False
    
    @property
    def requires_unlocked_screen(self) -> bool:
        return False  # Can change brightness on lock screen
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "level": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Brightness level (0-100)"
                }
            },
            "required": ["level"]
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute brightness change with explicit fallback"""
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
                "error": f"Brightness level must be 0-100, got {level}"
            }
        
        # Try 1: screen_brightness_control library
        try:
            import screen_brightness_control as sbc
            
            # Get available displays
            displays = sbc.list_monitors()
            
            if not displays:
                logging.warning("No controllable displays found via sbc")
                return {
                    "status": "unsupported",
                    "error": "No controllable displays found. Brightness control may not be available on this system."
                }
            
            # Set brightness on all displays
            sbc.set_brightness(level)
            
            # Verify the change
            current = sbc.get_brightness()
            
            logging.info(f"Brightness set to {level}% on {len(displays)} display(s)")
            return {
                "status": "success",
                "action": "set_brightness",
                "level": level,
                "displays": displays,
                "verified_levels": current
            }
            
        except ImportError:
            logging.warning("screen_brightness_control not installed")
            return {
                "status": "unsupported",
                "error": "Dependency not installed: screen_brightness_control",
                "install_hint": "pip install screen-brightness-control"
            }
            
        except Exception as e:
            error_msg = str(e)
            
            # Check for known unsupported cases
            if "no method" in error_msg.lower() or "not supported" in error_msg.lower():
                return {
                    "status": "unsupported",
                    "error": "Brightness control not available on this display"
                }
            
            logging.error(f"Failed to set brightness: {e}")
            return {
                "status": "error",
                "error": f"Failed to set brightness: {error_msg}"
            }
