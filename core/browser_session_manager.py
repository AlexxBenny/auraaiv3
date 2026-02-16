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
    nav_lock: Lock = field(default_factory=Lock, repr=False)
    
    def is_active(self) -> bool:
        """Check if session is still usable.
        
        INVARIANT: If this returns True, the session is fully executable.
        All three must be alive: browser, context, page.
        """
        try:
            # If a browser handle exists, ensure it's connected.
            # Note: persistent-profile launches may return (None, context, page),
            # so lack of a browser handle alone does NOT imply an inactive session.
            if self.browser:
                try:
                    if not self.browser.is_connected():
                        return False
                except Exception:
                    return False

            # Context must exist
            if not self.context:
                return False

            # Page must exist and not be closed
            if not self.page or self.page.is_closed():
                return False

            # Sanity check: accessing context.pages should not throw
            _ = self.context.pages

            return True
        except Exception:
            return False

    def ensure_page(self) -> bool:
        """Ensure the session has a live page, attempting to heal from context.

        Returns True if the session has a usable page (either already valid or successfully created).
        Returns False if the session cannot be healed (no context/browser).
        """
        try:
            # If we have a context, reconcile cached page against context.pages first.
            if self.context:
                try:
                    pages = list(getattr(self.context, "pages", []) or [])

                    # 1) Cached page is valid only if it's still present in context.pages and not closed
                    if self.page and any(self.page is p for p in pages):
                        try:
                            if not self.page.is_closed():
                                return True
                        except Exception:
                            # Fall through to reconciliation/create
                            pass

                    # 2) Reattach to most-recent live page from context
                    for p in reversed(pages):
                        try:
                            if not p.is_closed():
                                self.page = p
                                logging.info(
                                    f"Healed session {self.session_id}: attached to existing context page"
                                )
                                return True
                        except Exception:
                            # Ignore per-page probe failures and continue
                            continue

                    # 3) No live page found in context — create a new one
                    self.page = self.context.new_page()
                    logging.info(
                        f"Healed session {self.session_id}: created new page from context"
                    )
                    return True
                except Exception as e:
                    logging.info(
                        f"Failed to heal session {self.session_id} from context: {e}"
                    )
                    return False

            # If no context, fall back to cached page check
            if self.page and not getattr(self.page, "is_closed", lambda: False)():
                return True

            # No context and no valid cached page -> unrecoverable
            return False
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
            # Try to ensure the session has a usable page; this will attempt healing via context.new_page()
            try:
                if existing.ensure_page():
                    logging.info(f"Reusing existing session: {session_id}")
                    return existing
                else:
                    logging.info(f"Session {session_id} not recoverable, recreating")
                    self._cleanup_session(session_id)
            except Exception as e:
                logging.info(f"Error while attempting to heal session {session_id}: {e}")
                self._cleanup_session(session_id)
        
        # Create new session
        browser_type = browser_type or config.default_browser
        engine = self._get_engine()
        
        # Resolve user_data_dir with profile support from apps.yaml
        user_data_dir = config.user_data_dir
        
        # If using default/isolated path and browser supports profiles,
        # try to use profile from apps.yaml
        if browser_type in ("chrome", "edge"):
            # Check if user_data_dir is default/isolated or the default path
            is_default_path = (
                user_data_dir in ("auto", "isolated") or
                (isinstance(user_data_dir, str) and "browser_profiles" in user_data_dir)
            )
            
            if is_default_path:
                from core.apps_config import AppsConfig
                
                apps_config = AppsConfig.get()
                profile_name = apps_config.get_browser_profile(browser_type)
                
                if profile_name:
                    # Resolve profile name to actual User Data directory
                    profile_path = BrowserConfig.resolve_browser_profile_path(
                        browser_type, profile_name
                    )
                    if profile_path:
                        user_data_dir = profile_path
                        logging.info(
                            f"Using {browser_type} profile '{profile_name}' from apps.yaml: {profile_path}"
                        )
        
        browser, context, page = engine.launch(
            browser_type=browser_type,
            headless=config.headless,
            user_data_dir=user_data_dir
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
        if session:
            if session.is_active():
                return session
            else:
                self._sessions.pop(session_id, None)
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
    
    def shutdown(self) -> None:
        """Gracefully shut down all sessions and Playwright.
        
        CRITICAL: sync_playwright().start() MUST be matched with .stop().
        Call this on program exit.
        """
        # Close all sessions first
        self.close_all()
        
        # Shut down the engine (stops Playwright)
        if self._engine:
            try:
                self._engine.shutdown()
            except Exception as e:
                logging.warning(f"Error shutting down engine: {e}")
            self._engine = None
        
        logging.info("BrowserSessionManager shutdown complete")
