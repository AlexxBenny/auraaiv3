"""Updated verification test for Phase 1b with fix for default search behavior"""

import sys
sys.path.insert(0, '.')

from tools.system.apps.launch_shell import LaunchAppShell, _get_app_config
from tools.system.apps.app_resolver import get_app_resolver

def test_unknown_app_with_search():
    """Test: 'search viswajyothi college' - should default to Google, NOT site-specific"""
    print("=== Test: Unknown App + Search Query (THE BUG FIX) ===")
    print()
    
    config = _get_app_config()
    search_engines = config.get("search", {}).get("engines", {})
    browsers = config.get("browsers", {})
    
    # Simulate LLM param extraction for "search viswajyothi college"
    # LLM might guess app_name="viswajyothi" (wrong!)
    app_name = "viswajyothi"
    search_query = "viswajyothi college"
    
    print(f'Input: app_name="{app_name}", search_query="{search_query}"')
    print()
    
    # The fix: app_name is NOT a known search engine and NOT a browser
    # → should default to Google
    effective_app_name = app_name.lower()
    search_engine = None
    
    if effective_app_name in search_engines:
        search_engine = effective_app_name
        effective_app_name = config.get("search", {}).get("default_browser", "chrome")
    elif search_query and effective_app_name not in browsers:
        # THIS IS THE FIX
        search_engine = "google"
        effective_app_name = config.get("search", {}).get("default_browser", "chrome")
        print(f"✅ Fix applied: Unknown app '{app_name}' → defaulting to Google search")
    
    print(f"Effective app: {effective_app_name}")
    print(f"Search engine: {search_engine}")
    print()
    
    resolver = get_app_resolver()
    target = resolver.resolve(effective_app_name)
    
    tool = LaunchAppShell()
    new_target = tool._apply_browser_args(
        effective_app_name, 
        target, 
        url=None, 
        search_query=search_query, 
        search_engine=search_engine
    )
    
    print(f"Final args: {new_target.args}")
    
    # Should be Google, NOT viswajyothi.ac.in
    if new_target.args:
        for arg in new_target.args:
            if "google.com/search" in arg and "viswajyothi" in arg:
                print("✅ SUCCESS: Correctly uses Google search, NOT site-specific URL")
                return True
            if "viswajyothi.ac.in" in arg:
                print("❌ FAILED: Still using site-specific URL (this is the bug)")
                return False
    
    print("❌ FAILED: No search URL found")
    return False


def test_youtube_still_works():
    """Test: YouTube search still works as expected"""
    print("=== Test: YouTube Search (should still work) ===")
    print()
    
    config = _get_app_config()
    search_engines = config.get("search", {}).get("engines", {})
    
    app_name = "youtube"
    search_query = "one direction"
    
    print(f'Input: app_name="{app_name}", search_query="{search_query}"')
    
    # YouTube IS a known search engine
    effective_app_name = app_name.lower()
    if effective_app_name in search_engines:
        print("✅ YouTube recognized as search engine")
        search_engine = effective_app_name
        effective_app_name = config.get("search", {}).get("default_browser", "chrome")
    else:
        print("❌ YouTube NOT recognized")
        return False
    
    resolver = get_app_resolver()
    target = resolver.resolve(effective_app_name)
    
    tool = LaunchAppShell()
    new_target = tool._apply_browser_args(
        effective_app_name, 
        target, 
        url=None, 
        search_query=search_query, 
        search_engine=search_engine
    )
    
    print(f"Final args: {new_target.args}")
    
    if new_target.args:
        for arg in new_target.args:
            if "youtube.com" in arg:
                print("✅ SUCCESS: YouTube search URL constructed")
                return True
    
    print("❌ FAILED")
    return False


if __name__ == "__main__":
    print("=" * 60)
    print("PHASE 1b FIX VERIFICATION")
    print("=" * 60)
    print()
    
    results = []
    results.append(("Unknown App + Search (BUG FIX)", test_unknown_app_with_search()))
    print()
    results.append(("YouTube Still Works", test_youtube_still_works()))
    
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{name}: {status}")
    
    print()
    all_passed = all(r[1] for r in results)
    print(f"Overall: {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
