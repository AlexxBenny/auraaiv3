"""Critic Agent - Evaluates execution results

Effect-Based Evaluation (Phase 4):
- Two-tier verification: deterministic first, LLM fallback
- Per-effect evaluation with structured evidence
- Retry recommendations based on effect state

Post-execution analysis. Determines if retry is needed.
"""

import logging
from typing import Dict, Any, List, Optional
from models.model_manager import get_model_manager


class CriticAgent:
    """Evaluates tool execution results - Effect-based evaluation"""
    
    # Legacy schema (kept for backward compat)
    CRITIC_SCHEMA = {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["success", "partial", "failure"]
            },
            "retry": {"type": "boolean"},
            "retry_reason": {"type": "string"},
            "notes": {"type": "string"},
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1
            },
            "tool_effectiveness": {
                "type": "object",
                "properties": {
                    "tool_name": {"type": "string"},
                    "satisfaction": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1
                    },
                    "issues": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "recommendations": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                }
            }
        },
        "required": ["status", "retry", "notes"]
    }
    
    # NEW: Effect-based evaluation schema (Phase 4)
    EFFECT_EVAL_SCHEMA = {
        "type": "object",
        "properties": {
            "effect_id": {"type": "string"},
            "satisfied": {"type": "boolean"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "evidence": {"type": "string"},
            "verification_method": {
                "type": "string",
                "enum": ["deterministic", "llm_judgment"]
            }
        },
        "required": ["effect_id", "satisfied", "evidence"]
    }
    
    def __init__(self):
        self.model = get_model_manager().get_critic_model()
        logging.info("CriticAgent initialized with effect-based evaluation")
    
    def evaluate(self, goal: str, result: Dict[str, Any], error: str = None) -> Dict[str, Any]:
        """Evaluate execution result
        
        Args:
            goal: Original goal
            result: Tool execution result
            error: Error message if any
            
        Returns:
            {
                "status": "success",
                "retry": false,
                "notes": "Task completed successfully",
                "confidence": 0.95
            }
        """
        result_status = result.get("status", "unknown")
        result_data = result.get("data", {})
        
        prompt = f"""Evaluate this task execution:

Goal: {goal}
Result Status: {result_status}
Result Data: {result_data}
Error: {error if error else "None"}

Determine:
1. Was the task successful? (success/partial/failure)
2. Should we retry? (true/false)
3. Why retry or not retry?
4. Any notes about the execution?

Respond with JSON containing your evaluation.
"""
        
        try:
            evaluation = self.model.generate(prompt, schema=self.CRITIC_SCHEMA)
            
            # Ensure confidence is a float
            if "confidence" in evaluation:
                evaluation["confidence"] = float(evaluation.get("confidence", 0.5))
            
            logging.info(f"Critic evaluation: {evaluation.get('status')}, retry={evaluation.get('retry')}")
            return evaluation
            
        except Exception as e:
            logging.error(f"Critic evaluation failed: {e}")
            # Default to failure if evaluation fails
            return {
                "status": "failure",
                "retry": False,
                "retry_reason": f"Evaluation failed: {str(e)}",
                "notes": "Could not evaluate result",
                "confidence": 0.0
            }
    
    def evaluate_tool_effectiveness(self, tool_name: str, result: Dict[str, Any], goal: str) -> Dict[str, Any]:
        """Evaluate how well a tool performed
        
        Args:
            tool_name: Name of the tool used
            result: Tool execution result
            goal: Original goal
            
        Returns:
            {
                "tool_name": "system.display.take_screenshot",
                "satisfaction": 0.9,
                "issues": [],
                "recommendations": ["Tool worked well"]
            }
        """
        result_status = result.get("status", "unknown")
        error = result.get("error")
        
        prompt = f"""Evaluate the effectiveness of this tool execution:

Tool: {tool_name}
Goal: {goal}
Result Status: {result_status}
Error: {error if error else "None"}

Determine:
1. How satisfied are you with the result? (0.0 to 1.0)
2. What issues, if any, were encountered?
3. What recommendations do you have for improvement?

Respond with JSON containing your evaluation.
"""
        
        try:
            evaluation = self.model.generate(prompt, schema={
                "type": "object",
                "properties": {
                    "tool_name": {"type": "string"},
                    "satisfaction": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1
                    },
                    "issues": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "recommendations": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["tool_name", "satisfaction"]
            })
            
            evaluation["tool_name"] = tool_name
            if "satisfaction" in evaluation:
                evaluation["satisfaction"] = float(evaluation.get("satisfaction", 0.5))
            
            logging.info(f"Tool effectiveness evaluated: {tool_name} - satisfaction: {evaluation.get('satisfaction', 0)}")
            return evaluation
            
        except Exception as e:
            logging.error(f"Tool effectiveness evaluation failed: {e}")
            return {
                "tool_name": tool_name,
                "satisfaction": 0.5,
                "issues": [f"Evaluation failed: {str(e)}"],
                "recommendations": []
            }
    
    # =========================================================================
    # EFFECT-BASED EVALUATION (Phase 4)
    # =========================================================================
    
    def evaluate_effects(self, effects: List[Dict[str, Any]], 
                        execution_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Evaluate effect satisfaction using two-tier verification
        
        Tier 1: Deterministic verification (fast, no LLM)
        Tier 2: LLM judgment (only for 'custom' types)
        
        Args:
            effects: List of effects from plan
            execution_result: Result from ToolExecutor (optional)
            
        Returns:
            {
                "overall_status": "success" | "partial" | "failure",
                "effects": [
                    {
                        "effect_id": "app.chrome.running",
                        "satisfied": true,
                        "evidence": "Process 'chrome.exe' found",
                        "verification_method": "deterministic"
                    },
                    ...
                ],
                "retry_recommended": false,
                "unsatisfied_effects": []
            }
        """
        if not effects:
            return {
                "overall_status": "success",
                "effects": [],
                "retry_recommended": False,
                "unsatisfied_effects": []
            }
        
        # Import verifiers
        try:
            from core.effects.verification import DETERMINISTIC_VERIFIERS, is_deterministically_verifiable
        except ImportError:
            logging.warning("Effects verification module not available - falling back to LLM-only")
            return self._evaluate_effects_llm_only(effects, execution_result)
        
        effect_results = []
        llm_needed = []
        
        # Tier 1: Deterministic verification
        for effect in effects:
            effect_id = effect.get("id", "unknown")
            state = effect.get("state", "PENDING")
            
            # Already handled effects
            if state == "SKIPPED":
                effect_results.append({
                    "effect_id": effect_id,
                    "satisfied": True,  # Skipped = precondition false, not a failure
                    "evidence": "Precondition not met - effect skipped",
                    "verification_method": "precondition_check",
                    "confidence": 1.0
                })
                continue
            
            if state == "SATISFIED":
                effect_results.append({
                    "effect_id": effect_id,
                    "satisfied": True,
                    "evidence": "Effect was already satisfied before execution",
                    "verification_method": "pre_execution_check",
                    "confidence": 1.0
                })
                continue
            
            # Verify postcondition
            postcondition = effect.get("postcondition", {})
            postcond_type = postcondition.get("type")
            
            if is_deterministically_verifiable(postcond_type):
                verifier = DETERMINISTIC_VERIFIERS.get(postcond_type)
                if verifier:
                    result = verifier(postcondition.get("params", {}))
                    effect_results.append({
                        "effect_id": effect_id,
                        "satisfied": result.satisfied,
                        "evidence": result.evidence,
                        "verification_method": "deterministic",
                        "confidence": 1.0 if result.satisfied else 0.0
                    })
                    logging.debug(f"Tier 1 verified '{effect_id}': satisfied={result.satisfied}")
                else:
                    # Should not happen, but handle gracefully
                    llm_needed.append(effect)
            else:
                # Custom type - needs LLM judgment
                llm_needed.append(effect)
        
        # Tier 2: LLM judgment for custom types
        if llm_needed:
            logging.info(f"Tier 2: {len(llm_needed)} effects require LLM judgment")
            llm_results = self._verify_effects_with_llm(llm_needed, execution_result)
            effect_results.extend(llm_results)
        
        # Aggregate results
        satisfied_count = sum(1 for e in effect_results if e.get("satisfied"))
        total_count = len(effect_results)
        unsatisfied = [e["effect_id"] for e in effect_results if not e.get("satisfied")]
        
        if satisfied_count == total_count:
            overall_status = "success"
        elif satisfied_count > 0:
            overall_status = "partial"
        else:
            overall_status = "failure"
        
        retry_recommended = overall_status != "success" and len(unsatisfied) > 0
        
        logging.info(f"Effect evaluation: {satisfied_count}/{total_count} satisfied, status={overall_status}")
        
        return {
            "overall_status": overall_status,
            "effects": effect_results,
            "retry_recommended": retry_recommended,
            "unsatisfied_effects": unsatisfied
        }
    
    def _verify_effects_with_llm(self, effects: List[Dict[str, Any]], 
                                  execution_result: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Tier 2: LLM-based verification for custom effects"""
        results = []
        
        for effect in effects:
            effect_id = effect.get("id", "unknown")
            postcondition = effect.get("postcondition", {})
            description = postcondition.get("description", "Effect should be satisfied")
            
            prompt = f"""Verify if this effect was satisfied:

Effect ID: {effect_id}
Target: {effect.get("target", "unknown")}
Operation: {effect.get("operation", "unknown")}
Expected Postcondition: {description}

Execution Result: {execution_result.get("status", "unknown") if execution_result else "No execution data"}
Execution Data: {execution_result.get("data", {}) if execution_result else {}}

Based on the execution result, determine:
1. Was the effect satisfied? (true/false)
2. What evidence supports your conclusion?
3. How confident are you? (0.0 to 1.0)

Respond with JSON.
"""
            
            try:
                eval_result = self.model.generate(prompt, schema={
                    "type": "object",
                    "properties": {
                        "satisfied": {"type": "boolean"},
                        "evidence": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1}
                    },
                    "required": ["satisfied", "evidence"]
                })
                
                results.append({
                    "effect_id": effect_id,
                    "satisfied": eval_result.get("satisfied", False),
                    "evidence": eval_result.get("evidence", "LLM judgment"),
                    "verification_method": "llm_judgment",
                    "confidence": float(eval_result.get("confidence", 0.5))
                })
                
            except Exception as e:
                logging.error(f"LLM verification failed for '{effect_id}': {e}")
                # Fail closed - treat as unsatisfied
                results.append({
                    "effect_id": effect_id,
                    "satisfied": False,
                    "evidence": f"Verification failed: {str(e)}",
                    "verification_method": "llm_judgment",
                    "confidence": 0.0
                })
        
        return results
    
    def _evaluate_effects_llm_only(self, effects: List[Dict[str, Any]], 
                                    execution_result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Fallback: Evaluate all effects with LLM when verifiers unavailable"""
        logging.warning("Using LLM-only effect evaluation (verifiers unavailable)")
        
        effect_results = self._verify_effects_with_llm(effects, execution_result)
        
        satisfied_count = sum(1 for e in effect_results if e.get("satisfied"))
        total_count = len(effect_results)
        unsatisfied = [e["effect_id"] for e in effect_results if not e.get("satisfied")]
        
        if satisfied_count == total_count:
            overall_status = "success"
        elif satisfied_count > 0:
            overall_status = "partial"
        else:
            overall_status = "failure"
        
        return {
            "overall_status": overall_status,
            "effects": effect_results,
            "retry_recommended": overall_status != "success",
            "unsatisfied_effects": unsatisfied
        }

