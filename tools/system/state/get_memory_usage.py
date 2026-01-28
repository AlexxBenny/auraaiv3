"""Tool: system.state.get_memory_usage

Gets system memory (RAM) usage information.

Category: query
Risk Level: low
Side Effects: none (read-only)
"""

import logging
from typing import Dict, Any

from ...base import Tool


class GetMemoryUsage(Tool):
    """Get system memory usage"""
    
    @property
    def name(self) -> str:
        return "system.state.get_memory_usage"
    
    @property
    def description(self) -> str:
        return "Gets system memory (RAM) usage information"
    
    @property
    def risk_level(self) -> str:
        return "low"
    
    @property
    def side_effects(self) -> list[str]:
        return []
    
    @property
    def stabilization_time_ms(self) -> int:
        return 0
    
    @property
    def reversible(self) -> bool:
        return True
    
    @property
    def requires_visual_confirmation(self) -> bool:
        return False
    
    @property
    def requires_focus(self) -> bool:
        return False
    
    @property
    def requires_unlocked_screen(self) -> bool:
        return False
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    def _format_bytes(self, bytes_val: int) -> str:
        """Format bytes to human-readable string"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_val < 1024:
                return f"{bytes_val:.1f} {unit}"
            bytes_val /= 1024
        return f"{bytes_val:.1f} PB"
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute memory usage query"""
        try:
            import psutil
        except ImportError:
            return {
                "status": "error",
                "error": "Dependency not available: psutil"
            }
        
        try:
            mem = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            result = {
                "status": "success",
                "action": "get_memory_usage",
                "ram": {
                    "total_bytes": mem.total,
                    "available_bytes": mem.available,
                    "used_bytes": mem.used,
                    "percent_used": mem.percent,
                    "total_human": self._format_bytes(mem.total),
                    "available_human": self._format_bytes(mem.available),
                    "used_human": self._format_bytes(mem.used)
                },
                "swap": {
                    "total_bytes": swap.total,
                    "used_bytes": swap.used,
                    "free_bytes": swap.free,
                    "percent_used": swap.percent,
                    "total_human": self._format_bytes(swap.total),
                    "used_human": self._format_bytes(swap.used)
                }
            }
            
            logging.info(f"Memory usage: {mem.percent}% RAM, {swap.percent}% swap")
            return result
            
        except Exception as e:
            logging.error(f"Failed to get memory usage: {e}")
            return {
                "status": "error",
                "error": f"Failed to get memory usage: {str(e)}"
            }
