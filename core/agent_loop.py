"""Agentic Loop - Main orchestration

Effect-Based Execution Model:
- Routing is based on EFFECTS presence, not action_type
- Preconditions are checked BEFORE execution
- Already-satisfied effects are marked, not re-executed
- Explanation is generated AFTER execution (lazy)

Neo4j Integration:
- Plans may be refused due to blocking constraints
- Refusals are handled before tool execution
- User-facing messages are generated from structural refusals
"""

import logging
from typing import Dict, Any, Optional, List
from .context import SessionContext
from .response_formatter import format_refusal_message, format_safety_warnings
from agents.intent_agent import IntentAgent
from agents.planner_agent import PlannerAgent
from agents.critic_agent import CriticAgent
from agents.limitation_agent import LimitationAnalysisAgent
from execution.executor import ToolExecutor
from core.skill_gate import SkillGate
from memory.procedural import ProceduralMemory
from core.tool_scaffold import ToolScaffoldGenerator


class AgentLoop:
    """Main agentic loop orchestrator - Effect-based execution"""
    
    def __init__(self):
        self.intent_agent = IntentAgent()
        self.planner_agent = PlannerAgent()
        self.critic_agent = CriticAgent()
        self.limitation_agent = LimitationAnalysisAgent()
        self.executor = ToolExecutor()
        self.context = SessionContext()
        
        # Self-evolution components
        self.skill_gate = SkillGate(autonomy_mode="manual")
        self.procedural_memory = ProceduralMemory()
        self.scaffold_generator = ToolScaffoldGenerator()
        
        logging.info("AgentLoop initialized with effect-based execution")
    
    def process(self, user_input: str) -> Dict[str, Any]:
        """Process user input through effect-based agentic loop
        
        Flow:
        1. Intent Agent: Classify intent
        2. Planner Agent: Create plan with effects + explanation
        3. Route based on EFFECTS presence (not action_type):
           - effects=[] → pure explanation, NO tools
           - effects present → check preconditions → execute → evaluate
        4. Generate explanation AFTER execution (lazy)
        
        Args:
            user_input: User's command
            
        Returns:
            {
                "intent": {...},
                "plan": {...},
                "execution": {...} | null,
                "evaluation": {...} | null,
                "final_status": "success" | "failure" | "information" | ...,
                "response": "..." (for explanations)
            }
        """
        logging.info(f"Processing user input: {user_input}")
        
        # Step 1: Classify intent
        intent_result = self.intent_agent.classify(user_input)
        intent = intent_result.get("intent", "unknown")
        
        # Step 2: Create plan (effects-first model)
        plan = self.planner_agent.plan(user_input, intent)
        effects = plan.get("effects", [])
        explanation = plan.get("explanation", {})
        steps = plan.get("steps", [])
        
        # =========================================================================
        # EFFECT-BASED ROUTING (Phase 3)
        # =========================================================================
        # PRIMARY TRIGGER: Presence of effects (not steps, not action_type)
        # Effects presence = execution path
        # Effects empty = pure explanation path
        # =========================================================================
        
        result = {
            "intent": intent_result,
            "plan": plan,
            "execution": None,
            "evaluation": None,
            "final_status": None,
            "response": None
        }
        
        if effects:
            # ===== EFFECTS PRESENT: Execution path =====
            logging.info(f"Effects present ({len(effects)}) — routing to EFFECT handler")
            
            # Phase 3 Refinement B: Explicit precondition checking
            effects = self._check_preconditions(effects)
            
            # Phase 3 Refinement C: Pre-execution satisfaction check
            effects, all_satisfied = self._check_already_satisfied(effects)
            
            if all_satisfied:
                # All effects already satisfied - no execution needed
                logging.info("All effects already satisfied - skipping execution")
                result["final_status"] = "success"
                result["evaluation"] = {"all_effects_pre_satisfied": True}
            else:
                # Route to action handler for pending effects
                pending_effects = [e for e in effects if e.get("state") == "PENDING"]
                logging.info(f"Pending effects: {len(pending_effects)} — executing")
                action_result = self._handle_action(plan, intent_result, user_input, pending_effects)
                result.update(action_result)
        else:
            # ===== NO EFFECTS: Pure explanation/information path =====
            logging.info("No effects — routing to EXPLANATION handler")
            
            # Derive final_status from action_type for backward compat
            action_type = plan.get("action_type", "information")
            if action_type == "system":
                result = self._handle_system(plan, intent_result, user_input)
            elif action_type == "planning":
                result = self._handle_planning(plan, intent_result, user_input)
            else:
                result = self._handle_information(plan, intent_result, user_input)
        
        # ===== Phase 3 Refinement D: Lazy explanation generation =====
        # Generate explanation AFTER execution + evaluation
        if explanation and explanation.get("required"):
            result["response"] = self._generate_explanation(
                user_input, 
                explanation.get("topic"),
                result.get("execution")
            )
        
        return result
    
    def _check_preconditions(self, effects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Check preconditions for each effect - mark SKIPPED if false"""
        try:
            from core.effects.verification import DETERMINISTIC_VERIFIERS
        except ImportError:
            logging.warning("Effects verification not available - skipping precondition checks")
            return effects
        
        for effect in effects:
            precondition = effect.get("precondition")
            if precondition:
                precond_type = precondition.get("type")
                verifier = DETERMINISTIC_VERIFIERS.get(precond_type)
                if verifier:
                    result = verifier(precondition.get("params", {}))
                    if not result.satisfied:
                        effect["state"] = "SKIPPED"
                        logging.info(f"Effect '{effect.get('id')}' SKIPPED - precondition not met: {result.evidence}")
                    else:
                        effect["state"] = "PENDING"
                else:
                    # No verifier - assume precondition met
                    effect["state"] = "PENDING"
            else:
                # No precondition - proceed
                effect["state"] = "PENDING"
        
        return effects
    
    def _check_already_satisfied(self, effects: List[Dict[str, Any]]) -> tuple:
        """Check if effects are already satisfied - mark SATISFIED if true"""
        try:
            from core.effects.verification import DETERMINISTIC_VERIFIERS
        except ImportError:
            logging.warning("Effects verification not available - cannot check satisfaction")
            return effects, False
        
        all_satisfied = True
        
        for effect in effects:
            if effect.get("state") == "SKIPPED":
                continue  # Already handled
            
            postcondition = effect.get("postcondition", {})
            postcond_type = postcondition.get("type")
            verifier = DETERMINISTIC_VERIFIERS.get(postcond_type)
            
            if verifier:
                result = verifier(postcondition.get("params", {}))
                if result.satisfied:
                    effect["state"] = "SATISFIED"
                    logging.info(f"Effect '{effect.get('id')}' already SATISFIED: {result.evidence}")
                else:
                    effect["state"] = "PENDING"
                    all_satisfied = False
            else:
                # Custom types can't be pre-checked
                effect["state"] = "PENDING"
                all_satisfied = False
        
        return effects, all_satisfied
    
    def _generate_explanation(self, user_input: str, topic: Optional[str], 
                             execution_result: Optional[Dict[str, Any]]) -> str:
        """Generate explanation AFTER execution (lazy generation)"""
        # If there was execution, include result context
        if execution_result and execution_result.get("status") == "success":
            if topic:
                return f"About {topic}: I've completed the action you requested. Let me explain..."
            return "I've completed the action. Let me explain what happened..."
        elif execution_result and execution_result.get("status") != "success":
            return f"The action encountered issues. Regarding {topic or 'your request'}..."
        else:
            # Pure explanation (no execution)
            return self._generate_information_response(user_input)
    

    def _handle_information(self, plan: Dict[str, Any], intent_result: Dict[str, Any], user_input: str) -> Dict[str, Any]:
        """Handle information request - NO tool execution"""
        response = plan.get("response")
        if not response:
            # Generate information response from available tools
            response = self._generate_information_response(user_input)
        
        logging.info("INFORMATION request — no tools executed")
        
        return {
            "intent": intent_result,
            "plan": plan,
            "execution": None,
            "evaluation": None,
            "final_status": "information",
            "response": response
        }
    
    def _handle_planning(self, plan: Dict[str, Any], intent_result: Dict[str, Any], user_input: str) -> Dict[str, Any]:
        """Handle planning request - NO tool execution"""
        response = plan.get("response")
        if not response:
            response = f"I can help you accomplish: {plan.get('goal', user_input)}. Here's how I would approach it..."
        
        logging.info("PLANNING request — no tools executed")
        
        return {
            "intent": intent_result,
            "plan": plan,
            "execution": None,
            "evaluation": None,
            "final_status": "planning",
            "response": response
        }
    
    def _handle_system(self, plan: Dict[str, Any], intent_result: Dict[str, Any], user_input: str) -> Dict[str, Any]:
        """Handle system command - NO tool execution"""
        goal = plan.get("goal", user_input).lower()
        response = plan.get("response")
        
        if "exit" in goal or "quit" in goal or "stop" in goal:
            response = "Exiting..."
        elif "help" in goal:
            response = self._generate_help_response()
        elif "status" in goal:
            response = self._generate_status_response()
        elif not response:
            response = f"System command: {goal}"
        
        logging.info("SYSTEM command — no tools executed")
        
        return {
            "intent": intent_result,
            "plan": plan,
            "execution": None,
            "evaluation": None,
            "final_status": "system",
            "response": response
        }
    
    def _handle_action(self, plan: Dict[str, Any], intent_result: Dict[str, Any], 
                       user_input: str, pending_effects: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Handle action request - ONLY place where tools execute
        
        Args:
            plan: The execution plan
            intent_result: Intent classification result
            user_input: Original user input
            pending_effects: List of effects that need to be satisfied (Phase 3)
        """
        
        # =========================================================================
        # NEO4J REFUSAL CHECK
        # =========================================================================
        if plan.get("refused", False):
            refusal = plan.get("refusal", {})
            refusal_message = format_refusal_message(refusal)
            
            logging.warning(f"Plan refused by Neo4j: {refusal_message}")
            logging.info(f"  Blocked tools: {refusal.get('blocked_tools', [])}")
            for constraint in refusal.get("blocking_constraints", []):
                logging.info(f"  Constraint: {constraint.get('constraint')} ({constraint.get('type')})")
            
            return {
                "intent": intent_result,
                "plan": plan,
                "execution": None,
                "evaluation": None,
                "final_status": "refused",
                "response": refusal_message,
                "eligibility_checked": plan.get("eligibility_checked", False)
            }
        
        # Check if new skill is needed
        if plan.get("requires_new_skill", False):
            return self._handle_missing_skill(user_input, plan, intent_result)
        
        # HARD GUARD: Ensure steps exist when effects are pending
        steps = plan.get("steps", [])
        if not steps:
            # Effects present but no steps = requires_new_skill should have been set
            logging.warning("Effects present but no steps - treating as requires_new_skill")
            return {
                "intent": intent_result,
                "plan": plan,
                "execution": None,
                "evaluation": None,
                "final_status": "requires_new_skill",
                "response": f"I understand you want to: {plan.get('goal', user_input)}. However, I don't have the tools to accomplish this yet."
            }
        
        # Execute tools (ONLY authorized path)
        logging.info(f"ACTION request — executing {len(steps)} tool step(s)")
        execution_result = self.executor.execute_plan(plan)
        
        # =========================================================================
        # EFFECT-BASED EVALUATION (Phase 4)
        # =========================================================================
        effects = plan.get("effects", [])
        
        if effects:
            # Use effect-based evaluation (two-tier verification)
            evaluation = self.critic_agent.evaluate_effects(effects, execution_result)
            
            # Determine final status from effect evaluation
            if evaluation.get("overall_status") == "success":
                final_status = "success"
            elif evaluation.get("retry_recommended", False):
                final_status = "retry_needed"
            elif evaluation.get("overall_status") == "partial":
                final_status = "partial"
            else:
                final_status = "failure"
        else:
            # Legacy fallback (no effects defined)
            goal = plan.get("goal", user_input)
            error = None
            if execution_result.get("errors"):
                error = "; ".join([e.get("error", "") for e in execution_result.get("errors", [])])
            
            evaluation = self.critic_agent.evaluate(
                goal,
                {"status": execution_result.get("status"), "data": execution_result},
                error
            )
            
            if execution_result.get("status") == "success" and not evaluation.get("retry", False):
                final_status = "success"
            elif evaluation.get("retry", False):
                final_status = "retry_needed"
            else:
                final_status = "failure"
        
        return {
            "intent": intent_result,
            "plan": plan,
            "execution": execution_result,
            "evaluation": evaluation,
            "final_status": final_status
        }
    
    def _handle_missing_skill(self, user_input: str, plan: Dict[str, Any], intent_result: Dict[str, Any]) -> Dict[str, Any]:
        """Handle missing skill scenario (ONLY for ACTION type)"""
        # Ensure this is only called for ACTION type
        action_type = plan.get("action_type", "action")
        if action_type != "action":
            logging.error(f"CRITICAL: _handle_missing_skill called for non-action type: {action_type}")
            raise RuntimeError(f"Self-evolution can only trigger for ACTION type, got: {action_type}")
        
        goal = plan.get("goal", user_input)
        missing_capability = plan.get("missing_capability", "Unknown")
        reason = plan.get("reason", "No suitable tool")
        
        # Step 1: Analyze limitation
        proposal = self.limitation_agent.analyze(
            goal, missing_capability, reason
        )
        
        # Step 2: Validate proposal
        validation = self.skill_gate.validate_proposal(proposal)
        
        # Step 3: Store in procedural memory
        proposal_id = self.procedural_memory.store_proposal(
            proposal, goal, validation
        )
        
        # Step 4: Generate scaffold (if assisted mode)
        scaffold_path = None
        if self.skill_gate.get_autonomy_mode() in ["assisted", "sandboxed"]:
            scaffold_path = self.scaffold_generator.generate_scaffold(proposal)
        
        return {
            "intent": intent_result,
            "plan": plan,
            "execution": None,
            "evaluation": None,
            "final_status": "requires_new_skill",
            "proposal": proposal,
            "validation": validation,
            "proposal_id": proposal_id,
            "scaffold_path": str(scaffold_path) if scaffold_path else None,
            "message": self._format_skill_message(validation, proposal)
        }
    
    def _format_skill_message(self, validation: Dict[str, Any], proposal: Dict[str, Any]) -> str:
        """Format message for user about skill proposal"""
        tool_name = proposal.get("proposed_tool", {}).get("name", "unknown")
        
        if not validation["valid"]:
            return f"Skill proposal rejected: {', '.join(validation['errors'])}"
        
        if validation["action"] == "manual_review":
            return f"New skill '{tool_name}' proposed. Requires manual review. Proposal ID: {proposal.get('id', 'unknown')}"
        
        return f"New skill '{tool_name}' proposed and validated."
    
    def _generate_information_response(self, user_input: str) -> str:
        """Generate information response without executing tools"""
        user_lower = user_input.lower()
        
        if "tool" in user_lower or "capabilit" in user_lower or "what can" in user_lower:
            # List available tools
            from tools.registry import get_registry
            registry = get_registry()
            tools = registry.list_all()
            
            if not tools:
                return "I currently have no tools available."
            
            tool_list = "\n".join([f"- {name}: {meta.get('description', 'No description')}" 
                                  for name, meta in tools.items()])
            return f"I currently have the following tools available:\n{tool_list}"
        
        elif "how" in user_lower and "work" in user_lower:
            return "I can explain how my tools work. Which specific tool would you like to know about?"
        
        else:
            return f"I can help you with information about: {user_input}. What would you like to know?"
    
    def _generate_help_response(self) -> str:
        """Generate help response"""
        from tools.registry import get_registry
        registry = get_registry()
        tool_count = len(registry.list_all())
        
        return f"""AURA Agentic Assistant Help

I can help you with:
- Information queries (ask questions)
- Planning tasks (explain how I would do something)
- Executing actions (perform tasks using tools)
- System commands (exit, help, status)

Currently available: {tool_count} tool(s)

Commands:
- Ask questions: "What tools do you have?"
- Request actions: "Take a screenshot"
- System: "exit", "help", "status"
"""
    
    def _generate_status_response(self) -> str:
        """Generate status response"""
        from tools.registry import get_registry
        registry = get_registry()
        tools = registry.list_all()
        
        return f"""AURA System Status

Runtime: Agentic mode (NO code execution)
Tools registered: {len(tools)}
Self-evolution: Enabled (manual mode)

Available tools: {', '.join(tools.keys()) if tools else 'None'}
"""

