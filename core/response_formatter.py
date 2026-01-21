"""Response Formatter - Generates user-facing messages from structural data

This module converts structured refusal objects into human-readable messages.

Principle: Prose is generated AFTER, not stored in refusal objects.
           Refusal objects remain purely structural and machine-readable.
"""

from typing import Dict, Any, List, Optional


def format_refusal_message(refusal: Dict[str, Any]) -> str:
    """
    Generate user-friendly message from structural refusal object.
    
    Args:
        refusal: Refusal object with blocked_tools and blocking_constraints
        
    Returns:
        Human-readable refusal message
    """
    if not refusal:
        return "Action was refused due to safety constraints."
    
    blocked_tools = refusal.get("blocked_tools", [])
    blocking_constraints = refusal.get("blocking_constraints", [])
    error_type = refusal.get("error_type")
    
    # Handle error cases first
    if error_type == "system_unavailable":
        return "I cannot verify this action is safe right now. Please try again later."
    
    if error_type == "tool_unknown":
        return "This action is not registered in my safety system."
    
    if error_type == "eligibility_check_failed":
        return "Safety verification failed. Cannot proceed with this action."
    
    if not blocked_tools and not blocking_constraints:
        return "Action was refused due to safety constraints."
    
    # Build message from constraints
    messages = []
    
    # Group constraints by type for cleaner messaging
    constraint_msgs = []
    resolution_hints = []
    
    for constraint in blocking_constraints:
        c_name = constraint.get("constraint", "unknown")
        c_type = constraint.get("type", "unknown")
        hint = constraint.get("resolution_hint", "")
        resolvable = constraint.get("resolvable", False)
        
        # Generate constraint-specific message
        if c_name == "requires_target_context":
            constraint_msgs.append("I don't know which window to target")
        elif c_name == "window_must_exist":
            constraint_msgs.append("The target window doesn't exist")
        elif c_name == "unique_target_required":
            constraint_msgs.append("Multiple windows match your request")
        elif c_name == "executable_must_exist":
            constraint_msgs.append("The application was not found")
        elif c_name == "coordinates_within_screen":
            constraint_msgs.append("The specified location is outside the screen")
        elif c_name == "tool_not_in_ontology":
            constraint_msgs.append("This action is not registered in my safety system")
        else:
            constraint_msgs.append(f"Safety constraint '{c_name}' is not satisfied")
        
        if hint and resolvable:
            resolution_hints.append(hint)
    
    # Build the final message
    if constraint_msgs:
        main_msg = "I cannot complete this action because: " + "; ".join(constraint_msgs) + "."
    else:
        main_msg = "I cannot complete this action due to safety constraints."
    
    # Add resolution suggestion if available
    if resolution_hints:
        # Deduplicate hints
        unique_hints = list(dict.fromkeys(resolution_hints))
        suggestion = " Try: " + unique_hints[0]
        main_msg += suggestion
    
    return main_msg


def format_safety_warnings(warnings: List[Dict[str, Any]]) -> Optional[str]:
    """
    Generate user-friendly message from safety warnings.
    
    Args:
        warnings: List of warning dicts with tool, warning, type, recommendation
        
    Returns:
        Human-readable warning message, or None if no warnings
    """
    if not warnings:
        return None
    
    warning_msgs = []
    
    for w in warnings:
        tool = w.get("tool", "unknown")
        constraint = w.get("warning", "unknown")
        hint = w.get("recommendation", "")
        
        # Generate warning-specific message
        if constraint == "unsafe_without_context":
            msg = f"Proceeding without explicit window context"
        elif constraint == "may_prompt_save_dialog":
            msg = f"The application may show a save dialog"
        else:
            msg = f"Warning: {constraint}"
        
        if hint:
            msg += f" ({hint})"
        
        warning_msgs.append(msg)
    
    if warning_msgs:
        return "Note: " + "; ".join(warning_msgs)
    
    return None


def format_plan_response(plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add formatted messages to a plan response.
    
    This processes the plan and adds user-facing messages while
    keeping the structural data intact.
    
    Args:
        plan: Plan dict from PlannerAgent
        
    Returns:
        Plan with added formatted_message field
    """
    result = plan.copy()
    
    if plan.get("refused"):
        refusal = plan.get("refusal", {})
        result["formatted_message"] = format_refusal_message(refusal)
    elif plan.get("safety_warnings"):
        warning_msg = format_safety_warnings(plan["safety_warnings"])
        if warning_msg:
            result["formatted_warning"] = warning_msg
    
    return result
