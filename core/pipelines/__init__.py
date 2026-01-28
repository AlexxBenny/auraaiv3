"""Pipelines package for JARVIS architecture."""

from .info_pipeline import handle_information
from .action_pipeline import handle_action
from .multi_pipeline import handle_multi
from .fallback_pipeline import handle_fallback

__all__ = [
    "handle_information",
    "handle_action", 
    "handle_multi",
    "handle_fallback"
]
