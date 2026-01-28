"""Multi-Action Pipeline - Compiler mode for complex queries

JARVIS Architecture Role:
- Handles multi-query decomposed actions
- Explicit dependency handling
- Fail-fast for unresolved tools
- Prerequisite validation before execution
- Sequential execution (conservative - no parallel for now)
"""

import logging
from typing import Dict, Any, List

from core.sanity_checks import check_prerequisites, validate_action_chain, refresh_context


def handle_multi(actions: List[Dict], intent_agent, tool_resolver,
                 executor, context: Dict[str, Any]) -> Dict[str, Any]:
    """Execute multiple actions with dependency awareness.
    
    Args:
        actions: List of actions from TDA with dependencies
            [{"id": "a1", "description": "...", "depends_on": [...]}]
        intent_agent: IntentAgent instance
        tool_resolver: ToolResolver instance
        executor: ToolExecutor instance
        context: Current system context
        
    Returns:
        {
            "status": "success" | "partial" | "blocked",
            "type": "multi",
            "results": [...]
        }
    """
    if not actions:
        return {
            "status": "success",
            "type": "multi",
            "results": [],
            "message": "No actions to execute"
        }
    
    logging.info(f"MultiPipeline: processing {len(actions)} actions")
    
    # ==========================================================================
    # PHASE 1: Resolution (upfront)
    # ==========================================================================
    # Resolve all tools BEFORE execution to catch issues early
    
    for action in actions:
        # Classify intent
        intent_result = intent_agent.classify(action["description"])
        action["_resolved_intent"] = intent_result.get("intent", "unknown")
        action["_intent_confidence"] = intent_result.get("confidence", 0)
        
        # Resolve tool
        resolution = tool_resolver.resolve(
            action["description"],
            action["_resolved_intent"],
            context
        )
        action["_resolved_tool"] = resolution.get("tool")
        action["_resolved_params"] = resolution.get("params", {})
        action["_resolution_reason"] = resolution.get("reason")
        
        logging.debug(
            f"  {action['id']}: intent={action['_resolved_intent']}, "
            f"tool={action['_resolved_tool']}"
        )
    
    # ==========================================================================
    # PHASE 1.5: Fail-fast for unresolved tools
    # ==========================================================================
    # If any action has no resolved tool, fail the entire chain
    
    unresolved = [
        a for a in actions 
        if a.get("_resolved_tool") is None
    ]
    
    if unresolved:
        logging.warning(f"MultiPipeline: {len(unresolved)} unresolved actions - failing fast")
        return {
            "status": "error",
            "type": "multi",
            "error": "Some actions could not be resolved to tools",
            "unresolved": [
                {
                    "id": a["id"],
                    "description": a["description"],
                    "reason": a.get("_resolution_reason", "No matching tool")
                }
                for a in unresolved
            ],
            "results": []
        }
    
    # ==========================================================================
    # PHASE 2: Prerequisite validation
    # ==========================================================================
    # Check all prerequisites BEFORE starting execution
    
    issues = validate_action_chain(actions, context)
    
    if issues:
        logging.warning(f"MultiPipeline: {len(issues)} prerequisite issues")
        return {
            "status": "blocked",
            "type": "multi",
            "issues": issues,
            "suggestion": "Some actions have unmet prerequisites",
            "results": []
        }
    
    # ==========================================================================
    # PHASE 3: Dependency-aware execution
    # ==========================================================================
    
    completed = {}
    results = []
    pending = {a["id"]: a for a in actions}
    
    while pending:
        # Find actions that are ready (all dependencies satisfied)
        ready = [
            a for a in pending.values()
            if all(dep in completed for dep in a.get("depends_on", []))
        ]
        
        if not ready:
            # Check for failed dependencies
            failed_deps = [
                a for a in pending.values()
                if any(
                    completed.get(dep, {}).get("status") == "error"
                    for dep in a.get("depends_on", [])
                )
            ]
            
            for action in failed_deps:
                result = {
                    "id": action["id"],
                    "status": "skipped",
                    "reason": "Dependency failed"
                }
                results.append(result)
                completed[action["id"]] = result
                del pending[action["id"]]
            
            if not pending:
                break
            
            # Re-check ready
            ready = [
                a for a in pending.values()
                if all(dep in completed for dep in a.get("depends_on", []))
            ]
            
            if not ready:
                # Circular dependency or other issue
                logging.error("MultiPipeline: circular dependency or deadlock")
                for action in pending.values():
                    results.append({
                        "id": action["id"],
                        "status": "error",
                        "error": "Circular dependency detected"
                    })
                break
        
        # Execute ready actions SEQUENTIALLY (conservative)
        for action in ready:
            logging.info(f"MultiPipeline: executing {action['id']} ({action['_resolved_tool']})")
            
            # Re-check prerequisites (context may have changed)
            prereq = check_prerequisites(action["_resolved_tool"], context)
            
            if not prereq["satisfied"]:
                result = {
                    "id": action["id"],
                    "status": "blocked",
                    "tool": action["_resolved_tool"],
                    "reason": prereq["reason"],
                    "suggestion": prereq.get("suggestion")
                }
            else:
                # Execute
                try:
                    exec_result = executor.execute_tool(
                        action["_resolved_tool"],
                        action["_resolved_params"]
                    )
                    result = {
                        "id": action["id"],
                        "status": exec_result.get("status", "success"),
                        "tool": action["_resolved_tool"],
                        "result": exec_result
                    }
                except Exception as e:
                    result = {
                        "id": action["id"],
                        "status": "error",
                        "tool": action["_resolved_tool"],
                        "error": str(e)
                    }
            
            results.append(result)
            completed[action["id"]] = result
            del pending[action["id"]]
            
            # Refresh context after each action
            context = refresh_context(executor)
    
    # ==========================================================================
    # PHASE 4: Aggregate results with structured output
    # ==========================================================================
    # Every action must either execute or be explainably skipped/blocked
    
    executed = [r for r in results if r.get("status") == "success"]
    blocked = [r for r in results if r.get("status") == "blocked"]
    skipped = [r for r in results if r.get("status") == "skipped"]
    errored = [r for r in results if r.get("status") == "error"]
    
    # Build human-readable summary
    summary_parts = []
    
    if executed:
        exec_desc = ", ".join([r.get("tool", r.get("id", "?")).split(".")[-1] for r in executed])
        summary_parts.append(f"Executed: {exec_desc}")
    
    if blocked:
        for r in blocked:
            reason = r.get("reason", "unknown reason")
            tool = r.get("tool", r.get("id", "?")).split(".")[-1]
            summary_parts.append(f"{tool} was blocked: {reason}")
    
    if skipped:
        skip_desc = ", ".join([r.get("id", "?") for r in skipped])
        summary_parts.append(f"Skipped (dependency failed): {skip_desc}")
    
    if errored:
        for r in errored:
            error = r.get("error", "unknown error")
            tool = r.get("tool", r.get("id", "?")).split(".")[-1]
            summary_parts.append(f"{tool} failed: {error}")
    
    summary = ". ".join(summary_parts) if summary_parts else "No actions processed"
    
    # Determine overall status
    total = len(results)
    success_count = len(executed)
    
    if success_count == total and total > 0:
        status = "success"
    elif success_count > 0:
        status = "partial"
    elif blocked:
        status = "blocked"
    else:
        status = "error"
    
    logging.info(f"MultiPipeline: {success_count}/{total} succeeded, {len(blocked)} blocked, {len(skipped)} skipped")
    
    return {
        "status": status,
        "type": "multi",
        "results": results,
        "executed": [r["id"] for r in executed],
        "blocked": [{"id": r["id"], "reason": r.get("reason")} for r in blocked],
        "skipped": [{"id": r["id"], "reason": r.get("reason")} for r in skipped],
        "errored": [{"id": r["id"], "error": r.get("error")} for r in errored],
        "summary": summary
    }
