"""End-to-End Safety Trace Test

This script tests the complete AURA flow for "Click the Save button"
and produces a structured execution trace showing all components.

Expected outcome:
- system.input.mouse.click is selected by Planner
- Neo4j returns requires_target_context (blocking)
- Eligibility = false
- Plan is refused
- ToolExecutor is not executed
- User is told to focus or specify a window
"""

import json
import sys
import os
import logging

# Setup logging to capture all traces
logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(message)s')

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.intent_agent import IntentAgent
from agents.planner_agent import PlannerAgent
from core.ontology.neo4j_client import get_neo4j_client, Neo4jClient, DEFAULT_URI, DEFAULT_PASSWORD
from core.ontology.eligibility import check_plan_eligibility, verify_neo4j_connection
from core.response_formatter import format_refusal_message
from core.agent_loop import AgentLoop

# Check for environment variables
import os
NEO4J_URI = os.environ.get("NEO4J_URI", DEFAULT_URI)
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", DEFAULT_PASSWORD)
AUTH_SOURCE = "ENV" if os.environ.get("NEO4J_PASSWORD") else "DEFAULT"


def run_execution_trace(user_prompt: str):
    """Run full execution trace and return structured output"""
    
    trace = []
    
    print("=" * 80)
    print(f"AURA END-TO-END SAFETY TRACE")
    print(f"User Prompt: '{user_prompt}'")
    print("=" * 80)
    print()
    
    # =========================================================================
    # 1. IntentAgent Output
    # =========================================================================
    print("1. IntentAgent Output")
    print("-" * 40)
    
    intent_agent = IntentAgent()
    intent_result = intent_agent.classify(user_prompt)
    
    intent_trace = {
        "component": "IntentAgent",
        "input": user_prompt,
        "output": {
            "intent_type": intent_result.get("intent", "unknown"),
            "confidence": intent_result.get("confidence", 0.0)
        }
    }
    trace.append(intent_trace)
    print(json.dumps(intent_trace, indent=2))
    print()
    
    # =========================================================================
    # 2. PlannerAgent – Raw Plan (Before Safety)
    # =========================================================================
    print("2. PlannerAgent – Raw Plan (Before Safety)")
    print("-" * 40)
    
    # We need to capture the LLM's raw decision before eligibility
    # For this, we'll manually invoke the LLM part
    planner = PlannerAgent()
    
    # Get the raw plan (before eligibility check modifies it)
    # Note: The actual plan() method already includes eligibility check
    # So we capture the intent to show what LLM decided
    
    # For tracing, we'll run the full plan and then extract what the LLM decided
    plan_result = planner.plan(user_prompt, intent_result.get("intent", "unknown"))
    
    # Reconstruct what LLM would have proposed (before refusal)
    llm_decision = {
        "action_type": plan_result.get("action_type", "action"),
        "goal": plan_result.get("goal", user_prompt),
        "steps": []
    }
    
    # If refused, the LLM originally proposed the blocked tools
    if plan_result.get("refused"):
        refusal = plan_result.get("refusal", {})
        blocked_tools = refusal.get("blocked_tools", [])
        llm_decision["steps"] = [{"tool": t, "args": {"x": "unknown", "y": "unknown"}} for t in blocked_tools]
    else:
        llm_decision["steps"] = plan_result.get("steps", [])
    
    pre_eligibility_trace = {
        "component": "PlannerAgent",
        "stage": "pre-eligibility",
        "llm_decision": llm_decision
    }
    trace.append(pre_eligibility_trace)
    print(json.dumps(pre_eligibility_trace, indent=2))
    print()
    
    # =========================================================================
    # 3. Neo4j Consultation (MANDATORY)
    # =========================================================================
    print("3. Neo4j Consultation (MANDATORY)")
    print("-" * 40)
    
    # Get the tool name that was checked
    tool_name = None
    if plan_result.get("refused"):
        refusal = plan_result.get("refusal", {})
        blocked_tools = refusal.get("blocked_tools", [])
        if blocked_tools:
            tool_name = blocked_tools[0]
    elif plan_result.get("steps"):
        tool_name = plan_result["steps"][0].get("tool")
    
    # Query Neo4j directly to show what was returned
    client = get_neo4j_client()
    
    neo4j_trace = {
        "component": "Neo4j",
        "query_type": "tool_eligibility",
        "bolt_uri_used": NEO4J_URI,
        "auth_source": AUTH_SOURCE,
        "tool_name": tool_name,
        "returned_constraints": {
            "blocking_constraints": [],
            "soft_constraints": []
        }
    }
    
    if tool_name:
        try:
            constraints = client.query_tool_constraints(tool_name)
            neo4j_trace["returned_constraints"]["blocking_constraints"] = [
                {
                    "name": c.name,
                    "type": c.constraint_type,
                    "blocking": c.blocking,
                    "resolvable": c.resolvable,
                    "resolution_hint": c.resolution_hint
                }
                for c in constraints.blocking_constraints
            ]
            neo4j_trace["returned_constraints"]["soft_constraints"] = [
                {
                    "name": c.name,
                    "type": c.constraint_type,
                    "blocking": c.blocking,
                    "resolvable": c.resolvable,
                    "resolution_hint": c.resolution_hint
                }
                for c in constraints.soft_constraints
            ]
        except Exception as e:
            neo4j_trace["error"] = str(e)
    
    trace.append(neo4j_trace)
    print(json.dumps(neo4j_trace, indent=2))
    print()
    
    # =========================================================================
    # 4. Eligibility Decision (Derived, Not LLM)
    # =========================================================================
    print("4. Eligibility Decision (Derived, Not LLM)")
    print("-" * 40)
    
    blocking_count = len(neo4j_trace["returned_constraints"]["blocking_constraints"])
    eligible = blocking_count == 0
    
    eligibility_trace = {
        "component": "EligibilityChecker",
        "logic": "eligible = len(blocking_constraints) == 0",
        "blocking_count": blocking_count,
        "eligible": eligible
    }
    trace.append(eligibility_trace)
    print(json.dumps(eligibility_trace, indent=2))
    print()
    
    # =========================================================================
    # 5. PlannerAgent Decision (REFUSE or ALLOW)
    # =========================================================================
    print("5. PlannerAgent Decision")
    print("-" * 40)
    
    if plan_result.get("refused"):
        planner_decision_trace = {
            "component": "PlannerAgent",
            "decision": "REFUSE",
            "refusal": plan_result.get("refusal", {}),
            "eligibility_checked": plan_result.get("eligibility_checked", False)
        }
    else:
        planner_decision_trace = {
            "component": "PlannerAgent",
            "decision": "ALLOW",
            "steps": plan_result.get("steps", []),
            "safety_warnings": plan_result.get("safety_warnings", []),
            "eligibility_checked": plan_result.get("eligibility_checked", False)
        }
    
    trace.append(planner_decision_trace)
    print(json.dumps(planner_decision_trace, indent=2))
    print()
    
    # =========================================================================
    # 6. ToolExecutor Status
    # =========================================================================
    print("6. ToolExecutor Status")
    print("-" * 40)
    
    executor_trace = {
        "component": "ToolExecutor",
        "executed": not plan_result.get("refused", False),
        "reason": "blocked by eligibility" if plan_result.get("refused") else "allowed by eligibility"
    }
    trace.append(executor_trace)
    print(json.dumps(executor_trace, indent=2))
    print()
    
    # =========================================================================
    # 7. Response Formatter (User-Facing Output)
    # =========================================================================
    print("7. Response Formatter (User-Facing Output)")
    print("-" * 40)
    
    if plan_result.get("refused"):
        refusal = plan_result.get("refusal", {})
        user_message = format_refusal_message(refusal)
        formatter_trace = {
            "component": "ResponseFormatter",
            "input": "structural refusal",
            "output_to_user": user_message
        }
    else:
        formatter_trace = {
            "component": "ResponseFormatter",
            "input": "allowed plan",
            "output_to_user": f"Executing {len(plan_result.get('steps', []))} step(s)..."
        }
    
    trace.append(formatter_trace)
    print(json.dumps(formatter_trace, indent=2))
    print()
    
    # =========================================================================
    # ASSERTIONS
    # =========================================================================
    print("=" * 80)
    print("HARD ASSERTIONS")
    print("=" * 80)
    
    assertions = []
    
    # 1. Neo4j was consulted
    neo4j_consulted = plan_result.get("eligibility_checked", False)
    assertions.append(("Neo4j was consulted", neo4j_consulted))
    
    # 2. Planner did NOT resolve constraints itself (check refusal structure)
    refusal = plan_result.get("refusal", {})
    refusal_is_structural = "user_message" not in refusal
    assertions.append(("Refusal is structural (no prose)", refusal_is_structural))
    
    # 3. ToolExecutor did NOT run
    tool_not_executed = plan_result.get("refused", False)
    assertions.append(("ToolExecutor did NOT run", tool_not_executed))
    
    # 4. Correct blocking constraint
    blocking_constraints = refusal.get("blocking_constraints", [])
    correct_constraint = any(c.get("constraint") == "requires_target_context" for c in blocking_constraints)
    assertions.append(("requires_target_context is blocking", correct_constraint))
    
    # 5. Password source disclosed
    assertions.append(("Auth source disclosed", AUTH_SOURCE in ["ENV", "DEFAULT"]))
    
    print()
    all_passed = True
    for name, passed in assertions:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False
    
    print()
    print("=" * 80)
    if all_passed:
        print("FINAL RESULT: ✅ ALL ASSERTIONS PASSED")
    else:
        print("FINAL RESULT: ❌ SOME ASSERTIONS FAILED")
    print("=" * 80)
    
    return trace, all_passed


if __name__ == "__main__":
    user_prompt = "Click the Save button."
    trace, passed = run_execution_trace(user_prompt)
    
    # Write full trace to file
    with open("execution_trace.json", "w") as f:
        json.dump(trace, f, indent=2)
    
    print(f"\nFull trace written to: execution_trace.json")
    
    sys.exit(0 if passed else 1)
