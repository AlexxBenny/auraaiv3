"""Tool: files.delete_file

Deletes a file.

Category: file_operation
Risk Level: high
Side Effects: file_deleted

SAFETY: Protected paths are blocked at executor level.
"""

from pathlib import Path
from typing import Dict, Any
from ..base import Tool
from .safety import normalize_path, validate_delete_path


class DeleteFile(Tool):
    """Delete a file"""
    
    @property
    def name(self) -> str:
        return "files.delete_file"
    
    @property
    def description(self) -> str:
        return "Permanently deletes a file (cannot be undone)"
    
    @property
    def risk_level(self) -> str:
        return "high"  # Irreversible
    
    @property
    def side_effects(self) -> list[str]:
        return ["file_deleted"]
    
    @property
    def stabilization_time_ms(self) -> int:
        return 100
    
    @property
    def reversible(self) -> bool:
        return False  # Cannot recover deleted file
    
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
                    "description": "Path to the file to delete"
                }
            },
            "required": ["path"]
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a file"""
        if not self.validate_args(args):
            raise ValueError(f"Invalid arguments for {self.name}")
        
        raw_path = args.get("path")
        
        if not raw_path:
            return {"status": "error", "error": "Path is required"}
        
        # Normalize path FIRST (prevents traversal attacks)
        path = normalize_path(raw_path)
        
        # CRITICAL: Validate delete is allowed
        valid, error = validate_delete_path(path)
        if not valid:
            return {"status": "blocked", "error": error}
        
        # Check existence
        if not path.exists():
            return {"status": "error", "error": f"File does not exist: {path}"}
        
        # Must be a file, not directory
        if not path.is_file():
            return {
                "status": "error",
                "error": f"Not a file: {path}",
                "hint": "Use files.delete_folder for directories"
            }
        
        try:
            # Get file info before deletion
            size = path.stat().st_size
            name = path.name
            
            # Delete the file
            path.unlink()
            
            return {
                "status": "success",
                "deleted_path": str(path),
                "deleted_name": name,
                "deleted_size_bytes": size
            }
            
        except PermissionError:
            return {"status": "error", "error": f"Permission denied: {path}"}
        except OSError as e:
            return {"status": "error", "error": f"Failed to delete file: {e}"}
