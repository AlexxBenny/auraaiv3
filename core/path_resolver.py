"""PathResolver - Single authority for path resolution.

INVARIANT: All relative paths resolve against a known base anchor.
NO Path.cwd() leaks. NO tool-level resolution.

This is the ONLY place where user/LLM paths become absolute filesystem paths.
Planners, executors, and tools must NEVER call .resolve() on user paths.
"""

from pathlib import Path
from typing import Optional, TYPE_CHECKING
from dataclasses import dataclass
import logging

if TYPE_CHECKING:
    from core.context import SessionContext


# =============================================================================
# RESOLVED PATH CONTRACT
# =============================================================================

@dataclass(frozen=True)
class ResolvedPath:
    """A path that has been deterministically resolved.
    
    INVARIANTS:
    - absolute_path is ALWAYS absolute
    - base_anchor is None IFF is_user_absolute is True
    - This is immutable (frozen)
    """
    raw: str                          # Original from user/LLM
    base_anchor: Optional[str]        # None if user-absolute, else WORKSPACE/DESKTOP/etc.
    absolute_path: Path               # The authoritative, absolute path
    is_user_absolute: bool            # True if user provided absolute path
    
    def __post_init__(self):
        # Enforce invariants
        assert self.absolute_path.is_absolute(), \
            f"absolute_path must be absolute: {self.absolute_path}"
        assert not str(self.absolute_path).startswith("\\\\?\\"), \
            f"UNC paths not supported: {self.absolute_path}"
        
        # base_anchor and is_user_absolute must be consistent
        if self.is_user_absolute:
            assert self.base_anchor is None, \
                "User-absolute paths must have base_anchor=None"
        else:
            assert self.base_anchor is not None, \
                "Relative paths must have a base_anchor"


# =============================================================================
# PATH RESOLVER
# =============================================================================

class PathResolver:
    """Single authority for path resolution.
    
    RESPONSIBILITY:
    - Convert user-intent paths → absolute filesystem paths
    - Ensure deterministic resolution based on session context
    
    DOES NOT:
    - Execute anything
    - Validate write permissions (safety.py's job)
    - Create directories (tools' job)
    """
    
    @staticmethod
    def get_base_anchors(context: Optional["SessionContext"] = None) -> dict:
        """Get base anchors for path resolution.
        
        CRITICAL: This is context-dependent, NOT frozen at import time.
        
        Args:
            context: Session context with cwd. If None, falls back to Path.cwd()
                     but logs a warning (this should only happen in tests).
        
        Returns:
            Dict of anchor name → Path
        """
        if context is None:
            logging.warning("PathResolver: No context provided, using Path.cwd()")
            workspace = Path.cwd()
        else:
            workspace = context.cwd
        
        return {
            "WORKSPACE": workspace,
            "DESKTOP": Path.home() / "Desktop",
            "DOCUMENTS": Path.home() / "Documents",
            "DOWNLOADS": Path.home() / "Downloads",
            "DRIVE_C": Path("C:/"),
            "DRIVE_D": Path("D:/"),
            "DRIVE_E": Path("E:/"),
            "HOME": Path.home(),
        }
    
    @staticmethod
    def resolve(
        raw_path: str,
        base_anchor: str = "WORKSPACE",
        parent_resolved: Optional[Path] = None,
        context: Optional["SessionContext"] = None
    ) -> ResolvedPath:
        """Resolve a path deterministically.
        
        Resolution rules (in order):
        1. If path is absolute → use as-is (is_user_absolute=True)
        2. If parent_resolved provided → inherit parent location
        3. Otherwise → resolve against base_anchor
        
        Args:
            raw_path: Path from user/LLM (may be relative or absolute)
            base_anchor: Where to anchor relative paths (WORKSPACE, DESKTOP, etc.)
            parent_resolved: For dependent goals, inherit parent's resolved path
            context: Session context for WORKSPACE anchor
        
        Returns:
            ResolvedPath with absolute_path guaranteed to be absolute
        
        Raises:
            ValueError: If base_anchor is unknown
        """
        if not raw_path:
            raise ValueError("raw_path cannot be empty")
        
        p = Path(raw_path)
        
        # Rule 1: If absolute, use as-is
        if p.is_absolute():
            logging.debug(f"PathResolver: '{raw_path}' is user-absolute")
            return ResolvedPath(
                raw=raw_path,
                base_anchor=None,
                absolute_path=p,
                is_user_absolute=True
            )
        
        # Rule 2: If parent context provided (dependent goal)
        if parent_resolved is not None:
            resolved = parent_resolved / p
            logging.debug(f"PathResolver: '{raw_path}' inherits from parent → {resolved}")
            return ResolvedPath(
                raw=raw_path,
                base_anchor="INHERITED",
                absolute_path=resolved,
                is_user_absolute=False
            )
        
        # Rule 3: Resolve against base anchor
        anchors = PathResolver.get_base_anchors(context)
        base = anchors.get(base_anchor)
        
        if base is None:
            valid_anchors = list(anchors.keys())
            raise ValueError(f"Unknown base anchor: {base_anchor}. Valid: {valid_anchors}")
        
        resolved = base / p
        logging.debug(f"PathResolver: '{raw_path}' + {base_anchor} → {resolved}")
        
        return ResolvedPath(
            raw=raw_path,
            base_anchor=base_anchor,
            absolute_path=resolved,
            is_user_absolute=False
        )
    
    @staticmethod
    def infer_base_anchor(user_input: str) -> Optional[str]:
        """Infer base anchor from user input.
        
        This is a helper for GoalInterpreter to detect explicit locations.
        
        Examples:
            "in D drive" → DRIVE_D
            "on desktop" → DESKTOP
            "in documents" → DOCUMENTS
            (no location) → None (use default)
        
        Args:
            user_input: Raw user input
        
        Returns:
            Inferred base anchor or None
        """
        lower = user_input.lower()
        
        # Explicit drive mentions
        if "d drive" in lower or "d:" in lower:
            return "DRIVE_D"
        if "c drive" in lower or "c:" in lower:
            return "DRIVE_C"
        if "e drive" in lower or "e:" in lower:
            return "DRIVE_E"
        
        # Named locations
        if "desktop" in lower:
            return "DESKTOP"
        if "documents" in lower or "my documents" in lower:
            return "DOCUMENTS"
        if "downloads" in lower:
            return "DOWNLOADS"
        
        # No explicit location
        return None
