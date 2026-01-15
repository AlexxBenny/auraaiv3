"""Agentic Loop - Main orchestration

This replaces the old exec(generated_code) pattern.
"""

import logging
from typing import Dict, Any, Optional
from .context import SessionContext
from agents.intent_agent import IntentAgent
from agents.planner_agent import PlannerAgent
from agents.critic_agent import CriticAgent
from agents.limitation_agent import LimitationAnalysisAgent
from execution.executor import ToolExecutor
from core.skill_gate import SkillGate
from memory.procedural import ProceduralMemory
from core.tool_scaffold import ToolScaffoldGenerator


class AgentLoop:
    """Main agentic loop orchestrator"""
    
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
        
        logging.info("AgentLoop initialized with self-evolution support")
    
    def process(self, user_input: str) -> Dict[str, Any]:
        """Process user input through agentic loop with action type routing
        
        Flow:
        1. Intent Agent: Classify intent
        2. Planner Agent: Create plan with action_type
        3. Route based on action_type:
           - INFORMATION: Return response, NO tools
           - PLANNING: Return response, NO tools
           - SYSTEM: Handle system command, NO tools
           - ACTION: Execute tools (only if authorized)
        
        Args:
            user_input: User's command
            
        Returns:
            {
                "intent": {...},
                "plan": {...},
                "execution": {...} | null,
                "evaluation": {...} | null,
                "final_status": "information" | "planning" | "system" | "success" | "failure",
                "response": "..." (for information/planning/system)
            }
        """
        logging.info(f"Processing user input: {user_input}")
        
        # Step 1: Classify intent
        intent_result = self.intent_agent.classify(user_input)
        intent = intent_result.get("intent", "unknown")
        
        # Step 2: Create plan (includes action_type classification)
        plan = self.planner_agent.plan(user_input, intent)
        action_type = plan.get("action_type", "action")
        
        logging.info(f"Action type: {action_type.upper()} — {'tools will execute' if action_type == 'action' else 'NO tools executed'}")
        
        # Route based on action_type (CRITICAL: Tools only execute for ACTION)
        if action_type == "information":
            return self._handle_information(plan, intent_result, user_input)
        
        elif action_type == "planning":
            return self._handle_planning(plan, intent_result, user_input)
        
        elif action_type == "system":
            return self._handle_system(plan, intent_result, user_input)
        
        elif action_type == "action":
            return self._handle_action(plan, intent_result, user_input)
        
        else:
            # Fallback: treat as action (should not happen due to schema validation)
            logging.warning(f"Unknown action_type '{action_type}', treating as action")
            return self._handle_action(plan, intent_result, user_input)
    
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
    
    def _handle_action(self, plan: Dict[str, Any], intent_result: Dict[str, Any], user_input: str) -> Dict[str, Any]:
        """Handle action request - ONLY place where tools execute"""
        # Check if new skill is needed (only for ACTION type)
        if plan.get("requires_new_skill", False):
            return self._handle_missing_skill(user_input, plan, intent_result)
        
        # HARD GUARD: Ensure steps exist for action type
        steps = plan.get("steps", [])
        if not steps:
            logging.warning("ACTION type but no steps provided - treating as information")
            return {
                "intent": intent_result,
                "plan": plan,
                "execution": None,
                "evaluation": None,
                "final_status": "information",
                "response": f"I understand you want to: {plan.get('goal', user_input)}. However, I don't have a clear action plan for this."
            }
        
        # Execute tools (ONLY authorized path)
        logging.info(f"ACTION request — executing {len(steps)} tool step(s)")
        execution_result = self.executor.execute_plan(plan)
        
        # Evaluate result
        goal = plan.get("goal", user_input)
        error = None
        if execution_result.get("errors"):
            error = "; ".join([e.get("error", "") for e in execution_result.get("errors", [])])
        
        evaluation = self.critic_agent.evaluate(
            goal,
            {"status": execution_result.get("status"), "data": execution_result},
            error
        )
        
        # Determine final status
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

