"""Tool: system.state.get_date

Returns the current system date.

Category: query
Risk Level: none
Side Effects: none
"""

from datetime import datetime
from typing import Dict, Any
from ...base import Tool


class GetDate(Tool):
    """Get current system date"""
    
    @property
    def name(self) -> str:
        return "system.state.get_date"
    
    @property
    def description(self) -> str:
        return "Returns the current system date"
    
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
                    "enum": ["short", "long", "iso"],
                    "default": "long",
                    "description": "Date format: short (01/28/26), long (January 28, 2026), iso (2026-01-28)"
                }
            },
            "required": []
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute date query"""
        if not self.validate_args(args):
            raise ValueError(f"Invalid arguments for {self.name}")
        
        date_format = args.get("format", "long")
        now = datetime.now()
        
        if date_format == "short":
            date_str = now.strftime("%m/%d/%y")
        elif date_format == "iso":
            date_str = now.strftime("%Y-%m-%d")
        else:  # long
            date_str = now.strftime("%B %d, %Y")
        
        # Get day of week
        day_of_week = now.strftime("%A")
        
        return {
            "status": "success",
            "date": date_str,
            "day_of_week": day_of_week,
            "year": now.year,
            "month": now.month,
            "day": now.day,
            "format": date_format
        }
