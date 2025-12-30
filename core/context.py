"""Session context management - strict, no AI here"""

from typing import Dict, Any, Optional
from datetime import datetime


class SessionContext:
    """Strict session context - working memory only
    
    This is NOT persistent memory - that's in memory/ modules
    """
    
    def __init__(self):
        self.session_id = datetime.now().isoformat()
        self.start_time = datetime.now()
        self.command_count = 0
        self.current_task: Optional[Dict[str, Any]] = None
        self.last_result: Optional[Dict[str, Any]] = None
        self.metadata: Dict[str, Any] = {}
    
    def start_task(self, task: Dict[str, Any]):
        """Start a new task"""
        self.current_task = task
        self.command_count += 1
    
    def complete_task(self, result: Dict[str, Any]):
        """Complete current task"""
        self.last_result = result
        self.current_task = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Export context as dictionary"""
        return {
            "session_id": self.session_id,
            "start_time": self.start_time.isoformat(),
            "command_count": self.command_count,
            "current_task": self.current_task,
            "last_result": self.last_result,
            "metadata": self.metadata
        }

