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

from core.location_config import LocationConfig


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
        Delegates to LocationConfig for all anchor definitions.
        
        Args:
            context: Session context with cwd. If None, falls back to Path.cwd()
                     but logs a warning (this should only happen in tests).
        
        Returns:
            Dict of anchor name → Path
        """
        return LocationConfig.get().get_all_anchors(context)
    
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
        
        # INVARIANT CHECK: Detect targets that already contain parent path segments
        # This indicates double-application bug (containment applied twice)
        if parent_resolved is not None:
            # When inheriting from parent, raw_path should be just a name
            # NOT a full path like "space/galaxy" or "D:\space\galaxy"
            if "/" in raw_path or ("\\" in raw_path and not Path(raw_path).is_absolute()):
                logging.warning(
                    f"PathResolver: raw_path contains separators before resolution: '{raw_path}'. "
                    f"This may cause double-application. Target should be just the name."
                )
        
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
        
        Delegates to LocationConfig for alias matching.
        
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
        return LocationConfig.get().infer_anchor_from_text(user_input)
