"""Tool: files.write_file

Writes content to a file, replacing existing content.

Category: file_operation
Risk Level: medium (destructive)
Side Effects: file_modified
"""

from pathlib import Path
from typing import Dict, Any
from ..base import Tool
from .safety import normalize_path, validate_write_path, validate_parent_creation


class WriteFile(Tool):
    """Write content to a file"""
    
    @property
    def name(self) -> str:
        return "files.write_file"
    
    @property
    def description(self) -> str:
        return "Writes content to a file, replacing any existing content"
    
    @property
    def risk_level(self) -> str:
        return "medium"  # Destructive - replaces content
    
    @property
    def side_effects(self) -> list[str]:
        return ["file_modified"]
    
    @property
    def stabilization_time_ms(self) -> int:
        return 100
    
    @property
    def reversible(self) -> bool:
        return False  # Cannot recover overwritten content
    
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
                    "description": "Path to the file"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file"
                },
                "overwrite": {
                    "type": "boolean",
                    "default": False,
                    "description": "If True, overwrite existing file. If False, fail if file exists."
                },
                "create_if_missing": {
                    "type": "boolean",
                    "default": True,
                    "description": "Create the file if it doesn't exist"
                }
            },
            "required": ["path", "content"]
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Write content to file"""
        if not self.validate_args(args):
            raise ValueError(f"Invalid arguments for {self.name}")
        
        raw_path = args.get("path")
        content = args.get("content")
        overwrite = args.get("overwrite", False)
        create_if_missing = args.get("create_if_missing", True)
        
        if not raw_path:
            return {
                "status": "error",
                "error": "Path is required",
                "failure_class": "logical"  # Invalid input (not retryable)
            }
        if content is None:
            return {
                "status": "error",
                "error": "Content is required",
                "failure_class": "logical"  # Invalid input (not retryable)
            }
        
        # Normalize path FIRST
        path = normalize_path(raw_path)
        
        # Validate write is allowed
        valid, error = validate_write_path(path)
        if not valid:
            return {"status": "blocked", "error": error}
        
        # Check existence and overwrite flag
        if path.exists():
            # Check if file is empty - empty files don't need overwrite
            try:
                file_size = path.stat().st_size
            except OSError:
                file_size = 0
                
            if file_size > 0 and not overwrite:
                return {
                    "status": "error",
                    "error": f"File has content and overwrite=False: {path}",
                    "hint": "Set overwrite=True to replace content",
                    "failure_class": "logical"  # Policy violation (not retryable)
                }
        else:
            if not create_if_missing:
                return {
                    "status": "error",
                    "error": f"File does not exist: {path}",
                    "failure_class": "logical"  # File doesn't exist (not retryable)
                }
            
            # Validate parent creation
            if not path.parent.exists():
                valid, error = validate_parent_creation(path)
                if not valid:
                    return {"status": "blocked", "error": error}
                path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            # Get previous size for reporting
            previous_size = path.stat().st_size if path.exists() else 0
            
            # Write content
            path.write_text(content, encoding="utf-8")
            
            new_size = len(content.encode("utf-8"))
            
            return {
                "status": "success",
                "path": str(path),
                "previous_size_bytes": previous_size,
                "new_size_bytes": new_size,
                "overwrote": path.exists() and overwrite
            }
            
        except PermissionError:
            return {
                "status": "error",
                "error": f"Permission denied: {path}",
                "failure_class": "permission"  # Access denied (not retryable)
            }
        except OSError as e:
            error_str = str(e).lower()
            # Determine if transient (environmental) or permanent (logical)
            if "device" in error_str or "network" in error_str or "timeout" in error_str or "disk full" in error_str:
                failure_class = "environmental"
            else:
                failure_class = "logical"
            return {
                "status": "error",
                "error": f"Failed to write file: {e}",
                "failure_class": failure_class
            }
