"""Tool: system.clipboard.read

Reads text content from the system clipboard.

Category: query
Risk Level: low (accesses user clipboard data)
Side Effects: none

Dependencies: pyperclip (hard requirement)

CONSTRAINT: Text-only. Does not support images, rich text, or files.
"""

from typing import Dict, Any
from ...base import Tool


class ReadClipboard(Tool):
    """Read text content from clipboard"""
    
    @property
    def name(self) -> str:
        return "system.clipboard.read"
    
    @property
    def description(self) -> str:
        return "Reads text content from the system clipboard"
    
    @property
    def risk_level(self) -> str:
        return "low"  # Reads potentially sensitive data
    
    @property
    def side_effects(self) -> list[str]:
        return []  # No side effects (read-only)
    
    @property
    def stabilization_time_ms(self) -> int:
        return 0  # Instantaneous
    
    @property
    def reversible(self) -> bool:
        return True  # Nothing to reverse
    
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
            "properties": {},
            "required": []
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute clipboard read"""
        if not self.validate_args(args):
            raise ValueError(f"Invalid arguments for {self.name}")
        
        try:
            import pyperclip
        except ImportError:
            return {
                "status": "error",
                "error": "Dependency not installed: pyperclip"
            }
        
        try:
            content = pyperclip.paste()
            
            return {
                "status": "success",
                "content": content,
                "length": len(content),
                "content_type": "text"  # Explicit: text-only
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": f"Failed to read clipboard: {str(e)}"
            }
