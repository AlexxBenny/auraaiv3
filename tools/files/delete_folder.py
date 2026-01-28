"""Tool: files.delete_folder

Deletes a folder.

Category: file_operation
Risk Level: high
Side Effects: folder_deleted

SAFETY: 
- Protected paths are blocked
- Recursive deletion requires explicit flag
"""

import shutil
from pathlib import Path
from typing import Dict, Any
from ..base import Tool
from .safety import normalize_path, validate_delete_path


class DeleteFolder(Tool):
    """Delete a folder"""
    
    @property
    def name(self) -> str:
        return "files.delete_folder"
    
    @property
    def description(self) -> str:
        return "Deletes a folder. Requires recursive=True for non-empty folders."
    
    @property
    def risk_level(self) -> str:
        return "high"
    
    @property
    def side_effects(self) -> list[str]:
        return ["folder_deleted"]
    
    @property
    def stabilization_time_ms(self) -> int:
        return 200
    
    @property
    def reversible(self) -> bool:
        return False
    
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
                    "description": "Path to the folder to delete"
                },
                "recursive": {
                    "type": "boolean",
                    "default": False,
                    "description": "If True, delete folder and all contents. If False, fail if not empty."
                }
            },
            "required": ["path"]
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a folder"""
        if not self.validate_args(args):
            raise ValueError(f"Invalid arguments for {self.name}")
        
        raw_path = args.get("path")
        recursive = args.get("recursive", False)
        
        if not raw_path:
            return {"status": "error", "error": "Path is required"}
        
        # Normalize path FIRST
        path = normalize_path(raw_path)
        
        # CRITICAL: Validate delete is allowed
        valid, error = validate_delete_path(path)
        if not valid:
            return {"status": "blocked", "error": error}
        
        # Check existence
        if not path.exists():
            return {"status": "error", "error": f"Folder does not exist: {path}"}
        
        if not path.is_dir():
            return {
                "status": "error",
                "error": f"Not a folder: {path}",
                "hint": "Use files.delete_file for files"
            }
        
        # Check if empty
        contents = list(path.iterdir())
        is_empty = len(contents) == 0
        
        if not is_empty and not recursive:
            return {
                "status": "error",
                "error": f"Folder is not empty ({len(contents)} items)",
                "hint": "Set recursive=True to delete folder and all contents"
            }
        
        try:
            name = path.name
            
            if is_empty:
                path.rmdir()
            else:
                shutil.rmtree(path)
            
            return {
                "status": "success",
                "deleted_path": str(path),
                "deleted_name": name,
                "was_recursive": not is_empty
            }
            
        except PermissionError:
            return {"status": "error", "error": f"Permission denied: {path}"}
        except OSError as e:
            return {"status": "error", "error": f"Failed to delete folder: {e}"}
