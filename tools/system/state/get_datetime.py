"""Get Datetime Tool - System date, time, timezone

Primitive system tool for date/time queries.
Returns structured datetime data for deterministic fact extraction.

Why this exists (not a context hack):
- Deterministic
- Auditable
- Mockable/testable
- Scales to timezone, locale, uptime, etc.
"""

from datetime import datetime
from typing import Dict, Any, List
import platform
import time


class GetDatetimeTool:
    """Get current date and time with full context."""
    
    name = "system.state.get_datetime"
    description = "Get current date, time, day of week, timezone"
    
    # Schema-driven fact extraction (Phase 2D typed format)
    fact_schema = {
        "current_year": {
            "path": ["year"],
            "type": int,
            "required": True
        },
        "current_month": {
            "path": ["month"],
            "type": int,
            "required": True
        },
        "current_day": {
            "path": ["day"],
            "type": int,
            "required": True
        },
        "current_hour": {
            "path": ["hour"],
            "type": int,
            "required": True
        },
        "current_minute": {
            "path": ["minute"],
            "type": int,
            "required": True
        },
        "day_of_week": {
            "path": ["day_of_week"],
            "type": str,
            "required": True
        },
        "timezone": {
            "path": ["timezone"],
            "type": str,
            "required": False
        }
    }
    
    parameters = {}  # No parameters needed
    
    tags = ["datetime", "time", "date", "year", "clock", "calendar"]
    
    @staticmethod
    def execute(params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get current datetime information.
        
        Returns:
            {
                "status": "success",
                "year": 2026,
                "month": 1,
                "day": 28,
                "hour": 6,
                "minute": 30,
                "second": 45,
                "day_of_week": "Tuesday",
                "date_formatted": "2026-01-28",
                "time_formatted": "06:30:45",
                "datetime_formatted": "2026-01-28 06:30:45",
                "timezone": "India Standard Time",
                "unix_timestamp": 1769567445
            }
        """
        now = datetime.now()
        
        # Day names
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", 
                "Friday", "Saturday", "Sunday"]
        
        # Get timezone name
        try:
            # Try to get timezone name from time module
            if time.daylight:
                tz_name = time.tzname[time.localtime().tm_isdst]
            else:
                tz_name = time.tzname[0]
        except Exception:
            tz_name = "Unknown"
        
        return {
            "status": "success",
            "year": now.year,
            "month": now.month,
            "day": now.day,
            "hour": now.hour,
            "minute": now.minute,
            "second": now.second,
            "day_of_week": days[now.weekday()],
            "date_formatted": now.strftime("%Y-%m-%d"),
            "time_formatted": now.strftime("%H:%M:%S"),
            "datetime_formatted": now.strftime("%Y-%m-%d %H:%M:%S"),
            "timezone": tz_name,
            "unix_timestamp": int(now.timestamp())
        }
