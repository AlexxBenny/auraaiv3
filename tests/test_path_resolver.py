"""Tests for PathResolver architecture.

Verifies:
1. Relative paths resolve against WORKSPACE
2. Absolute paths are preserved
3. Dependent goals inherit parent paths
4. Different base anchors work correctly
5. Session context cwd is used
"""

import pytest
from pathlib import Path
from unittest.mock import Mock

# Import the components
from core.path_resolver import PathResolver, ResolvedPath
from core.context import SessionContext


class TestResolvedPath:
    """Test ResolvedPath dataclass invariants."""
    
    def test_absolute_path_required(self):
        """ResolvedPath must have absolute path."""
        with pytest.raises(AssertionError) as exc:
            ResolvedPath(
                raw="relative/path",
                base_anchor="WORKSPACE",
                absolute_path=Path("relative/path"),  # Not absolute!
                is_user_absolute=False
            )
        assert "absolute" in str(exc.value).lower()
    
    def test_user_absolute_must_have_none_anchor(self):
        """User-absolute paths must have base_anchor=None."""
        with pytest.raises(AssertionError):
            ResolvedPath(
                raw="D:/abs/path",
                base_anchor="WORKSPACE",  # Should be None!
                absolute_path=Path("D:/abs/path"),
                is_user_absolute=True
            )
    
    def test_relative_must_have_anchor(self):
        """Relative paths must have a base_anchor."""
        with pytest.raises(AssertionError):
            ResolvedPath(
                raw="relative/path",
                base_anchor=None,  # Should have anchor!
                absolute_path=Path("D:/base/relative/path"),
                is_user_absolute=False
            )


class TestPathResolver:
    """Test PathResolver resolution logic."""
    
    def test_absolute_path_preserved(self):
        """Absolute paths should be preserved as-is."""
        result = PathResolver.resolve("D:/some/absolute/path")
        
        assert result.is_user_absolute
        assert result.base_anchor is None
        assert result.absolute_path == Path("D:/some/absolute/path")
    
    def test_relative_path_default_workspace(self):
        """Relative paths resolve to WORKSPACE by default."""
        # Create mock context
        context = Mock()
        context.cwd = Path("D:/aura/AURA")
        
        result = PathResolver.resolve(
            "test_folder",
            base_anchor="WORKSPACE",
            context=context
        )
        
        assert not result.is_user_absolute
        assert result.base_anchor == "WORKSPACE"
        assert result.absolute_path == Path("D:/aura/AURA/test_folder")
    
    def test_nested_relative_path(self):
        """Nested relative paths work correctly."""
        context = Mock()
        context.cwd = Path("D:/aura/AURA")
        
        result = PathResolver.resolve(
            "parent/child/file.txt",
            base_anchor="WORKSPACE",
            context=context
        )
        
        assert result.absolute_path == Path("D:/aura/AURA/parent/child/file.txt")
    
    def test_inherited_path_from_parent(self):
        """Dependent goals inherit parent's resolved path."""
        parent_path = Path("D:/aura/AURA/parent_folder")
        
        result = PathResolver.resolve(
            "child_file.txt",
            parent_resolved=parent_path
        )
        
        assert result.base_anchor == "INHERITED"
        assert result.absolute_path == Path("D:/aura/AURA/parent_folder/child_file.txt")
        assert not result.is_user_absolute
    
    def test_desktop_anchor(self):
        """DESKTOP anchor resolves to Desktop directory."""
        result = PathResolver.resolve(
            "my_file.txt",
            base_anchor="DESKTOP"
        )
        
        expected = Path.home() / "Desktop" / "my_file.txt"
        assert result.absolute_path == expected
        assert result.base_anchor == "DESKTOP"
    
    def test_drive_d_anchor(self):
        """DRIVE_D anchor resolves to D:/ root."""
        result = PathResolver.resolve(
            "folder/file.txt",
            base_anchor="DRIVE_D"
        )
        
        assert result.absolute_path == Path("D:/folder/file.txt")
        assert result.base_anchor == "DRIVE_D"
    
    def test_unknown_anchor_raises(self):
        """Unknown base anchor should raise ValueError."""
        with pytest.raises(ValueError) as exc:
            PathResolver.resolve("test", base_anchor="UNKNOWN_ANCHOR")
        
        assert "UNKNOWN_ANCHOR" in str(exc.value)
    
    def test_empty_path_raises(self):
        """Empty path should raise ValueError."""
        with pytest.raises(ValueError):
            PathResolver.resolve("")


class TestSessionContext:
    """Test SessionContext cwd field."""
    
    def test_cwd_captured_at_init(self):
        """Session should capture cwd at initialization."""
        context = SessionContext()
        
        assert hasattr(context, "cwd")
        assert isinstance(context.cwd, Path)
        assert context.cwd.is_absolute()


class TestInferBaseAnchor:
    """Test base anchor inference from user input."""
    
    def test_infer_d_drive(self):
        """Should detect D drive mention."""
        assert PathResolver.infer_base_anchor("create folder in D drive") == "DRIVE_D"
        assert PathResolver.infer_base_anchor("save to D:") == "DRIVE_D"
    
    def test_infer_desktop(self):
        """Should detect desktop mention."""
        assert PathResolver.infer_base_anchor("create on desktop") == "DESKTOP"
    
    def test_infer_documents(self):
        """Should detect documents mention."""
        assert PathResolver.infer_base_anchor("save in documents") == "DOCUMENTS"
    
    def test_no_location_returns_none(self):
        """No location should return None (use default)."""
        assert PathResolver.infer_base_anchor("create a folder called test") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
