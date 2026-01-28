"""Tool: system.state.get_battery

Returns current battery percentage and charging status.

Category: query
Risk Level: none
Side Effects: none

Dependencies: psutil (hard requirement)
"""

from typing import Dict, Any
from ...base import Tool


class GetBattery(Tool):
    """Get battery status and percentage"""
    
    @property
    def name(self) -> str:
        return "system.state.get_battery"
    
    @property
    def description(self) -> str:
        return "Returns battery percentage and charging status"
    
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
        """Execute battery query"""
        if not self.validate_args(args):
            raise ValueError(f"Invalid arguments for {self.name}")
        
        try:
            import psutil
        except ImportError:
            return {
                "status": "error",
                "error": "Dependency not installed: psutil"
            }
        
        battery = psutil.sensors_battery()
        
        if battery is None:
            return {
                "status": "error",
                "error": "No battery detected (desktop system?)"
            }
        
        # Calculate time remaining
        if battery.secsleft == psutil.POWER_TIME_UNLIMITED:
            time_remaining = "Unlimited (plugged in)"
        elif battery.secsleft == psutil.POWER_TIME_UNKNOWN:
            time_remaining = "Unknown"
        else:
            hours = battery.secsleft // 3600
            minutes = (battery.secsleft % 3600) // 60
            time_remaining = f"{hours}h {minutes}m"
        
        return {
            "status": "success",
            "percentage": round(battery.percent),
            "is_charging": battery.power_plugged,
            "time_remaining": time_remaining,
            "plugged_in": battery.power_plugged
        }
