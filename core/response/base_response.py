"""Base Response - Deterministic natural language from facts

Templates are contracts, not boring scaffolding.
This layer provides:
- Testability
- Reproducibility
- Regression safety
- Works even if LLM is offline

PURE FUNCTION - No side effects, logging, or I/O.
"""

from typing import Dict, Any, List
from .fact_extractor import ExtractedFacts


def generate_base_response(extracted: ExtractedFacts) -> str:
    """Generate deterministic natural language from facts.
    
    PURE FUNCTION - No LLM, no side effects.
    
    Args:
        extracted: ExtractedFacts from fact_extractor
        
    Returns:
        Deterministic natural language string
    """
    tool_name = extracted.tool
    facts = extracted.facts
    status = extracted.status
    
    # Handle non-success statuses
    if status == "refused":
        return _format_refused(tool_name, facts)
    
    if status == "unsupported":
        return _format_unsupported(tool_name, facts)
    
    if status == "blocked":
        return _format_blocked(tool_name, facts)
    
    if status == "error":
        return _format_error(tool_name, facts)
    
    # Success - use domain templates
    domain = _get_domain(tool_name)
    return _format_by_domain(domain, tool_name, facts)


def _get_domain(tool_name: str) -> str:
    """Extract domain from tool name."""
    parts = tool_name.split('.')
    if len(parts) >= 2:
        return '.'.join(parts[:2])
    return tool_name


def _format_refused(tool_name: str, facts: Dict[str, Any]) -> str:
    """Format response for refused actions."""
    action = tool_name.split('.')[-1].replace('_', ' ')
    return f"I need confirmation before I can {action}. Please confirm to proceed."


def _format_unsupported(tool_name: str, facts: Dict[str, Any]) -> str:
    """Format response for unsupported operations."""
    action = tool_name.split('.')[-1].replace('_', ' ')
    reason = facts.get("error", "This operation is not supported on your system")
    return f"Cannot {action}: {reason}."


def _format_blocked(tool_name: str, facts: Dict[str, Any]) -> str:
    """Format response for blocked actions."""
    action = tool_name.split('.')[-1].replace('_', ' ')
    reason = facts.get("reason", "Prerequisites not met")
    return f"Cannot {action} right now: {reason}."


def _format_error(tool_name: str, facts: Dict[str, Any]) -> str:
    """Format response for errors."""
    action = tool_name.split('.')[-1].replace('_', ' ')
    error = facts.get("error", "An unexpected error occurred")
    return f"Failed to {action}: {error}."


def _format_by_domain(domain: str, tool_name: str, facts: Dict[str, Any]) -> str:
    """Format response based on tool domain."""
    
    # System state queries
    if domain == "system.state":
        return _format_state(tool_name, facts)
    
    # System audio
    if domain == "system.audio":
        return _format_audio(tool_name, facts)
    
    # System display
    if domain == "system.display":
        return _format_display(tool_name, facts)
    
    # System power
    if domain == "system.power":
        return _format_power(tool_name, facts)
    
    # Window management
    if domain == "system.window":
        return _format_window(tool_name, facts)
    
    # Desktop controls
    if domain == "system.desktop":
        return _format_desktop(tool_name, facts)
    
    # Network
    if domain == "system.network":
        return _format_network(tool_name, facts)
    
    # Apps
    if domain == "system.apps":
        return _format_apps(tool_name, facts)
    
    # Clipboard
    if domain == "system.clipboard":
        return _format_clipboard(tool_name, facts)
    
    # Memory recall - memory.* has only 2 parts
    if domain.startswith("memory"):
        return _format_memory(tool_name, facts)
    
    # Generic fallback
    return _format_generic(tool_name, facts)


# --- Domain-specific formatters ---

def _format_state(tool_name: str, facts: Dict[str, Any]) -> str:
    """Format system.state.* responses"""
    
    if "get_memory" in tool_name:
        ram = facts.get("ram_used_percent")
        swap = facts.get("swap_used_percent")
        parts = []
        if ram is not None:
            parts.append(f"RAM usage is {ram}%")
        if swap is not None:
            parts.append(f"Swap usage is {swap}%")
        return ". ".join(parts) + "." if parts else "Memory status retrieved."
    
    if "get_disk" in tool_name:
        drives = facts.get("drives", [])
        if not drives:
            return f"Found {facts.get('drive_count', 0)} drives."
        
        parts = []
        for d in drives[:3]:  # Limit to 3 drives
            drive = d.get("drive", "?")
            pct = d.get("percent_used")
            free = d.get("free_human")
            if pct is not None and free:
                parts.append(f"{drive} is {pct}% full ({free} free)")
            elif pct is not None:
                parts.append(f"{drive} is {pct}% full")
        
        return ". ".join(parts) + "." if parts else "Disk usage retrieved."
    
    if "get_network" in tool_name:
        connected = facts.get("connected")
        route = facts.get("default_route")
        ssid = facts.get("wifi_ssid")
        
        if connected:
            if route == "wifi" and ssid:
                return f"Connected to WiFi network '{ssid}'."
            elif route == "wifi":
                return "Connected via WiFi."
            elif route == "ethernet":
                return "Connected via Ethernet."
            else:
                return "You are connected to the internet."
        else:
            return "You are not connected to the internet."
    
    if "get_battery" in tool_name:
        pct = facts.get("battery_percent")
        plugged = facts.get("plugged_in")
        if pct is not None:
            status = "and charging" if plugged else "on battery power"
            return f"Battery is at {pct}% {status}."
        return "Battery status retrieved."
    
    if "get_time" in tool_name:
        time = facts.get("time")
        return f"The current time is {time}." if time else "Time retrieved."
    
    if "get_date" in tool_name:
        date = facts.get("date")
        return f"Today's date is {date}." if date else "Date retrieved."
    
    if "get_datetime" in tool_name:
        # Handle datetime queries with flexible responses
        year = facts.get("current_year")
        month = facts.get("current_month")
        day = facts.get("current_day")
        hour = facts.get("current_hour")
        minute = facts.get("current_minute")
        day_of_week = facts.get("day_of_week")
        
        # Build response based on what facts are available
        if year and month and day and hour is not None and minute is not None:
            time_str = f"{hour:02d}:{minute:02d}"
            date_str = f"{day_of_week}, {year}-{month:02d}-{day:02d}"
            return f"It's {time_str} on {date_str}."
        elif year:
            return f"The year is {year}."
        return "Date and time retrieved."
    
    if "get_active_window" in tool_name:
        title = facts.get("window_title")
        process = facts.get("process_name")
        if title and process:
            return f"Active window: {title} ({process})."
        elif title:
            return f"Active window: {title}."
        return "Active window information retrieved."
    
    return "System information retrieved."


def _format_audio(tool_name: str, facts: Dict[str, Any]) -> str:
    """Format system.audio.* responses"""
    
    if "set_volume" in tool_name or "get_volume" in tool_name:
        level = facts.get("volume_level")
        if level is not None:
            return f"Volume is set to {level}%."
        return "Volume adjusted."
    
    if "mute" in tool_name.lower():
        muted = facts.get("muted", True)
        return "Audio muted." if muted else "Audio unmuted."
    
    if "media_play_pause" in tool_name:
        return "Toggled media playback."
    
    if "media_next" in tool_name:
        return "Skipped to next track."
    
    if "media_previous" in tool_name:
        return "Went back to previous track."
    
    action = facts.get("action", "Audio control")
    return f"{action} completed."


def _format_display(tool_name: str, facts: Dict[str, Any]) -> str:
    """Format system.display.* responses"""
    
    if "brightness" in tool_name.lower():
        level = facts.get("brightness_level")
        count = facts.get("display_count", 1)
        if level is not None:
            if count > 1:
                return f"Brightness set to {level}% on {count} displays."
            return f"Brightness set to {level}%."
        return "Brightness adjusted."
    
    if "screenshot" in tool_name.lower():
        path = facts.get("screenshot_path")
        if path:
            return f"Screenshot saved to {path}."
        return "Screenshot captured."
    
    return "Display setting updated."


def _format_power(tool_name: str, facts: Dict[str, Any]) -> str:
    """Format system.power.* responses"""
    action = facts.get("action", tool_name.split('.')[-1])
    
    if action == "lock":
        return "Screen locked."
    elif action == "sleep":
        return "Putting system to sleep."
    elif action == "shutdown":
        return "System is shutting down."
    elif action == "restart":
        return "System is restarting."
    
    return f"Power action '{action}' completed."


def _format_window(tool_name: str, facts: Dict[str, Any]) -> str:
    """Format system.window.* responses"""
    action = facts.get("action", tool_name.split('.')[-1])
    
    action_messages = {
        "minimize_all": "All windows minimized.",
        "snap_left": "Window snapped to the left.",
        "snap_right": "Window snapped to the right.",
        "maximize": "Window maximized.",
        "minimize": "Window minimized.",
        "close": "Window closed.",
        "switch": "Switched to another window.",
        "task_view": "Opened task view."
    }
    
    return action_messages.get(action, f"Window action '{action}' completed.")


def _format_desktop(tool_name: str, facts: Dict[str, Any]) -> str:
    """Format system.desktop.* responses"""
    
    if "night_light" in tool_name.lower():
        enabled = facts.get("night_light_enabled")
        if enabled is not None:
            return "Night light enabled." if enabled else "Night light disabled."
        return "Night light setting updated."
    
    if "icons" in tool_name.lower():
        visible = facts.get("icons_visible")
        if visible is not None:
            return "Desktop icons shown." if visible else "Desktop icons hidden."
        return "Desktop icons toggled."
    
    if "recycle" in tool_name.lower():
        emptied = facts.get("recycle_bin_emptied")
        if emptied:
            return "Recycle bin emptied."
        return "Recycle bin operation completed."
    
    if "explorer" in tool_name.lower():
        return "Windows Explorer restarted."
    
    return "Desktop setting updated."


def _format_network(tool_name: str, facts: Dict[str, Any]) -> str:
    """Format system.network.* responses"""
    
    if "airplane" in tool_name.lower():
        enabled = facts.get("airplane_mode_enabled")
        if enabled is not None:
            return "Airplane mode enabled." if enabled else "Airplane mode disabled."
        return "Airplane mode toggled."
    
    return "Network setting updated."


def _format_apps(tool_name: str, facts: Dict[str, Any]) -> str:
    """Format system.apps.* responses"""
    
    if "launch" in tool_name.lower():
        app_name = facts.get("app_name")
        if app_name:
            return f"Launched {app_name}."
        return "Application launched."
    
    if "focus" in tool_name.lower():
        focused = facts.get("app_focused")
        if focused:
            return f"Focused {focused}." if isinstance(focused, str) else "Application focused."
        return "Application focused."
    
    if "close" in tool_name.lower():
        return "Application closed."
    
    return "Application operation completed."


def _format_clipboard(tool_name: str, facts: Dict[str, Any]) -> str:
    """Format system.clipboard.* responses"""
    
    if "read" in tool_name.lower():
        content = facts.get("clipboard_content", "")
        length = facts.get("content_length", 0)
        if content:
            preview = content[:50] + "..." if len(content) > 50 else content
            return f"Clipboard contains: {preview}"
        return "Clipboard is empty."
    
    if "write" in tool_name.lower():
        written = facts.get("clipboard_written")
        if written:
            return "Text copied to clipboard."
        return "Clipboard operation completed."
    
    return "Clipboard operation completed."


def _format_memory(tool_name: str, facts: Dict[str, Any]) -> str:
    """Format memory.* responses (recall)"""
    
    if "get_recent_facts" in tool_name:
        recalled = facts.get("recalled_facts", [])
        count = facts.get("recall_count", 0)
        time_range = facts.get("time_range_minutes", 60)
        
        if count == 0:
            return f"I don't have any records from the last {time_range} minutes."
        
        # Build summary of recalled facts
        if count == 1 and recalled:
            # Single fact - more detailed
            fact = recalled[0]
            tool_short = fact.get("tool", "").split(".")[-1].replace("_", " ")
            keys = fact.get("keys", [])
            fact_data = fact.get("facts", {})
            
            # Format the most relevant value
            if keys and fact_data:
                key = keys[0]
                value = fact_data.get(key)
                if value is not None:
                    return f"Earlier ({tool_short}): {key.replace('_', ' ')} was {value}."
            
            return f"Found 1 record from {tool_short}."
        
        # Multiple facts - summary
        tools_seen = set()
        for f in recalled:
            t = f.get("tool", "").split(".")[-1].replace("_", " ")
            if t:
                tools_seen.add(t)
        
        tools_str = ", ".join(list(tools_seen)[:3])
        return f"Found {count} records from the last {time_range} minutes: {tools_str}."
    
    return "Memory query completed."


def _format_generic(tool_name: str, facts: Dict[str, Any]) -> str:
    """Generic formatter for unknown tools"""
    action = tool_name.split('.')[-1].replace('_', ' ')
    return f"Completed {action}."

