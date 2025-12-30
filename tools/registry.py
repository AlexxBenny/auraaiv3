"""Tool Registry - central registry for all available tools

This is the deterministic router - no AI here.
"""

from typing import Dict, Optional
from .base import Tool


class ToolRegistry:
    """Central registry for all tools"""
    
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
    
    def register(self, tool: Tool):
        """Register a tool"""
        if not isinstance(tool, Tool):
            raise TypeError(f"Tool must inherit from Tool base class")
        
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        
        self._tools[tool.name] = tool
    
    def get(self, tool_name: str) -> Optional[Tool]:
        """Get a tool by name"""
        return self._tools.get(tool_name)
    
    def has(self, tool_name: str) -> bool:
        """Check if tool exists"""
        return tool_name in self._tools
    
    def list_all(self) -> Dict[str, Dict[str, any]]:
        """List all registered tools with metadata"""
        return {
            name: tool.to_dict()
            for name, tool in self._tools.items()
        }
    
    def get_tools_for_llm(self) -> list[Dict[str, any]]:
        """Get tool metadata formatted for LLM"""
        return [tool.to_dict() for tool in self._tools.values()]


# Global registry instance
_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """Get global tool registry"""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry

