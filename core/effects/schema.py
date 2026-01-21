"""Effect Schema - Declarative goal objects for effect-based execution

This module defines the data structures for effects. 
Effects are DECLARATIVE GOALS, not logic.

CRITICAL CONSTRAINTS:
- Effect must not call verifiers
- Effect must not mutate itself (except state)
- Effect must not know about tools
- Effect is a data model ONLY

Phase 1: Schema introduction (no runtime integration)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, List


class EffectState(Enum):
    """
    Effect lifecycle state.
    
    Phase 1 transitions: PENDING → SATISFIED | SKIPPED
    Phase 4 adds: → FAILED
    
    State transitions are ONE-WAY per phase. No back-and-forth.
    """
    PENDING = "PENDING"      # Initial state, not yet evaluated
    SATISFIED = "SATISFIED"  # Postcondition verified true
    SKIPPED = "SKIPPED"      # Precondition was false, no action needed
    FAILED = "FAILED"        # Postcondition could not be satisfied (Phase 4)


class PostconditionType(Enum):
    """
    Typed postcondition categories.
    
    90% of effects should use typed postconditions (deterministic).
    10% may use CUSTOM (requires LLM judgment).
    0% should be ambiguous.
    """
    PROCESS_RUNNING = "process_running"
    WINDOW_VISIBLE = "window_visible"
    FILE_EXISTS = "file_exists"
    FILE_MODIFIED = "file_modified"
    STATE_CHANGED = "state_changed"
    CONTENT_CAPTURED = "content_captured"
    CUSTOM = "custom"  # LLM-judged escape hatch (rare)


@dataclass
class Postcondition:
    """
    Typed postcondition for machine-checkable verification.
    
    Attributes:
        type: PostconditionType - mandatory
        params: Dict - optional but structured (type-specific parameters)
        description: str - human-readable fallback for CUSTOM type
    """
    type: PostconditionType
    params: Dict[str, Any] = field(default_factory=dict)
    description: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for JSON output"""
        result = {
            "type": self.type.value,
            "params": self.params
        }
        if self.description:
            result["description"] = self.description
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Postcondition":
        """Deserialize from JSON input"""
        return cls(
            type=PostconditionType(data.get("type", "custom")),
            params=data.get("params", {}),
            description=data.get("description")
        )


@dataclass
class Precondition:
    """
    Optional precondition for conditional effects.
    
    If precondition is false, effect state becomes SKIPPED.
    """
    type: str  # Same types as PostconditionType but as string for flexibility
    params: Dict[str, Any] = field(default_factory=dict)
    description: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"type": self.type, "params": self.params}
        if self.description:
            result["description"] = self.description
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Precondition":
        return cls(
            type=data.get("type", ""),
            params=data.get("params", {}),
            description=data.get("description")
        )


@dataclass
class Effect:
    """
    A declarative goal object representing a desired postcondition.
    
    Effects are DATA MODELS, not logic. They:
    - Describe what should be true after execution
    - Do NOT call verifiers
    - Do NOT mutate themselves (except state field)
    - Do NOT know about tools
    
    ID Format: domain.entity.operation (semantic, stable)
    Examples:
    - "app.chrome.running"
    - "file.readme.created"
    - "display.screenshot.captured"
    
    Attributes:
        id: Semantic identifier (domain.entity.operation)
        target: Entity reference (domain:name format)
        operation: What kind of change (running, created, etc.)
        postcondition: Typed success criterion
        precondition: Optional condition for conditional effects
        state: Current lifecycle state (PENDING initially)
    """
    id: str  # Semantic: domain.entity.operation
    target: str  # Entity reference: domain:name
    operation: str  # exists, running, closed, created, modified, deleted, captured
    postcondition: Postcondition
    precondition: Optional[Precondition] = None
    state: EffectState = EffectState.PENDING
    
    def __post_init__(self):
        """Validate semantic ID format"""
        parts = self.id.split(".")
        if len(parts) < 2:
            raise ValueError(
                f"Effect ID '{self.id}' must be semantic format: domain.entity.operation"
            )
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for JSON output"""
        result = {
            "id": self.id,
            "target": self.target,
            "operation": self.operation,
            "postcondition": self.postcondition.to_dict(),
            "state": self.state.value
        }
        if self.precondition:
            result["precondition"] = self.precondition.to_dict()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Effect":
        """Deserialize from JSON input (e.g., from LLM output)"""
        precondition = None
        if data.get("precondition"):
            precondition = Precondition.from_dict(data["precondition"])
        
        return cls(
            id=data["id"],
            target=data["target"],
            operation=data["operation"],
            postcondition=Postcondition.from_dict(data["postcondition"]),
            precondition=precondition,
            state=EffectState(data.get("state", "PENDING"))
        )


@dataclass
class Explanation:
    """
    Non-state-changing information to deliver to user.
    
    Can coexist with effects (mixed intent).
    Generated lazily AFTER execution (Phase 3).
    """
    topic: Optional[str] = None
    content: Optional[str] = None
    required: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "content": self.content,
            "required": self.required
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Explanation":
        if not data:
            return cls()
        return cls(
            topic=data.get("topic"),
            content=data.get("content"),
            required=data.get("required", False)
        )


@dataclass
class EffectPlan:
    """
    Container for effects + explanation produced by PlannerAgent.
    
    This is the new plan structure (Phase 2+).
    Phase 1: Define structure only, no integration.
    """
    goal: str
    effects: List[Effect] = field(default_factory=list)
    explanation: Optional[Explanation] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "effects": [e.to_dict() for e in self.effects],
            "explanation": self.explanation.to_dict() if self.explanation else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EffectPlan":
        effects = [Effect.from_dict(e) for e in data.get("effects", [])]
        explanation = None
        if data.get("explanation"):
            explanation = Explanation.from_dict(data["explanation"])
        return cls(
            goal=data.get("goal", ""),
            effects=effects,
            explanation=explanation
        )
