"""Tool: files.rename

Renames a file or folder.

Category: file_operation
Risk Level: medium
Side Effects: file_renamed
"""

from pathlib import Path
from typing import Dict, Any
from ..base import Tool
from .safety import normalize_path, validate_write_path, validate_delete_path


class Rename(Tool):
    """Rename a file or folder"""
    
    @property
    def name(self) -> str:
        return "files.rename"
    
    @property
    def description(self) -> str:
        return "Renames a file or folder to a new name (in the same directory)"
    
    @property
    def risk_level(self) -> str:
        return "medium"
    
    @property
    def side_effects(self) -> list[str]:
        return ["file_renamed"]
    
    @property
    def stabilization_time_ms(self) -> int:
        return 100
    
    @property
    def reversible(self) -> bool:
        return True  # Can rename back
    
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
                    "description": "Path to the file or folder to rename"
                },
                "new_name": {
                    "type": "string",
                    "description": "New name (not full path, just the name)"
                }
            },
            "required": ["path", "new_name"]
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Rename file or folder"""
        if not self.validate_args(args):
            raise ValueError(f"Invalid arguments for {self.name}")
        
        raw_path = args.get("path")
        new_name = args.get("new_name")
        
        if not raw_path:
            return {"status": "error", "error": "Path is required"}
        if not new_name:
            return {"status": "error", "error": "New name is required"}
        
        # Validate new_name doesn't contain path separators
        if "/" in new_name or "\\" in new_name:
            return {
                "status": "error",
                "error": "new_name must be a name, not a path",
                "hint": "Use files.move to change location"
            }
        
        # Normalize source path
        source = normalize_path(raw_path)
        
        # Check source exists
        if not source.exists():
            return {"status": "error", "error": f"Source does not exist: {source}"}
        
        # Build destination path (same directory, new name)
        destination = source.parent / new_name
        
        # Validate we can modify source and destination
        valid, error = validate_delete_path(source)  # Need to "remove" old name
        if not valid:
            return {"status": "blocked", "error": error}
        
        valid, error = validate_write_path(destination)
        if not valid:
            return {"status": "blocked", "error": error}
        
        # Check destination doesn't exist
        if destination.exists():
            return {"status": "error", "error": f"Destination already exists: {destination}"}
        
        try:
            old_name = source.name
            source.rename(destination)
            
            return {
                "status": "success",
                "old_path": str(source),
                "new_path": str(destination),
                "old_name": old_name,
                "new_name": new_name
            }
            
        except PermissionError:
            return {"status": "error", "error": f"Permission denied"}
        except OSError as e:
            return {"status": "error", "error": f"Failed to rename: {e}"}
