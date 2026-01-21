"""Tool Index - Manages Qdrant indexing of tools

This module synchronizes the tool registry with Qdrant.
Indexing happens at startup; runtime is read-only.

Strategy:
- Startup: sync_index() aligns Qdrant with registry
- New tools: Automatically indexed on next startup
- Removed tools: Automatically removed on next startup
- Hot-reload: NOT supported (restart required)

ID Strategy:
- Tool names are converted to deterministic UUIDs via uuid5
- Original tool name is stored in payload for recovery
- Same tool name ALWAYS produces same UUID (idempotent)
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass

from .qdrant_client import get_qdrant_client
from .embedding_service import embed, get_dimension, is_available as embedding_available
from .canonical_text import generate_canonical_text
from .id_mapping import tool_name_to_uuid, uuid_to_tool_name


@dataclass
class SyncResult:
    """Result of sync operation"""
    success: bool
    indexed: int       # New tools indexed
    removed: int       # Stale tools removed
    skipped: int       # Tools that failed to index
    total: int         # Total tools in registry
    error: Optional[str] = None
    
    def __str__(self) -> str:
        if self.success:
            return f"Sync complete: indexed={self.indexed}, removed={self.removed}, total={self.total}"
        return f"Sync failed: {self.error}"


def sync_index() -> SyncResult:
    """
    Synchronize Qdrant index with tool registry.
    
    This is IDEMPOTENT:
    - Inserts new tools
    - Removes stale tools
    - Does not re-embed unchanged tools
    
    Run at startup after tools are loaded.
    
    Returns:
        SyncResult with counts
    """
    # Check embedding service availability
    if not embedding_available():
        logging.warning("Embedding service not available - skipping Qdrant sync")
        return SyncResult(
            success=False,
            indexed=0,
            removed=0,
            skipped=0,
            total=0,
            error="Embedding service not available"
        )
    
    # Get Qdrant client
    client = get_qdrant_client()
    
    # Ensure collection exists
    if not client.ensure_collection(dimension=get_dimension()):
        logging.warning("Failed to ensure Qdrant collection - skipping sync")
        return SyncResult(
            success=False,
            indexed=0,
            removed=0,
            skipped=0,
            total=0,
            error="Qdrant collection setup failed"
        )
    
    # Get tools from registry
    from tools.registry import get_registry
    registry = get_registry()
    registry_tools = registry.list_all()
    registry_names = set(registry_tools.keys())
    
    # Get existing IDs from Qdrant (these are UUIDs)
    # We need to get payloads to map back to tool names
    indexed_tool_names = _get_indexed_tool_names(client)
    
    # Calculate diff using tool names
    to_index = registry_names - indexed_tool_names
    to_remove = indexed_tool_names - registry_names
    
    logging.info(f"Qdrant sync: {len(to_index)} to index, {len(to_remove)} to remove")
    
    indexed = 0
    skipped = 0
    
    # Index new tools
    for tool_name in to_index:
        tool = registry.get(tool_name)
        if tool is None:
            skipped += 1
            continue
        
        if index_tool(tool):
            indexed += 1
        else:
            skipped += 1
    
    # Remove stale tools (convert names to UUIDs for deletion)
    removed = 0
    if to_remove:
        uuids_to_remove = [tool_name_to_uuid(name) for name in to_remove]
        if client.delete(uuids_to_remove):
            removed = len(to_remove)
            logging.info(f"Removed {removed} stale tools from Qdrant")
    
    # Verification (soft check - warning only)
    final_count = client.count()
    expected_count = len(registry_tools)
    if final_count != expected_count:
        logging.warning(
            f"Qdrant count mismatch: expected {expected_count}, got {final_count}. "
            f"May indicate partial failure or concurrent modification."
        )
    
    return SyncResult(
        success=True,
        indexed=indexed,
        removed=removed,
        skipped=skipped,
        total=len(registry_tools)
    )


def _get_indexed_tool_names(client) -> Set[str]:
    """
    Get all tool names currently indexed in Qdrant.
    
    Since Qdrant stores UUIDs as point IDs, we must read
    the 'name' field from each point's payload.
    
    Args:
        client: QdrantClient instance
        
    Returns:
        Set of tool names (not UUIDs)
    """
    tool_names = set()
    
    try:
        # Scroll through all points with payload
        offset = None
        
        while True:
            result = client._client.scroll(
                collection_name=client._collection,
                limit=100,
                offset=offset,
                with_payload=True,  # Need payload to get name
                with_vectors=False
            )
            
            points, offset = result
            if not points:
                break
            
            for point in points:
                payload = point.payload or {}
                if "name" in payload:
                    tool_names.add(payload["name"])
                else:
                    logging.warning(f"Point {point.id} missing 'name' in payload")
            
            if offset is None:
                break
        
        return tool_names
        
    except Exception as e:
        logging.warning(f"Failed to get indexed tool names: {e}")
        return set()


def index_tool(tool) -> bool:
    """
    Index a single tool to Qdrant.
    
    Args:
        tool: Tool instance
        
    Returns:
        True if successful
    """
    try:
        # Generate canonical text
        canonical = generate_canonical_text(tool)
        
        # Embed
        vector = embed(canonical)
        
        # Build payload (metadata only - NO safety info)
        # CRITICAL: 'name' field is required for UUID→name recovery
        payload = {
            "name": tool.name,  # REQUIRED for search result mapping
            "description": tool.description,
            "indexed_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Generate deterministic UUID from tool name
        point_id = tool_name_to_uuid(tool.name)
        
        # Upsert to Qdrant
        client = get_qdrant_client()
        success = client.upsert([{
            "id": point_id,  # UUID, not string name
            "vector": vector,
            "payload": payload
        }])
        
        if success:
            logging.debug(f"Indexed tool: {tool.name}")
        return success
        
    except Exception as e:
        logging.warning(f"Failed to index tool '{tool.name}': {e}")
        return False


def remove_tool(tool_name: str) -> bool:
    """
    Remove a tool from Qdrant index.
    
    Args:
        tool_name: Tool name to remove
        
    Returns:
        True if successful
    """
    client = get_qdrant_client()
    point_id = tool_name_to_uuid(tool_name)
    return client.delete([point_id])


def get_index_stats() -> Dict[str, Any]:
    """
    Get indexing statistics.
    
    Returns:
        Dict with index stats
    """
    client = get_qdrant_client()
    health = client.health_check()
    
    if not health.get("connected"):
        return {
            "status": "disconnected",
            "error": health.get("error")
        }
    
    from tools.registry import get_registry
    registry = get_registry()
    registry_count = len(registry.list_all())
    
    indexed_ids = client.get_all_ids()
    
    return {
        "status": "connected",
        "indexed_count": len(indexed_ids),
        "registry_count": registry_count,
        "in_sync": len(indexed_ids) == registry_count,
        "missing": registry_count - len(indexed_ids),
        "stale": len(indexed_ids) - registry_count if len(indexed_ids) > registry_count else 0
    }


def force_reindex() -> SyncResult:
    """
    Force complete reindex of all tools.
    
    Use when:
    - Canonical text format changed
    - Embedding model changed
    - Corruption suspected
    
    Returns:
        SyncResult with counts
    """
    logging.info("Starting forced reindex...")
    
    # Get client
    client = get_qdrant_client()
    
    # Delete all existing points
    existing_ids = client.get_all_ids()
    if existing_ids:
        client.delete(list(existing_ids))
        logging.info(f"Cleared {len(existing_ids)} existing points")
    
    # Reindex all tools
    from tools.registry import get_registry
    registry = get_registry()
    registry_tools = registry.list_all()
    
    indexed = 0
    skipped = 0
    
    for tool_name in registry_tools:
        tool = registry.get(tool_name)
        if tool is None:
            skipped += 1
            continue
        
        if index_tool(tool):
            indexed += 1
        else:
            skipped += 1
    
    return SyncResult(
        success=True,
        indexed=indexed,
        removed=len(existing_ids),
        skipped=skipped,
        total=len(registry_tools)
    )
