"""Tool: files.append_file

Appends content to an existing file.

Category: file_operation
Risk Level: low
Side Effects: file_modified
"""

from pathlib import Path
from typing import Dict, Any
from ..base import Tool
from .safety import normalize_path, validate_write_path


class AppendFile(Tool):
    """Append content to a file"""
    
    @property
    def name(self) -> str:
        return "files.append_file"
    
    @property
    def description(self) -> str:
        return "Appends content to the end of an existing file"
    
    @property
    def risk_level(self) -> str:
        return "low"  # Non-destructive, adds to existing
    
    @property
    def side_effects(self) -> list[str]:
        return ["file_modified"]
    
    @property
    def stabilization_time_ms(self) -> int:
        return 100
    
    @property
    def reversible(self) -> bool:
        return False  # Cannot easily remove appended content
    
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
                    "description": "Content to append"
                },
                "newline": {
                    "type": "boolean",
                    "default": True,
                    "description": "Add newline before content if file doesn't end with one"
                }
            },
            "required": ["path", "content"]
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Append content to file"""
        if not self.validate_args(args):
            raise ValueError(f"Invalid arguments for {self.name}")
        
        raw_path = args.get("path")
        content = args.get("content")
        add_newline = args.get("newline", True)
        
        if not raw_path:
            return {"status": "error", "error": "Path is required"}
        if content is None:
            return {"status": "error", "error": "Content is required"}
        
        # Normalize path FIRST
        path = normalize_path(raw_path)
        
        # Validate write is allowed
        valid, error = validate_write_path(path)
        if not valid:
            return {"status": "blocked", "error": error}
        
        # File must exist for append
        if not path.exists():
            return {
                "status": "error",
                "error": f"File does not exist: {path}",
                "hint": "Use files.create_file or files.write_file first"
            }
        
        if not path.is_file():
            return {"status": "error", "error": f"Not a file: {path}"}
        
        try:
            # Get current content to check if we need newline
            previous_size = path.stat().st_size
            
            # Read last character to check for newline
            needs_newline = False
            if add_newline and previous_size > 0:
                with open(path, "rb") as f:
                    f.seek(-1, 2)  # Go to last byte
                    last_char = f.read(1)
                    needs_newline = last_char not in (b"\n", b"\r")
            
            # Append content
            with open(path, "a", encoding="utf-8") as f:
                if needs_newline:
                    f.write("\n")
                f.write(content)
            
            new_size = path.stat().st_size
            
            return {
                "status": "success",
                "path": str(path),
                "previous_size_bytes": previous_size,
                "new_size_bytes": new_size,
                "bytes_added": new_size - previous_size
            }
            
        except PermissionError:
            return {"status": "error", "error": f"Permission denied: {path}"}
        except OSError as e:
            return {"status": "error", "error": f"Failed to append to file: {e}"}
