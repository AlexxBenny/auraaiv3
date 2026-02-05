"""Browser Session Manager - Single Authority for Browser Sessions

Mirrors PathResolver pattern. Tracks active browser contexts, enforces lifecycle.

RESPONSIBILITY:
- Create/retrieve browser sessions
- Track session_id → page mapping
- Enforce session reuse policy

DOES NOT:
- Decide browser settings (BrowserConfig's job)
- Know about tools
- Perform navigation (tools do that)

GUARDRAIL: Sessions have explicit IDs from Phase 1 onward.
"""

import logging
import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional, Any
from threading import Lock


@dataclass
class BrowserSession:
    """A tracked browser session.
    
    INVARIANT: session_id is always present, even for default sessions.
    """
    session_id: str
    browser_type: str  # chromium, chrome, edge, firefox
    page: Any = None  # Playwright Page object (typed loosely for abstraction)
    context: Any = None  # Playwright BrowserContext
    browser: Any = None  # Playwright Browser instance
    headless: bool = False
    
    def is_active(self) -> bool:
        """Check if session is still usable."""
        if self.page is None:
            return False
        try:
            # Playwright pages have is_closed()
            return not self.page.is_closed()
        except Exception:
            return False


class BrowserSessionManager:
    """Singleton session authority.
    
    Usage:
        manager = BrowserSessionManager.get()
        session = manager.get_or_create()
        page = session.page
        
    Tools should NOT:
        - Launch browsers directly
        - Cache pages locally
        - Close contexts without going through manager
    """
    
    _instance: Optional["BrowserSessionManager"] = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._sessions: Dict[str, BrowserSession] = {}
                    cls._instance._default_session_id: Optional[str] = None
                    cls._instance._engine = None
        return cls._instance
    
    @classmethod
    def get(cls) -> "BrowserSessionManager":
        """Get singleton instance."""
        return cls()
    
    def _get_engine(self):
        """Lazily initialize browser engine."""
        if self._engine is None:
            from tools.browsers._engine.playwright import PlaywrightEngine
            self._engine = PlaywrightEngine()
        return self._engine
    
    def get_or_create(
        self, 
        session_id: Optional[str] = None,
        browser_type: Optional[str] = None
    ) -> BrowserSession:
        """Get existing session or create new one.
        
        Args:
            session_id: Optional specific session to retrieve/create.
                        If None, uses default session (creates if needed).
            browser_type: Override default browser (from BrowserConfig).
        
        Returns:
            BrowserSession with active page.
        """
        from core.browser_config import BrowserConfig
        config = BrowserConfig.get().settings
        
        # Determine session ID
        if session_id is None:
            # Use default session if reuse_session is enabled and one exists
            if config.reuse_session and self._default_session_id:
                session_id = self._default_session_id
            else:
                session_id = str(uuid.uuid4())[:8]
        
        # Check for existing active session
        if session_id in self._sessions:
            existing = self._sessions[session_id]
            if existing.is_active():
                logging.info(f"Reusing existing session: {session_id}")
                return existing
            else:
                logging.info(f"Session {session_id} is stale, recreating")
                self._cleanup_session(session_id)
        
        # Create new session
        browser_type = browser_type or config.default_browser
        engine = self._get_engine()
        
        browser, context, page = engine.launch(
            browser_type=browser_type,
            headless=config.headless,
            user_data_dir=config.user_data_dir
        )
        
        session = BrowserSession(
            session_id=session_id,
            browser_type=browser_type,
            page=page,
            context=context,
            browser=browser,
            headless=config.headless
        )
        
        self._sessions[session_id] = session
        
        # Track as default if reuse is enabled
        if config.reuse_session:
            self._default_session_id = session_id
        
        logging.info(f"Created new browser session: {session_id} ({browser_type})")
        return session
    
    def get_session(self, session_id: str) -> Optional[BrowserSession]:
        """Get specific session by ID (None if not found/inactive)."""
        session = self._sessions.get(session_id)
        if session and session.is_active():
            return session
        return None
    
    def close_session(self, session_id: str) -> bool:
        """Close and untrack a session."""
        if session_id not in self._sessions:
            return False
        
        self._cleanup_session(session_id)
        logging.info(f"Closed browser session: {session_id}")
        return True
    
    def _cleanup_session(self, session_id: str) -> None:
        """Internal cleanup of a session."""
        if session_id not in self._sessions:
            return
        
        session = self._sessions[session_id]
        
        try:
            if session.context:
                session.context.close()
            if session.browser:
                session.browser.close()
        except Exception as e:
            logging.warning(f"Error closing session {session_id}: {e}")
        
        del self._sessions[session_id]
        
        if self._default_session_id == session_id:
            self._default_session_id = None
    
    def close_all(self) -> int:
        """Close all sessions (for cleanup/shutdown)."""
        count = 0
        for session_id in list(self._sessions.keys()):
            if self.close_session(session_id):
                count += 1
        return count
    
    def list_sessions(self) -> Dict[str, Dict[str, Any]]:
        """List all active sessions (for debugging)."""
        return {
            sid: {
                "browser_type": s.browser_type,
                "headless": s.headless,
                "is_active": s.is_active()
            }
            for sid, s in self._sessions.items()
        }
