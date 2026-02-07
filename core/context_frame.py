"""ContextFrame - Typed semantic continuity frames passed along dependency edges.

Immutable, domain-scoped, and small. These are NOT runtime state or environment
probes. They are semantic metadata produced by Planner or Interpreter and
consumed by downstream Planner invocations via the Orchestrator.
"""
from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass(frozen=True)
class ContextFrame:
    """Immutable semantic context frame.

    Fields:
        domain: Domain of the context (e.g., "browser", "file", "media")
        data: Small typed mapping of keys → scalar or small structured values
        produced_by: Optional identifier (goal_id/action_id) that produced the frame
    """
    domain: str
    data: Dict[str, Any]
    produced_by: Optional[str] = None

    def get(self, key: str, default: Optional[Any] = None) -> Optional[Any]:
        return self.data.get(key, default)


