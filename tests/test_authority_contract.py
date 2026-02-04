"""Test QC-LLM Authority Contract Enforcement.

INVARIANT: When QC confidence >= 0.85, GI MUST respect topology:
- QC says "single" → GI must return exactly 1 goal
- QC says "multi" → GI must return ≥ 2 goals
"""

import pytest
from unittest.mock import MagicMock, patch
from agents.goal_interpreter import GoalInterpreter, TopologyViolationError


class TestAuthorityContractEnforcement:
    """Test that _enforce_topology correctly raises on violations."""
    
    @pytest.fixture
    def interpreter(self):
        """Create interpreter with mocked model."""
        with patch('agents.goal_interpreter.get_model_manager') as mock_mm:
            mock_model = MagicMock()
            mock_mm.return_value.get_planner_model.return_value = mock_model
            return GoalInterpreter()
    
    def test_high_confidence_single_with_multiple_goals_raises(self, interpreter):
        """QC=single (high conf) + LLM returns 2 goals → TopologyViolationError."""
        qc_output = {
            "classification": "single",
            "confidence": 0.95,
            "reasoning": "Syntactic pattern"
        }
        goals = [
            {"goal_type": "app_launch", "target": "chrome"},
            {"goal_type": "app_launch", "target": "spotify"}
        ]
        
        with pytest.raises(TopologyViolationError) as exc:
            interpreter._enforce_topology(qc_output, goals)
        
        assert "QC='single'" in str(exc.value)
        assert "2 goal(s)" in str(exc.value)
    
    def test_high_confidence_multi_with_single_goal_raises(self, interpreter):
        """QC=multi (high conf) + LLM returns 1 goal → TopologyViolationError."""
        qc_output = {
            "classification": "multi",
            "confidence": 0.90,
            "reasoning": "Independent pattern"
        }
        goals = [{"goal_type": "app_launch", "target": "chrome"}]
        
        with pytest.raises(TopologyViolationError) as exc:
            interpreter._enforce_topology(qc_output, goals)
        
        assert "QC='multi'" in str(exc.value)
        assert "only 1 goal(s)" in str(exc.value)
    
    def test_low_confidence_allows_override(self, interpreter):
        """QC with low confidence does not enforce."""
        qc_output = {
            "classification": "single",
            "confidence": 0.75,  # Below threshold
            "reasoning": "LLM semantic"
        }
        goals = [
            {"goal_type": "app_launch", "target": "chrome"},
            {"goal_type": "app_launch", "target": "spotify"}
        ]
        
        # Should NOT raise
        interpreter._enforce_topology(qc_output, goals)
    
    def test_no_qc_output_allows_freedom(self, interpreter):
        """No QC output means LLM is free."""
        goals = [
            {"goal_type": "app_launch", "target": "chrome"},
            {"goal_type": "app_launch", "target": "spotify"}
        ]
        
        # Should NOT raise
        interpreter._enforce_topology(None, goals)
    
    def test_correct_topology_passes(self, interpreter):
        """Correct topology passes enforcement."""
        # Single with 1 goal
        qc_output = {"classification": "single", "confidence": 0.95}
        goals = [{"goal_type": "app_launch", "target": "chrome"}]
        interpreter._enforce_topology(qc_output, goals)  # Should not raise
        
        # Multi with 2 goals
        qc_output = {"classification": "multi", "confidence": 0.95}
        goals = [
            {"goal_type": "app_launch", "target": "chrome"},
            {"goal_type": "app_launch", "target": "spotify"}
        ]
        interpreter._enforce_topology(qc_output, goals)  # Should not raise
    
    def test_boundary_confidence_085(self, interpreter):
        """Exactly 0.85 confidence should enforce."""
        qc_output = {
            "classification": "single",
            "confidence": 0.85,  # Exactly at threshold
            "reasoning": "Boundary case"
        }
        goals = [
            {"goal_type": "app_launch", "target": "chrome"},
            {"goal_type": "app_launch", "target": "spotify"}
        ]
        
        with pytest.raises(TopologyViolationError):
            interpreter._enforce_topology(qc_output, goals)
    
    def test_just_below_threshold_allows_override(self, interpreter):
        """0.84 confidence should NOT enforce."""
        qc_output = {
            "classification": "single",
            "confidence": 0.84,  # Just below threshold
            "reasoning": "Boundary case"
        }
        goals = [
            {"goal_type": "app_launch", "target": "chrome"},
            {"goal_type": "app_launch", "target": "spotify"}
        ]
        
        # Should NOT raise
        interpreter._enforce_topology(qc_output, goals)


class TestClassifyWithConfidence:
    """Test QueryClassifier confidence output."""
    
    @pytest.fixture
    def classifier(self):
        """Create classifier with mocked model."""
        with patch('agents.query_classifier.get_model_manager') as mock_mm:
            mock_model = MagicMock()
            mock_model.generate.return_value = {
                "classification": "single",
                "reasoning": "Test"
            }
            mock_mm.return_value.get_planner_model.return_value = mock_model
            from agents.query_classifier import QueryClassifier
            return QueryClassifier()
    
    def test_syntactic_dependency_high_confidence(self, classifier):
        """Syntactic dependency patterns get 0.95 confidence."""
        result = classifier.classify_with_confidence(
            "create folder and put file inside it"
        )
        assert result["classification"] == "multi"
        assert result["confidence"] == 0.95
        assert result["detection_method"] == "syntactic"
    
    def test_syntactic_independent_high_confidence(self, classifier):
        """Syntactic independent patterns get 0.90 confidence."""
        result = classifier.classify_with_confidence(
            "open chrome and open spotify"
        )
        assert result["classification"] == "multi"
        assert result["confidence"] == 0.90
        assert result["detection_method"] == "syntactic"
    
    def test_llm_fallback_lower_confidence(self, classifier):
        """LLM fallback gets 0.75 confidence."""
        result = classifier.classify_with_confidence(
            "do something complex"
        )
        assert result["confidence"] == 0.75
        assert result["detection_method"] == "llm"
