"""Fallback Pipeline - PlannerAgent reasoning for unknown/low-confidence

JARVIS Architecture Role:
- Handles low-confidence intents (< 0.75)
- Handles "unknown" intent
- Uses PlannerAgent reasoning (not effects)
- Last resort before giving up
"""

import logging
from typing import Dict, Any

from agents.planner_agent import PlannerAgent
from core.sanity_checks import check_prerequisites


# Singleton planner for fallback
_planner = None


def get_planner() -> PlannerAgent:
    """Get or create PlannerAgent singleton."""
    global _planner
    if _planner is None:
        _planner = PlannerAgent()
    return _planner


def handle_fallback(user_input: str, context: Dict[str, Any],
                    executor=None, planner: PlannerAgent = None) -> Dict[str, Any]:
    """Use PlannerAgent reasoning for ambiguous requests.
    
    Args:
        user_input: User's request
        context: Current system context
        executor: Optional ToolExecutor for executing planned steps
        planner: Optional PlannerAgent instance (uses singleton if not provided)
        
    Returns:
        {
            "status": "success" | "error" | "clarification_needed",
            "type": "fallback",
            "response": "...",
            "results": [...] if actions were taken
        }
    """
    if planner is None:
        planner = get_planner()
    
    logging.info(f"FallbackPipeline: reasoning over '{user_input[:50]}...'")
    
    # Get reasoning from PlannerAgent
    reasoning = planner.reason(user_input, context)
    
    # Check if clarification is needed
    if reasoning.get("needs_clarification"):
        return {
            "status": "clarification_needed",
            "type": "fallback",
            "response": reasoning.get("clarification_question", "Could you please clarify?"),
            "confidence": reasoning.get("confidence", 0)
        }
    
    action_type = reasoning.get("action_type", "information")
    explanation = reasoning.get("explanation", "")
    steps = reasoning.get("steps", [])
    
    # If pure information, return the explanation
    if action_type == "information" or not steps:
        return {
            "status": "success",
            "type": "fallback",
            "action_type": "information",
            "response": explanation,
            "confidence": reasoning.get("confidence", 0)
        }
    
    # If action with steps, execute them
    if executor is None:
        # No executor - return the plan without executing
        return {
            "status": "success",
            "type": "fallback",
            "action_type": "action_planned",
            "response": explanation,
            "steps": steps,
            "confidence": reasoning.get("confidence", 0),
            "note": "Steps planned but not executed (no executor provided)"
        }
    
    # Execute planned steps
    results = []
    
    for i, step in enumerate(steps):
        tool_name = step.get("tool")
        params = step.get("params", {})
        
        logging.info(f"FallbackPipeline: executing step {i+1}/{len(steps)}: {tool_name}")
        
        # Check prerequisites
        prereq = check_prerequisites(tool_name, context)
        if not prereq["satisfied"]:
            results.append({
                "step": i + 1,
                "tool": tool_name,
                "status": "blocked",
                "reason": prereq["reason"]
            })
            # Stop execution on blocked prerequisite
            break
        
        # Execute
        try:
            result = executor.execute_tool(tool_name, params)
            results.append({
                "step": i + 1,
                "tool": tool_name,
                "status": result.get("status", "success"),
                "result": result
            })
            
            # Stop on error
            if result.get("status") == "error":
                break
                
        except Exception as e:
            results.append({
                "step": i + 1,
                "tool": tool_name,
                "status": "error",
                "error": str(e)
            })
            break
    
    # Determine overall status
    success_count = sum(1 for r in results if r.get("status") == "success")
    
    if success_count == len(steps):
        status = "success"
    elif success_count > 0:
        status = "partial"
    else:
        status = "error"
    
    return {
        "status": status,
        "type": "fallback",
        "action_type": "action",
        "response": explanation,
        "results": results,
        "confidence": reasoning.get("confidence", 0)
    }
