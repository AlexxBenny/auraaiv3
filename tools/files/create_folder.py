"""Tool: files.create_folder

Creates a new folder.

Category: file_operation
Risk Level: low
Side Effects: folder_created
"""

from pathlib import Path
from typing import Dict, Any
from ..base import Tool
from .safety import normalize_path, validate_write_path, validate_parent_creation


class CreateFolder(Tool):
    """Create a new folder"""
    
    @property
    def name(self) -> str:
        return "files.create_folder"
    
    @property
    def description(self) -> str:
        return "Creates a new folder at the specified path"
    
    @property
    def risk_level(self) -> str:
        return "low"
    
    @property
    def side_effects(self) -> list[str]:
        return ["folder_created"]
    
    @property
    def stabilization_time_ms(self) -> int:
        return 100
    
    @property
    def reversible(self) -> bool:
        return True  # Can delete the folder
    
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
                    "description": "Path for the new folder"
                },
                "parents": {
                    "type": "boolean",
                    "default": True,
                    "description": "Create parent directories if they don't exist"
                },
                "exist_ok": {
                    "type": "boolean",
                    "default": True,
                    "description": "Don't fail if folder already exists"
                }
            },
            "required": ["path"]
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new folder"""
        if not self.validate_args(args):
            raise ValueError(f"Invalid arguments for {self.name}")
        
        raw_path = args.get("path")
        create_parents = args.get("parents", True)
        exist_ok = args.get("exist_ok", True)
        
        if not raw_path:
            return {
                "status": "error",
                "error": "Path is required",
                "failure_class": "logical"  # Invalid input
            }
        
        # Normalize path FIRST
        path = normalize_path(raw_path)
        
        # Validate we can create here
        valid, error = validate_write_path(path)
        if not valid:
            return {
                "status": "blocked",
                "error": error,
                "failure_class": "logical"  # Validation failure
            }
        
        # Check if exists
        if path.exists():
            if exist_ok and path.is_dir():
                return {
                    "status": "success",
                    "path": str(path),
                    "already_existed": True
                }
            elif path.is_file():
                return {
                    "status": "error",
                    "error": f"A file exists at this path: {path}",
                    "failure_class": "logical"  # Conflict
                }
            else:
                return {
                    "status": "error",
                    "error": f"Path already exists: {path}",
                    "failure_class": "logical"  # Conflict
                }
        
        # Validate parent creation if needed
        if create_parents and not path.parent.exists():
            valid, error = validate_parent_creation(path)
            if not valid:
                return {
                    "status": "blocked",
                    "error": error,
                    "failure_class": "logical"  # Validation failure
                }
        
        try:
            path.mkdir(parents=create_parents, exist_ok=exist_ok)
            
            return {
                "status": "success",
                "path": str(path),
                "already_existed": False,
                "created_parents": create_parents
            }
            
        except PermissionError:
            return {
                "status": "error",
                "error": f"Permission denied: {path}",
                "failure_class": "permission"  # Access denied
            }
        except FileNotFoundError:
            return {
                "status": "error",
                "error": f"Parent directory does not exist",
                "hint": "Set parents=True to create parent directories",
                "failure_class": "logical"  # Parent doesn't exist
            }
        except OSError as e:
            # File operations can fail due to locks, disk issues (environmental)
            return {
                "status": "error",
                "error": f"Failed to create folder: {e}",
                "failure_class": "environmental"  # Transient IO issue
            }
