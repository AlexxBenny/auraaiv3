"""Tests for scope-based dependency derivation in GoalInterpreter.

Verifies:
1. _derive_dependencies_from_scope correctly builds DAG from scope annotations
2. _derive_anchor_from_scope correctly extracts anchors
3. Scope-based resolution works for containment, ordering, and drives
"""

import pytest
from agents.goal_interpreter import GoalInterpreter


class TestDerriveDependenciesFromScope:
    """Test _derive_dependencies_from_scope method."""
    
    @pytest.fixture
    def interpreter(self):
        return GoalInterpreter()
    
    def test_three_level_nesting(self, interpreter):
        """space → galaxy → milkyway via scope annotations."""
        goals = [
            {"goal_type": "file_operation", "object_type": "folder", "target": "space", "scope": "root"},
            {"goal_type": "file_operation", "object_type": "folder", "target": "galaxy", "scope": "inside:space"},
            {"goal_type": "file_operation", "object_type": "file", "target": "milkyway.txt", "scope": "inside:galaxy"},
        ]
        
        deps = interpreter._derive_dependencies_from_scope(goals)
        
        # Convert to dict for easier assertion
        deps_map = {idx: list(parents) for idx, parents in deps}
        
        assert deps_map.get(1) == [0], "galaxy should depend on space"
        assert deps_map.get(2) == [1], "milkyway should depend on galaxy"
    
    def test_siblings_no_dependencies(self, interpreter):
        """Sibling folders at root have no dependencies."""
        goals = [
            {"goal_type": "file_operation", "object_type": "folder", "target": "A", "scope": "root"},
            {"goal_type": "file_operation", "object_type": "folder", "target": "B", "scope": "root"},
            {"goal_type": "file_operation", "object_type": "folder", "target": "C", "scope": "root"},
        ]
        
        deps = interpreter._derive_dependencies_from_scope(goals)
        
        assert deps == [], "No dependencies for siblings at root"
    
    def test_mixed_containment_and_siblings(self, interpreter):
        """A and B are siblings, C inside A, D inside B."""
        goals = [
            {"goal_type": "file_operation", "object_type": "folder", "target": "A", "scope": "root"},
            {"goal_type": "file_operation", "object_type": "folder", "target": "B", "scope": "root"},
            {"goal_type": "file_operation", "object_type": "file", "target": "C.txt", "scope": "inside:A"},
            {"goal_type": "file_operation", "object_type": "file", "target": "D.txt", "scope": "inside:B"},
        ]
        
        deps = interpreter._derive_dependencies_from_scope(goals)
        deps_map = {idx: list(parents) for idx, parents in deps}
        
        assert 0 not in deps_map, "A has no dependency"
        assert 1 not in deps_map, "B has no dependency"
        assert deps_map.get(2) == [0], "C depends on A"
        assert deps_map.get(3) == [1], "D depends on B"
    
    def test_multi_scope_with_drive(self, interpreter):
        """X in D drive, Y inside X, Z at root (workspace)."""
        goals = [
            {"goal_type": "file_operation", "object_type": "folder", "target": "X", "scope": "drive:D"},
            {"goal_type": "file_operation", "object_type": "folder", "target": "Y", "scope": "inside:X"},
            {"goal_type": "file_operation", "object_type": "folder", "target": "Z", "scope": "root"},
        ]
        
        deps = interpreter._derive_dependencies_from_scope(goals)
        deps_map = {idx: list(parents) for idx, parents in deps}
        
        assert 0 not in deps_map, "X has no dependency (drive scope)"
        assert deps_map.get(1) == [0], "Y depends on X"
        assert 2 not in deps_map, "Z has no dependency (root scope)"
    
    def test_after_scope_for_ordering(self, interpreter):
        """Download and analyze - ordering via after: scope."""
        goals = [
            {"goal_type": "file_operation", "action": "download", "target": "report.pdf", "scope": "root"},
            {"goal_type": "file_operation", "action": "analyze", "target": "report.pdf", "scope": "after:report.pdf"},
        ]
        
        deps = interpreter._derive_dependencies_from_scope(goals)
        deps_map = {idx: list(parents) for idx, parents in deps}
        
        assert deps_map.get(1) == [0], "analyze depends on download"
    
    def test_unknown_target_warning(self, interpreter):
        """Reference to unknown target should not create dependency."""
        goals = [
            {"goal_type": "file_operation", "object_type": "folder", "target": "A", "scope": "root"},
            {"goal_type": "file_operation", "object_type": "file", "target": "B.txt", "scope": "inside:UNKNOWN"},
        ]
        
        deps = interpreter._derive_dependencies_from_scope(goals)
        deps_map = {idx: list(parents) for idx, parents in deps}
        
        # B should NOT have a dependency since UNKNOWN doesn't exist
        assert 1 not in deps_map, "B should not have dependency on unknown target"
    
    def test_forward_reference_only(self, interpreter):
        """Backward references should be rejected."""
        goals = [
            {"goal_type": "file_operation", "object_type": "file", "target": "A.txt", "scope": "inside:B"},
            {"goal_type": "file_operation", "object_type": "folder", "target": "B", "scope": "root"},
        ]
        
        deps = interpreter._derive_dependencies_from_scope(goals)
        
        # A references B which comes AFTER it - should be rejected
        assert deps == [], "Backward reference should not create dependency"


class TestDeriveAnchorFromScope:
    """Test _derive_anchor_from_scope method."""
    
    @pytest.fixture
    def interpreter(self):
        return GoalInterpreter()
    
    def test_drive_d_scope(self, interpreter):
        assert interpreter._derive_anchor_from_scope("drive:D") == "DRIVE_D"
    
    def test_drive_c_scope(self, interpreter):
        assert interpreter._derive_anchor_from_scope("drive:C") == "DRIVE_C"
    
    def test_drive_lowercase(self, interpreter):
        assert interpreter._derive_anchor_from_scope("drive:d") == "DRIVE_D"
    
    def test_root_scope_no_anchor(self, interpreter):
        assert interpreter._derive_anchor_from_scope("root") is None
    
    def test_inside_scope_no_anchor(self, interpreter):
        assert interpreter._derive_anchor_from_scope("inside:X") is None
    
    def test_after_scope_no_anchor(self, interpreter):
        assert interpreter._derive_anchor_from_scope("after:X") is None


class TestScopeIntegration:
    """Integration tests for scope-based goal interpretation."""
    
    @pytest.fixture
    def interpreter(self):
        return GoalInterpreter()
    
    def test_anchor_does_not_leak_across_scopes(self, interpreter):
        """CRITICAL: The anchor leakage bug test case.
        
        X in D drive, Y inside X, Z at root
        Z must NOT get DRIVE_D anchor.
        """
        goals_data = [
            {"goal_type": "file_operation", "object_type": "folder", "target": "X", "scope": "drive:D"},
            {"goal_type": "file_operation", "object_type": "folder", "target": "Y", "scope": "inside:X"},
            {"goal_type": "file_operation", "object_type": "folder", "target": "Z", "scope": "root"},
        ]
        
        # Derive anchors for each goal
        anchors = [interpreter._derive_anchor_from_scope(g["scope"]) for g in goals_data]
        
        assert anchors[0] == "DRIVE_D", "X should have DRIVE_D anchor"
        assert anchors[1] is None, "Y should inherit via dependency, not explicit anchor"
        assert anchors[2] is None, "Z should have NO anchor (defaults to workspace)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
