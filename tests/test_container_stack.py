"""Tests for container stack dependency fix in GoalInterpreter.

Verifies:
1. Deep nesting bug is fixed (the original issue)
2. Explicit dependencies are preserved
3. Mixed files/folders work correctly
4. Edge cases handled properly
"""

import pytest
from agents.goal_interpreter import GoalInterpreter


class TestContainerDependencyFix:
    """Test _fix_container_dependencies method."""
    
    @pytest.fixture
    def interpreter(self):
        return GoalInterpreter()
    
    def test_three_level_nesting_bug_case(self, interpreter):
        """The original bug: 'space → galaxy → milkyway' was creating wrong paths."""
        goals = [
            {"goal_type": "file_operation", "object_type": "folder", "target": "space"},
            {"goal_type": "file_operation", "object_type": "folder", "target": "galaxy"},
            {"goal_type": "file_operation", "object_type": "file", "target": "milkyway.txt"},
        ]
        # LLM incorrectly bound g2 to g0 (first container) instead of g1 (most recent)
        llm_deps = [
            {"goal_idx": 1, "depends_on": [0]},  # galaxy → space ✅
            {"goal_idx": 2, "depends_on": [0]},  # milkyway → space ❌ should be → galaxy
        ]
        
        fixed = interpreter._fix_container_dependencies(goals, llm_deps)
        
        # Convert to dict for easier assertion
        fixed_map = {d["goal_idx"]: d["depends_on"] for d in fixed}
        
        assert fixed_map[1] == [0], "galaxy should depend on space"
        assert fixed_map[2] == [1], "milkyway should depend on galaxy (FIXED)"
    
    def test_explicit_dependency_preserved(self, interpreter):
        """Explicit dependencies (folder A, folder B, file inside B) should be preserved."""
        goals = [
            {"goal_type": "file_operation", "object_type": "folder", "target": "A"},
            {"goal_type": "file_operation", "object_type": "folder", "target": "B"},
            {"goal_type": "file_operation", "object_type": "file", "target": "X.txt"},
        ]
        # LLM correctly bound X to B (not first container A)
        llm_deps = [
            {"goal_idx": 2, "depends_on": [1]},  # X → B (correct, explicit)
        ]
        
        fixed = interpreter._fix_container_dependencies(goals, llm_deps)
        fixed_map = {d["goal_idx"]: d["depends_on"] for d in fixed}
        
        # Should NOT rewrite - LLM was correct
        assert fixed_map[2] == [1], "X should still depend on B (preserved)"
    
    def test_deep_five_level_nesting(self, interpreter):
        """Deep nesting: universe → galaxy → milkyway → solar → earth.txt"""
        goals = [
            {"goal_type": "file_operation", "object_type": "folder", "target": "universe"},
            {"goal_type": "file_operation", "object_type": "folder", "target": "galaxy"},
            {"goal_type": "file_operation", "object_type": "folder", "target": "milkyway"},
            {"goal_type": "file_operation", "object_type": "folder", "target": "solar"},
            {"goal_type": "file_operation", "object_type": "file", "target": "earth.txt"},
        ]
        # LLM incorrectly bound everything to g0
        llm_deps = [
            {"goal_idx": 1, "depends_on": [0]},  # galaxy → universe ✅
            {"goal_idx": 2, "depends_on": [0]},  # milkyway → universe ❌
            {"goal_idx": 3, "depends_on": [0]},  # solar → universe ❌
            {"goal_idx": 4, "depends_on": [0]},  # earth → universe ❌
        ]
        
        fixed = interpreter._fix_container_dependencies(goals, llm_deps)
        fixed_map = {d["goal_idx"]: d["depends_on"] for d in fixed}
        
        assert fixed_map[1] == [0], "galaxy → universe"
        assert fixed_map[2] == [1], "milkyway → galaxy (FIXED)"
        assert fixed_map[3] == [2], "solar → milkyway (FIXED)"
        assert fixed_map[4] == [3], "earth → solar (FIXED)"
    
    def test_file_does_not_push_to_stack(self, interpreter):
        """Files don't push to container stack: folder A → file X → folder B → file Y"""
        goals = [
            {"goal_type": "file_operation", "object_type": "folder", "target": "A"},
            {"goal_type": "file_operation", "object_type": "file", "target": "X.txt"},
            {"goal_type": "file_operation", "object_type": "folder", "target": "B"},
            {"goal_type": "file_operation", "object_type": "file", "target": "Y.txt"},
        ]
        # LLM bound B and Y to A (first container)
        llm_deps = [
            {"goal_idx": 1, "depends_on": [0]},  # X → A ✅ (correct)
            {"goal_idx": 2, "depends_on": [0]},  # B → A ✅ (correct - B inside A)
            {"goal_idx": 3, "depends_on": [0]},  # Y → A ❌ (should be Y → B)
        ]
        
        fixed = interpreter._fix_container_dependencies(goals, llm_deps)
        fixed_map = {d["goal_idx"]: d["depends_on"] for d in fixed}
        
        # After A and X, stack is [A] (files don't push)
        # After B, stack is [A, B]
        # Y should bind to B (top of stack)
        assert fixed_map[1] == [0], "X → A"
        assert fixed_map[2] == [0], "B → A (preserved, not bound to first)"
        assert fixed_map[3] == [2], "Y → B (FIXED)"
    
    def test_two_level_simple(self, interpreter):
        """Simple two-level: folder → file inside."""
        goals = [
            {"goal_type": "file_operation", "object_type": "folder", "target": "space"},
            {"goal_type": "file_operation", "object_type": "file", "target": "doc.txt"},
        ]
        llm_deps = [
            {"goal_idx": 1, "depends_on": [0]},  # doc → space ✅
        ]
        
        fixed = interpreter._fix_container_dependencies(goals, llm_deps)
        fixed_map = {d["goal_idx"]: d["depends_on"] for d in fixed}
        
        # No rewrite needed - only one container
        assert fixed_map[1] == [0], "doc → space (correct, no change)"
    
    def test_no_dependencies_preserved(self, interpreter):
        """Goals with no dependencies stay that way."""
        goals = [
            {"goal_type": "file_operation", "object_type": "folder", "target": "A"},
            {"goal_type": "file_operation", "object_type": "folder", "target": "B"},
        ]
        # No dependencies (independent folders)
        llm_deps = []
        
        fixed = interpreter._fix_container_dependencies(goals, llm_deps)
        
        # Should return empty (first folder has no dependency)
        assert fixed == [], "No dependencies to fix"
    
    def test_non_file_operation_ignored(self, interpreter):
        """Non-file_operation goals are ignored."""
        goals = [
            {"goal_type": "app_launch", "target": "chrome"},
            {"goal_type": "file_operation", "object_type": "folder", "target": "space"},
            {"goal_type": "file_operation", "object_type": "file", "target": "doc.txt"},
        ]
        llm_deps = [
            {"goal_idx": 2, "depends_on": [1]},  # doc → space ✅
        ]
        
        fixed = interpreter._fix_container_dependencies(goals, llm_deps)
        fixed_map = {d["goal_idx"]: d["depends_on"] for d in fixed}
        
        # App launch is ignored, file_operation preserved
        assert fixed_map[2] == [1], "doc → space"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
