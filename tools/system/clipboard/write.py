"""Tool: system.clipboard.write

Writes text content to the system clipboard.

Category: action
Risk Level: low
Side Effects: clipboard_modified

Dependencies: pyperclip (hard requirement)

CONSTRAINT: Text-only. Does not support images, rich text, or files.
"""

from typing import Dict, Any
from ...base import Tool


class WriteClipboard(Tool):
    """Write text content to clipboard"""
    
    @property
    def name(self) -> str:
        return "system.clipboard.write"
    
    @property
    def description(self) -> str:
        return "Writes text content to the system clipboard"
    
    @property
    def risk_level(self) -> str:
        return "low"  # Overwrites clipboard, but reversible
    
    @property
    def side_effects(self) -> list[str]:
        return ["clipboard_modified"]
    
    @property
    def stabilization_time_ms(self) -> int:
        return 50
    
    @property
    def reversible(self) -> bool:
        return True  # Can overwrite again
    
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
                "text": {
                    "type": "string",
                    "description": "Text to copy to clipboard"
                }
            },
            "required": ["text"]
        }
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute clipboard write"""
        if not self.validate_args(args):
            raise ValueError(f"Invalid arguments for {self.name}")
        
        text = args.get("text")
        if text is None:
            return {
                "status": "error",
                "error": "Required argument 'text' not provided"
            }
        
        # Ensure text is string
        if not isinstance(text, str):
            text = str(text)
        
        try:
            import pyperclip
        except ImportError:
            return {
                "status": "error",
                "error": "Dependency not installed: pyperclip"
            }
        
        try:
            pyperclip.copy(text)
            
            return {
                "status": "success",
                "copied_text": text,
                "length": len(text),
                "content_type": "text"  # Explicit: text-only
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": f"Failed to write to clipboard: {str(e)}"
            }
