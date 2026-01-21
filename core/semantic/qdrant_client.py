"""Qdrant Client - Connection management for semantic tool search

This module is the ONLY interface between AURA and Qdrant.
Qdrant is for semantic recall ONLY - NOT for safety decisions.

Failure Strategy:
- Connection failure at startup: WARN, proceed (system works without semantic search)
- Connection failure at runtime: Return empty results (fall back to all tools)
- Neo4j is NEVER bypassed
"""

import logging
import os
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass

try:
    from qdrant_client import QdrantClient as QdrantSDK
    from qdrant_client.models import (
        Distance,
        VectorParams,
        PointStruct,
        SearchRequest,
    )
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    QdrantSDK = None
    Distance = None
    VectorParams = None
    PointStruct = None
    SearchRequest = None


# Default connection settings (override via environment)
DEFAULT_HOST = os.getenv("QDRANT_HOST", "localhost")
DEFAULT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
DEFAULT_COLLECTION = os.getenv("QDRANT_COLLECTION", "aura_tools")


@dataclass
class SearchResult:
    """Single search result from Qdrant"""
    id: str
    score: float
    payload: Dict[str, Any]


class QdrantConnectionError(Exception):
    """Raised when Qdrant connection fails"""
    pass


class QdrantClient:
    """
    Qdrant client for semantic tool search.
    
    FAIL SOFT: System continues without semantic search if Qdrant unavailable.
    Safety is preserved because Neo4j is always consulted.
    """
    
    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        collection: str = DEFAULT_COLLECTION
    ):
        self._host = host
        self._port = port
        self._collection = collection
        self._client: Optional[QdrantSDK] = None
        self._connected = False
        
        if not QDRANT_AVAILABLE:
            logging.warning("Qdrant client library not installed. Run: pip install qdrant-client")
    
    def connect(self) -> bool:
        """
        Establish connection to Qdrant.
        
        Returns:
            True if connected, False otherwise
        """
        if not QDRANT_AVAILABLE:
            logging.warning("Qdrant library not available")
            return False
        
        try:
            self._client = QdrantSDK(host=self._host, port=self._port)
            # Verify connectivity with a simple operation
            self._client.get_collections()
            self._connected = True
            logging.info(f"Connected to Qdrant at {self._host}:{self._port}")
            return True
        except Exception as e:
            logging.warning(f"Qdrant connection failed (non-fatal): {e}")
            self._connected = False
            return False
    
    def disconnect(self):
        """Close Qdrant connection"""
        if self._client:
            self._client.close()
            self._client = None
            self._connected = False
            logging.info("Disconnected from Qdrant")
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to Qdrant"""
        return self._connected and self._client is not None
    
    def ensure_collection(self, dimension: int = 768, distance: str = "Cosine") -> bool:
        """
        Ensure collection exists with correct configuration.
        
        Args:
            dimension: Vector dimension (768 for all-mpnet-base-v2)
            distance: Distance metric (Cosine, Euclidean, Dot)
            
        Returns:
            True if collection is ready
        """
        if not self._ensure_connected():
            return False
        
        try:
            collections = self._client.get_collections().collections
            collection_names = [c.name for c in collections]
            
            if self._collection not in collection_names:
                # Create collection
                distance_enum = Distance.COSINE if distance == "Cosine" else Distance.EUCLID
                self._client.create_collection(
                    collection_name=self._collection,
                    vectors_config=VectorParams(
                        size=dimension,
                        distance=distance_enum
                    )
                )
                logging.info(f"Created Qdrant collection '{self._collection}' (dim={dimension})")
            else:
                logging.debug(f"Qdrant collection '{self._collection}' already exists")
            
            return True
        except Exception as e:
            logging.warning(f"Failed to ensure collection (non-fatal): {e}")
            return False
    
    def upsert(self, points: List[Dict[str, Any]]) -> bool:
        """
        Upsert points into collection.
        
        Args:
            points: List of dicts with 'id', 'vector', 'payload'
            
        Returns:
            True if successful
        """
        if not self._ensure_connected():
            return False
        
        try:
            point_structs = [
                PointStruct(
                    id=p["id"],
                    vector=p["vector"],
                    payload=p.get("payload", {})
                )
                for p in points
            ]
            
            self._client.upsert(
                collection_name=self._collection,
                points=point_structs
            )
            logging.debug(f"Upserted {len(points)} points to Qdrant")
            return True
        except Exception as e:
            logging.warning(f"Qdrant upsert failed (non-fatal): {e}")
            return False
    
    def search(
        self,
        query_vector: List[float],
        limit: int = 10,
        score_threshold: float = 0.25
    ) -> List[SearchResult]:
        """
        Search for similar vectors.
        
        Args:
            query_vector: Query embedding
            limit: Maximum results
            score_threshold: Minimum score (0-1 for cosine)
            
        Returns:
            List of SearchResult (empty on failure)
        """
        if not self._ensure_connected():
            return []
        
        try:
            # Use query_points (modern API) instead of deprecated search()
            from qdrant_client.models import models
            
            response = self._client.query_points(
                collection_name=self._collection,
                query=query_vector,
                limit=limit,
                score_threshold=score_threshold,
                with_payload=True
            )
            
            # Extract points from response
            points = response.points if hasattr(response, 'points') else []
            
            return [
                SearchResult(
                    id=str(p.id),
                    score=p.score,
                    payload=p.payload or {}
                )
                for p in points
            ]
        except Exception as e:
            logging.warning(f"Qdrant search failed (non-fatal): {e}")
            return []
    
    def delete(self, ids: List[str]) -> bool:
        """
        Delete points by ID.
        
        Args:
            ids: List of point IDs to delete
            
        Returns:
            True if successful
        """
        if not self._ensure_connected():
            return False
        
        try:
            from qdrant_client.models import PointIdsList
            self._client.delete(
                collection_name=self._collection,
                points_selector=PointIdsList(points=ids)
            )
            logging.debug(f"Deleted {len(ids)} points from Qdrant")
            return True
        except Exception as e:
            logging.warning(f"Qdrant delete failed (non-fatal): {e}")
            return False
    
    def get_all_ids(self) -> Set[str]:
        """
        Get all point IDs in collection.
        
        Returns:
            Set of point IDs (empty on failure)
        """
        if not self._ensure_connected():
            return set()
        
        try:
            # Scroll through all points
            all_ids = set()
            offset = None
            
            while True:
                result = self._client.scroll(
                    collection_name=self._collection,
                    limit=100,
                    offset=offset,
                    with_payload=False,
                    with_vectors=False
                )
                
                points, offset = result
                if not points:
                    break
                
                for point in points:
                    all_ids.add(str(point.id))
                
                if offset is None:
                    break
            
            return all_ids
        except Exception as e:
            logging.warning(f"Failed to get Qdrant IDs (non-fatal): {e}")
            return set()
    
    def count(self) -> int:
        """
        Get point count in collection.
        
        Returns:
            Point count (0 on failure)
        """
        if not self._ensure_connected():
            return 0
        
        try:
            info = self._client.get_collection(self._collection)
            return info.points_count
        except Exception as e:
            logging.warning(f"Failed to get Qdrant count (non-fatal): {e}")
            return 0
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check Qdrant health.
        
        Returns:
            Dict with connected status and collection info
        """
        if not self._ensure_connected():
            return {"connected": False, "error": "Not connected"}
        
        try:
            info = self._client.get_collection(self._collection)
            return {
                "connected": True,
                "collection": self._collection,
                "points_count": info.points_count,
                "status": info.status
            }
        except Exception as e:
            return {"connected": False, "error": str(e)}
    
    def _ensure_connected(self) -> bool:
        """Ensure connection is established"""
        if self.is_connected:
            return True
        return self.connect()


# Singleton instance
_client: Optional[QdrantClient] = None


def get_qdrant_client() -> QdrantClient:
    """
    Get the singleton Qdrant client.
    
    Returns:
        QdrantClient instance
    """
    global _client
    if _client is None:
        _client = QdrantClient()
    return _client
