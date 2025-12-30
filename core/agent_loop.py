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
        """Process user input through agentic loop
        
        Flow:
        1. Intent Agent: Classify intent
        2. Planner Agent: Create execution plan
        3. Tool Executor: Execute plan
        4. Critic Agent: Evaluate result
        
        Args:
            user_input: User's command
            
        Returns:
            {
                "intent": {...},
                "plan": {...},
                "execution": {...},
                "evaluation": {...},
                "final_status": "success" | "failure"
            }
        """
        logging.info(f"Processing user input: {user_input}")
        
        # Step 1: Classify intent
        intent_result = self.intent_agent.classify(user_input)
        intent = intent_result.get("intent", "unknown")
        
        # Step 2: Create plan
        plan = self.planner_agent.plan(user_input, intent)
        
        # Check if new skill is needed
        if plan.get("requires_new_skill", False):
            return self._handle_missing_skill(user_input, plan, intent_result)
        
        # Step 3: Execute plan
        execution_result = self.executor.execute_plan(plan)
        
        # Step 4: Evaluate result
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
        """Handle missing skill scenario"""
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

