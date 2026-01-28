"""GUIAdapter - Async bridge between any GUI and Orchestrator.

This is a PURE BRIDGE:
- Runs Orchestrator.process() in a thread pool (non-blocking)
- Converts result to UserResponse
- Zero intelligence, zero policy

The GUI calls:
    response = await adapter.process("open notepad")
    websocket.send(response.to_websocket())

The terminal still shows logs via logging module - completely separate.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Callable

from core.orchestrator import Orchestrator
from core.response.user_response import UserResponse, from_orchestrator_result
from tools.loader import load_all_tools
from gui.progress import ProgressEmitter, ProgressCallback, NULL_EMITTER


class GUIAdapter:
    """Thread-safe adapter for GUI → Orchestrator communication.
    
    This adapter:
    - Runs blocking Orchestrator.process() in a thread pool
    - Converts raw results to UserResponse (GUI-safe)
    - Passes ProgressEmitter for real-time progress streaming
    
    INVARIANT: This class adds zero intelligence or policy.
    
    PROGRESS OWNERSHIP:
    - GUIAdapter: Emits pre-processing message only
    - Orchestrator + Pipelines: Emit reasoning/execution progress
    """
    
    def __init__(self):
        self._orchestrator: Optional[Orchestrator] = None
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="gui_worker")
        self._initialized = False
    
    @property
    def orchestrator(self) -> Orchestrator:
        """Lazy initialization of Orchestrator.
        
        IMPORTANT: Must load tools before creating Orchestrator.
        This mirrors what Assistant.__init__() does in main.py.
        """
        if self._orchestrator is None:
            logging.info("GUIAdapter: Loading tools...")
            discovered = load_all_tools()
            logging.info(f"GUIAdapter: Registered {len(discovered)} tools")
            
            logging.info("GUIAdapter: Initializing Orchestrator")
            self._orchestrator = Orchestrator()
            self._initialized = True
        return self._orchestrator
    
    @property
    def is_initialized(self) -> bool:
        """Check if Orchestrator is initialized."""
        return self._initialized
    
    async def process(self, command: str, 
                     on_progress: Optional[ProgressCallback] = None) -> UserResponse:
        """Process command asynchronously with progress streaming.
        
        Args:
            command: User's input from GUI
            on_progress: Optional callback for real-time progress updates
            
        Returns:
            UserResponse ready for WebSocket
        """
        # Create emitter (or null emitter if no callback)
        emitter = ProgressEmitter(callback=on_progress) if on_progress else NULL_EMITTER
        
        # Pre-processing message (GUIAdapter's only emit)
        emitter.emit("Understanding your request...")
        
        loop = asyncio.get_event_loop()
        
        try:
            # Run blocking orchestrator in thread pool, passing emitter
            result = await loop.run_in_executor(
                self._executor,
                lambda: self.orchestrator.process(command, progress=emitter)
            )
            
            # Convert to GUI contract
            return from_orchestrator_result(result)
            
        except Exception as e:
            # Log internally (terminal), return safe error to GUI
            logging.error(f"GUIAdapter: Orchestrator error - {e}")
            return UserResponse(
                type="error",
                content="An unexpected error occurred. Please try again."
            )
    
    def process_sync(self, command: str) -> UserResponse:
        """Synchronous version for non-async contexts.
        
        Useful for testing or simple integrations.
        """
        try:
            result = self.orchestrator.process(command)
            return from_orchestrator_result(result)
        except Exception as e:
            logging.error(f"GUIAdapter: Orchestrator error - {e}")
            return UserResponse(
                type="error",
                content="An unexpected error occurred. Please try again."
            )
    
    def shutdown(self):
        """Clean shutdown of thread pool."""
        self._executor.shutdown(wait=True)


# Module-level singleton
_adapter: Optional[GUIAdapter] = None


def get_gui_adapter() -> GUIAdapter:
    """Get or create the global GUIAdapter instance."""
    global _adapter
    if _adapter is None:
        _adapter = GUIAdapter()
    return _adapter
