"""Tool base class - ALL tools must inherit from this

CRITICAL: Tools are deterministic Python only. NO AI inside tools.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class Tool(ABC):
    """Base class for all tools
    
    Tools are deterministic Python functions. They:
    - Have a name and description
    - Define their input schema (JSON Schema)
    - Execute deterministically
    - Return structured results
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name (must be unique)"""
        raise NotImplementedError
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description for LLM understanding"""
        raise NotImplementedError
    
    @property
    @abstractmethod
    def schema(self) -> Dict[str, Any]:
        """JSON Schema for tool arguments
        
        Example:
        {
            "type": "object",
            "properties": {
                "save_location": {"type": "string"}
            },
            "required": ["save_location"]
        }
        """
        raise NotImplementedError
    
    @property
    def risk_level(self) -> str:
        """Risk level: 'low', 'medium', 'high'"""
        return "medium"
        
    @property
    def side_effects(self) -> list[str]:
        """List of side effects (e.g., 'modifies_fs', 'changes_focus')"""
        return []
        
    @property
    def stabilization_time_ms(self) -> int:
        """Expected time for system to settle after execution (ms)"""
        return 0
        
    @property
    def reversible(self) -> bool:
        """Can this action be reversed trivially?"""
        return False

    @property
    def requires_visual_confirmation(self) -> bool:
        """Does this tool require visual checks to confirm success?"""
        return False

    @abstractmethod
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the tool with given arguments
        
        Args:
            args: Arguments matching the schema
            
        Returns:
            Dict with execution result. Must include "status" key.
            Example: {"status": "success", "path": "/path/to/file"}
            
        Raises:
            ValueError: If args don't match schema
            RuntimeError: If execution fails
        """
        raise NotImplementedError
    
    def validate_args(self, args: Dict[str, Any]) -> bool:
        """Validate arguments against schema (basic validation)"""
        if not isinstance(args, dict):
            return False
        
        # Check required fields
        required = self.schema.get("required", [])
        for field in required:
            if field not in args:
                return False
        
        # Basic type checking
        properties = self.schema.get("properties", {})
        for key, value in args.items():
            if key in properties:
                expected_type = properties[key].get("type")
                if expected_type == "string" and not isinstance(value, str):
                    return False
                elif expected_type == "integer" and not isinstance(value, int):
                    return False
                elif expected_type == "boolean" and not isinstance(value, bool):
                    return False
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Export tool metadata for LLM"""
        return {
            "name": self.name,
            "description": self.description,
            "schema": self.schema,
            "risk_level": self.risk_level,
            "side_effects": self.side_effects,
            "stabilization_time_ms": self.stabilization_time_ms,
            "reversible": self.reversible,
            "requires_visual_confirmation": self.requires_visual_confirmation
        }

