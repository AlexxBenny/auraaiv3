"""Planner Rules - Declarative mapping from (domain, verb) to PlannedAction.

ARCHITECTURAL PRINCIPLE:
    Goals are semantic (WHAT)
    Tools are procedural (HOW)
    Planner rules map between them

This table replaces all per-domain planner methods.
No branching, no if/elif chains, just table lookup.

PARAM VALIDATION (Phase 4.1):
    Each rule can specify:
    - required_params: Must be present
    - allowed_values: Constrained enum values (fail-fast if invalid)
    - default_params: Applied if missing
"""

import logging
from typing import Dict, Tuple, Any, List, Optional, Set


# =============================================================================
# PLANNER RULES TABLE
# =============================================================================

PLANNER_RULES: Dict[Tuple[str, str], Dict[str, Any]] = {
    # =========================================================================
    # BROWSER DOMAIN
    # =========================================================================
    ("browser", "navigate"): {
        "intent": "browser_control",
        "action_class": "actuate",
        "description_template": "navigate:{url}",
        "required_params": ["url"],
    },
    ("browser", "search"): {
        "intent": "browser_control",
        "action_class": "actuate",
        "description_template": "search:{platform}:{query}",
        "required_params": ["query"],
        "default_params": {"platform": "google"},
        "allowed_values": {
            "platform": {"google", "youtube", "bing", "duckduckgo", "github"},
        },
    },
    ("browser", "wait"): {
        "intent": "browser_control",
        "action_class": "actuate",
        "description_template": "wait:{selector}:{state}",
        "required_params": ["selector"],
        "default_params": {"state": "visible"},
        "allowed_values": {
            "state": {"attached", "detached", "visible", "hidden"},
        },
    },
    ("browser", "click"): {
        "intent": "browser_control",
        "action_class": "actuate",
        "description_template": "click:{selector}",
        "required_params": ["selector"],
    },
    ("browser", "type"): {
        "intent": "browser_control",
        "action_class": "actuate",
        "description_template": "type:{selector}:{text}",
        "required_params": ["selector", "text"],
    },
    ("browser", "read"): {
        "intent": "browser_control",
        "action_class": "observe",
        "description_template": "read:{target}",
        "required_params": ["target"],
        "allowed_values": {
            "target": {"title", "url", "text"},  # LOCKED - no free-form
        },
    },
    ("browser", "scroll"): {
        "intent": "browser_control",
        "action_class": "actuate",
        "description_template": "scroll:{direction}",
        "required_params": [],
        "default_params": {"direction": "down"},
        "allowed_values": {
            "direction": {"up", "down", "left", "right"},
        },
    },
    ("browser", "select"): {
        "intent": "browser_control",
        "action_class": "actuate",
        "description_template": "select:{selector}:{value}",
        "required_params": ["selector", "value"],
    },
    
    # =========================================================================
    # FILE DOMAIN
    # =========================================================================
    ("file", "create"): {
        "intent": "file_operation",
        "action_class": "actuate",
        "description_template": "create:{object_type}:{name}",
        "required_params": ["object_type", "name"],
        "allowed_values": {
            "object_type": {"file", "folder"},  # LOCKED
        },
    },
    ("file", "delete"): {
        "intent": "file_operation",
        "action_class": "actuate",
        "description_template": "delete:{object_type}:{name}",
        "required_params": ["object_type", "name"],
        "allowed_values": {
            "object_type": {"file", "folder"},
        },
    },
    ("file", "move"): {
        "intent": "file_operation",
        "action_class": "actuate",
        "description_template": "move:{source}:{destination}",
        "required_params": ["source", "destination"],
    },
    ("file", "copy"): {
        "intent": "file_operation",
        "action_class": "actuate",
        "description_template": "copy:{source}:{destination}",
        "required_params": ["source", "destination"],
    },
    ("file", "read"): {
        "intent": "file_operation",
        "action_class": "observe",
        "description_template": "read:{path}",
        "required_params": ["path"],
    },
    ("file", "write"): {
        "intent": "file_operation",
        "action_class": "actuate",
        "description_template": "write:{path}",
        "required_params": ["path"],
    },
    ("file", "rename"): {
        "intent": "file_operation",
        "action_class": "actuate",
        "description_template": "rename:{source}:{target}",
        "required_params": ["source", "target"],
    },
    ("file", "list"): {
        "intent": "file_operation",
        "action_class": "observe",
        "description_template": "list:{path}",
        "required_params": [],
        "default_params": {"path": "."},
    },
    
    # =========================================================================
    # APP DOMAIN
    # =========================================================================
    ("app", "launch"): {
        "intent": "application_launch",
        "action_class": "actuate",
        "description_template": "launch:{app_name}",
        "required_params": ["app_name"],
    },
    ("app", "focus"): {
        "intent": "application_control",
        "action_class": "actuate",
        "description_template": "focus:{app_name}",
        "required_params": ["app_name"],
    },
    ("app", "close"): {
        "intent": "application_control",
        "action_class": "actuate",
        "description_template": "close:{app_name}",
        "required_params": ["app_name"],
    },
    
    # =========================================================================
    # SYSTEM DOMAIN
    # =========================================================================
    ("system", "set"): {
        "intent": "system_control",
        "action_class": "actuate",
        "description_template": "set:{target}:{value}",
        "required_params": ["target", "value"],
        "allowed_values": {
            "target": {"volume", "brightness"},
        },
    },
    ("system", "get"): {
        "intent": "system_query",
        "action_class": "observe",
        "description_template": "get:{target}",
        "required_params": ["target"],
        "allowed_values": {
            "target": {"battery", "time", "screenshot", "wifi", "bluetooth"},
        },
    },
    ("system", "toggle"): {
        "intent": "system_control",
        "action_class": "actuate",
        "description_template": "toggle:{target}",
        "required_params": ["target"],
        "allowed_values": {
            "target": {"mute", "wifi", "bluetooth", "airplane_mode"},
        },
    },
    ("system", "query"): {
        "intent": "system_query",
        "action_class": "observe",
        "description_template": "query:{target}",
        "required_params": ["target"],
    },
    
    # =========================================================================
    # MEDIA DOMAIN
    # =========================================================================
    ("media", "play"): {
        "intent": "system_control",
        "action_class": "actuate",
        "description_template": "media:play",
        "required_params": [],
    },
    ("media", "pause"): {
        "intent": "system_control",
        "action_class": "actuate",
        "description_template": "media:pause",
        "required_params": [],
    },
    ("media", "stop"): {
        "intent": "system_control",
        "action_class": "actuate",
        "description_template": "media:stop",
        "required_params": [],
    },
    ("media", "next"): {
        "intent": "system_control",
        "action_class": "actuate",
        "description_template": "media:next",
        "required_params": [],
    },
    ("media", "previous"): {
        "intent": "system_control",
        "action_class": "actuate",
        "description_template": "media:previous",
        "required_params": [],
    },
    
    # =========================================================================
    # MEMORY DOMAIN
    # =========================================================================
    ("memory", "store"): {
        "intent": "memory_operation",
        "action_class": "actuate",
        "description_template": "store:{key}:{value}",
        "required_params": ["key", "value"],
    },
    ("memory", "recall"): {
        "intent": "memory_operation",
        "action_class": "observe",
        "description_template": "recall:{key}",
        "required_params": [],
    },
}


# =============================================================================
# VALIDATION (FAIL-FAST)
# =============================================================================

class ParamValidationError(Exception):
    """Raised when params fail validation. Fail-fast, semantic error."""
    pass


def validate_params(
    domain: str, 
    verb: str, 
    params: Dict[str, Any],
    rule: Dict[str, Any]
) -> Dict[str, Any]:
    """Validate params against rule schema. Fail-fast on errors.
    
    Returns merged params with defaults applied.
    Raises ParamValidationError if validation fails.
    """
    # Apply defaults first
    merged = {**rule.get("default_params", {}), **params}
    
    # Check required params
    required = rule.get("required_params", [])
    missing = [p for p in required if p not in merged or merged[p] is None]
    if missing:
        raise ParamValidationError(
            f"({domain}, {verb}): Missing required params: {missing}"
        )
    
    # Check allowed values (CRITICAL for semantic constraints)
    allowed = rule.get("allowed_values", {})
    for param_name, allowed_set in allowed.items():
        if param_name in merged:
            value = merged[param_name]
            if value not in allowed_set:
                raise ParamValidationError(
                    f"({domain}, {verb}): Invalid value '{value}' for '{param_name}'. "
                    f"Allowed: {sorted(allowed_set)}"
                )
    
    logging.debug(
        f"PLANNER_RULES: Validated ({domain}, {verb}) params={merged}"
    )
    
    return merged


def get_planner_rule(domain: str, verb: str) -> Dict[str, Any] | None:
    """Get planner rule for (domain, verb) pair."""
    rule = PLANNER_RULES.get((domain, verb))
    if rule:
        logging.debug(f"PLANNER_RULES: Found rule for ({domain}, {verb})")
    else:
        logging.warning(f"PLANNER_RULES: No rule for ({domain}, {verb})")
    return rule


def format_description(rule: Dict[str, Any], params: Dict[str, Any]) -> str:
    """Format description template with params."""
    template = rule["description_template"]
    # Merge default params with actual params
    merged = {**rule.get("default_params", {}), **params}
    try:
        result = template.format(**merged)
        logging.debug(f"PLANNER_RULES: Formatted description: {result}")
        return result
    except KeyError as e:
        logging.error(f"PLANNER_RULES: Missing param for template: {e}")
        return template
