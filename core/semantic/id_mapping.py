"""Tool ID Mapping - Deterministic UUID generation for Qdrant

Qdrant requires point IDs to be unsigned integers or UUIDs.
This module provides deterministic UUID5 generation from tool names.

Properties:
- DETERMINISTIC: Same tool name always produces same UUID
- STABLE: Works across restarts without state
- REVERSIBLE: Original name stored in payload, recovered during search
- COLLISION-FREE: UUID5 namespace ensures uniqueness

Example:
    "system.input.mouse.click" → UUID5(AURA_NAMESPACE, "system.input.mouse.click")
    → "a1b2c3d4-e5f6-5789-abcd-ef1234567890"
"""

import uuid
from typing import Dict

# Fixed namespace UUID for AURA tools
# This ensures the same tool name always produces the same UUID
# DO NOT CHANGE - changing this invalidates all existing Qdrant data
AURA_TOOL_NAMESPACE = uuid.UUID("f47ac10b-58cc-4372-a567-0e02b2c3d479")


def tool_name_to_uuid(tool_name: str) -> str:
    """
    Generate deterministic UUID from tool name.
    
    Uses UUID5 (SHA-1 based) with fixed namespace.
    Same input ALWAYS produces same output.
    
    Args:
        tool_name: Tool name (e.g., "system.input.mouse.click")
        
    Returns:
        UUID string (e.g., "a1b2c3d4-e5f6-5789-abcd-ef1234567890")
    """
    return str(uuid.uuid5(AURA_TOOL_NAMESPACE, tool_name))


def tool_names_to_uuids(tool_names: list) -> Dict[str, str]:
    """
    Generate UUIDs for multiple tool names.
    
    Args:
        tool_names: List of tool names
        
    Returns:
        Dict mapping tool_name → uuid_string
    """
    return {name: tool_name_to_uuid(name) for name in tool_names}


def uuid_to_tool_name(point_uuid: str, payload: Dict) -> str:
    """
    Recover tool name from Qdrant search result.
    
    Since UUID generation is one-way, we must store the original
    tool name in the payload and recover it from there.
    
    Args:
        point_uuid: The Qdrant point ID (UUID string)
        payload: The point payload (must contain 'name' field)
        
    Returns:
        Original tool name
        
    Raises:
        KeyError: If 'name' not in payload
    """
    if "name" not in payload:
        raise KeyError(f"Payload missing 'name' field for point {point_uuid}")
    return payload["name"]
