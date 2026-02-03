"""Centralized file system safety rules.

EXECUTOR-LEVEL enforcement. LLM cannot override.

This module defines:
- Protected directories that cannot be modified/deleted
- Protected file extensions
- Path normalization and validation functions

All file tools MUST import and use these validators.
"""

from pathlib import Path
from typing import Set, Tuple

# ============================================================================
# PROTECTED PATHS (Cannot be modified or deleted)
# ============================================================================

# System directories - absolute protection
PROTECTED_DIRECTORIES: Set[Path] = {
    # Windows Core
    Path("C:/Windows"),
    Path("C:/Windows/System32"),
    Path("C:/Windows/SysWOW64"),
    Path("C:/Program Files"),
    Path("C:/Program Files (x86)"),
    Path("C:/ProgramData"),
    Path("C:/$Recycle.Bin"),
    
    # Boot/Recovery
    Path("C:/Recovery"),
    Path("C:/System Volume Information"),
    Path("C:/Boot"),
    
    # EFI
    Path("C:/EFI"),
}

# User-level protected paths (expanded at runtime in _get_user_protected_paths)
def _get_user_protected_paths() -> Set[Path]:
    """Get user-specific protected paths."""
    home = Path.home()
    return {
        home / "AppData",
        home / "AppData/Local",
        home / "AppData/LocalLow",
        home / "AppData/Roaming",
        home / "NTUSER.DAT",
    }

# File extensions that cannot be deleted/modified
PROTECTED_EXTENSIONS: Set[str] = {
    ".sys",   # System drivers
    ".dll",   # Dynamic libraries
    ".exe",   # Executables in protected dirs
    ".reg",   # Registry files
    ".msi",   # Installer packages
    ".cat",   # Security catalogs
    ".inf",   # Setup information
}

# Maximum file size to read (prevent memory exhaustion)
MAX_READ_SIZE_MB = 50
MAX_READ_SIZE_BYTES = MAX_READ_SIZE_MB * 1024 * 1024

# ============================================================================
# PATH NORMALIZATION
# ============================================================================

def normalize_path(path: str) -> Path:
    """Convert path string to Path object.
    
    This function handles:
    - ~ expansion for home directory
    - String to Path conversion
    
    NOTE: This function does NOT call .resolve() anymore.
    Path resolution is now the sole responsibility of PathResolver.
    Paths passed to tools should already be absolute.
    
    If a relative path is passed, we log a warning but still expand ~.
    
    Args:
        path: Path string (should be absolute from PathResolver)
        
    Returns:
        Path object
    """
    p = Path(path).expanduser()
    
    # Warn if not absolute - indicates upstream issue
    if not p.is_absolute():
        import logging
        logging.warning(
            f"normalize_path received relative path: '{path}'. "
            "Paths should be resolved by PathResolver before reaching tools."
        )
    
    return p


# ============================================================================
# PROTECTION CHECKS
# ============================================================================

def is_protected_path(path: Path) -> bool:
    """Check if path is protected from modification.
    
    Args:
        path: Already-normalized Path object
        
    Returns:
        True if path is protected
    """
    resolved = path.resolve()
    
    # Get all protected paths (system + user)
    all_protected = PROTECTED_DIRECTORIES | _get_user_protected_paths()
    
    # Check if path IS a protected directory
    for protected in all_protected:
        try:
            protected_resolved = protected.resolve()
            if resolved == protected_resolved:
                return True
        except (OSError, ValueError):
            continue
    
    # Check if path is INSIDE a protected directory
    for protected in all_protected:
        try:
            protected_resolved = protected.resolve()
            resolved.relative_to(protected_resolved)
            return True  # Path is inside protected directory
        except (ValueError, OSError):
            continue
    
    return False


def is_protected_extension(path: Path) -> bool:
    """Check if file extension is protected.
    
    Args:
        path: Path object
        
    Returns:
        True if extension is protected
    """
    return path.suffix.lower() in PROTECTED_EXTENSIONS


# ============================================================================
# VALIDATION FUNCTIONS (Use these in tools)
# ============================================================================

def validate_read_path(path: Path) -> Tuple[bool, str]:
    """Validate path is safe to read.
    
    Reading is generally safe, but we still check:
    - File exists
    - File size is reasonable
    
    Args:
        path: Normalized Path object
        
    Returns:
        (is_valid, error_message)
    """
    if not path.exists():
        return False, f"File does not exist: {path}"
    
    if path.is_file():
        try:
            size = path.stat().st_size
            if size > MAX_READ_SIZE_BYTES:
                return False, f"File too large ({size / 1024 / 1024:.1f}MB > {MAX_READ_SIZE_MB}MB limit)"
        except OSError as e:
            return False, f"Cannot access file: {e}"
    
    return True, ""


def validate_write_path(path: Path) -> Tuple[bool, str]:
    """Validate path is safe to write/modify.
    
    Args:
        path: Normalized Path object
        
    Returns:
        (is_valid, error_message)
    """
    if is_protected_path(path):
        return False, f"Protected path: {path}"
    
    if is_protected_extension(path):
        return False, f"Protected extension: {path.suffix}"
    
    return True, ""


def validate_delete_path(path: Path) -> Tuple[bool, str]:
    """Validate path is safe to delete.
    
    More restrictive than write validation.
    
    Args:
        path: Normalized Path object
        
    Returns:
        (is_valid, error_message)
    """
    if is_protected_path(path):
        return False, f"Cannot delete protected path: {path}"
    
    if is_protected_extension(path):
        return False, f"Cannot delete protected file type: {path.suffix}"
    
    # Don't allow deleting root drives
    if path.parent == path:  # Is a root (C:\, D:\, etc.)
        return False, f"Cannot delete drive root: {path}"
    
    return True, ""


def validate_parent_creation(path: Path) -> Tuple[bool, str]:
    """Validate that creating parent directories is safe.
    
    Called BEFORE creating parents, to ensure we don't
    create directories in protected locations.
    
    Args:
        path: Final target path (parents will be created for this)
        
    Returns:
        (is_valid, error_message)
    """
    # Check each parent in the chain
    for parent in path.parents:
        if is_protected_path(parent):
            return False, f"Cannot create directories in protected path: {parent}"
    
    return True, ""
