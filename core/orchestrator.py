"""Orchestrator - Main entry point for JARVIS architecture

JARVIS Architecture Role:
- Routes to single-query or multi-query pipeline based on DecompositionGate
- For single queries: uses intent-based authoritative routing
- For multi queries: uses dependency-aware execution

Flow:
1. DecompositionGate → single/multi
2. Single: IntentAgent → IntentRouter → pipeline
3. Multi: TDA → action resolution → dependency execution
"""

import logging
from typing import Dict, Any

from agents.decomposition_gate import DecompositionGate
from agents.intent_agent import IntentAgent
from agents.task_decomposition import TaskDecompositionAgent
from core.intent_router import IntentRouter
from core.tool_resolver import ToolResolver
from core.pipelines import handle_information, handle_action, handle_multi, handle_fallback
from core.context import SessionContext
from execution.executor import ToolExecutor
from memory.ambient import get_ambient_memory
from models.model_manager import get_model_manager

# Progress streaming (GUI only, no-op for terminal)
try:
    from gui.progress import ProgressEmitter, NULL_EMITTER
except ImportError:
    # Fallback if gui module not available
    class ProgressEmitter:
        def __init__(self, callback=None): pass
        def emit(self, msg): pass
    NULL_EMITTER = ProgressEmitter()


class Orchestrator:
    """Main orchestrator - routes to single or multi pipeline.
    
    This replaces the old SubtaskOrchestrator with simpler, intent-based routing.
    """
    
    def __init__(self):
        logging.info("Initializing Orchestrator (JARVIS mode)")
        
        # Core agents
        self.gate = DecompositionGate()
        self.intent_agent = IntentAgent()
        self.tda = TaskDecompositionAgent()
        
        # Execution components
        self.executor = ToolExecutor()
        self.tool_resolver = ToolResolver()
        self.context = SessionContext()
        
        # Ambient memory (starts background monitoring)
        self.ambient = get_ambient_memory()
        
        # LLM for responses
        self.model_manager = get_model_manager()
        self.response_llm = self.model_manager.get_planner_model()
        
        # Setup intent router
        self.router = IntentRouter()
        self._register_pipelines()
        
        logging.info("Orchestrator initialized")
    
    def _register_pipelines(self):
        """Register intent-specific pipelines.
        
        Intent taxonomy (10 categories):
        - application_launch / application_control: App lifecycle
        - system_query / screen_capture / screen_perception / input_control: System ops
        - file_operation / browser_control / office_operation: Future domains
        - information_query: Pure LLM response
        """
        # Pure LLM (no tools)
        self.router.register("information_query", self._handle_info)
        
        # Application lifecycle
        self.router.register("application_launch", self._handle_action)
        self.router.register("application_control", self._handle_action)
        
        # Window management (Phase 2B')
        self.router.register("window_management", self._handle_action)
        
        # System operations (all use action pipeline with tool resolution)
        self.router.register("system_query", self._handle_action)
        self.router.register("screen_capture", self._handle_action)
        self.router.register("screen_perception", self._handle_action)
        self.router.register("input_control", self._handle_action)
        
        # System control (audio, display, power actions)
        self.router.register("system_control", self._handle_action)
        
        # Clipboard operations
        self.router.register("clipboard_operation", self._handle_action)
        
        # Memory recall (Phase 3A - episodic memory)
        self.router.register("memory_recall", self._handle_action)
        
        # Future domains (route to action, will fail gracefully if no tools)
        self.router.register("file_operation", self._handle_action)
        self.router.register("browser_control", self._handle_action)
        self.router.register("office_operation", self._handle_action)
        
        # Unknown → try action, fall back to reasoning
        self.router.register("unknown", self._handle_action)
        
        # Fallback handler for low confidence
        self.router.set_fallback(self._handle_fallback)
    
    def process(self, user_input: str, progress: ProgressEmitter = None) -> Dict[str, Any]:
        """Main entry point - process user input.
        
        Args:
            user_input: User's command/question
            progress: Optional ProgressEmitter for GUI streaming
            
        Returns:
            Result dict with status, type, response/results
        """
        if progress is None:
            progress = NULL_EMITTER
        
        logging.info(f"Processing: {user_input[:50]}...")
        
        # Update session
        self.context.start_task({"input": user_input})
        
        # Get current context from ambient memory
        context = self._get_context()
        
        # STEP 1: Semantic segmentation with action extraction
        gate_result = self.gate.classify_with_actions(user_input)
        classification = gate_result.get("classification", "single")
        logging.info(f"Gate classification: {classification}")
        progress.emit("Analyzing your request...")
        
        if classification == "single":
            result = self._process_single(user_input, context, progress)
        else:
            # Pass pre-extracted actions to avoid redundant decomposition
            progress.emit("Breaking down multi-step request...")
            result = self._process_multi(user_input, context, gate_result, progress)
        
        # Update session
        self.context.complete_task(result)
        
        return result
    
    def _process_single(self, user_input: str, context: Dict[str, Any], 
                        progress: ProgressEmitter = NULL_EMITTER) -> Dict[str, Any]:
        """Fast path for single queries.
        
        Flow: IntentAgent → IntentRouter → pipeline
        """
        # STEP 2: Intent classification (AUTHORITATIVE)
        intent_result = self.intent_agent.classify(user_input)
        intent = intent_result.get("intent", "unknown")
        confidence = intent_result.get("confidence", 0)
        
        logging.info(f"Intent: {intent} (confidence: {confidence:.2f})")
        progress.emit(f"Identified: {intent.replace('_', ' ')}")
        
        # STEP 3: Route to intent-specific pipeline
        # IntentRouter handles confidence threshold internally
        result = self.router.route(
            intent_result, user_input, context,
            progress=progress  # Pass to pipeline handlers
        )
        
        # Add metadata
        result["intent"] = intent
        result["confidence"] = confidence
        result["mode"] = "single"
        
        return result
    
    def _process_multi(self, user_input: str, context: Dict[str, Any],
                        gate_result: Dict[str, Any] = None,
                        progress: ProgressEmitter = NULL_EMITTER) -> Dict[str, Any]:
        """Multi-action path with dependency-aware execution.
        
        Flow: Gate actions → intent resolution per action → dependency execution
        
        Args:
            user_input: Original user input
            context: System context
            gate_result: Output from gate.classify_with_actions() (optional)
            progress: Optional ProgressEmitter for GUI streaming
        """
        # Use pre-extracted actions from gate (avoids redundant TDA call)
        gate_actions = gate_result.get("actions", []) if gate_result else []
        
        if not gate_actions:
            # Fallback to TDA if gate didn't extract actions
            logging.warning("Gate provided no actions, falling back to TDA")
            decomposition = self.tda.decompose(user_input)
            actions = decomposition.get("subtasks", [])
            formatted_actions = []
            for i, subtask in enumerate(actions):
                formatted_actions.append({
                    "id": f"a{i+1}",
                    "description": subtask.get("description", ""),
                    "depends_on": subtask.get("dependencies", [])
                })
        else:
            # Convert gate actions to multi-pipeline format
            formatted_actions = []
            for i, action in enumerate(gate_actions):
                action_id = f"a{i+1}"
                depends_on = []
                
                # Convert boolean depends_on_previous to actual dependency list
                if action.get("depends_on_previous", False) and i > 0:
                    depends_on = [f"a{i}"]  # Depends on previous action
                
                formatted_actions.append({
                    "id": action_id,
                    "description": action.get("description", ""),
                    "depends_on": depends_on
                })
        
        if not formatted_actions:
            # Fallback to single if decomposition fails
            logging.warning("Multi decomposition failed, falling back to single")
            return self._process_single(user_input, context)
        
        logging.info(f"Executing {len(formatted_actions)} actions with dependencies")
        
        # STEP 3: Execute with dependency awareness
        result = handle_multi(
            actions=formatted_actions,
            intent_agent=self.intent_agent,
            tool_resolver=self.tool_resolver,
            executor=self.executor,
            context=context
        )
        
        result["mode"] = "multi"
        return result
    
    def _handle_info(self, user_input: str, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Handle information queries."""
        progress = kwargs.get("progress", NULL_EMITTER)
        progress.emit("Looking up information...")
        return handle_information(user_input, context, self.response_llm)
    
    def _handle_action(self, user_input: str, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Handle action queries.
        
        Note: High intent confidence ≠ guaranteed executability.
        If tool resolution fails, route to fallback for reasoning.
        """
        progress = kwargs.get("progress", NULL_EMITTER)
        
        # Re-classify to get intent (router already has it, but we need it for tool_resolver)
        intent_result = self.intent_agent.classify(user_input)
        intent = intent_result.get("intent", "unknown")
        
        result = handle_action(
            user_input=user_input,
            intent=intent,
            context=context,
            tool_resolver=self.tool_resolver,
            executor=self.executor,
            progress=progress  # Pass progress to pipeline
        )
        
        # If action pipeline couldn't resolve a tool, try fallback reasoning
        if result.get("status") == "needs_fallback":
            logging.info("Action resolution failed, trying fallback reasoning")
            return self._handle_fallback(user_input, context, **kwargs)
        
        return result
    
    def _handle_fallback(self, user_input: str, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Handle low-confidence or unknown intents."""
        progress = kwargs.get("progress", NULL_EMITTER)
        progress.emit("Thinking about how to help...")
        return handle_fallback(
            user_input=user_input,
            context=context,
            executor=self.executor
        )
    
    def _get_context(self) -> Dict[str, Any]:
        """Get current context from ambient memory."""
        try:
            return self.ambient.get_context()
        except Exception as e:
            logging.debug(f"Failed to get ambient context: {e}")
            return {"session": self.context.to_dict()}


# Backward compatibility alias
SubtaskOrchestrator = Orchestrator
