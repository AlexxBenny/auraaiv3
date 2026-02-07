"""Tool: files.get_info

Gets information about a file or folder.

Category: file_operation
Risk Level: none
Side Effects: none
"""

from pathlib import Path
from datetime import datetime
from typing import Dict, Any
from ..base import Tool
from .safety import normalize_path


class GetInfo(Tool):
    """Get file or folder information"""
    
    @property
    def name(self) -> str:
        return "files.get_info"
    
    @property
    def description(self) -> str:
        return "Gets detailed information about a file or folder"
    
    @property
    def risk_level(self) -> str:
        return "none"
    
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
                "path": {
                    "type": "string",
                    "description": "Path to the file or folder"
                }
            },
            "required": ["path"]
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get file/folder info"""
        if not self.validate_args(args):
            raise ValueError(f"Invalid arguments for {self.name}")
        
        raw_path = args.get("path")
        
        if not raw_path:
            return {
                "status": "error",
                "error": "Path is required",
                "failure_class": "logical"  # Invalid input
            }
        
        # Normalize path
        path = normalize_path(raw_path)
        
        # Check existence
        if not path.exists():
            return {
                "status": "error",
                "error": f"Path does not exist: {path}",
                "failure_class": "logical"  # Path doesn't exist
            }
        
        try:
            stat = path.stat()
            
            info = {
                "status": "success",
                "path": str(path),
                "name": path.name,
                "is_file": path.is_file(),
                "is_directory": path.is_dir(),
                "size_bytes": stat.st_size,
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "accessed": datetime.fromtimestamp(stat.st_atime).isoformat(),
            }
            
            if path.is_file():
                info["extension"] = path.suffix
                info["stem"] = path.stem  # Filename without extension
            
            if path.is_dir():
                try:
                    contents = list(path.iterdir())
                    info["item_count"] = len(contents)
                    info["file_count"] = sum(1 for c in contents if c.is_file())
                    info["folder_count"] = sum(1 for c in contents if c.is_dir())
                except PermissionError:
                    info["item_count"] = "Permission denied"
            
            return info
            
        except PermissionError:
            return {
                "status": "error",
                "error": f"Permission denied: {path}",
                "failure_class": "permission"  # Access denied
            }
        except OSError as e:
            # File info operations can fail due to transient IO issues (environmental)
            return {
                "status": "error",
                "error": f"Failed to get info: {e}",
                "failure_class": "environmental"  # Transient IO issue
            }
