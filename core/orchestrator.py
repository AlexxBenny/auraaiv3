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
from core.pipelines import handle_information, handle_action, handle_fallback
from core.context import SessionContext
from execution.executor import ToolExecutor
from memory.ambient import get_ambient_memory
from models.model_manager import get_model_manager
from core.execution_coordinator import ExecutionCoordinator

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
        # Note: ToolExecutor is plan-scoped. Do NOT reuse a single executor instance across plans.
        # Keep a convenience field for legacy code, but prefer creating per-plan executors.
        self.executor = None
        self.tool_resolver = ToolResolver()
        self.context = SessionContext()
        
        # Ambient memory (starts background monitoring)
        self.ambient = get_ambient_memory()
        
        # LLM for responses - role-based access (config-driven)
        self.model_manager = get_model_manager()
        self.response_llm = self.model_manager.get("response")
        
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
    
    def _get_execution_mode(self, user_input: str, classification: str, intent: str = None) -> str:
        """Conservative gate for execution routing.
        
        THIS IS NOT THE INTELLIGENCE - just cost control.
        When in doubt, return "orchestrated" and let the LLM decide.
        
        Args:
            user_input: User's command
            classification: QueryClassifier result ("single" or "multi")
            intent: Optional pre-classified intent (if available)
            
        Returns:
            "direct": Single pipeline, LLM exits (obvious simple case)
            "orchestrated": Coordinator takes over (everything else)
        """
        SEMANTIC_INTENTS = {"browser_control", "file_operation"}
        # SAFETY: Certain intents always need orchestration (composite actions)
        if intent and self._requires_orchestration(intent):
            return "orchestrated"
        if intent in SEMANTIC_INTENTS:
            return "orchestrated"
        
        # Only skip coordinator when EXTREMELY safe
        if classification == "single":
            lower = user_input.lower()
            # No conjunctions, no conditionals → direct is safe
            if " and " not in lower and " then " not in lower and " if " not in lower:
                return "direct"
        
        # Let coordinator decide - it may still do one-shot execution
        return "orchestrated"
    
    def _requires_orchestration(self, intent: str) -> bool:
        """Intents that require multi-step sequencing.
        
        Browser control is inherently composite:
        - open browser → navigate → observe (get_title/url)
        
        Direct mode cannot guarantee this sequencing.
        """
        COMPOSITE_INTENTS = {
            "browser_control",  # Always: open → navigate → read
        }
        return intent in COMPOSITE_INTENTS
    
    def _detect_early_intent(self, user_input: str) -> str:
        """Heuristic early intent detection (not LLM, just keywords).
        
        Used ONLY to force orchestration for composite intents.
        Does NOT replace IntentAgent's authoritative classification.
        
        Returns:
            Intent string or None if no early detection possible.
        """
        lower = user_input.lower()
        
        # Browser control signals (semantic, not lexical browser names)
        BROWSER_SIGNALS = [
            "search for", "search ",  # Search intent
            "go to ", "navigate to", "open http", "open www",  # Navigation  
            "browse to", "visit ",  # Web browsing
        ]
        
        if any(signal in lower for signal in BROWSER_SIGNALS):
            return "browser_control"
        
        return None

    
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
        
        # STEP 1.5: Early intent detection (heuristic, not LLM)
        # Catches browser_control before mode decision to ensure orchestration
        early_intent = self._detect_early_intent(user_input)
        
        # STEP 2: Determine execution mode (conservative gate)
        mode = self._get_execution_mode(user_input, classification, intent=early_intent)
        logging.info(f"ExecutionMode: {mode} (early_intent={early_intent})")
        
        if mode == "direct":
            # Fast path: single pipeline, LLM exits
            result = self._process_single(user_input, context, progress)
        else:
            # Coordinator handles batch + orchestrated
            # LLM inside coordinator decides if iteration needed
            progress.emit("Planning execution...")
            coordinator = ExecutionCoordinator(self)
            result = coordinator.execute(user_input, context)
        
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
            
            # Phase 5: Track goal execution status
            goal_action_status = {}  # goal_idx → list of (action_id, success)
            
            # Create a plan-scoped executor to hold execution-scoped state (session_id, etc.)
            from execution.executor import ToolExecutor
            from core.tool_resolver import ToolResolver
            from tools.registry import get_registry
            from core.browser_session_manager import BrowserSessionManager

            executor = ToolExecutor()

            # Pre-scan resolved tools for the plan to determine if any action requires a session.
            # This improves auditability by acquiring the session once at plan start.
            try:
                resolver = self.tool_resolver
                registry = get_registry()
                plan_requires_session = False
                explicit_session_id = None
                import inspect
                resolve_sig = inspect.signature(resolver.resolve)
                # Cache resolutions to avoid duplicate LLM calls and ensure determinism
                resolution_cache = {}
                for node_id, node in plan_graph.nodes.items():
                    if "action_args" in resolve_sig.parameters:
                        resolution = resolver.resolve(
                            description=node.description,
                            intent=node.intent,
                            context=context,
                            action_class=node.action_class,
                            action_args=getattr(node, "args", {}) or {}
                        )
                    else:
                        resolution = resolver.resolve(
                            description=node.description,
                            intent=node.intent,
                            context=context,
                            action_class=node.action_class
                        )
                    resolution_cache[node_id] = resolution
                    tool_name = resolution.get("tool")
                    # Planner-explicit session id (planner sets _planned_session_id in action.args if needed)
                    explicit_session_id = getattr(node, "args", {}) and node.args.get("_planned_session_id")
                    if tool_name:
                        tool_instance = registry.get(tool_name)
                        if tool_instance and getattr(tool_instance, "requires_session", False):
                            plan_requires_session = True
                            break

                if plan_requires_session:
                    manager = BrowserSessionManager.get()
                    if explicit_session_id:
                        session = manager.get_session(explicit_session_id) or manager.get_or_create(session_id=explicit_session_id)
                    else:
                        session = manager.get_or_create()
                    if session:
                        executor.set_current_session_id(session.session_id)
                        logging.info(f"Plan acquired session: {session.session_id} (plan-scoped)")
            except Exception:
                logging.debug("Plan-level session pre-scan failed; falling back to lazy acquisition", exc_info=True)

            for action_id in plan_graph.execution_order:
                action = plan_graph.nodes[action_id]
                logging.info(f"DEBUG ORCH: action_id={action_id}, action.action_class={action.action_class}")
                
                # Find which goal this action belongs to
                goal_idx = None
                for g_idx, action_ids in plan_graph.goal_map.items():
                    if action_id in action_ids:
                        goal_idx = g_idx
                        break
                
                try:
                    # Execute via resolver - Phase 3 abstract action → concrete tool
                    # Use cached resolution when available
                    cached_resolution = resolution_cache.get(action_id)
                    tool_result = self.goal_orchestrator._resolve_and_execute(
                        action, context, executor=executor, resolver=self.tool_resolver, resolution=cached_resolution
                    )
                    
                    if tool_result.get("status") == "success":
                        success_count += 1
                        results.append({
                            "action_id": action_id,
                            "status": "success",
                            "description": action.description,
                            "result": tool_result
                        })
                        if goal_idx is not None:
                            goal_action_status.setdefault(goal_idx, []).append((action_id, True))
                    else:
                        # Phase 5: Track failure with failure_class
                        failure_class = tool_result.get("failure_class", "unknown")
                        results.append({
                            "action_id": action_id,
                            "status": "failed",
                            "description": action.description,
                            "error": tool_result.get("error", tool_result.get("reason", "Unknown error")),
                            "failure_class": failure_class
                        })
                        if goal_idx is not None:
                            goal_action_status.setdefault(goal_idx, []).append((action_id, False, failure_class))
                        
                except Exception as e:
                    logging.error(f"Action {action_id} failed: {e}")
                    results.append({
                        "action_id": action_id,
                        "status": "error",
                        "error": str(e),
                        "failure_class": "unknown"
                    })
                    if goal_idx is not None:
                        goal_action_status.setdefault(goal_idx, []).append((action_id, False, "unknown"))
            
            # Phase 5: Build ExecutionSummary
            from agents.goal_orchestrator import ExecutionSummary, FailedGoal
            
            completed_goals = []
            failed_goals = []
            
            # Check each goal's execution status
            for goal_idx, goal in enumerate(meta_goal.goals):
                if goal_idx in goal_action_status:
                    actions = goal_action_status[goal_idx]
                    # Goal succeeds if all its actions succeed
                    if all(success for _, success, *_ in actions):
                        completed_goals.append(goal_idx)
                    else:
                        # Find first failure for this goal
                        for action_id, success, *failure_info in actions:
                            if not success:
                                failure_class = failure_info[0] if failure_info else "unknown"
                                # Find error message from results
                                error_msg = "Action failed"
                                for r in results:
                                    if r.get("action_id") == action_id:
                                        error_msg = r.get("error", r.get("reason", "Action failed"))
                                        break
                                
                                failed_goals.append(FailedGoal(
                                    goal_idx=goal_idx,
                                    goal=goal,
                                    reason=error_msg,
                                    failure_class=failure_class
                                ))
                                break
                elif goal_idx in [fg.goal_idx for fg in orch_result.failed_goals]:
                    # Planning failure - already in orch_result.failed_goals
                    pass
                else:
                    # Goal had no actions (shouldn't happen, but handle gracefully)
                    logging.warning(f"Goal {goal_idx} had no actions")
            
            # Determine overall status
            if success_count == plan_graph.total_actions and not orch_result.failed_goals:
                exec_status = "success"
            elif success_count > 0 or completed_goals:
                exec_status = "partial"
            else:
                exec_status = "failed"
            
            execution_summary = ExecutionSummary(
                status=exec_status,
                failed_goals=failed_goals + list(orch_result.failed_goals),  # Combine execution + planning failures
                completed_goals=completed_goals
            )
            
            # Phase 5: Attempt repair if partial failure
            if exec_status == "partial" and failed_goals:
                logging.info(f"Partial execution detected, attempting repair for {len(failed_goals)} failed goal(s)")
                # Initialize repair budget if not present
                if "_repair_attempts" not in context:
                    context["_repair_attempts"] = 0
                
                # Call orchestrate with execution_summary to trigger repair
                repaired_result = self.goal_orchestrator.orchestrate(
                    meta_goal,
                    context,
                    capabilities=None,
                    execution_summary=execution_summary
                )
                
                # If repair succeeded, execute repaired plan
                if repaired_result.status == "success" and repaired_result.plan_graph:
                    logging.info("Repair succeeded, executing repaired plan")
                    progress.emit("Executing repaired plan...")
                    
                    # Execute repaired plan and normalize reporting (same format as non-repaired)
                    repaired_plan_graph = repaired_result.plan_graph
                    repaired_results = []
                    repaired_success_count = 0
                    
                    # Phase 5: Track goal execution status for repaired plan (normalized reporting)
                    repaired_goal_action_status = {}  # goal_idx → list of (action_id, success)
                    
                    for action_id in repaired_plan_graph.execution_order:
                        action = repaired_plan_graph.nodes[action_id]
                        
                        # Find which goal this action belongs to
                        repaired_goal_idx = None
                        for g_idx, action_ids in repaired_plan_graph.goal_map.items():
                            if action_id in action_ids:
                                repaired_goal_idx = g_idx
                                break
                        
                        try:
                            tool_result = self.goal_orchestrator._resolve_and_execute(action, context, executor=executor, resolver=self.tool_resolver)
                            if tool_result.get("status") == "success":
                                repaired_success_count += 1
                                if repaired_goal_idx is not None:
                                    repaired_goal_action_status.setdefault(repaired_goal_idx, []).append((action_id, True))
                            else:
                                failure_class = tool_result.get("failure_class", "unknown")
                                if repaired_goal_idx is not None:
                                    repaired_goal_action_status.setdefault(repaired_goal_idx, []).append((action_id, False, failure_class))
                            
                            repaired_results.append({
                                "action_id": action_id,
                                "status": tool_result.get("status", "unknown"),
                                "description": action.description,
                                "result": tool_result if tool_result.get("status") == "success" else None,
                                "error": tool_result.get("error") if tool_result.get("status") != "success" else None
                            })
                        except Exception as e:
                            logging.error(f"Repaired action {action_id} failed: {e}")
                            if repaired_goal_idx is not None:
                                repaired_goal_action_status.setdefault(repaired_goal_idx, []).append((action_id, False, "unknown"))
                            repaired_results.append({
                                "action_id": action_id,
                                "status": "error",
                                "error": str(e)
                            })
                    
                    # Phase 5: Build ExecutionSummary for repaired execution (normalized reporting)
                    # Note: We don't trigger second-level repair, but we normalize the reporting format
                    repaired_completed_goals = []
                    repaired_failed_goals = []
                    
                    for goal_idx, goal in enumerate(meta_goal.goals):
                        if goal_idx in repaired_goal_action_status:
                            actions = repaired_goal_action_status[goal_idx]
                            if all(success for _, success, *_ in actions):
                                repaired_completed_goals.append(goal_idx)
                            else:
                                # Find first failure for this goal
                                for action_id, success, *failure_info in actions:
                                    if not success:
                                        failure_class = failure_info[0] if failure_info else "unknown"
                                        error_msg = "Action failed"
                                        for r in repaired_results:
                                            if r.get("action_id") == action_id:
                                                error_msg = r.get("error", r.get("reason", "Action failed"))
                                                break
                                        
                                        repaired_failed_goals.append(FailedGoal(
                                            goal_idx=goal_idx,
                                            goal=goal,
                                            reason=error_msg,
                                            failure_class=failure_class
                                        ))
                                        break
                    
                    # Determine overall status
                    if repaired_success_count == repaired_plan_graph.total_actions:
                        repaired_status = "success"
                        response = f"Completed all {repaired_success_count} action(s) after repair"
                    elif repaired_success_count > 0:
                        repaired_status = "partial"
                        response = f"Completed {repaired_success_count} of {repaired_plan_graph.total_actions} action(s) after repair"
                    else:
                        repaired_status = "partial"
                        response = "Repair attempted but execution still failed"
                    
                    # Return normalized response (same format as non-repaired execution)
                    return {
                        "status": repaired_status,
                        "type": "goal_execution",
                        "response": response,
                        "results": repaired_results,
                        "mode": "goal",
                        "meta_type": meta_goal.meta_type,
                        "total_goals": len(meta_goal.goals),
                        "total_actions": repaired_plan_graph.total_actions,
                        "repair_attempted": True,
                        "repair_reason": repaired_result.repair_reason
                    }
            
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
                "total_actions": plan_graph.total_actions,
                "repair_attempted": orch_result.repair_attempted if hasattr(orch_result, 'repair_attempted') else False,
                "repair_reason": orch_result.repair_reason if hasattr(orch_result, 'repair_reason') else None
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
        
        # Use a plan-scoped executor for this single action execution
        from execution.executor import ToolExecutor
        plan_executor = ToolExecutor()
        result = handle_action(
            user_input=user_input,
            intent=intent,
            context=context,
            tool_resolver=self.tool_resolver,
            executor=plan_executor,
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
        from execution.executor import ToolExecutor
        plan_executor = ToolExecutor()
        return handle_fallback(
            user_input=user_input,
            context=context,
            executor=plan_executor
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
