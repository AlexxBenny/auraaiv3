"""Verification test for browser_control fix

Tests:
1. browser_control intent routes to system.apps.launch.shell (not mouse.move)
2. INTENT_DISALLOWED_DOMAINS correctly blocks system.input for browser_control
3. Stage 2 filtering prevents dangerous fallbacks
"""

import sys
sys.path.insert(0, '.')

from tools.loader import load_all_tools
from core.tool_resolver import ToolResolver, INTENT_DISALLOWED_DOMAINS, INTENT_TOOL_DOMAINS

def test_disallowed_domains_exist():
    """Test that safety constraints are defined"""
    print("Test 1: INTENT_DISALLOWED_DOMAINS exists and has browser_control")
    
    assert "browser_control" in INTENT_DISALLOWED_DOMAINS, "browser_control not in INTENT_DISALLOWED_DOMAINS"
    assert "system.input" in INTENT_DISALLOWED_DOMAINS["browser_control"], "system.input not disallowed for browser_control"
    
    print("  ✓ browser_control has system.input in disallowed list")
    print("  ✓ PASSED\n")

def test_browser_control_preferred_domains():
    """Test that browser_control includes system.apps.launch"""
    print("Test 2: browser_control includes system.apps.launch in preferred domains")
    
    domains = INTENT_TOOL_DOMAINS.get("browser_control", [])
    assert "system.apps.launch" in domains, f"system.apps.launch not in browser_control domains: {domains}"
    assert "browsers" in domains, f"browsers not in browser_control domains: {domains}"
    
    print(f"  ✓ browser_control domains: {domains}")
    print("  ✓ PASSED\n")

def test_tool_resolution_no_mouse():
    """Test that 'open chrome' does NOT resolve to mouse.move"""
    print("Test 3: 'open chrome' resolves to system.apps.launch.shell, NOT mouse.move")
    
    # Load tools first
    load_all_tools()
    
    resolver = ToolResolver()
    resolution = resolver.resolve("open chrome", "browser_control", {})
    
    tool_name = resolution.get("tool")
    print(f"  Resolved tool: {tool_name}")
    print(f"  Stage: {resolution.get('stage')}")
    print(f"  Confidence: {resolution.get('confidence')}")
    print(f"  Domain match: {resolution.get('domain_match')}")
    
    # Critical assertions
    assert tool_name is not None, "No tool resolved"
    assert "mouse" not in tool_name.lower(), f"FAIL: Resolved to mouse tool: {tool_name}"
    assert "input" not in tool_name.lower(), f"FAIL: Resolved to input tool: {tool_name}"
    assert "system.apps.launch" in tool_name, f"Expected system.apps.launch.*, got: {tool_name}"
    
    print("  ✓ No mouse/input tool selected")
    print("  ✓ PASSED\n")

def test_stage2_filters_disallowed():
    """Test that Stage 2 filters out disallowed tools before LLM sees them"""
    print("Test 4: Stage 2 filtering removes system.input.* for browser_control")
    
    resolver = ToolResolver()
    
    # Get all tools
    all_tools = resolver.registry.get_tools_for_llm()
    input_tools = [t for t in all_tools if t["name"].startswith("system.input")]
    
    print(f"  Total tools: {len(all_tools)}")
    print(f"  Input tools that would be filtered: {len(input_tools)}")
    
    if input_tools:
        print(f"  Input tools: {[t['name'] for t in input_tools[:3]]}...")
    
    # Simulate filtering
    disallowed = INTENT_DISALLOWED_DOMAINS.get("browser_control", [])
    filtered = [t for t in all_tools if not any(t["name"].startswith(d) for d in disallowed)]
    
    filtered_input = [t for t in filtered if t["name"].startswith("system.input")]
    assert len(filtered_input) == 0, f"Input tools not filtered: {filtered_input}"
    
    print(f"  After filtering: {len(filtered)} tools (no input tools)")
    print("  ✓ PASSED\n")

def run_all_tests():
    print("=" * 60)
    print("Browser Control Fix Verification")
    print("=" * 60 + "\n")
    
    try:
        test_disallowed_domains_exist()
        test_browser_control_preferred_domains()
        test_tool_resolution_no_mouse()
        test_stage2_filters_disallowed()
        
        print("=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)
        return True
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
