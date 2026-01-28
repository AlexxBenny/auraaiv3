"""Tool: system.state.get_disk_usage

Gets disk usage information for all drives.

Category: query
Risk Level: low
Side Effects: none (read-only)
"""

import logging
from typing import Dict, Any, List

from ...base import Tool


class GetDiskUsage(Tool):
    """Get disk usage for all drives"""
    
    @property
    def name(self) -> str:
        return "system.state.get_disk_usage"
    
    @property
    def description(self) -> str:
        return "Gets disk usage information for all drives"
    
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
            "properties": {
                "drive": {
                    "type": "string",
                    "description": "Optional: specific drive letter (e.g., 'C:'). If omitted, returns all drives."
                }
            },
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
        """Execute disk usage query"""
        try:
            import psutil
        except ImportError:
            return {
                "status": "error",
                "error": "Dependency not available: psutil"
            }
        
        specific_drive = args.get("drive")
        
        try:
            partitions = psutil.disk_partitions()
            drives = []
            
            for partition in partitions:
                # Skip CD-ROMs and removable without media
                if 'cdrom' in partition.opts.lower():
                    continue
                
                drive_letter = partition.mountpoint
                
                # If specific drive requested, filter
                if specific_drive:
                    if not drive_letter.upper().startswith(specific_drive.upper()):
                        continue
                
                try:
                    usage = psutil.disk_usage(partition.mountpoint)
                    
                    drive_info = {
                        "drive": drive_letter,
                        "filesystem": partition.fstype,
                        "total_bytes": usage.total,
                        "used_bytes": usage.used,
                        "free_bytes": usage.free,
                        "percent_used": usage.percent,
                        "total_human": self._format_bytes(usage.total),
                        "used_human": self._format_bytes(usage.used),
                        "free_human": self._format_bytes(usage.free)
                    }
                    drives.append(drive_info)
                    
                except PermissionError:
                    # Some drives may not be accessible
                    drives.append({
                        "drive": drive_letter,
                        "error": "Permission denied"
                    })
            
            if not drives:
                return {
                    "status": "error",
                    "error": f"No drives found" + (f" matching '{specific_drive}'" if specific_drive else "")
                }
            
            logging.info(f"Disk usage queried for {len(drives)} drive(s)")
            return {
                "status": "success",
                "action": "get_disk_usage",
                "drives": drives
            }
            
        except Exception as e:
            logging.error(f"Failed to get disk usage: {e}")
            return {
                "status": "error",
                "error": f"Failed to get disk usage: {str(e)}"
            }
