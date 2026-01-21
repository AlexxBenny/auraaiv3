"""Tool Search - Query interface for semantic tool retrieval

This module provides the search interface used by PlannerAgent.
Qdrant is queried for candidate tools based on semantic similarity.

CRITICAL DISTINCTIONS:
- Candidates are SUGGESTIONS, not commands
- LLM is free to ignore candidates
- Neo4j eligibility check is STILL MANDATORY after LLM
- Qdrant failure = fall back to all tools (safety preserved)
"""

import logging
import os
from typing import List, Optional
from dataclasses import dataclass

from .qdrant_client import get_qdrant_client
from .embedding_service import embed, is_available as embedding_available


# Configurable score threshold (tune empirically)
QDRANT_SCORE_THRESHOLD = float(os.getenv("QDRANT_SCORE_THRESHOLD", "0.25"))


@dataclass
class ToolCandidate:
    """A candidate tool from semantic search"""
    name: str
    score: float
    
    def __repr__(self) -> str:
        return f"ToolCandidate({self.name}, score={self.score:.3f})"


def find_candidates(
    query: str,
    top_k: int = 10,
    score_threshold: Optional[float] = None
) -> List[ToolCandidate]:
    """
    Find candidate tools for a natural language query.
    
    This is the main interface for PlannerAgent.
    
    FAIL SOFT: Returns empty list on any failure.
    Empty list = use all tools (safety preserved via Neo4j).
    
    Args:
        query: Natural language query (user's original utterance)
        top_k: Maximum candidates to return
        score_threshold: Minimum similarity score (default from config)
        
    Returns:
        List of ToolCandidate ordered by relevance (empty on failure)
    """
    if score_threshold is None:
        score_threshold = QDRANT_SCORE_THRESHOLD
    
    # Check embedding availability
    if not embedding_available():
        logging.debug("Embedding service not available - returning empty candidates")
        return []
    
    try:
        # Embed the query (user's original utterance)
        query_vector = embed(query)
        
        # Search Qdrant
        client = get_qdrant_client()
        results = client.search(
            query_vector=query_vector,
            limit=top_k,
            score_threshold=score_threshold
        )
        
        if not results:
            logging.debug(f"No Qdrant candidates for query: '{query[:50]}...'")
            return []
        
        # Log score distribution for tuning
        scores = [r.score for r in results]
        logging.debug(
            f"Qdrant scores: min={min(scores):.3f}, max={max(scores):.3f}, "
            f"mean={sum(scores)/len(scores):.3f}, count={len(scores)}"
        )
        
        # Convert to ToolCandidate
        # CRITICAL: r.id is a UUID, tool name is in r.payload["name"]
        candidates = []
        for r in results:
            tool_name = r.payload.get("name") if r.payload else None
            if tool_name:
                candidates.append(ToolCandidate(name=tool_name, score=r.score))
            else:
                logging.warning(f"Search result {r.id} missing 'name' in payload")
        
        logging.info(f"Qdrant candidates ({len(candidates)}): {[c.name for c in candidates]}")
        return candidates
        
    except Exception as e:
        # FAIL SOFT - log and return empty
        logging.warning(f"Qdrant search failed (non-fatal): {e}")
        return []


def get_candidate_names(
    query: str,
    top_k: int = 10
) -> List[str]:
    """
    Convenience function to get just tool names.
    
    Args:
        query: Natural language query
        top_k: Maximum candidates
        
    Returns:
        List of tool names
    """
    candidates = find_candidates(query, top_k)
    return [c.name for c in candidates]


def search_health() -> dict:
    """
    Check semantic search health.
    
    Returns:
        Dict with status information
    """
    client = get_qdrant_client()
    qdrant_health = client.health_check()
    
    embedding_ok = embedding_available()
    
    return {
        "qdrant": qdrant_health,
        "embedding_available": embedding_ok,
        "operational": qdrant_health.get("connected", False) and embedding_ok,
        "score_threshold": QDRANT_SCORE_THRESHOLD
    }
