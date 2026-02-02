"""Provider Exception Hierarchy

Defines exceptions for provider-level failures with clear classification:
- ProviderUnavailableError: Infrastructure failures (fallback-safe)
- Other exceptions: Semantic failures (do not fallback)
"""


class ProviderUnavailableError(RuntimeError):
    """Raised when a provider is unreachable or unavailable.
    
    This is an INFRASTRUCTURE failure, not a SEMANTIC failure.
    HybridProvider uses this to decide when to fallback.
    
    THROW when:
    - Connection refused
    - Provider unreachable
    - API key missing/invalid
    - Service unavailable (5xx)
    - Request timeout
    
    DO NOT throw for:
    - Model returned malformed output (raise ValueError)
    - Schema validation failed (raise ValueError)
    - Tool planner made a bad decision (propagate normally)
    """
    
    def __init__(self, provider: str, message: str):
        super().__init__(message)
        self.provider = provider
    
    def __str__(self):
        return f"[{self.provider}] {super().__str__()}"
