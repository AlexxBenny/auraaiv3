"""Effects module - Effect-based execution primitives

Phase 1: Schema and verification only (no runtime integration)
"""

from .schema import (
    Effect,
    EffectState,
    EffectPlan,
    Postcondition,
    PostconditionType,
    Precondition,
    Explanation,
)

from .verification import (
    VerificationResult,
    DETERMINISTIC_VERIFIERS,
    get_verifier,
    is_deterministically_verifiable,
    verify_process_running,
    verify_file_exists,
    verify_window_visible,
)

__all__ = [
    # Schema
    "Effect",
    "EffectState",
    "EffectPlan",
    "Postcondition",
    "PostconditionType",
    "Precondition",
    "Explanation",
    # Verification
    "VerificationResult",
    "DETERMINISTIC_VERIFIERS",
    "get_verifier",
    "is_deterministically_verifiable",
    "verify_process_running",
    "verify_file_exists",
    "verify_window_visible",
]
