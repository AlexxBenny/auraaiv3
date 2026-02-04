"""Action Pipeline - Tool resolution and execution for single actions

JARVIS Architecture Role:
- Handles action intents (application_launch, system_control, file_operation)
- Resolves tool + params via ToolResolver
- Validates prerequisites via sanity checks
- Executes immediately
"""

import logging
from typing import Dict, Any, List

from core.sanity_checks import check_prerequisites

# Progress streaming (GUI only, no-op for terminal)
try:
    from gui.progress import ProgressEmitter, NULL_EMITTER
except ImportError:
    class ProgressEmitter:
        def __init__(self, callback=None): pass
        def emit(self, msg): pass
    NULL_EMITTER = ProgressEmitter()


def handle_action(user_input: str, intent: str, context: Dict[str, Any],
                  tool_resolver, executor, progress: ProgressEmitter = None) -> Dict[str, Any]:
    """Resolve tool + params, validate prerequisites, execute.
    
    Args:
        user_input: User's action request
        intent: Classified intent
        context: Current system context
        tool_resolver: ToolResolver instance
        executor: ToolExecutor instance
        progress: Optional ProgressEmitter for GUI streaming
        
    Returns:
        {
            "status": "success" | "error" | "blocked",
            "type": "action",
            "tool": "tool.name",
            "result": {...}
        }
    """
    if progress is None:
        progress = NULL_EMITTER
    
    logging.info(f"ActionPipeline: processing '{user_input[:50]}...' (intent={intent})")
    
    # Step 1: Resolve tool + params (two-stage resolution)
    resolution = tool_resolver.resolve(user_input, intent, context)
    
    tool_name = resolution.get("tool")
    params = resolution.get("params", {})
    confidence = resolution.get("confidence", 0)
    stage = resolution.get("stage", 1)
    domain_match = resolution.get("domain_match", True)
    
    if not tool_name:
        reason = resolution.get("reason", "Could not determine which tool to use")
        resolution_status = resolution.get("status", "")
        logging.warning(f"ActionPipeline: no tool resolved (stage={stage}) - {reason}")
        
        # Check if this was blocked by safety constraints (capability_missing)
        # vs just not finding a matching tool (needs_fallback)
        if resolution_status == "capability_missing":
            # Safety constraint blocked resolution - don't fall back to reasoning
            # This is intentional, not a failure to find tools
            progress.emit("This action isn't supported yet")
            return {
                "status": "capability_missing",
                "type": "action",
                "intent": intent,
                "reason": reason,
                "message": f"I can't do that yet. {reason}",
                "resolution": resolution
            }
        else:
            # Normal resolution failure - try fallback reasoning
            return {
                "status": "needs_fallback",
                "type": "action",
                "reason": reason,
                "resolution": resolution
            }
    
    # Log resolution details for debugging
    logging.info(
        f"ActionPipeline: resolved to {tool_name} "
        f"(stage={stage}, conf={confidence:.2f}, domain_match={domain_match})"
    )
    # Human-friendly progress: "Found tool: set brightness"
    tool_display = tool_name.split('.')[-1].replace('_', ' ')
    progress.emit(f"Found tool: {tool_display}")
    
    # Step 1.5: PathResolver enforcement for file operations
    # INVARIANT: All file paths must go through PathResolver before reaching tools
    if intent == "file_operation" or tool_name.startswith("files."):
        params = _resolve_file_params(user_input, params, context)
    
    
    # Step 2: Prerequisite sanity check
    prereq = check_prerequisites(tool_name, context)
    
    if not prereq["satisfied"]:
        logging.warning(f"ActionPipeline: prerequisite not satisfied - {prereq['reason']}")
        return {
            "status": "blocked",
            "type": "action",
            "tool": tool_name,
            "reason": prereq["reason"],
            "suggestion": prereq.get("suggestion")
        }
    
    # Step 3: Execute immediately
    progress.emit("Executing...")
    try:
        result = executor.execute_tool(tool_name, params)
        
        status = result.get("status", "success")
        logging.info(f"ActionPipeline: executed {tool_name} -> {status}")
        
        # Step 4: Generate natural language response (NEW - Phase 2D)
        from core.response.pipeline import generate_response
        response_result = generate_response(tool_name, result, polish_enabled=False)
        
        # Step 5: Store facts in FactsMemory (NEW - Phase 3A)
        try:
            from memory.facts import get_facts_memory
            facts_memory = get_facts_memory()
            facts_memory.store(
                extracted=response_result.facts,
                query=user_input,
                session_id=context.get("session_id", "unknown")
            )
        except Exception as e:
            # Non-blocking - facts storage should never break execution
            logging.warning(f"FactsMemory storage failed: {e}")
        
        return {
            "status": status,
            "type": "action",
            "tool": tool_name,
            "params": params,
            "result": result,
            "facts": response_result.facts.facts,  # Memory-safe facts
            "response": response_result.final_response  # Natural language
        }
        
    except Exception as e:
        logging.error(f"ActionPipeline: execution failed - {e}")
        return {
            "status": "error",
            "type": "action",
            "tool": tool_name,
            "error": str(e)
        }


def handle_action_with_tools(user_input: str, intent: str, context: Dict[str, Any],
                             tools: List[Dict], llm, executor) -> Dict[str, Any]:
    """Alternative signature with explicit tools and LLM (for orchestrator use).
    
    This version doesn't require a ToolResolver instance.
    """
    from core.tool_resolver import ToolResolver
    
    resolver = ToolResolver()
    return handle_action(user_input, intent, context, resolver, executor)


def _resolve_file_params(user_input: str, params: Dict[str, Any], 
                         context: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve file paths through PathResolver before execution.
    
    INVARIANT: All paths reaching file tools must be absolute.
    This is the SINGLE AUTHORITY enforcement for the single pipeline.
    
    Args:
        user_input: Original user command (for anchor inference)
        params: Tool parameters (may contain relative paths)
        context: System context with session info
        
    Returns:
        Updated params with resolved absolute paths
    """
    from pathlib import Path
    from core.path_resolver import PathResolver
    
    # Path keys that file tools accept
    path_keys = ["path", "source", "destination", "src", "dest", "target"]
    
    for key in path_keys:
        if key not in params or not params[key]:
            continue
            
        raw_path = params[key]
        
        # Skip if already absolute
        if Path(raw_path).is_absolute():
            logging.debug(f"PathResolver (single): {key}='{raw_path}' already absolute")
            continue
        
        # Infer anchor from user input
        anchor = PathResolver.infer_base_anchor(user_input) or "WORKSPACE"
        
        # Get session context for WORKSPACE resolution
        session_ctx = context.get("_session_context")
        
        try:
            resolved = PathResolver.resolve(
                raw_path=raw_path,
                base_anchor=anchor,
                context=session_ctx
            )
            params[key] = str(resolved.absolute_path)
            logging.info(
                f"PathResolver (single): {key}='{raw_path}' → "
                f"'{resolved.absolute_path}' (anchor={anchor})"
            )
        except Exception as e:
            logging.warning(f"PathResolver (single) failed for {key}='{raw_path}': {e}")
            # Fall through with original value - tool may handle it
    
    return params

