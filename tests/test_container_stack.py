"""Tests for container stack and scope switching in GoalInterpreter.

Verifies:
1. Deep nesting bug is fixed (the original issue)
2. Explicit dependencies are preserved
3. Mixed files/folders work correctly
4. Multi-scope commands (different explicit locations)
5. Linguistic anchor detection (not LLM paths)
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
        user_input = "create a folder named space and inside it another folder named galaxy and inside it a text file named milkyway"
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
        
        fixed = interpreter._fix_container_dependencies(goals, llm_deps, user_input)
        
        # Convert to dict for easier assertion
        fixed_map = {d["goal_idx"]: d["depends_on"] for d in fixed}
        
        assert fixed_map[1] == [0], "galaxy should depend on space"
        assert fixed_map[2] == [1], "milkyway should depend on galaxy (FIXED)"
    
    def test_explicit_dependency_preserved(self, interpreter):
        """Explicit dependencies (folder A, folder B, file inside B) should be preserved."""
        user_input = "create folder A and folder B and file X inside B"
        goals = [
            {"goal_type": "file_operation", "object_type": "folder", "target": "A"},
            {"goal_type": "file_operation", "object_type": "folder", "target": "B"},
            {"goal_type": "file_operation", "object_type": "file", "target": "X.txt"},
        ]
        # LLM correctly bound X to B (not first container A)
        llm_deps = [
            {"goal_idx": 2, "depends_on": [1]},  # X → B (correct, explicit)
        ]
        
        fixed = interpreter._fix_container_dependencies(goals, llm_deps, user_input)
        fixed_map = {d["goal_idx"]: d["depends_on"] for d in fixed}
        
        # Should NOT rewrite - LLM was correct
        assert fixed_map[2] == [1], "X should still depend on B (preserved)"
    
    def test_deep_five_level_nesting(self, interpreter):
        """Deep nesting: universe → galaxy → milkyway → solar → earth.txt"""
        user_input = "create folder universe, inside it galaxy, inside it milkyway, inside it solar, inside it earth.txt"
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
        
        fixed = interpreter._fix_container_dependencies(goals, llm_deps, user_input)
        fixed_map = {d["goal_idx"]: d["depends_on"] for d in fixed}
        
        assert fixed_map[1] == [0], "galaxy → universe"
        assert fixed_map[2] == [1], "milkyway → galaxy (FIXED)"
        assert fixed_map[3] == [2], "solar → milkyway (FIXED)"
        assert fixed_map[4] == [3], "earth → solar (FIXED)"
    
    def test_file_does_not_push_to_stack(self, interpreter):
        """Files don't push to container stack: folder A → file X → folder B → file Y"""
        user_input = "create folder A, file X inside it, folder B inside it, file Y inside it"
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
        
        fixed = interpreter._fix_container_dependencies(goals, llm_deps, user_input)
        fixed_map = {d["goal_idx"]: d["depends_on"] for d in fixed}
        
        # After A and X, stack is [A] (files don't push)
        # After B, stack is [A, B]
        # Y should bind to B (top of stack)
        assert fixed_map[1] == [0], "X → A"
        assert fixed_map[2] == [0], "B → A (preserved, not bound to first)"
        assert fixed_map[3] == [2], "Y → B (FIXED)"
    
    def test_two_level_simple(self, interpreter):
        """Simple two-level: folder → file inside."""
        user_input = "create folder space and file doc.txt inside it"
        goals = [
            {"goal_type": "file_operation", "object_type": "folder", "target": "space"},
            {"goal_type": "file_operation", "object_type": "file", "target": "doc.txt"},
        ]
        llm_deps = [
            {"goal_idx": 1, "depends_on": [0]},  # doc → space ✅
        ]
        
        fixed = interpreter._fix_container_dependencies(goals, llm_deps, user_input)
        fixed_map = {d["goal_idx"]: d["depends_on"] for d in fixed}
        
        # No rewrite needed - only one container
        assert fixed_map[1] == [0], "doc → space (correct, no change)"
    
    def test_no_dependencies_preserved(self, interpreter):
        """Goals with no dependencies stay that way."""
        user_input = "create folder A and folder B"
        goals = [
            {"goal_type": "file_operation", "object_type": "folder", "target": "A"},
            {"goal_type": "file_operation", "object_type": "folder", "target": "B"},
        ]
        # No dependencies (independent folders)
        llm_deps = []
        
        fixed = interpreter._fix_container_dependencies(goals, llm_deps, user_input)
        
        # Should return empty (first folder has no dependency)
        assert fixed == [], "No dependencies to fix"
    
    def test_non_file_operation_ignored(self, interpreter):
        """Non-file_operation goals are ignored."""
        user_input = "open chrome and create folder space and file doc.txt inside it"
        goals = [
            {"goal_type": "app_launch", "target": "chrome"},
            {"goal_type": "file_operation", "object_type": "folder", "target": "space"},
            {"goal_type": "file_operation", "object_type": "file", "target": "doc.txt"},
        ]
        llm_deps = [
            {"goal_idx": 2, "depends_on": [1]},  # doc → space ✅
        ]
        
        fixed = interpreter._fix_container_dependencies(goals, llm_deps, user_input)
        fixed_map = {d["goal_idx"]: d["depends_on"] for d in fixed}
        
        # App launch is ignored, file_operation preserved
        assert fixed_map[2] == [1], "doc → space"


class TestExplicitAnchorDetection:
    """Test _detect_explicit_anchor method for linguistic grounding."""
    
    @pytest.fixture
    def interpreter(self):
        return GoalInterpreter()
    
    def test_d_drive_detection(self, interpreter):
        assert interpreter._detect_explicit_anchor("create folder in d drive", 0) == "DRIVE_D"
        assert interpreter._detect_explicit_anchor("create folder in drive d", 0) == "DRIVE_D"
    
    def test_c_drive_detection(self, interpreter):
        assert interpreter._detect_explicit_anchor("create folder in c drive", 0) == "DRIVE_C"
    
    def test_desktop_detection(self, interpreter):
        assert interpreter._detect_explicit_anchor("create folder on desktop", 0) == "DESKTOP"
    
    def test_documents_detection(self, interpreter):
        assert interpreter._detect_explicit_anchor("save file to documents", 0) == "DOCUMENTS"
        assert interpreter._detect_explicit_anchor("save file to my documents", 0) == "DOCUMENTS"
    
    def test_downloads_detection(self, interpreter):
        assert interpreter._detect_explicit_anchor("move file to downloads", 0) == "DOWNLOADS"
    
    def test_root_folder_detection(self, interpreter):
        assert interpreter._detect_explicit_anchor("create folder in root folder", 0) == "WORKSPACE"
        assert interpreter._detect_explicit_anchor("create folder in root directory", 0) == "WORKSPACE"
    
    def test_no_anchor_when_not_mentioned(self, interpreter):
        assert interpreter._detect_explicit_anchor("create folder space", 0) is None
        assert interpreter._detect_explicit_anchor("create file inside it", 0) is None


class TestMultiScopeCommands:
    """Test multi-scope commands with different explicit locations."""
    
    @pytest.fixture
    def interpreter(self):
        return GoalInterpreter()
    
    def test_scope_switch_d_drive(self, interpreter):
        """When user mentions D drive, second goal should start new scope."""
        user_input = "create folder space in root folder and folder galaxy in d drive and folder milkyway inside it"
        goals = [
            {"goal_type": "file_operation", "object_type": "folder", "target": "space"},
            {"goal_type": "file_operation", "object_type": "folder", "target": "D:\\galaxy"},
            {"goal_type": "file_operation", "object_type": "file", "target": "D:\\galaxy\\milkyway"},
        ]
        # LLM bound everything incorrectly
        llm_deps = [
            {"goal_idx": 1, "depends_on": [0]},  # galaxy → space ❌ wrong scope
            {"goal_idx": 2, "depends_on": [0]},  # milkyway → space ❌ wrong scope
        ]
        
        fixed = interpreter._fix_container_dependencies(goals, llm_deps, user_input)
        fixed_map = {d["goal_idx"]: d["depends_on"] for d in fixed}
        
        # g1 (galaxy) should have no dependency in new D drive scope
        # g2 (milkyway) should depend on g1 (galaxy)
        assert fixed_map.get(2) == [1], "milkyway should depend on galaxy (same D drive scope)"
    
    def test_no_scope_switch_without_linguistic_evidence(self, interpreter):
        """Absolute paths from LLM should NOT trigger scope switch without user mention."""
        user_input = "create folder space and folder galaxy inside it and file milkyway inside it"
        # LLM emits absolute paths but user didn't mention D drive
        goals = [
            {"goal_type": "file_operation", "object_type": "folder", "target": "D:\\space"},
            {"goal_type": "file_operation", "object_type": "folder", "target": "D:\\space\\galaxy"},
            {"goal_type": "file_operation", "object_type": "file", "target": "D:\\space\\galaxy\\milkyway.txt"},
        ]
        llm_deps = [
            {"goal_idx": 1, "depends_on": [0]},
            {"goal_idx": 2, "depends_on": [0]},
        ]
        
        fixed = interpreter._fix_container_dependencies(goals, llm_deps, user_input)
        fixed_map = {d["goal_idx"]: d["depends_on"] for d in fixed}
        
        # Should still fix nesting within the implicit scope
        assert fixed_map[1] == [0], "galaxy → space"
        assert fixed_map[2] == [1], "milkyway → galaxy (FIXED within same scope)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
