"""Tool: system.state.get_time

Returns the current system time.

Category: query
Risk Level: none
Side Effects: none
"""

from datetime import datetime
from typing import Dict, Any
from ...base import Tool


class GetTime(Tool):
    """Get current system time"""
    
    @property
    def name(self) -> str:
        return "system.state.get_time"
    
    @property
    def description(self) -> str:
        return "Returns the current system time"
    
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
            "properties": {
                "format": {
                    "type": "string",
                    "enum": ["12h", "24h"],
                    "default": "12h",
                    "description": "Time format: 12-hour or 24-hour"
                }
            },
            "required": []
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute time query"""
        if not self.validate_args(args):
            raise ValueError(f"Invalid arguments for {self.name}")
        
        time_format = args.get("format", "12h")
        now = datetime.now()
        
        if time_format == "24h":
            time_str = now.strftime("%H:%M:%S")
        else:
            time_str = now.strftime("%I:%M:%S %p")
        
        return {
            "status": "success",
            "time": time_str,
            "hour": now.hour,
            "minute": now.minute,
            "second": now.second,
            "format": time_format
        }
