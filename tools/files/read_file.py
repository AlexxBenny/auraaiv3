"""Tool: files.read_file

Reads content from a file.

Category: file_operation
Risk Level: none
Side Effects: none
"""

from pathlib import Path
from typing import Dict, Any
from ..base import Tool
from .safety import normalize_path, validate_read_path


class ReadFile(Tool):
    """Read content from a file"""
    
    @property
    def name(self) -> str:
        return "files.read_file"
    
    @property
    def description(self) -> str:
        return "Reads and returns the content of a file"
    
    @property
    def risk_level(self) -> str:
        return "none"  # Read-only operation
    
    @property
    def side_effects(self) -> list[str]:
        return []  # No side effects
    
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
                    "description": "Path to the file to read"
                },
                "encoding": {
                    "type": "string",
                    "default": "utf-8",
                    "description": "Text encoding (utf-8, latin-1, etc.)"
                }
            },
            "required": ["path"]
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Read file content"""
        if not self.validate_args(args):
            raise ValueError(f"Invalid arguments for {self.name}")
        
        raw_path = args.get("path")
        encoding = args.get("encoding", "utf-8")
        
        if not raw_path:
            return {"status": "error", "error": "Path is required"}
        
        # Normalize path
        path = normalize_path(raw_path)
        
        # Validate read is allowed
        valid, error = validate_read_path(path)
        if not valid:
            return {"status": "error", "error": error}
        
        if not path.is_file():
            return {"status": "error", "error": f"Not a file: {path}"}
        
        try:
            content = path.read_text(encoding=encoding)
            
            return {
                "status": "success",
                "path": str(path),
                "content": content,
                "size_bytes": len(content.encode(encoding)),
                "lines": content.count("\n") + (1 if content and not content.endswith("\n") else 0)
            }
            
        except UnicodeDecodeError:
            return {
                "status": "error",
                "error": f"Cannot decode file with {encoding} encoding",
                "hint": "Try a different encoding like 'latin-1'"
            }
        except PermissionError:
            return {"status": "error", "error": f"Permission denied: {path}"}
        except OSError as e:
            return {"status": "error", "error": f"Failed to read file: {e}"}
