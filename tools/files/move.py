"""Tool: files.move

Moves a file or folder to a new location.

Category: file_operation
Risk Level: medium
Side Effects: file_moved
"""

import shutil
from pathlib import Path
from typing import Dict, Any
from ..base import Tool
from .safety import normalize_path, validate_write_path, validate_delete_path


class Move(Tool):
    """Move a file or folder"""
    
    @property
    def name(self) -> str:
        return "files.move"
    
    @property
    def description(self) -> str:
        return "Moves a file or folder to a new location"
    
    @property
    def risk_level(self) -> str:
        return "medium"
    
    @property
    def side_effects(self) -> list[str]:
        return ["file_moved"]
    
    @property
    def stabilization_time_ms(self) -> int:
        return 200
    
    @property
    def reversible(self) -> bool:
        return True  # Can move back
    
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
                "source": {
                    "type": "string",
                    "description": "Path to the file or folder to move"
                },
                "destination": {
                    "type": "string",
                    "description": "Destination path (can be directory or full path)"
                },
                "overwrite": {
                    "type": "boolean",
                    "default": False,
                    "description": "Overwrite if destination exists"
                }
            },
            "required": ["source", "destination"]
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Move file or folder"""
        if not self.validate_args(args):
            raise ValueError(f"Invalid arguments for {self.name}")
        
        raw_source = args.get("source")
        raw_dest = args.get("destination")
        overwrite = args.get("overwrite", False)
        
        if not raw_source:
            return {
                "status": "error",
                "error": "Source is required",
                "failure_class": "logical"  # Invalid input
            }
        if not raw_dest:
            return {
                "status": "error",
                "error": "Destination is required",
                "failure_class": "logical"  # Invalid input
            }
        
        # Normalize paths FIRST
        source = normalize_path(raw_source)
        destination = normalize_path(raw_dest)
        
        # Check source exists
        if not source.exists():
            return {
                "status": "error",
                "error": f"Source does not exist: {source}",
                "failure_class": "logical"  # File doesn't exist
            }
        
        # Validate we can modify source
        valid, error = validate_delete_path(source)
        if not valid:
            return {
                "status": "blocked",
                "error": error,
                "failure_class": "logical"  # Validation failure
            }
        
        # If destination is a directory, put source inside it
        if destination.is_dir():
            destination = destination / source.name
        
        # Validate we can write to destination
        valid, error = validate_write_path(destination)
        if not valid:
            return {
                "status": "blocked",
                "error": error,
                "failure_class": "logical"  # Validation failure
            }
        
        # Check destination
        if destination.exists():
            if not overwrite:
                return {
                    "status": "error",
                    "error": f"Destination exists and overwrite=False: {destination}",
                    "hint": "Set overwrite=True to replace",
                    "failure_class": "logical"  # Policy violation
                }
            # Remove destination if overwriting
            if destination.is_file():
                destination.unlink()
            else:
                shutil.rmtree(destination)
        
        try:
            # Create parent directories if needed
            destination.parent.mkdir(parents=True, exist_ok=True)
            
            # Move
            shutil.move(str(source), str(destination))
            
            return {
                "status": "success",
                "source": str(source),
                "destination": str(destination)
            }
            
        except PermissionError:
            return {
                "status": "error",
                "error": f"Permission denied",
                "failure_class": "permission"  # Access denied
            }
        except OSError as e:
            # File operations can fail due to locks, disk issues (environmental)
            # or invalid paths (logical). Default to environmental for IO operations.
            return {
                "status": "error",
                "error": f"Failed to move: {e}",
                "failure_class": "environmental"  # Transient IO issue
            }
