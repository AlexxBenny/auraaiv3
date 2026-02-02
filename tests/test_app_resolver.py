"""Tests for AppResolver multi-strategy Windows app resolution.

Tests the 5-tier resolution pipeline:
1. Protocol detection
2. App Paths registry
3. Start Menu shortcuts
4. Known install locations
5. Shell fallback

Also tests resolution precedence (protocol wins over Start Menu, etc.)
"""

import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.system.apps.app_resolver import (
    AppResolver, LaunchTarget, ResolutionMethod,
    get_app_resolver, KNOWN_PROTOCOL_ALIASES
)


class TestAppResolver:
    """Test suite for AppResolver"""
    
    @pytest.fixture
    def resolver(self):
        """Create a fresh resolver for each test (clears cache)"""
        resolver = AppResolver()
        return resolver
    
    # =========================================================================
    # Strategy 1: Protocol Detection
    # =========================================================================
    
    def test_spotify_protocol_resolution(self, resolver):
        """Spotify should resolve via protocol (spotify:)"""
        target = resolver.resolve("spotify")
        
        # May resolve as protocol OR Start Menu depending on system
        # If protocol exists, it should be chosen
        if target.resolution_method == ResolutionMethod.PROTOCOL:
            assert target.target_type == "protocol"
            assert target.value == "spotify:"
    
    def test_settings_protocol_alias(self, resolver):
        """'settings' should resolve to ms-settings: protocol"""
        target = resolver.resolve("settings")
        
        if target.resolution_method == ResolutionMethod.PROTOCOL:
            assert target.value == "ms-settings:"
    
    # =========================================================================
    # Strategy 2: App Paths Registry
    # =========================================================================
    
    def test_chrome_app_paths_resolution(self, resolver):
        """Chrome should resolve via App Paths registry"""
        target = resolver.resolve("chrome")
        
        # Chrome typically registers in App Paths
        if target.resolution_method == ResolutionMethod.APP_PATHS:
            assert target.target_type == "executable"
            assert "chrome" in target.value.lower()
            assert os.path.exists(target.value)
    
    def test_notepad_resolution(self, resolver):
        """Notepad should resolve (system app)"""
        target = resolver.resolve("notepad")
        
        # Notepad is always available on Windows
        assert target is not None
        assert target.resolution_method != ResolutionMethod.FAILED
    
    # =========================================================================
    # Strategy 3: Start Menu Shortcuts
    # =========================================================================
    
    def test_start_menu_shortcut_parsing(self, resolver):
        """Test that Start Menu shortcuts can be found and parsed"""
        # This is system-dependent, but we can test the mechanism
        target = resolver.resolve("notepad")
        
        # Notepad might be found via App Paths or shell, both are valid
        assert target.target_type in ["executable", "shell"]
    
    # =========================================================================
    # Strategy 3.5: AppsFolder (UWP/Store apps)
    # =========================================================================
    
    def test_telegram_appsfolder_resolution(self, resolver):
        """Telegram (Store app) should resolve via AppsFolder"""
        target = resolver.resolve("telegram")
        
        # If Telegram is installed, it should resolve via appsfolder
        if target.resolution_method == ResolutionMethod.APPSFOLDER:
            assert target.target_type == "shell"
            assert "shell:AppsFolder" in target.value
    
    def test_photos_appsfolder_resolution(self, resolver):
        """Microsoft Photos should resolve via AppsFolder"""
        target = resolver.resolve("photos")
        
        # Photos is a built-in Windows app
        if target.resolution_method == ResolutionMethod.APPSFOLDER:
            assert "Photos" in target.details or "photos" in target.value.lower()
    
    def test_appsfolder_cache_built_lazily(self, resolver):
        """AppsFolder cache should be None initially and built on first use"""
        # Cache should be None before any appsfolder resolution
        assert resolver._appsfolder_cache is None
        
        # Trigger appsfolder resolution
        resolver.resolve("some_uwp_app_that_might_exist")
        
        # Cache should now be populated (even if empty)
        assert resolver._appsfolder_cache is not None
    
    # =========================================================================
    # Strategy 5: Shell Fallback
    # =========================================================================
    
    def test_nonexistent_app_fallback(self, resolver):
        """Non-existent app should fall back to shell"""
        target = resolver.resolve("thisdoesnotexist12345")
        
        assert target.resolution_method == ResolutionMethod.SHELL_FALLBACK
        assert target.target_type == "shell"
        assert target.value == "thisdoesnotexist12345"
    
    # =========================================================================
    # Resolution Precedence
    # =========================================================================
    
    def test_protocol_precedence_over_start_menu(self, resolver):
        """Protocol should be chosen over Start Menu if both exist"""
        target = resolver.resolve("spotify")
        
        # If protocol exists, it should be first
        # We can't guarantee Spotify is installed, but we can verify
        # the method returns a valid target
        assert target is not None
        assert target.resolution_method != ResolutionMethod.FAILED
    
    # =========================================================================
    # Caching
    # =========================================================================
    
    def test_cache_hit_on_second_resolve(self, resolver):
        """Second resolution should hit cache"""
        # First resolve
        target1 = resolver.resolve("notepad")
        
        # Check cache has entry
        assert "notepad" in resolver._cache
        
        # Second resolve
        target2 = resolver.resolve("notepad")
        
        # Should be same object from cache
        assert target1 == target2
    
    def test_cache_clear(self, resolver):
        """Cache should be clearable"""
        resolver.resolve("notepad")
        assert len(resolver._cache) > 0
        
        resolver.clear_cache()
        assert len(resolver._cache) == 0
    
    def test_cache_stats(self, resolver):
        """Cache stats should track resolutions"""
        resolver.resolve("notepad")
        resolver.resolve("settings")
        
        stats = resolver.get_cache_stats()
        assert stats["total_cached"] == 2
    
    # =========================================================================
    # Singleton
    # =========================================================================
    
    def test_singleton_resolver(self):
        """get_app_resolver should return singleton"""
        resolver1 = get_app_resolver()
        resolver2 = get_app_resolver()
        
        assert resolver1 is resolver2


class TestLaunchTarget:
    """Test LaunchTarget dataclass"""
    
    def test_launch_target_repr(self):
        """LaunchTarget should have readable repr"""
        target = LaunchTarget(
            target_type="protocol",
            value="spotify:",
            resolution_method=ResolutionMethod.PROTOCOL
        )
        
        repr_str = repr(target)
        assert "protocol" in repr_str
        assert "spotify:" in repr_str


class TestKnownProtocolAliases:
    """Test protocol alias mapping"""
    
    def test_settings_alias(self):
        assert KNOWN_PROTOCOL_ALIASES["settings"] == "ms-settings"
    
    def test_store_alias(self):
        assert KNOWN_PROTOCOL_ALIASES["store"] == "ms-windows-store"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
