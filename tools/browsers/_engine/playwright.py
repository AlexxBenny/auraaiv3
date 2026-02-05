"""Playwright Browser Backend Implementation

Implements AbstractBrowserBackend using Playwright.
Uses sync API for AURA compatibility.

Dependency: playwright
Setup: playwright install chromium
"""

import logging
from pathlib import Path
from typing import Any, Tuple, Optional
from .base import AbstractBrowserBackend


class PlaywrightEngine(AbstractBrowserBackend):
    """Playwright implementation of browser backend."""
    
    def __init__(self):
        self._playwright = None
        self._sync_playwright = None
    
    def _ensure_playwright(self):
        """Lazily initialize Playwright."""
        if self._playwright is None:
            try:
                from playwright.sync_api import sync_playwright
                self._sync_playwright = sync_playwright()
                self._playwright = self._sync_playwright.start()
                logging.info("Playwright engine initialized")
            except ImportError:
                raise RuntimeError(
                    "Playwright not installed. Run: pip install playwright && playwright install chromium"
                )
    
    def launch(
        self,
        browser_type: str = "chromium",
        headless: bool = False,
        user_data_dir: str = "auto"
    ) -> Tuple[Any, Any, Any]:
        """Launch browser and return (browser, context, page).
        
        Persistent context (user_data_dir is a path):
        - Uses launch_persistent_context()
        - Keeps cookies, logins, sessions across runs
        - Returns (None, context, page) - no separate browser handle
        
        Ephemeral context (auto/isolated):
        - Uses browser.new_context()
        - Fresh profile each time
        - Returns (browser, context, page)
        """
        self._ensure_playwright()
        
        # Map browser type to Playwright browser
        browser_map = {
            "chromium": self._playwright.chromium,
            "chrome": self._playwright.chromium,
            "edge": self._playwright.chromium,
            "firefox": self._playwright.firefox,
        }
        
        browser_launcher = browser_map.get(browser_type)
        if not browser_launcher:
            raise ValueError(f"Unknown browser type: {browser_type}")
        
        # Handle Chrome/Edge channel
        channel = None
        if browser_type == "chrome":
            channel = "chrome"
        elif browser_type == "edge":
            channel = "msedge"
        
        # PERSISTENT CONTEXT: custom path provided
        if user_data_dir not in ("auto", "isolated"):
            profile_path = Path(user_data_dir)
            profile_path.mkdir(parents=True, exist_ok=True)
            
            logging.info(f"Using persistent profile: {profile_path}")
            
            try:
                # Persistent context keeps cookies/logins across sessions
                launch_opts = {
                    "user_data_dir": str(profile_path),
                    "headless": headless,
                }
                if channel:
                    launch_opts["channel"] = channel
                
                context = browser_launcher.launch_persistent_context(**launch_opts)
                
                # Reuse existing page if available, else create new
                page = context.pages[0] if context.pages else context.new_page()
                
                logging.info(f"Launched {browser_type} with persistent profile (headless={headless})")
                return None, context, page  # No separate browser handle
                
            except Exception as e:
                logging.error(f"Failed to launch persistent context: {e}")
                raise RuntimeError(f"Persistent browser launch failed: {e}")
        
        # EPHEMERAL CONTEXT: auto/isolated - fresh profile each time
        launch_opts = {"headless": headless}
        if channel:
            launch_opts["channel"] = channel
        
        try:
            browser = browser_launcher.launch(**launch_opts)
            context = browser.new_context()
            page = context.new_page()
            
            logging.info(f"Launched {browser_type} ephemeral (headless={headless})")
            return browser, context, page
            
        except Exception as e:
            logging.error(f"Failed to launch {browser_type}: {e}")
            raise RuntimeError(f"Browser launch failed: {e}")
    
    def navigate(self, page: Any, url: str, timeout_ms: int = 10000) -> bool:
        """Navigate to URL."""
        try:
            # Ensure URL has protocol
            if not url.startswith(("http://", "https://")):
                url = f"https://{url}"
            
            page.goto(url, timeout=timeout_ms)
            logging.info(f"Navigated to: {url}")
            return True
            
        except Exception as e:
            logging.error(f"Navigation failed: {e}")
            return False
    
    def get_url(self, page: Any) -> str:
        """Get current page URL."""
        return page.url
    
    def get_title(self, page: Any) -> str:
        """Get current page title."""
        return page.title()
    
    def close(self, browser: Any) -> None:
        """Close browser instance."""
        try:
            if browser:
                browser.close()
                logging.info("Browser closed")
        except Exception as e:
            logging.warning(f"Error closing browser: {e}")
    
    def shutdown(self) -> None:
        """Gracefully stop Playwright.
        
        CRITICAL: sync_playwright().start() MUST be matched with .stop().
        """
        if self._playwright:
            try:
                self._playwright.stop()
                logging.info("Playwright engine stopped")
            except Exception as e:
                logging.warning(f"Error stopping Playwright: {e}")
            finally:
                self._playwright = None
                self._sync_playwright = None
    
    def __del__(self):
        """Cleanup on destruction (fallback)."""
        self.shutdown()
