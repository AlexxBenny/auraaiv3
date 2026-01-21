"""Semantic tool search via Qdrant

This module provides semantic search capabilities for tool retrieval.
Qdrant is used for semantic recall ONLY - NOT for safety decisions.

Authority:
- Qdrant: Suggests candidate tools based on semantic similarity
- Neo4j: SOLE authority for eligibility and safety (NEVER bypassed)
"""

from .tool_search import find_candidates, ToolCandidate
from .tool_index import sync_index, get_index_stats
from .id_mapping import tool_name_to_uuid

__all__ = [
    "find_candidates",
    "ToolCandidate",
    "sync_index",
    "get_index_stats",
    "tool_name_to_uuid",
]
