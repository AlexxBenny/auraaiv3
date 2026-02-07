"""Tool: files.create_file

Creates a new file, optionally with initial content.

Category: file_operation
Risk Level: low
Side Effects: file_created
"""

from pathlib import Path
from typing import Dict, Any
from ..base import Tool
from .safety import normalize_path, validate_write_path, validate_parent_creation


class CreateFile(Tool):
    """Create a new file"""
    
    @property
    def name(self) -> str:
        return "files.create_file"
    
    @property
    def description(self) -> str:
        return "Creates a new file at the specified path, optionally with initial content"
    
    @property
    def risk_level(self) -> str:
        return "low"
    
    @property
    def side_effects(self) -> list[str]:
        return ["file_created"]
    
    @property
    def stabilization_time_ms(self) -> int:
        return 100
    
    @property
    def reversible(self) -> bool:
        return True  # Can delete the file
    
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
                    "description": "Path for the new file (absolute or relative)"
                },
                "content": {
                    "type": "string",
                    "default": "",
                    "description": "Initial content for the file (empty by default)"
                },
                "create_parents": {
                    "type": "boolean",
                    "default": True,
                    "description": "Create parent directories if they don't exist"
                }
            },
            "required": ["path"]
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new file"""
        if not self.validate_args(args):
            raise ValueError(f"Invalid arguments for {self.name}")
        
        raw_path = args.get("path")
        content = args.get("content", "")
        create_parents = args.get("create_parents", True)
        
        if not raw_path:
            return {
                "status": "error",
                "error": "Path is required",
                "failure_class": "logical"  # Invalid input (not retryable)
            }
        
        # Normalize path FIRST (prevents traversal attacks)
        path = normalize_path(raw_path)
        
        # Validate write is allowed
        valid, error = validate_write_path(path)
        if not valid:
            return {
                "status": "blocked",
                "error": error,
                "failure_class": "logical"  # Validation failure (not retryable)
            }
        
        # Check if file already exists
        if path.exists():
            return {
                "status": "error",
                "error": f"File already exists: {path}",
                "hint": "Use files.write_file with overwrite=True to replace",
                "failure_class": "logical"  # File exists (not retryable)
            }
        
        # Validate parent creation is safe (if needed)
        if create_parents and not path.parent.exists():
            valid, error = validate_parent_creation(path)
            if not valid:
                return {"status": "blocked", "error": error}
        
        try:
            # Create parents if requested and needed
            if create_parents:
                path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create the file with content
            path.write_text(content, encoding="utf-8")
            
            return {
                "status": "success",
                "path": str(path),
                "size_bytes": len(content.encode("utf-8")),
                "created_parents": create_parents and not path.parent.exists()
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
                "error": f"Failed to create file: {e}",
                "failure_class": failure_class
            }
