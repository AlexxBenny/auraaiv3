"""ProgressEmitter - Explicit progress callback for GUI streaming.

ARCHITECTURE:
- ProgressEmitter is passed explicitly through the call chain
- No global state, no log interception
- Thread-safe, request-scoped

OWNERSHIP RULE:
- GUIAdapter: Emits pre-processing message only
- Orchestrator + Pipelines: Emit reasoning/execution progress

VOCABULARY (frozen to prevent UX drift):
- "Analyzing your request..." (after gate)
- "Identified: {intent}" (after intent classification)
- "Found tool: {tool}" (after tool resolution)
- "Executing..." (before tool execution)
- "Thinking about how to help..." (fallback pipeline)
- "Looking up information..." (info pipeline)
"""

from dataclasses import dataclass
from typing import Callable, Optional


# Type alias for progress callbacks
ProgressCallback = Callable[[str], None]


@dataclass
class ProgressEmitter:
    """Thread-safe progress emitter passed through call chain.
    
    INVARIANT: This class has no intelligence or policy.
    It is a pure callback wrapper.
    """
    callback: Optional[ProgressCallback] = None
    
    def emit(self, message: str) -> None:
        """Emit progress to GUI. No-op if no callback.
        
        Args:
            message: Human-friendly progress message (not log text)
        """
        if self.callback is not None:
            self.callback(message)


# Null emitter for non-GUI contexts (main.py, tests)
# This ensures no branching on "am I in GUI mode?"
NULL_EMITTER = ProgressEmitter(callback=None)
