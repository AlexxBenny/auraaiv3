"""Tool: files.copy

Copies a file or folder to a new location.

Category: file_operation
Risk Level: low
Side Effects: file_created
"""

import shutil
from pathlib import Path
from typing import Dict, Any
from ..base import Tool
from .safety import normalize_path, validate_write_path, validate_read_path


class Copy(Tool):
    """Copy a file or folder"""
    
    @property
    def name(self) -> str:
        return "files.copy"
    
    @property
    def description(self) -> str:
        return "Copies a file or folder to a new location"
    
    @property
    def risk_level(self) -> str:
        return "low"  # Non-destructive
    
    @property
    def side_effects(self) -> list[str]:
        return ["file_created"]
    
    @property
    def stabilization_time_ms(self) -> int:
        return 200
    
    @property
    def reversible(self) -> bool:
        return True  # Can delete copy
    
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
                    "description": "Path to the file or folder to copy"
                },
                "destination": {
                    "type": "string",
                    "description": "Destination path"
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
        """Copy file or folder"""
        if not self.validate_args(args):
            raise ValueError(f"Invalid arguments for {self.name}")
        
        raw_source = args.get("source")
        raw_dest = args.get("destination")
        overwrite = args.get("overwrite", False)
        
        if not raw_source:
            return {"status": "error", "error": "Source is required"}
        if not raw_dest:
            return {"status": "error", "error": "Destination is required"}
        
        # Normalize paths FIRST
        source = normalize_path(raw_source)
        destination = normalize_path(raw_dest)
        
        # Check source exists
        if not source.exists():
            return {"status": "error", "error": f"Source does not exist: {source}"}
        
        # Validate read access on source (for files)
        if source.is_file():
            valid, error = validate_read_path(source)
            if not valid:
                return {"status": "error", "error": error}
        
        # If destination is a directory, put source inside it
        if destination.is_dir():
            destination = destination / source.name
        
        # Validate we can write to destination
        valid, error = validate_write_path(destination)
        if not valid:
            return {"status": "blocked", "error": error}
        
        # Check destination
        if destination.exists():
            if not overwrite:
                return {
                    "status": "error",
                    "error": f"Destination exists and overwrite=False: {destination}",
                    "hint": "Set overwrite=True to replace"
                }
            # Remove destination if overwriting
            if destination.is_file():
                destination.unlink()
            else:
                shutil.rmtree(destination)
        
        try:
            # Create parent directories if needed
            destination.parent.mkdir(parents=True, exist_ok=True)
            
            if source.is_file():
                shutil.copy2(str(source), str(destination))
            else:
                shutil.copytree(str(source), str(destination))
            
            return {
                "status": "success",
                "source": str(source),
                "destination": str(destination),
                "is_directory": source.is_dir()
            }
            
        except PermissionError:
            return {
                "status": "error",
                "error": f"Permission denied",
                "failure_class": "permission"  # Access denied (not retryable)
            }
        except OSError as e:
            error_str = str(e).lower()
            if "device" in error_str or "network" in error_str or "timeout" in error_str or "disk full" in error_str:
                failure_class = "environmental"
            else:
                failure_class = "logical"
            return {
                "status": "error",
                "error": f"Failed to copy: {e}",
                "failure_class": failure_class
            }
