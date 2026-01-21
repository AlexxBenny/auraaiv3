"""Subtask Orchestrator - Top-level orchestration with Task Decomposition

This is the NEW entry point that replaces AgentLoop.process() as the top-level
orchestrator. It implements the TDA v3 architecture:

1. Decomposition Gate (cheap LLM) -> single/multi classification
2. Task Decomposition Agent (if multi) -> subtasks
3. Per-subtask: IntentAgent -> PlannerAgent -> AgentLoop -> CriticAgent
4. Post-mortem memory (write-only)

LOCKED INVARIANTS (from v3 design):
- Gate is structural, not semantic (Invariant 1)
- Post-mortem memory is never read during execution (Invariant 2)
- No retries or tool alternatives at this layer (Invariant 3)

See: task_decomposition_agent_design_v3_final.md
"""

import logging
from typing import Dict, Any, List, Set, Optional
from dataclasses import dataclass

from agents.decomposition_gate import DecompositionGate
from agents.task_decomposition import TaskDecompositionAgent
from agents.intent_agent import IntentAgent
from agents.planner_agent import PlannerAgent
from core.agent_loop import AgentLoop
from memory.postmortem import PostMortemMemory


@dataclass
class SubtaskResult:
    """Result of a single subtask execution."""
    subtask_id: str
    status: str
    intent: Optional[Dict[str, Any]] = None
    plan: Optional[Dict[str, Any]] = None
    execution: Optional[Dict[str, Any]] = None
    evaluation: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None


class SubtaskOrchestrator:
    """
    Top-level orchestrator with Task Decomposition.
    
    Implements the TDA v3 architecture with:
    - Decomposition Gate (laziness)
    - Task Decomposition Agent (goal reasoning)
    - Per-subtask IntentAgent (goal-scoped intent)
    - Existing AgentLoop for execution (unchanged)
    
    INVARIANTS (DO NOT VIOLATE):
    - No retries or tool alternatives
    - No reads from PostMortemMemory during execution
    - Gate is structural only
    """
    
    def __init__(self):
        self.gate = DecompositionGate()
        self.tda = TaskDecompositionAgent()
        self.intent_agent = IntentAgent()
        self.planner_agent = PlannerAgent()
        self.agent_loop = AgentLoop()
        self.postmortem = PostMortemMemory()
        
        logging.info("SubtaskOrchestrator initialized")
    
    def process(self, user_input: str) -> Dict[str, Any]:
        """
        Main entry point. Processes user input through TDA v3 flow.
        
        Flow:
        1. Decomposition Gate -> single/multi
        2. If multi: TDA -> subtasks
        3. For each subtask: IntentAgent -> PlannerAgent -> AgentLoop
        4. Aggregate results
        """
        
        # =====================================================================
        # STEP 1: DECOMPOSITION GATE (cheap LLM)
        # =====================================================================
        gate_result = self.gate.classify(user_input)
        logging.info(f"Gate classification: {gate_result}")
        
        if gate_result == "single":
            # FAST PATH: Skip TDA, treat input as single subtask
            subtasks = [{
                "id": "subtask_001",
                "description": user_input,
                "depends_on": [],
                "is_optional": False
            }]
            decomposition_applied = False
            logging.info("Fast path: single goal, skipping TDA")
        else:
            # FULL PATH: Would run TDA (Phase 2)
            # For now, fall back to single subtask until TDA is implemented
            if self.tda is None:
                logging.info("TDA not yet implemented, falling back to single subtask")
                subtasks = [{
                    "id": "subtask_001",
                    "description": user_input,
                    "depends_on": [],
                    "is_optional": False
                }]
                decomposition_applied = False
            else:
                try:
                    tda_result = self.tda.decompose(user_input)
                    subtasks = tda_result.get("subtasks", [])
                    decomposition_applied = tda_result.get("decomposition_applied", True)
                    
                    if not subtasks:
                        # TDA returned empty - fallback
                        subtasks = [{
                            "id": "subtask_001",
                            "description": user_input,
                            "depends_on": [],
                            "is_optional": False
                        }]
                        decomposition_applied = False
                except Exception as e:
                    logging.error(f"TDA failed: {e}")
                    subtasks = [{
                        "id": "subtask_001",
                        "description": user_input,
                        "depends_on": [],
                        "is_optional": False
                    }]
                    decomposition_applied = False
        
        # =====================================================================
        # STEP 2: EXECUTE SUBTASKS
        # =====================================================================
        subtask_results: List[SubtaskResult] = []
        completed_ids: Set[str] = set()
        failed_ids: Set[str] = set()
        
        for subtask in self._dependency_order(subtasks):
            subtask_id = subtask["id"]
            description = subtask["description"]
            depends_on = subtask.get("depends_on", [])
            is_optional = subtask.get("is_optional", False)
            
            # Check dependencies
            if any(dep in failed_ids for dep in depends_on) and not is_optional:
                subtask_results.append(SubtaskResult(
                    subtask_id=subtask_id,
                    status="skipped",
                    reason=f"Dependency failed: {[d for d in depends_on if d in failed_ids]}"
                ))
                failed_ids.add(subtask_id)
                continue
            
            # -----------------------------------------------------------------
            # STEP 2a: IntentAgent (per subtask) - MANDATORY
            # -----------------------------------------------------------------
            intent_result = self.intent_agent.classify(description)
            subtask_intent = intent_result.get("intent", "unknown")
            logging.info(f"Subtask {subtask_id} intent: {subtask_intent}")
            
            # -----------------------------------------------------------------
            # STEP 2b: PlannerAgent (per subtask)
            # -----------------------------------------------------------------
            plan = self.planner_agent.plan(description, subtask_intent)
            
            if plan.get("refused", False):
                subtask_results.append(SubtaskResult(
                    subtask_id=subtask_id,
                    status="refused",
                    intent=intent_result,
                    plan=plan,
                    reason=str(plan.get("refusal", {}))
                ))
                
                # Post-mortem: record refusal (Phase 4)
                self._record_postmortem(
                    description=description,
                    intent=subtask_intent,
                    plan=plan,
                    outcome="refused"
                )
                
                if not is_optional:
                    failed_ids.add(subtask_id)
                continue
            
            # -----------------------------------------------------------------
            # STEP 2c-2e: Execute through AgentLoop
            # -----------------------------------------------------------------
            execution = self._execute_through_loop(plan, intent_result, description)
            final_status = execution.get("final_status", "unknown")
            
            subtask_results.append(SubtaskResult(
                subtask_id=subtask_id,
                status=final_status,
                intent=intent_result,
                plan=plan,
                execution=execution.get("execution"),
                evaluation=execution.get("evaluation")
            ))
            
            # Post-mortem: record outcome (Phase 4)
            self._record_postmortem(
                description=description,
                intent=subtask_intent,
                plan=plan,
                outcome=final_status,
                execution=execution
            )
            
            if final_status in ["success", "information", "planning", "system"]:
                completed_ids.add(subtask_id)
            elif not is_optional:
                failed_ids.add(subtask_id)
        
        # =====================================================================
        # STEP 3: AGGREGATE AND RETURN
        # =====================================================================
        return self._aggregate_results(
            user_input=user_input,
            decomposition_applied=decomposition_applied,
            subtask_results=subtask_results
        )
    
    def _dependency_order(self, subtasks: List[Dict]) -> List[Dict]:
        """
        Topological sort of subtasks based on depends_on.
        
        Returns subtasks in execution order (dependencies first).
        """
        if not subtasks:
            return subtasks
        
        # Build adjacency info
        id_to_subtask = {s["id"]: s for s in subtasks}
        in_degree = {s["id"]: 0 for s in subtasks}
        
        for subtask in subtasks:
            for dep in subtask.get("depends_on", []):
                if dep in in_degree:
                    in_degree[subtask["id"]] += 1
        
        # Kahn's algorithm
        queue = [sid for sid, deg in in_degree.items() if deg == 0]
        ordered = []
        
        while queue:
            current_id = queue.pop(0)
            ordered.append(id_to_subtask[current_id])
            
            for subtask in subtasks:
                if current_id in subtask.get("depends_on", []):
                    in_degree[subtask["id"]] -= 1
                    if in_degree[subtask["id"]] == 0:
                        queue.append(subtask["id"])
        
        if len(ordered) != len(subtasks):
            # Cycle detected - use original order as fallback
            logging.warning("Dependency cycle detected, using original order")
            return subtasks
        
        return ordered
    
    def _execute_through_loop(self, plan: Dict, intent_result: Dict, 
                               user_input: str) -> Dict[str, Any]:
        """
        Execute a plan through the existing AgentLoop flow.
        
        This reuses existing AgentLoop logic WITHOUT modification.
        """
        effects = plan.get("effects", [])
        
        if not effects:
            # No effects - pure information/planning/system path
            action_type = plan.get("action_type", "information")
            if action_type == "system":
                return self.agent_loop._handle_system(plan, intent_result, user_input)
            elif action_type == "planning":
                return self.agent_loop._handle_planning(plan, intent_result, user_input)
            else:
                return self.agent_loop._handle_information(plan, intent_result, user_input)
        
        # Effects present - action path
        # Check preconditions (reuse AgentLoop methods)
        effects = self.agent_loop._check_preconditions(effects)
        effects, all_satisfied = self.agent_loop._check_already_satisfied(effects)
        
        if all_satisfied:
            return {
                "final_status": "success",
                "evaluation": {"all_effects_pre_satisfied": True}
            }
        
        # Execute pending effects
        pending_effects = [e for e in effects if e.get("state") == "PENDING"]
        return self.agent_loop._handle_action(plan, intent_result, user_input, pending_effects)
    
    def _record_postmortem(self, description: str, intent: str, plan: Dict,
                           outcome: str, execution: Optional[Dict] = None) -> None:
        """
        Record execution outcome to PostMortemMemory.
        
        INVARIANT: Write-only, non-blocking. Failures are logged, not raised.
        """
        if self.postmortem is None:
            # Phase 4: PostMortemMemory not yet implemented
            return
        
        try:
            self.postmortem.record(
                subtask_description=description,
                intent=intent,
                effects=plan.get("effects", []),
                tools_used=[s.get("tool") for s in plan.get("steps", [])],
                outcome=outcome,
                failure_reason=self._extract_failure_reason(execution) if outcome == "failure" else None
            )
        except Exception as e:
            # Non-blocking - log and continue
            logging.warning(f"PostMortem write failed: {e}")
    
    def _extract_failure_reason(self, execution: Optional[Dict]) -> Optional[str]:
        """Extract failure reason from execution result."""
        if not execution:
            return None
        errors = execution.get("errors", [])
        if errors:
            return "; ".join([e.get("error", "Unknown") for e in errors])
        return None
    
    def _aggregate_results(self, user_input: str, decomposition_applied: bool,
                           subtask_results: List[SubtaskResult]) -> Dict[str, Any]:
        """
        Aggregate subtask results into final response.
        
        DETERMINISTIC - no LLM call.
        """
        total = len(subtask_results)
        succeeded = sum(1 for r in subtask_results if r.status in 
                        ["success", "information", "planning", "system"])
        failed = sum(1 for r in subtask_results if r.status in 
                     ["failure", "refused", "error"])
        skipped = sum(1 for r in subtask_results if r.status == "skipped")
        
        if failed == 0 and skipped == 0:
            overall_status = "success"
        elif succeeded > 0:
            overall_status = "partial"
        else:
            overall_status = "failure"
        
        # For single subtask, return compatible format with existing AgentLoop
        if total == 1 and not decomposition_applied:
            result = subtask_results[0]
            return {
                "intent": result.intent,
                "plan": result.plan,
                "execution": result.execution,
                "evaluation": result.evaluation,
                "final_status": result.status,
                "response": result.reason
            }
        
        # Multi-subtask response
        return {
            "overall_status": overall_status,
            "decomposition_applied": decomposition_applied,
            "original_goal": user_input,
            "subtask_count": total,
            "subtask_results": [
                {
                    "subtask_id": r.subtask_id,
                    "status": r.status,
                    "reason": r.reason
                }
                for r in subtask_results
            ],
            "summary": {
                "succeeded": succeeded,
                "failed": failed,
                "skipped": skipped
            }
        }
