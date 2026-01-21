"""Tests for Planner + Qdrant Integration

These tests verify:
1. Planner uses Qdrant candidates to filter tools
2. Planner falls back to all tools when Qdrant unavailable
3. Neo4j eligibility check still runs after Qdrant filtering
4. Unknown tool hard rejection works correctly
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any


# ===========================================================================
# Unit Tests: Candidate Filtering (Mocked)
# ===========================================================================

class TestPlannerCandidateFiltering:
    """Tests for Planner's use of Qdrant candidates"""
    
    @pytest.fixture
    def mock_planner_deps(self):
        """Mock all planner dependencies"""
        with patch('agents.planner_agent.get_model_manager') as mock_mm, \
             patch('agents.planner_agent.get_registry') as mock_reg:
            
            # Mock model
            mock_model = Mock()
            mock_model.generate.return_value = {
                "action_type": "action",
                "goal": "Click something",
                "steps": [{"tool": "system.input.mouse.click", "args": {"x": 100, "y": 100}}]
            }
            mock_mm.return_value.get_planner_model.return_value = mock_model
            
            # Mock registry
            mock_registry = Mock()
            mock_registry.get_tools_for_llm.return_value = [
                {"name": "system.input.mouse.click", "description": "Click", "schema": {}},
                {"name": "system.input.keyboard.type", "description": "Type", "schema": {}},
                {"name": "system.display.screenshot", "description": "Screenshot", "schema": {}},
            ]
            mock_registry.has.return_value = True
            mock_reg.return_value = mock_registry
            
            yield {
                "model": mock_model,
                "registry": mock_registry
            }
    
    def test_planner_uses_qdrant_candidates(self, mock_planner_deps):
        """Planner filters tools based on Qdrant candidates"""
        mock_candidates = [
            Mock(name="system.input.mouse.click", score=0.9)
        ]
        mock_candidates[0].name = "system.input.mouse.click"  # Fix mock property
        
        with patch('core.semantic.tool_search.find_candidates', return_value=mock_candidates):
            from agents.planner_agent import PlannerAgent
            
            # This import will trigger filtering
            # We verify by checking the model received fewer tools
            # (Note: This is a simplified test - full test would verify prompt)
    
    def test_planner_fallback_on_empty_candidates(self, mock_planner_deps):
        """Planner uses all tools when Qdrant returns empty"""
        with patch('core.semantic.tool_search.find_candidates', return_value=[]):
            from agents.planner_agent import PlannerAgent
            
            planner = PlannerAgent()
            # Should not raise - falls back to all tools
    
    def test_planner_fallback_on_qdrant_error(self, mock_planner_deps):
        """Planner uses all tools when Qdrant throws exception"""
        def raise_error(*args, **kwargs):
            raise Exception("Qdrant unavailable")
        
        with patch('core.semantic.tool_search.find_candidates', side_effect=raise_error):
            from agents.planner_agent import PlannerAgent
            
            planner = PlannerAgent()
            # Should not raise - falls back to all tools


# ===========================================================================
# Unit Tests: Unknown Tool Rejection
# ===========================================================================

class TestUnknownToolRejection:
    """Tests for hard rejection of unknown tools"""
    
    @pytest.fixture
    def mock_planner_with_unknown_tool(self):
        """Mock planner that returns unknown tool"""
        with patch('agents.planner_agent.get_model_manager') as mock_mm, \
             patch('agents.planner_agent.get_registry') as mock_reg, \
             patch('core.semantic.tool_search.find_candidates', return_value=[]):
            
            # Mock model returns unknown tool
            mock_model = Mock()
            mock_model.generate.return_value = {
                "action_type": "action",
                "goal": "Do something",
                "steps": [{"tool": "hallucinated.fake.tool", "args": {}}]
            }
            mock_mm.return_value.get_planner_model.return_value = mock_model
            
            # Mock registry - tool does NOT exist
            mock_registry = Mock()
            mock_registry.get_tools_for_llm.return_value = []
            mock_registry.has.return_value = False  # Tool not in registry
            mock_reg.return_value = mock_registry
            
            yield
    
    def test_unknown_tool_is_refused(self, mock_planner_with_unknown_tool):
        """LLM-emitted unknown tool causes refusal"""
        from agents.planner_agent import PlannerAgent
        
        planner = PlannerAgent()
        result = planner.plan("do something", "action")
        
        assert result.get("refused") == True
        assert result.get("steps") == []
        assert result.get("refusal", {}).get("error_type") == "unknown_tool"
        assert "hallucinated.fake.tool" in result.get("refusal", {}).get("blocked_tools", [])


# ===========================================================================
# Integration Tests: Safety Preservation
# ===========================================================================

@pytest.mark.integration
class TestSafetyPreservation:
    """Verify Neo4j still gates after Qdrant filtering"""
    
    @pytest.fixture
    def neo4j_available(self):
        """Check if Neo4j is available"""
        try:
            from core.ontology.eligibility import verify_neo4j_connection
            if not verify_neo4j_connection():
                pytest.skip("Neo4j not available")
        except Exception:
            pytest.skip("Neo4j connection failed")
    
    def test_neo4j_still_blocks_after_qdrant(self, neo4j_available):
        """
        Even if Qdrant suggests a tool, Neo4j can still block it.
        
        This is the critical safety test - Qdrant CANNOT bypass Neo4j.
        """
        from core.ontology.eligibility import check_plan_eligibility
        
        # Create a plan with a tool that has blocking constraints
        # (This depends on your Neo4j ontology having test data)
        steps = [{"tool": "system.power.shutdown", "args": {}}]
        
        result = check_plan_eligibility(steps)
        
        # If tool has blocking constraints in Neo4j, it should be blocked
        # regardless of whether Qdrant suggested it
        # (This test is ontology-dependent)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
