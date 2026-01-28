"""Information Pipeline - Context-aware responses for pure information queries

ISSUE 3 FIX: Uses FactExtractor pattern
- Extracts facts from context (deterministic)
- Generates base response from facts (templates)
- LLM may ONLY polish, never originate content

INVARIANT: No user-visible text unless it originates from facts.

For questions that can't be answered from context/tools,
we return a clear "I don't have information about that" - not LLM fabrication.
"""

import logging
from typing import Dict, Any, List


def handle_information(user_input: str, context: Dict[str, Any], llm) -> Dict[str, Any]:
    """Generate response from context facts - no tool execution.
    
    Args:
        user_input: User's question
        context: Current system context (active window, running apps, etc.)
        llm: LLM model (ONLY used for understanding question intent, NOT for answering)
        
    Returns:
        {
            "status": "success",
            "type": "information",
            "facts": {...},  # Canonical facts from context
            "response": "..."  # Natural language from facts
        }
    """
    # Step 1: Extract canonical facts from context
    facts = _extract_context_facts(context)
    
    # Step 2: Determine what the user is asking about
    question_type = _classify_question(user_input, llm)
    
    # Step 3: Generate response from facts only
    response, answerable = _generate_response_from_facts(user_input, question_type, facts)
    
    if answerable:
        logging.info(f"InfoPipeline: answered from facts (type={question_type})")
        return {
            "status": "success",
            "type": "information",
            "facts": facts,
            "response": response
        }
    else:
        # Cannot answer from facts - be honest
        logging.info(f"InfoPipeline: cannot answer from context (type={question_type})")
        return {
            "status": "success",
            "type": "information",
            "facts": facts,
            "response": _generate_capability_response(user_input, question_type)
        }


def _extract_context_facts(context: Dict[str, Any]) -> Dict[str, Any]:
    """Extract canonical facts from system context.
    
    PURE FUNCTION - No side effects.
    """
    facts = {}
    
    # Active window facts
    active_window = context.get("active_window", {})
    if active_window:
        facts["active_window_title"] = active_window.get("title")
        facts["active_window_process"] = active_window.get("process_name") or active_window.get("process")
    
    # Running apps facts
    running_apps = context.get("running_apps", [])
    if running_apps:
        facts["running_apps"] = running_apps[:10]
        facts["running_apps_count"] = len(running_apps)
    
    # Battery facts
    battery = context.get("battery", {})
    if battery:
        facts["battery_percent"] = battery.get("percent")
        facts["battery_plugged"] = battery.get("plugged")
    
    # Time facts (if available)
    if context.get("time"):
        facts["current_time"] = context.get("time")
    
    # Remove None values
    return {k: v for k, v in facts.items() if v is not None}


def _classify_question(user_input: str, llm) -> str:
    """Classify what type of information the user is asking about.
    
    Uses LLM ONLY to understand question intent, NOT to answer.
    """
    user_lower = user_input.lower()
    
    # Simple keyword matching first (no LLM needed)
    if any(w in user_lower for w in ["battery", "power", "charge"]):
        return "battery"
    if any(w in user_lower for w in ["running", "apps", "programs", "open"]):
        return "running_apps"
    if any(w in user_lower for w in ["window", "focus", "active"]):
        return "active_window"
    if any(w in user_lower for w in ["time", "clock"]):
        return "time"
    if any(w in user_lower for w in ["what can you do", "capabilities", "help"]):
        return "capabilities"
    if any(w in user_lower for w in ["who are you", "your name"]):
        return "identity"
    
    return "unknown"


def _generate_response_from_facts(user_input: str, question_type: str, facts: Dict[str, Any]) -> tuple:
    """Generate response strictly from facts.
    
    Returns: (response: str, answerable: bool)
    """
    
    if question_type == "battery":
        pct = facts.get("battery_percent")
        plugged = facts.get("battery_plugged")
        if pct is not None:
            status = "and charging" if plugged else "on battery power"
            return f"Battery is at {pct}% {status}.", True
        return "I don't have current battery information.", False
    
    if question_type == "running_apps":
        apps = facts.get("running_apps", [])
        count = facts.get("running_apps_count", 0)
        if apps:
            apps_str = ", ".join(apps[:5])
            more = f" and {count - 5} more" if count > 5 else ""
            return f"Running apps: {apps_str}{more}.", True
        return "I don't have information about running apps.", False
    
    if question_type == "active_window":
        title = facts.get("active_window_title")
        process = facts.get("active_window_process")
        if title:
            if process:
                return f"Active window: {title} ({process}).", True
            return f"Active window: {title}.", True
        return "I don't have information about the active window.", False
    
    if question_type == "time":
        time = facts.get("current_time")
        if time:
            return f"The current time is {time}.", True
        return "I don't have the current time. Try asking 'what time is it' as a system query.", False
    
    if question_type == "capabilities":
        return _get_capabilities_response(), True
    
    if question_type == "identity":
        return "I'm AURA, an intelligent desktop assistant. I can control your system, manage windows, adjust settings, and answer questions about your computer.", True
    
    return "I can only answer questions about your system state. For general knowledge, I don't have that capability yet.", False


def _generate_capability_response(user_input: str, question_type: str) -> str:
    """Generate response when question can't be answered from facts."""
    return (
        "I can answer questions about your system: battery, running apps, active window, time, etc. "
        "For this question, I don't have the information available. "
        "Try asking me to check something specific on your system."
    )


def _get_capabilities_response() -> str:
    """Return capabilities response - deterministic, not LLM-generated."""
    return (
        "I can help you with:\n"
        "• System control: volume, brightness, power actions\n"
        "• Window management: minimize, snap, switch windows\n"
        "• System queries: battery, memory, disk, network status\n"
        "• Applications: launch, focus, close apps\n"
        "• Media: play/pause, next/previous track\n"
        "• Desktop: night light, wallpaper, recycle bin"
    )

