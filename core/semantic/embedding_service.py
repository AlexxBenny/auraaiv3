"""Embedding Service - Deterministic text embedding using locked model

This module loads and caches the embedding model.
The model is LOCKED to ensure consistent embeddings across index/query.

Model: sentence-transformers/all-mpnet-base-v2
Dimension: 768
Distance: Cosine

CRITICAL: Changing the model requires a FULL REINDEX.
"""

import logging
import os
from typing import List, Optional
from functools import lru_cache

# Model configuration (LOCKED - do NOT change without full reindex)
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/all-mpnet-base-v2"
)
EMBEDDING_DIMENSION = 768

# Module-level model cache
_model = None
_model_load_attempted = False


def _load_model():
    """
    Load the embedding model.
    
    FAIL FATAL: If model cannot load, raise exception.
    This is intentional - inconsistent embeddings break the system.
    """
    global _model, _model_load_attempted
    
    if _model_load_attempted:
        return _model
    
    _model_load_attempted = True
    
    try:
        from sentence_transformers import SentenceTransformer
        
        logging.info(f"Loading embedding model: {EMBEDDING_MODEL}")
        _model = SentenceTransformer(EMBEDDING_MODEL)
        
        # Verify dimension
        test_embedding = _model.encode("test", convert_to_numpy=True)
        actual_dimension = len(test_embedding)
        
        if actual_dimension != EMBEDDING_DIMENSION:
            raise ValueError(
                f"Model dimension mismatch: expected {EMBEDDING_DIMENSION}, "
                f"got {actual_dimension}. Configuration error."
            )
        
        logging.info(f"Embedding model loaded (dimension={actual_dimension})")
        return _model
        
    except ImportError:
        logging.error("sentence-transformers not installed. Run: pip install sentence-transformers")
        raise RuntimeError("Embedding model not available - install sentence-transformers")
    except Exception as e:
        logging.error(f"Failed to load embedding model: {e}")
        raise RuntimeError(f"Embedding model load failed: {e}")


def get_model():
    """
    Get the cached embedding model.
    
    Returns:
        SentenceTransformer model
        
    Raises:
        RuntimeError: If model cannot be loaded
    """
    if _model is None:
        return _load_model()
    return _model


def embed(text: str) -> List[float]:
    """
    Embed text using the locked model.
    
    DETERMINISTIC: Same input always produces same output
    (under fixed model weights).
    
    Args:
        text: Text to embed
        
    Returns:
        768-dimensional embedding as list of floats
        
    Raises:
        RuntimeError: If model not available
    """
    model = get_model()
    if model is None:
        raise RuntimeError("Embedding model not available")
    
    # Encode to numpy array
    embedding = model.encode(text, convert_to_numpy=True)
    
    # Convert to list for JSON serialization and Qdrant
    return embedding.tolist()


def embed_batch(texts: List[str]) -> List[List[float]]:
    """
    Embed multiple texts efficiently.
    
    Args:
        texts: List of texts to embed
        
    Returns:
        List of embeddings
        
    Raises:
        RuntimeError: If model not available
    """
    model = get_model()
    if model is None:
        raise RuntimeError("Embedding model not available")
    
    embeddings = model.encode(texts, convert_to_numpy=True)
    return [e.tolist() for e in embeddings]


def get_dimension() -> int:
    """
    Get the embedding dimension.
    
    Returns:
        768 (locked for all-mpnet-base-v2)
    """
    return EMBEDDING_DIMENSION


def is_available() -> bool:
    """
    Check if embedding service is available.
    
    Returns:
        True if model loaded successfully
    """
    try:
        get_model()
        return True
    except RuntimeError:
        return False
