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
    
    @property
    def capability_class(self) -> str:
        """Semantic classification of what this tool does.
        
        MUST be one of: "actuate", "observe", "query"
        - actuate: causes change in world state (default)
        - observe: reads world state without modification
        - query: pure info request
        
        This is used as a HARD FILTER in ToolResolver. Only tools whose
        capability_class matches the PlannedAction's action_class will
        be considered. If no tools match, resolution FAILS LOUDLY.
        
        Override in subclasses. Default is "actuate" for backwards compatibility.
        """
        return "actuate"

    @property
    def requires_session(self) -> bool:
        """Indicates this tool requires an execution-scoped session (e.g., browser, UI automation).

        Tools that depend on a long-lived session (browser, remote desktop, mobile simulator, etc.)
        MUST override this to return True. This is treated as capability metadata (not browser-only).
        """
        return False

    @property
    def required_semantic_inputs(self) -> set:
        """Semantic inputs that must be provided by the planner (e.g., {'url', 'path'}).

        Tools that require planner-provided semantic fields should override this and list
        the required keys. The ToolResolver will never emit or populate these fields.
        """
        return set()
    
    @property
    def failure_class(self) -> str:
        """Default classification of this tool's failure mode for recoverability.
        
        MUST be one of: "environmental", "logical", "permission", "unknown"
        - environmental: network, timeout, transient OS state (RETRYABLE)
        - logical: invalid input, element not found (NOT retryable)
        - permission: access denied, elevation required (NOT retryable)
        - unknown: unclassified failures (default, treated as potentially retryable)
        
        This is a DEFAULT. Tools may override this per-execution by including
        "failure_class" in their result dictionary:
        
            return {
                "status": "error",
                "error": "Connection timed out",
                "failure_class": "environmental"  # overrides default
            }
        
        The orchestrator reads failure_class from the result first, then falls
        back to this property if not present.
        
        Override in subclasses. Default is "unknown" for safety.
        """
        return "unknown"

    # =========================================================================
    # MANDATORY PRECONDITIONS - Enforced by ToolExecutor, NOT LLM
    # =========================================================================
    
    @property
    def requires_focus(self) -> bool:
        """Does this tool require a focused window to work?
        
        If True, ToolExecutor will REFUSE to execute if no window is focused.
        Examples: keyboard.type, mouse.click
        """
        return False
    
    @property
    def requires_active_app(self) -> Optional[str]:
        """If set, tool requires a specific app to be focused.
        
        Value is a process name pattern (e.g., "notepad", "chrome").
        ToolExecutor will REFUSE if foreground window doesn't match.
        """
        return None
    
    @property
    def requires_unlocked_screen(self) -> bool:
        """Does this tool require an unlocked screen?
        
        If True, ToolExecutor will REFUSE if screen appears locked.
        Default True for safety - most actions need unlocked screen.
        """
        return True
    
    @property
    def is_destructive(self) -> bool:
        """Can this tool cause data loss or irreversible changes?
        
        If True, requires additional confirmation or safety checks.
        Examples: file delete, request_close (unsaved data)
        """
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
        """Export tool metadata for LLM and executor"""
        return {
            "name": self.name,
            "description": self.description,
            "schema": self.schema,
            "risk_level": self.risk_level,
            "side_effects": self.side_effects,
            "stabilization_time_ms": self.stabilization_time_ms,
            "reversible": self.reversible,
            "requires_visual_confirmation": self.requires_visual_confirmation,
            "capability_class": self.capability_class,  # Phase 2: semantic filter
            # Preconditions (enforced by executor, not LLM)
            "requires_focus": self.requires_focus,
            "requires_active_app": self.requires_active_app,
            "requires_unlocked_screen": self.requires_unlocked_screen,
            "is_destructive": self.is_destructive,
        }

