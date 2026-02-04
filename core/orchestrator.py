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

# Core agents
from agents.query_classifier import QueryClassifier
from agents.intent_agent import IntentAgent
from agents.task_decomposition import TaskDecompositionAgent

# Goal-oriented architecture (Phase 1)
from agents.goal_interpreter import GoalInterpreter
from agents.goal_orchestrator import GoalOrchestrator

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
        self.classifier = QueryClassifier()  # Demoted from DecompositionGate
        self.intent_agent = IntentAgent()
        self.tda = TaskDecompositionAgent()
        
        # Goal-oriented architecture (Phase 1)
        self.goal_interpreter = GoalInterpreter()
        self.goal_orchestrator = GoalOrchestrator()
        
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
        
        # STEP 1: Semantic classification (single vs multi-goal)
        classification = self.classifier.classify(user_input)
        logging.info(f"QueryClassifier: {classification}")
        progress.emit("Analyzing your request...")
        
        if classification == "single":
            # Single path: UNCHANGED from before
            result = self._process_single(user_input, context, progress)
        else:
            # Multi path: NEW goal-oriented architecture
            progress.emit("Understanding your goals...")
            result = self._process_goal(user_input, context, progress)
        
        # Update session
        self.context.complete_task(result)
        
        return result
    
    def _process_single(self, user_input: str, context: Dict[str, Any], 
                        progress: ProgressEmitter = NULL_EMITTER) -> Dict[str, Any]:
        """Fast path for single queries.
        
        Flow: IntentAgent → IntentRouter → pipeline
        
        LLM-CENTRIC: IntentAgent may return decision="ask" for clarification.
        """
        # STEP 2: Intent classification (AUTHORITATIVE) - with context for LLM reasoning
        intent_result = self.intent_agent.classify(user_input, context)
        
        # CHECK: LLM decided to ask for clarification
        decision = intent_result.get("decision", "execute")
        if decision == "ask":
            question = intent_result.get("question", "Could you please clarify what you'd like me to do?")
            logging.info(f"LLM requested clarification: {question}")
            progress.emit("Need more information...")
            return {
                "status": "clarification_needed",
                "type": "clarification",
                "question": question,
                "mode": "single",
                "reasoning": intent_result.get("reasoning", "")
            }
        
        intent = intent_result.get("intent", "unknown")
        confidence = intent_result.get("confidence", 0)
        strategy = intent_result.get("strategy")  # Strategy-first architecture
        
        logging.info(f"Strategy: {strategy} → Intent: {intent} (confidence: {confidence:.2f})")
        progress.emit(f"Identified: {intent.replace('_', ' ') if intent else 'unknown'}")
        
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
    
    def _process_goal(self, user_input: str, context: Dict[str, Any],
                      progress: ProgressEmitter = NULL_EMITTER) -> Dict[str, Any]:
        """Goal-oriented path for multi-goal queries.
        
        NEW ARCHITECTURE (Phase 1):
        1. GoalInterpreter → MetaGoal (semantic goal extraction)
        2. GoalOrchestrator → PlanGraph (per-goal planning + combination)
        3. Execute PlanGraph actions
        
        This is where "open youtube and search nvidia" becomes ONE action.
        """
        try:
            # STEP 1: Get QC classification with confidence for authority contract
            qc_result = self.classifier.classify_with_confidence(user_input)
            logging.info(
                f"QC: {qc_result['classification']} "
                f"(confidence={qc_result['confidence']}, method={qc_result['detection_method']})"
            )
            
            # STEP 2: Interpret goals semantically (with QC authority context)
            meta_goal = self.goal_interpreter.interpret(
                user_input, 
                qc_output=qc_result,  # Pass QC for authority contract
                context=context
            )
            logging.info(f"GoalInterpreter: {meta_goal.meta_type} ({len(meta_goal.goals)} goal(s))")
            
            # If interpreter says it's actually single, and it's a browser_search,
            # we can handle it optimally
            if meta_goal.meta_type == "single":
                progress.emit("Optimizing single goal...")
            else:
                progress.emit(f"Planning {len(meta_goal.goals)} goals...")
            
            # STEP 2: Orchestrate planning
            orch_result = self.goal_orchestrator.orchestrate(meta_goal, context)
            
            # NO LEGACY FALLBACK - Surface errors for proper debugging
            if orch_result.status == "blocked":
                logging.warning(f"Goal orchestration blocked: {orch_result.reason}")
                return {
                    "status": "error",
                    "type": "goal_blocked",
                    "error": orch_result.reason,
                    "mode": "goal"
                }
            
            if orch_result.status == "no_capability":
                logging.info(f"Goal type not supported: {orch_result.reason}")
                return {
                    "status": "error",
                    "type": "unsupported_goal",
                    "error": orch_result.reason,
                    "mode": "goal"
                }
            
            if orch_result.plan_graph is None:
                logging.warning("No plan graph produced")
                return {
                    "status": "error",
                    "type": "planning_failed",
                    "error": "Could not generate execution plan",
                    "mode": "goal"
                }
            
            # STEP 3: Execute plan graph
            plan_graph = orch_result.plan_graph
            logging.info(f"Executing plan with {plan_graph.total_actions} action(s)")
            progress.emit(f"Executing {plan_graph.total_actions} action(s)...")
            
            results = []
            success_count = 0
            
            for action_id in plan_graph.execution_order:
                action = plan_graph.nodes[action_id]
                
                try:
                    # Execute the action
                    tool_result = self.executor.execute_tool(action.tool, action.args)
                    
                    if tool_result.get("status") == "success":
                        success_count += 1
                        results.append({
                            "action_id": action_id,
                            "status": "success",
                            "tool": action.tool,
                            "result": tool_result
                        })
                    else:
                        results.append({
                            "action_id": action_id,
                            "status": "failed",
                            "tool": action.tool,
                            "error": tool_result.get("error", "Unknown error")
                        })
                        
                except Exception as e:
                    logging.error(f"Action {action_id} failed: {e}")
                    results.append({
                        "action_id": action_id,
                        "status": "error",
                        "error": str(e)
                    })
            
            # Build response
            if success_count == plan_graph.total_actions:
                status = "success"
                response = f"Completed all {success_count} action(s)"
            elif success_count > 0:
                status = "partial"
                response = f"Completed {success_count} of {plan_graph.total_actions} action(s)"
            else:
                status = "failed"
                response = "All actions failed"
            
            # Report partial failures
            if orch_result.failed_goals:
                failed_count = len(orch_result.failed_goals)
                response += f" ({failed_count} goal(s) could not be planned)"
            
            return {
                "status": status,
                "type": "goal_execution",
                "response": response,
                "results": results,
                "mode": "goal",
                "meta_type": meta_goal.meta_type,
                "total_goals": len(meta_goal.goals),
                "total_actions": plan_graph.total_actions
            }
            
        except Exception as e:
            logging.error(f"Goal processing failed: {e}", exc_info=True)
            # NO LEGACY FALLBACK - Let errors surface
            return {
                "status": "error",
                "type": "goal_execution",
                "error": str(e),
                "mode": "goal"
            }
    
    # LEGACY MULTI PATH REMOVED
    # Reason: Silent fallback to context-blind classification undermined
    # all strategy-first guarantees. Errors now surface properly.

    
    def _handle_info(self, user_input: str, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Handle information queries."""
        progress = kwargs.get("progress", NULL_EMITTER)
        progress.emit("Looking up information...")
        return handle_information(user_input, context, self.response_llm)
    
    def _handle_action(self, user_input: str, context: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Handle action queries.
        
        INVARIANT: Intent is computed once per request (in _process_single) and passed immutably.
        This handler may not re-classify intent.
        
        Note: High intent confidence ≠ guaranteed executability.
        If tool resolution fails, route to fallback for reasoning.
        """
        progress = kwargs.get("progress", NULL_EMITTER)
        
        # Intent MUST be passed from router - never re-classify
        intent = kwargs.get("intent")
        if intent is None:
            logging.error("INVARIANT VIOLATION: _handle_action called without intent")
            intent = "unknown"
        
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
            ctx = self.ambient.get_context()
        except Exception as e:
            logging.debug(f"Failed to get ambient context: {e}")
            ctx = {"session": self.context.to_dict()}
        
        # Include session context for PathResolver
        # This enables deterministic path resolution using session cwd
        ctx["_session_context"] = self.context
        
        return ctx


# Backward compatibility alias
SubtaskOrchestrator = Orchestrator
