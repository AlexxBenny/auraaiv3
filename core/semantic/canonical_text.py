"""Canonical Text Generation - Generates embeddable text for tools

This module creates the canonical text representation for each tool.
The format is LOCKED - changing it requires a FULL REINDEX.

What IS embedded:
- Tool name
- Category (derived from name)
- Capability with synonym expansion
- Description
- Example phrases

What is NOT embedded (Neo4j authority only):
- Risk levels
- Constraints
- ENABLES relationships
- Safety metadata
"""

import logging
from typing import List, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from tools.base import Tool


# ===========================================================================
# CAPABILITY ALIASES - LOCKED (changes require full reindex)
# ===========================================================================
# These synonyms improve semantic recall for natural language queries.
# For example, "press the button" matches "click" due to alias expansion.
# ===========================================================================

CAPABILITY_ALIASES: Dict[str, List[str]] = {
    # Input actions
    "click": ["click", "press", "tap", "select", "hit"],
    "type": ["type", "enter", "input", "write", "key", "text"],
    "move": ["move", "drag", "position", "relocate", "cursor"],
    "scroll": ["scroll", "wheel", "pan", "swipe"],
    
    # Display actions
    "screenshot": ["screenshot", "capture", "snap", "grab", "screen"],
    "brightness": ["brightness", "dim", "brighten", "screen", "display"],
    
    # Application actions
    "open": ["open", "launch", "start", "run", "execute"],
    "close": ["close", "exit", "quit", "terminate", "stop"],
    "focus": ["focus", "activate", "switch", "foreground"],
    "minimize": ["minimize", "hide", "collapse"],
    "maximize": ["maximize", "expand", "fullscreen"],
    
    # System actions
    "volume": ["volume", "sound", "audio", "mute", "unmute"],
    "shutdown": ["shutdown", "power", "restart", "reboot"],
    "sleep": ["sleep", "hibernate", "suspend"],
    
    # File actions
    "read": ["read", "get", "fetch", "load", "open"],
    "write": ["write", "save", "store", "create"],
    "delete": ["delete", "remove", "erase", "trash"],
    "copy": ["copy", "duplicate", "clone"],
}


def get_capability_synonyms(capability: str) -> List[str]:
    """
    Get synonyms for a capability verb.
    
    Args:
        capability: Base capability (e.g., "click")
        
    Returns:
        List of synonyms including the original
    """
    capability_lower = capability.lower()
    
    # Check if capability matches any alias group
    for base, aliases in CAPABILITY_ALIASES.items():
        if capability_lower == base or capability_lower in aliases:
            return aliases
    
    # No synonyms found - return original only
    return [capability_lower]


def derive_category(tool_name: str) -> str:
    """
    Derive category from tool name.
    
    Example:
        "system.input.mouse.click" → "input"
        "system.display.screenshot" → "display"
        "apps.browser.open" → "browser"
    
    Args:
        tool_name: Fully qualified tool name
        
    Returns:
        Category string
    """
    parts = tool_name.split(".")
    if len(parts) >= 2:
        # Use second part as category (after "system" or "apps")
        return parts[1]
    return "general"


def derive_capability(tool_name: str) -> str:
    """
    Derive capability from tool name (last component).
    
    Example:
        "system.input.mouse.click" → "click"
        "system.display.take_screenshot" → "take_screenshot"
    
    Args:
        tool_name: Fully qualified tool name
        
    Returns:
        Capability string
    """
    parts = tool_name.split(".")
    if parts:
        return parts[-1]
    return tool_name


def generate_example_phrases(tool: "Tool") -> str:
    """
    Generate example usage phrases for a tool.
    
    This is a simple implementation that can be enhanced
    with per-tool examples if needed.
    
    Args:
        tool: Tool instance
        
    Returns:
        Newline-separated example phrases
    """
    capability = derive_capability(tool.name)
    synonyms = get_capability_synonyms(capability)
    
    # Generate basic examples from synonyms
    examples = []
    for syn in synonyms[:3]:  # Limit to 3 examples
        examples.append(f"{syn} action")
    
    return "\n- ".join(examples)


def generate_canonical_text(tool: "Tool") -> str:
    """
    Generate the canonical text used for embedding.
    
    LOCKED FORMAT - Do NOT modify without full reindex.
    
    This text is designed to:
    1. Include the exact tool name for precise matching
    2. Include category for context
    3. Expand capability with synonyms for recall
    4. Include description for semantic understanding
    5. Include examples for natural language matching
    
    Args:
        tool: Tool instance
        
    Returns:
        Canonical text string for embedding
    """
    # Extract components
    category = derive_category(tool.name)
    capability = derive_capability(tool.name)
    synonyms = get_capability_synonyms(capability)
    capability_text = ", ".join(synonyms)
    
    # Generate examples
    examples = generate_example_phrases(tool)
    
    # Build canonical text
    # Format is intentionally verbose for better semantic matching
    canonical = f"""Tool name: {tool.name}
Category: {category}
Capability: {capability_text}
Description: {tool.description}
Examples:
- {examples}"""
    
    logging.debug(f"Generated canonical text for '{tool.name}' ({len(canonical)} chars)")
    return canonical
