"""Fact Extractor - Extract canonical facts from tool results

REFINEMENT 1: Schema-driven, not hardcoded
- Tools declare their own fact_schema in the Tool class
- FactExtractor uses that metadata
- Zero coupling between response layer and tool inventory

CRITICAL: This is the SOURCE OF TRUTH for memory storage.
Only facts extracted here should be stored in memory.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from tools.registry import get_registry


@dataclass
class ExtractedFacts:
    """Canonical fact extraction result
    
    Attributes:
        facts: Dict of normalized fact key-values (memory-safe)
        summary: One-line summary of what happened
        tool: Tool name that generated these facts
        status: Tool execution status
    """
    facts: Dict[str, Any]
    summary: str
    tool: str
    status: str


def extract_facts(tool_name: str, result: Dict[str, Any]) -> ExtractedFacts:
    """Extract normalized facts from tool result.
    
    PURE FUNCTION - No side effects, logging, or I/O.
    
    Resolution order:
    1. Tool's declared fact_schema (if present)
    2. Default extractor based on tool domain
    3. Generic extraction of top-level values
    
    Args:
        tool_name: Full tool name (e.g., "system.state.get_memory_usage")
        result: Raw execution result dict from tool
        
    Returns:
        ExtractedFacts with normalized facts and summary
    """
    status = result.get("status", "unknown")
    
    # Try tool-declared schema first (Refinement 1)
    tool_facts = _extract_by_tool_schema(tool_name, result)
    if tool_facts is not None:
        return ExtractedFacts(
            facts=tool_facts,
            summary=_generate_summary(tool_name, tool_facts, status),
            tool=tool_name,
            status=status
        )
    
    # Fall back to domain-based extraction
    domain = _get_domain(tool_name)
    domain_facts = _extract_by_domain(domain, tool_name, result)
    
    return ExtractedFacts(
        facts=domain_facts,
        summary=_generate_summary(tool_name, domain_facts, status),
        tool=tool_name,
        status=status
    )


def _extract_by_tool_schema(tool_name: str, result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract using tool's declared fact_schema if available.
    
    ISSUE 1 FIX: Bidirectional and typed schema format
    
    Schema format in tool class:
        fact_schema = {
            "ram_used_percent": {
                "path": ["ram", "percent_used"],  # List path, not dot notation
                "type": float,
                "required": True
            },
            "swap_used_percent": {
                "path": ["swap", "percent_used"],
                "type": float,
                "required": False
            }
        }
    
    Legacy format still supported:
        fact_schema = {
            "ram_used_percent": "ram.percent_used"  # Dot notation string
        }
    """
    try:
        registry = get_registry()
        tool = registry.get(tool_name)
        
        if tool is None:
            return None
        
        # Check if tool declares fact_schema
        fact_schema = getattr(tool, 'fact_schema', None)
        if fact_schema is None:
            return None
        
        # Extract according to schema
        facts = {}
        missing_required = []
        
        for fact_key, spec in fact_schema.items():
            # Handle both new typed format and legacy string format
            if isinstance(spec, str):
                # Legacy: "ram.percent_used"
                value = _get_nested_value(result, spec)
                if value is not None:
                    facts[fact_key] = value
            elif isinstance(spec, dict):
                # New typed format
                path = spec.get("path", [])
                required = spec.get("required", False)
                expected_type = spec.get("type")
                
                value = _get_nested_value_by_list(result, path)
                
                if value is not None:
                    # Type validation
                    if expected_type is not None and not isinstance(value, expected_type):
                        # Try type coercion
                        try:
                            value = expected_type(value)
                        except (ValueError, TypeError):
                            if required:
                                missing_required.append(fact_key)
                            continue
                    facts[fact_key] = value
                elif required:
                    missing_required.append(fact_key)
        
        # If any required fields missing, fall back to domain extraction
        if missing_required:
            return None
        
        return facts if facts else None
        
    except Exception:
        # Tool not found or schema issue - fall back to domain extraction
        return None


def _get_nested_value_by_list(data: Dict, path: List[str]) -> Any:
    """Get value from nested dict using list path.
    
    Example: _get_nested_value_by_list({"ram": {"percent": 70.8}}, ["ram", "percent"]) -> 70.8
    """
    value = data
    
    for key in path:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return None
        
        if value is None:
            return None
    
    return value


def _get_nested_value(data: Dict, path: str) -> Any:
    """Get value from nested dict using dot notation path (legacy support).
    
    Example: _get_nested_value({"ram": {"percent": 70.8}}, "ram.percent") -> 70.8
    """
    keys = path.split('.')
    value = data
    
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return None
        
        if value is None:
            return None
    
    return value


def _get_domain(tool_name: str) -> str:
    """Extract domain from tool name.
    
    Example: "system.state.get_memory_usage" -> "system.state"
    """
    parts = tool_name.split('.')
    if len(parts) >= 2:
        return '.'.join(parts[:2])
    return tool_name


def _extract_by_domain(domain: str, tool_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract facts based on tool domain."""
    
    # System state queries
    if domain == "system.state":
        return _extract_state_facts(tool_name, result)
    
    # System control actions
    if domain == "system.audio":
        return _extract_audio_facts(tool_name, result)
    
    if domain == "system.display":
        return _extract_display_facts(tool_name, result)
    
    if domain == "system.power":
        return _extract_power_facts(tool_name, result)
    
    if domain == "system.window":
        return _extract_window_facts(tool_name, result)
    
    if domain == "system.desktop":
        return _extract_desktop_facts(tool_name, result)
    
    if domain == "system.network":
        return _extract_network_facts(tool_name, result)
    
    if domain == "system.apps":
        return _extract_app_facts(tool_name, result)
    
    if domain == "system.clipboard":
        return _extract_clipboard_facts(tool_name, result)
    
    # Memory domain (Phase 3A) - memory.* has only 2 parts
    if domain.startswith("memory"):
        return _extract_memory_facts(tool_name, result)
    
    # Generic fallback
    return _extract_generic_facts(result)


# --- Domain-specific extractors ---

def _extract_state_facts(tool_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract facts from system.state.* tools"""
    facts = {"tool": tool_name}
    
    if "get_memory" in tool_name:
        ram = result.get("ram", {})
        swap = result.get("swap", {})
        facts.update({
            "ram_used_percent": ram.get("percent_used"),
            "ram_total_human": ram.get("total_human"),
            "ram_available_human": ram.get("available_human"),
            "swap_used_percent": swap.get("percent_used")
        })
    
    elif "get_disk" in tool_name:
        drives = result.get("drives", [])
        facts["drive_count"] = len(drives)
        facts["drives"] = [
            {
                "drive": d.get("drive"),
                "percent_used": d.get("percent_used"),
                "free_human": d.get("free_human")
            }
            for d in drives
        ]
    
    elif "get_network" in tool_name:
        facts.update({
            "connected": result.get("connected"),
            "default_route": result.get("default_route"),
            "wifi_ssid": result.get("wifi", {}).get("ssid"),
            "wifi_connected": result.get("wifi", {}).get("connected")
        })
    
    elif "get_battery" in tool_name:
        facts.update({
            "battery_percent": result.get("percentage"),  # Tool returns "percentage"
            "plugged_in": result.get("plugged_in")        # Tool returns "plugged_in"
        })
    
    elif "get_time" in tool_name:
        facts["time"] = result.get("time")
    
    elif "get_date" in tool_name:
        facts["date"] = result.get("date")
    
    elif "get_active_window" in tool_name:
        facts.update({
            "window_title": result.get("title"),
            "process_name": result.get("process_name")
        })
    
    # Remove None values
    return {k: v for k, v in facts.items() if v is not None}


def _extract_audio_facts(tool_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract facts from system.audio.* tools"""
    facts = {"tool": tool_name}
    
    if "volume" in tool_name.lower():
        facts["volume_level"] = result.get("level") or result.get("volume")
    
    if "mute" in tool_name.lower():
        facts["muted"] = result.get("muted", True)
    
    if "media" in tool_name.lower():
        facts["action"] = result.get("action", tool_name.split('.')[-1])
    
    return {k: v for k, v in facts.items() if v is not None}


def _extract_display_facts(tool_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract facts from system.display.* tools"""
    facts = {"tool": tool_name}
    
    if "brightness" in tool_name.lower():
        facts.update({
            "brightness_level": result.get("level"),
            "display_count": len(result.get("displays", [])),
            "displays": result.get("displays")
        })
    
    elif "screenshot" in tool_name.lower():
        facts["screenshot_path"] = result.get("path")
    
    return {k: v for k, v in facts.items() if v is not None}


def _extract_power_facts(tool_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract facts from system.power.* tools"""
    action = tool_name.split('.')[-1]  # lock, sleep, shutdown
    return {
        "tool": tool_name,
        "action": action,
        "executed": result.get("status") == "success"
    }


def _extract_window_facts(tool_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract facts from system.window.* tools"""
    action = tool_name.split('.')[-1]  # minimize_all, snap_left, etc.
    return {
        "tool": tool_name,
        "action": action,
        "executed": result.get("status") == "success"
    }


def _extract_desktop_facts(tool_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract facts from system.desktop.* tools"""
    facts = {"tool": tool_name}
    
    if "night_light" in tool_name.lower():
        facts["night_light_enabled"] = result.get("enabled")
    
    elif "icons" in tool_name.lower():
        facts["icons_visible"] = result.get("visible")
    
    elif "recycle" in tool_name.lower():
        facts["recycle_bin_emptied"] = result.get("status") == "success"
    
    return {k: v for k, v in facts.items() if v is not None}


def _extract_network_facts(tool_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract facts from system.network.* tools"""
    facts = {"tool": tool_name}
    
    if "airplane" in tool_name.lower():
        facts["airplane_mode_enabled"] = result.get("enabled")
    
    return {k: v for k, v in facts.items() if v is not None}


def _extract_app_facts(tool_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract facts from system.apps.* tools"""
    facts = {"tool": tool_name}
    
    if "launch" in tool_name.lower():
        facts.update({
            "app_launched": result.get("launched"),
            "app_name": result.get("app_name") or result.get("name"),
            "path": result.get("path")
        })
    
    elif "focus" in tool_name.lower():
        facts["app_focused"] = result.get("focused")
    
    elif "close" in tool_name.lower():
        facts["app_closed"] = result.get("closed")
    
    return {k: v for k, v in facts.items() if v is not None}


def _extract_clipboard_facts(tool_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract facts from system.clipboard.* tools"""
    facts = {"tool": tool_name}
    
    if "read" in tool_name.lower():
        content = result.get("content", "")
        facts.update({
            "clipboard_content": content[:100] if len(content) > 100 else content,
            "content_length": len(content)
        })
    
    elif "write" in tool_name.lower():
        facts["clipboard_written"] = result.get("status") == "success"
    
    return {k: v for k, v in facts.items() if v is not None}


def _extract_generic_facts(result: Dict[str, Any]) -> Dict[str, Any]:
    """Generic extraction for unknown tools - extract all scalar values"""
    facts = {}
    
    for key, value in result.items():
        # Skip internal keys
        if key.startswith('_'):
            continue
        
        # Only include scalar values
        if isinstance(value, (str, int, float, bool)):
            facts[key] = value
    
    return facts


def _extract_memory_facts(tool_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract facts from memory.* tools (Phase 3A)"""
    facts = {"tool": tool_name}
    
    if "get_recent_facts" in tool_name:
        recalled = result.get("facts", [])
        facts.update({
            "recalled_facts": recalled,
            "recall_count": result.get("count", 0),
            "time_range_minutes": result.get("time_range_minutes", 60)
        })
    
    return {k: v for k, v in facts.items() if v is not None}


def _generate_summary(tool_name: str, facts: Dict[str, Any], status: str) -> str:
    """Generate one-line summary from tool name and status."""
    action = tool_name.split('.')[-1].replace('_', ' ')
    
    if status == "success":
        return f"Completed {action}"
    elif status == "refused":
        return f"Refused {action} - confirmation required"
    elif status == "unsupported":
        return f"Unsupported: {action}"
    elif status == "blocked":
        return f"Blocked: {action}"
    else:
        return f"Failed {action}"
