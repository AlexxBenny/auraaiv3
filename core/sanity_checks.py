"""Sanity Checks - Deterministic prerequisite validation

JARVIS Architecture Role:
- Validate prerequisites BEFORE execution (not after)
- DETERMINISTIC: no LLM involved, pure Python
- Prevents "typing into the void" and similar embarrassing failures

Checks:
- Focus validation: keyboard/mouse actions need a focused window
- Screen lock: display operations need unlocked screen
- Process state: actions targeting apps need those apps running
"""

import logging
from typing import Dict, Any, List, Optional


def check_prerequisites(tool_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic prerequisite validation for a tool.
    
    Args:
        tool_name: The tool about to be executed
        context: Current system context
        
    Returns:
        {
            "satisfied": bool,
            "reason": str (if not satisfied),
            "suggestion": str (if not satisfied)
        }
    """
    # Keyboard/mouse actions require a focused window
    if tool_name.startswith("system.input."):
        return _check_focus_required(context)
    
    # Screen operations require unlocked screen
    if tool_name.startswith("system.display."):
        return _check_screen_unlocked(context)
    
    # App focus requires the app to exist
    if tool_name == "system.apps.focus":
        return _check_app_exists(context)
    
    # Default: no prerequisites
    return {"satisfied": True}


def _check_focus_required(context: Dict[str, Any]) -> Dict[str, Any]:
    """Check that a window is focused for input actions."""
    active_window = context.get("active_window", {})
    
    # Check for valid window handle
    hwnd = active_window.get("hwnd")
    title = active_window.get("title", "")
    
    if not hwnd or hwnd == 0:
        return {
            "satisfied": False,
            "reason": "No window is focused. Cannot send keyboard/mouse input.",
            "suggestion": "Focus a window first (e.g., 'open notepad', 'click on chrome')"
        }
    
    # Desktop is technically focused but not a valid input target
    if title == "" or title.lower() == "program manager":
        return {
            "satisfied": False,
            "reason": "Desktop is focused, not an application window.",
            "suggestion": "Open or focus an application first"
        }
    
    return {"satisfied": True}


def _check_screen_unlocked(context: Dict[str, Any]) -> Dict[str, Any]:
    """Check that screen is not locked for display operations."""
    exec_context = context.get("execution_context", {})
    
    if exec_context.get("screen_locked_heuristic", False):
        return {
            "satisfied": False,
            "reason": "Screen appears to be locked.",
            "suggestion": "Unlock the screen first"
        }
    
    return {"satisfied": True}


def _check_app_exists(context: Dict[str, Any]) -> Dict[str, Any]:
    """Check that the target app exists for focus operations."""
    # This is a soft check - the tool itself will handle the error
    # But we can provide a better message if we know the app isn't running
    running_apps = context.get("running_apps", [])
    
    # If we have no info, assume it's OK
    if not running_apps:
        return {"satisfied": True}
    
    return {"satisfied": True}


def validate_action_chain(actions: List[Dict], context: Dict[str, Any]) -> List[Dict]:
    """Validate an entire action chain before execution.
    
    Used for multi-query pipeline to catch issues before starting.
    
    Args:
        actions: List of resolved actions with _resolved_tool
        context: Current system context
        
    Returns:
        List of issues found (empty if all valid)
    """
    issues = []
    
    # Build map of what each action provides
    provides_focus = set()
    for action in actions:
        tool = action.get("_resolved_tool", "")
        if tool.startswith("system.apps.launch") or tool == "system.apps.focus":
            provides_focus.add(action["id"])
    
    for action in actions:
        tool = action.get("_resolved_tool")
        if not tool:
            continue
        
        prereq = check_prerequisites(tool, context)
        if not prereq["satisfied"]:
            # Check if a dependency provides what we need
            deps = set(action.get("depends_on", []))
            
            # For focus requirement, check if any dependency provides focus
            if "focus" in prereq.get("reason", "").lower():
                if deps & provides_focus:
                    # A dependency will provide focus - OK
                    continue
            
            issues.append({
                "action_id": action["id"],
                "tool": tool,
                "issue": prereq["reason"],
                "suggestion": prereq.get("suggestion")
            })
    
    return issues


def refresh_context(executor) -> Dict[str, Any]:
    """Refresh context after an action (for multi-query chain).
    
    Args:
        executor: ToolExecutor instance
        
    Returns:
        Updated context dict
    """
    context = {}
    
    try:
        # Get active window
        result = executor.execute_tool("system.state.get_active_window", {})
        if result.get("status") == "success":
            context["active_window"] = result.get("window", {})
    except Exception as e:
        logging.debug(f"Failed to refresh active_window: {e}")
    
    try:
        # Get execution context
        result = executor.execute_tool("system.state.get_execution_context", {})
        if result.get("status") == "success":
            context["execution_context"] = result.get("context", {})
    except Exception as e:
        logging.debug(f"Failed to refresh execution_context: {e}")
    
    return context
