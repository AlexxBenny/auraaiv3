from dataclasses import dataclass
from typing import List

@dataclass
class ToolCandidate:
    name: str
    score: float = 0.0

def find_candidates(*args, **kwargs) -> List[ToolCandidate]:
    """Return empty candidate list (test stub)."""
    return []

def embedding_available() -> bool:
    return False


