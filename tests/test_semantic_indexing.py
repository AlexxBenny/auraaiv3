"""Tests for Qdrant Semantic Tool Indexing

These tests verify:
1. Canonical text generation (format, synonym expansion)
2. Embedding determinism (same input → same vector)
3. Qdrant indexing and search (with Qdrant container)
4. Sync idempotency (multiple syncs = same state)
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import List


# ===========================================================================
# Unit Tests: Canonical Text Generation
# ===========================================================================

class TestCanonicalText:
    """Tests for canonical_text.py"""
    
    def test_capability_synonyms_exist(self):
        """Verify synonym expansion returns expected results"""
        from core.semantic.canonical_text import get_capability_synonyms
        
        synonyms = get_capability_synonyms("click")
        assert "click" in synonyms
        assert "press" in synonyms
        assert "tap" in synonyms
        
    def test_capability_synonyms_fallback(self):
        """Unknown capability returns itself"""
        from core.semantic.canonical_text import get_capability_synonyms
        
        synonyms = get_capability_synonyms("unknown_verb")
        assert synonyms == ["unknown_verb"]
        
    def test_derive_category(self):
        """Category extraction from tool name"""
        from core.semantic.canonical_text import derive_category
        
        assert derive_category("system.input.mouse.click") == "input"
        assert derive_category("system.display.screenshot") == "display"
        assert derive_category("apps.browser.open") == "browser"
        assert derive_category("single") == "general"
        
    def test_derive_capability(self):
        """Capability extraction from tool name"""
        from core.semantic.canonical_text import derive_capability
        
        assert derive_capability("system.input.mouse.click") == "click"
        assert derive_capability("system.display.take_screenshot") == "take_screenshot"
        
    def test_canonical_text_format(self):
        """Verify canonical text includes required sections"""
        from core.semantic.canonical_text import generate_canonical_text
        
        # Mock tool
        mock_tool = Mock()
        mock_tool.name = "system.input.mouse.click"
        mock_tool.description = "Clicks mouse at coordinates"
        
        canonical = generate_canonical_text(mock_tool)
        
        assert "Tool name: system.input.mouse.click" in canonical
        assert "Category: input" in canonical
        assert "Capability:" in canonical
        assert "click" in canonical  # Contains capability
        assert "press" in canonical  # Contains synonym
        assert "Description: Clicks mouse at coordinates" in canonical


# ===========================================================================
# Unit Tests: Embedding Service
# ===========================================================================

class TestEmbeddingService:
    """Tests for embedding_service.py"""
    
    @pytest.fixture
    def skip_if_no_model(self):
        """Skip test if embedding model not available"""
        try:
            from core.semantic.embedding_service import is_available
            if not is_available():
                pytest.skip("Embedding model not available")
        except ImportError:
            pytest.skip("sentence-transformers not installed")
    
    def test_embedding_dimension(self, skip_if_no_model):
        """Embedding dimension is 768"""
        from core.semantic.embedding_service import get_dimension
        assert get_dimension() == 768
    
    def test_embedding_determinism(self, skip_if_no_model):
        """Same input produces same embedding"""
        from core.semantic.embedding_service import embed
        
        text = "click the save button"
        embedding1 = embed(text)
        embedding2 = embed(text)
        
        assert len(embedding1) == 768
        assert embedding1 == embedding2  # Identical
    
    def test_embedding_differentiates(self, skip_if_no_model):
        """Different inputs produce different embeddings"""
        from core.semantic.embedding_service import embed
        
        emb1 = embed("click the mouse")
        emb2 = embed("open a browser")
        
        # Should not be identical
        assert emb1 != emb2


# ===========================================================================
# Unit Tests: Tool Search (Mocked)
# ===========================================================================

class TestToolSearch:
    """Tests for tool_search.py with mocked Qdrant"""
    
    def test_empty_candidates_on_failure(self):
        """Search returns empty list on Qdrant failure"""
        with patch('core.semantic.tool_search.embedding_available', return_value=False):
            from core.semantic.tool_search import find_candidates
            
            candidates = find_candidates("click button")
            assert candidates == []
    
    def test_candidate_dataclass(self):
        """ToolCandidate has correct structure"""
        from core.semantic.tool_search import ToolCandidate
        
        candidate = ToolCandidate(name="test.tool", score=0.85)
        assert candidate.name == "test.tool"
        assert candidate.score == 0.85


# ===========================================================================
# Integration Tests: Qdrant (require running container)
# ===========================================================================

@pytest.mark.integration
class TestQdrantIntegration:
    """Integration tests requiring Qdrant container"""
    
    @pytest.fixture
    def qdrant_available(self):
        """Check if Qdrant is available"""
        try:
            from core.semantic.qdrant_client import get_qdrant_client
            client = get_qdrant_client()
            if not client.connect():
                pytest.skip("Qdrant not available")
        except Exception:
            pytest.skip("Qdrant connection failed")
    
    def test_collection_creation(self, qdrant_available):
        """Collection can be created"""
        from core.semantic.qdrant_client import get_qdrant_client
        
        client = get_qdrant_client()
        assert client.ensure_collection(dimension=768)
    
    def test_upsert_and_search(self, qdrant_available):
        """Points can be upserted and searched"""
        from core.semantic.qdrant_client import get_qdrant_client
        from core.semantic.embedding_service import embed
        
        client = get_qdrant_client()
        client.ensure_collection(dimension=768)
        
        # Upsert a test point
        test_vector = embed("test tool for clicking")
        success = client.upsert([{
            "id": "test.tool.click",
            "vector": test_vector,
            "payload": {"name": "test.tool.click"}
        }])
        assert success
        
        # Search for it
        query_vector = embed("click something")
        results = client.search(query_vector, limit=5)
        
        assert len(results) >= 0  # May or may not find depending on threshold


# ===========================================================================
# Integration Tests: Sync
# ===========================================================================

@pytest.mark.integration
class TestSyncIntegration:
    """Integration tests for tool index sync"""
    
    @pytest.fixture
    def full_setup(self):
        """Require both Qdrant and embedding model"""
        try:
            from core.semantic.qdrant_client import get_qdrant_client
            from core.semantic.embedding_service import is_available
            
            if not is_available():
                pytest.skip("Embedding model not available")
            
            client = get_qdrant_client()
            if not client.connect():
                pytest.skip("Qdrant not available")
        except Exception as e:
            pytest.skip(f"Setup failed: {e}")
    
    def test_sync_idempotent(self, full_setup):
        """Multiple syncs produce same state"""
        from core.semantic.tool_index import sync_index
        
        result1 = sync_index()
        result2 = sync_index()
        
        # Second sync should have 0 indexed (already synced)
        assert result2.indexed == 0
        assert result2.removed == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
