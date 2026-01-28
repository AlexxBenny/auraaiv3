"""Tool: files.list_directory

Lists files and folders in a directory.

Category: file_operation
Risk Level: none
Side Effects: none
"""

from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
from ..base import Tool
from .safety import normalize_path


class ListDirectory(Tool):
    """List directory contents"""
    
    @property
    def name(self) -> str:
        return "files.list_directory"
    
    @property
    def description(self) -> str:
        return "Lists all files and folders in a directory"
    
    @property
    def risk_level(self) -> str:
        return "none"  # Read-only
    
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
                    "description": "Path to the directory to list"
                },
                "include_hidden": {
                    "type": "boolean",
                    "default": False,
                    "description": "Include hidden files (starting with .)"
                }
            },
            "required": ["path"]
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List directory contents"""
        if not self.validate_args(args):
            raise ValueError(f"Invalid arguments for {self.name}")
        
        raw_path = args.get("path")
        include_hidden = args.get("include_hidden", False)
        
        if not raw_path:
            return {"status": "error", "error": "Path is required"}
        
        # Normalize path
        path = normalize_path(raw_path)
        
        # Check existence
        if not path.exists():
            return {"status": "error", "error": f"Directory does not exist: {path}"}
        
        if not path.is_dir():
            return {"status": "error", "error": f"Not a directory: {path}"}
        
        try:
            files: List[Dict[str, Any]] = []
            folders: List[Dict[str, Any]] = []
            
            for item in path.iterdir():
                # Skip hidden files if not requested
                if not include_hidden and item.name.startswith("."):
                    continue
                
                try:
                    stat = item.stat()
                    info = {
                        "name": item.name,
                        "size_bytes": stat.st_size if item.is_file() else None,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                    }
                    
                    if item.is_file():
                        info["extension"] = item.suffix
                        files.append(info)
                    elif item.is_dir():
                        folders.append(info)
                        
                except (OSError, PermissionError):
                    # Skip inaccessible items
                    continue
            
            # Sort by name
            files.sort(key=lambda x: x["name"].lower())
            folders.sort(key=lambda x: x["name"].lower())
            
            return {
                "status": "success",
                "path": str(path),
                "folders": folders,
                "files": files,
                "folder_count": len(folders),
                "file_count": len(files),
                "total_count": len(folders) + len(files)
            }
            
        except PermissionError:
            return {"status": "error", "error": f"Permission denied: {path}"}
        except OSError as e:
            return {"status": "error", "error": f"Failed to list directory: {e}"}
