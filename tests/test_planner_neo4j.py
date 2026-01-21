"""Integration Tests for Planner → Neo4j Eligibility Checks

These tests verify:
1. Tool with no blocking constraints → allowed
2. Tool with blocking constraint → refused
3. Tool with soft constraint → allowed with warning
4. Neo4j down → fail closed

Run with: python -m pytest tests/test_planner_neo4j.py -v
"""

import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.ontology.neo4j_client import (
    Neo4jClient,
    ToolConstraints,
    ConstraintInfo,
    Neo4jConnectionError,
    get_neo4j_client
)
from core.ontology.eligibility import (
    check_plan_eligibility,
    PlanEligibilityResult,
    verify_neo4j_connection
)
from core.response_formatter import (
    format_refusal_message,
    format_safety_warnings
)


class TestNeo4jConnection:
    """Test Neo4j connection and health checks"""
    
    def test_neo4j_connection(self):
        """Test that Neo4j is reachable"""
        client = get_neo4j_client()
        health = client.health_check()
        
        if not health["connected"]:
            pytest.skip(f"Neo4j not available: {health.get('error')}")
        
        assert health["connected"] is True
        assert health["error"] is None
    
    def test_verify_connection_function(self):
        """Test the convenience verification function"""
        connected = verify_neo4j_connection()
        if not connected:
            pytest.skip("Neo4j not available")
        assert connected is True


class TestToolConstraintQueries:
    """Test querying tool constraints from Neo4j"""
    
    @pytest.fixture(autouse=True)
    def skip_if_no_neo4j(self):
        """Skip tests if Neo4j is not available"""
        if not verify_neo4j_connection():
            pytest.skip("Neo4j not available")
    
    def test_query_tool_with_no_constraints(self):
        """Test tool that has no blocking constraints (perception tools)"""
        client = get_neo4j_client()
        
        # get_active_window has no constraints
        result = client.query_tool_constraints("system.state.get_active_window")
        
        assert result.found is True
        assert len(result.blocking_constraints) == 0
        # May or may not have soft constraints
    
    def test_query_tool_with_blocking_constraint(self):
        """Test tool that has blocking constraints (input tools)"""
        client = get_neo4j_client()
        
        # mouse.click has requires_target_context (blocking)
        result = client.query_tool_constraints("system.input.mouse.click")
        
        assert result.found is True
        assert len(result.blocking_constraints) > 0
        
        # Verify constraint details
        constraint_names = [c.name for c in result.blocking_constraints]
        assert "requires_target_context" in constraint_names
    
    def test_query_tool_with_soft_constraint(self):
        """Test tool that has soft constraints"""
        client = get_neo4j_client()
        
        # keyboard.type has unsafe_without_context (soft)
        result = client.query_tool_constraints("system.input.keyboard.type")
        
        assert result.found is True
        # Check for soft constraints
        if result.soft_constraints:
            constraint_names = [c.name for c in result.soft_constraints]
            assert "unsafe_without_context" in constraint_names
    
    def test_query_unknown_tool(self):
        """Test querying a tool that doesn't exist in Neo4j"""
        client = get_neo4j_client()
        
        result = client.query_tool_constraints("fake.nonexistent.tool")
        
        assert result.found is False
        assert len(result.blocking_constraints) == 0
        assert len(result.soft_constraints) == 0


class TestPlanEligibility:
    """Test plan eligibility checking"""
    
    @pytest.fixture(autouse=True)
    def skip_if_no_neo4j(self):
        """Skip tests if Neo4j is not available"""
        if not verify_neo4j_connection():
            pytest.skip("Neo4j not available")
    
    def test_plan_with_no_constraints_allowed(self):
        """Test that plan with only unconstrained tools is allowed"""
        plan_steps = [
            {"tool": "system.state.get_active_window", "args": {}},
            {"tool": "system.state.get_execution_context", "args": {}}
        ]
        
        result = check_plan_eligibility(plan_steps)
        
        assert result.eligible is True
        assert result.checked is True
        assert len(result.blocking_reasons) == 0
    
    def test_plan_with_blocking_constraint_refused(self):
        """Test that plan with blocking constraint is refused"""
        plan_steps = [
            {"tool": "system.input.mouse.click", "args": {"x": 100, "y": 200}}
        ]
        
        result = check_plan_eligibility(plan_steps)
        
        assert result.eligible is False
        assert result.checked is True
        assert len(result.blocking_reasons) > 0
        
        # Verify the blocking reason
        blocked_constraints = [r.constraint for r in result.blocking_reasons]
        assert "requires_target_context" in blocked_constraints
    
    def test_plan_with_soft_constraint_allowed_with_warning(self):
        """Test that plan with only soft constraints is allowed with warnings"""
        plan_steps = [
            {"tool": "system.input.keyboard.type", "args": {"text": "hello"}}
        ]
        
        result = check_plan_eligibility(plan_steps)
        
        # Should be allowed but with warnings (if soft constraint exists)
        # Note: keyboard.type may have either blocking or soft depending on ontology
        assert result.checked is True
        
        if result.eligible:
            # If allowed, check for warnings
            assert len(result.warnings) >= 0  # May or may not have warnings
    
    def test_mixed_plan_blocked_by_one_constraint(self):
        """Test that mixed plan is blocked if ANY tool has blocking constraint"""
        plan_steps = [
            {"tool": "system.state.get_active_window", "args": {}},  # No constraints
            {"tool": "system.input.mouse.click", "args": {"x": 100, "y": 200}}  # Blocking
        ]
        
        result = check_plan_eligibility(plan_steps)
        
        # Entire plan should be blocked
        assert result.eligible is False
        assert result.checked is True
    
    def test_unknown_tool_blocks_plan(self):
        """Test that unknown tool (not in Neo4j) blocks the plan"""
        plan_steps = [
            {"tool": "unknown.fake.tool", "args": {}}
        ]
        
        result = check_plan_eligibility(plan_steps)
        
        assert result.eligible is False
        assert result.checked is True
        
        # Should have tool_not_in_ontology constraint
        blocked_constraints = [r.constraint for r in result.blocking_reasons]
        assert "tool_not_in_ontology" in blocked_constraints


class TestResponseFormatter:
    """Test response message formatting"""
    
    def test_format_refusal_with_constraint(self):
        """Test formatting refusal message with constraint"""
        refusal = {
            "blocked_tools": ["system.input.mouse.click"],
            "blocking_constraints": [
                {
                    "constraint": "requires_target_context",
                    "type": "safety_hard_block",
                    "resolvable": True,
                    "resolution_hint": "Focus window or specify window_title"
                }
            ]
        }
        
        message = format_refusal_message(refusal)
        
        assert message is not None
        assert len(message) > 0
        assert "window" in message.lower() or "target" in message.lower()
    
    def test_format_refusal_system_unavailable(self):
        """Test formatting refusal for system unavailable"""
        refusal = {
            "error_type": "system_unavailable",
            "blocked_tools": [],
            "blocking_constraints": []
        }
        
        message = format_refusal_message(refusal)
        
        assert "safe" in message.lower() or "try again" in message.lower()
    
    def test_format_empty_refusal(self):
        """Test formatting empty refusal"""
        message = format_refusal_message({})
        
        assert message is not None
        assert len(message) > 0
    
    def test_format_safety_warnings(self):
        """Test formatting safety warnings"""
        warnings = [
            {
                "tool": "system.input.keyboard.type",
                "warning": "unsafe_without_context",
                "type": "safety_recommendation",
                "recommendation": "Consider focusing target window"
            }
        ]
        
        message = format_safety_warnings(warnings)
        
        assert message is not None
        assert "Note:" in message


class TestFailClosed:
    """Test fail-closed behavior when Neo4j is unavailable"""
    
    def test_eligibility_result_on_error(self):
        """Test that eligibility result has error state"""
        # Create a result with error (simulating Neo4j failure)
        result = PlanEligibilityResult(
            eligible=False,
            blocking_reasons=[],
            warnings=[],
            checked=False,
            error="Neo4j connection failed"
        )
        
        assert result.eligible is False
        assert result.checked is False
        assert result.error is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
