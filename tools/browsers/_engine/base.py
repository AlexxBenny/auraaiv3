"""Abstract Browser Backend Interface

Private abstraction layer for browser automation.
NOT a tool. NOT resolver-visible. NOT user-configurable directly.

RESPONSIBILITY:
- Define interface for browser operations
- Allow backend swapping without tool changes

DOES NOT:
- Make policy decisions (BrowserConfig's job)
- Track sessions (BrowserSessionManager's job)
- Register with ToolRegistry
"""

from abc import ABC, abstractmethod
from typing import Any, Tuple, Optional


class AbstractBrowserBackend(ABC):
    """Interface for browser automation backends.
    
    Implementations:
    - PlaywrightEngine (playwright.py)
    - SeleniumEngine (future)
    - CDPEngine (future)
    
    All methods are synchronous for AURA compatibility.
    """
    
    @abstractmethod
    def launch(
        self,
        browser_type: str,
        headless: bool = False,
        user_data_dir: str = "auto"
    ) -> Tuple[Any, Any, Any]:
        """Launch a browser and return (browser, context, page).
        
        Args:
            browser_type: chromium | chrome | edge | firefox
            headless: Run in headless mode
            user_data_dir: "auto" | "isolated" | path
            
        Returns:
            (browser_instance, browser_context, page)
        """
        raise NotImplementedError
    
    @abstractmethod
    def navigate(self, page: Any, url: str, timeout_ms: int = 10000) -> bool:
        """Navigate to URL.
        
        Args:
            page: Page object from launch()
            url: Target URL
            timeout_ms: Navigation timeout
            
        Returns:
            True if navigation succeeded
        """
        raise NotImplementedError
    
    @abstractmethod
    def get_url(self, page: Any) -> str:
        """Get current page URL."""
        raise NotImplementedError
    
    @abstractmethod
    def get_title(self, page: Any) -> str:
        """Get current page title."""
        raise NotImplementedError
    
    @abstractmethod
    def close(self, browser: Any) -> None:
        """Close browser instance."""
        raise NotImplementedError
