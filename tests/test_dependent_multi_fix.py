"""Verification tests for dependent multi-step goal fixes

Tests:
1. QueryClassifier classifies "create folder and file inside" as multi
2. Stage 2 domain lock prevents hallucinated tool selection
3. Multi-JSON detection rejects multi-tool responses
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_query_classifier_dependency_detection():
    """Test that dependent commands are classified as multi."""
    print("\n" + "="*60)
    print("TEST 1: QueryClassifier Dependency Detection")
    print("="*60)
    
    from agents.query_classifier import QueryClassifier
    
    classifier = QueryClassifier()
    
    # These MUST be multi (dependent sequences)
    dependent_cases = [
        "create a folder named nvidia and create an empty text file inside it",
        "create folder projects and put readme inside it",
        "make a new folder called test then add a document to it",
        "create a spreadsheet and add data to it",
    ]
    
    # These should be single (one goal)
    single_cases = [
        "open youtube and search nvidia",
        "take a screenshot",
        "mute the volume",
        "open chrome and go to google.com",
    ]
    
    # These should be multi (independent)
    independent_multi_cases = [
        "open chrome and open spotify",
        "mute volume and take a screenshot",
    ]
    
    all_pass = True
    
    print("\nDependent (must be MULTI):")
    for case in dependent_cases:
        # Use syntactic check directly to avoid LLM calls
        has_dep = classifier._has_dependency_pattern(case)
        status = "[OK]" if has_dep else "[FAIL]"
        print(f"  {status} '{case[:50]}...'")
        if not has_dep:
            all_pass = False
    
    print("\nSingle (must stay SINGLE):")
    for case in single_cases:
        has_dep = classifier._has_dependency_pattern(case)
        has_multi = classifier._has_independent_multi_pattern(case)
        is_single = not has_dep and not has_multi
        status = "[OK]" if is_single else "[FAIL]"
        print(f"  {status} '{case[:50]}...'")
        if not is_single:
            all_pass = False
    
    print("\nIndependent Multi:")
    for case in independent_multi_cases:
        has_multi = classifier._has_independent_multi_pattern(case)
        status = "[OK]" if has_multi else "[FAIL]"
        print(f"  {status} '{case[:50]}...'")
        if not has_multi:
            all_pass = False
    
    return all_pass


def test_stage2_domain_lock():
    """Test that Stage 2 is domain-locked."""
    print("\n" + "="*60)
    print("TEST 2: Stage 2 Domain Lock")
    print("="*60)
    
    from core.tool_resolver import INTENT_STAGE2_ALLOWED_DOMAINS, INTENT_DISALLOWED_DOMAINS
    
    # Check file_operation is locked to files.*
    file_allowed = INTENT_STAGE2_ALLOWED_DOMAINS.get("file_operation")
    file_correct = file_allowed == ["files"]
    print(f"  file_operation allowed domains: {file_allowed}")
    print(f"  [{'OK' if file_correct else 'FAIL'}] file_operation locked to files.*")
    
    # Check browser_control is locked to system.apps.launch
    browser_allowed = INTENT_STAGE2_ALLOWED_DOMAINS.get("browser_control")
    browser_correct = browser_allowed == ["system.apps.launch"]
    print(f"  browser_control allowed domains: {browser_allowed}")
    print(f"  [{'OK' if browser_correct else 'FAIL'}] browser_control locked to system.apps.launch")
    
    # Check information_query has empty list (no Stage 2)
    info_allowed = INTENT_STAGE2_ALLOWED_DOMAINS.get("information_query")
    info_correct = info_allowed == []
    print(f"  information_query allowed domains: {info_allowed}")
    print(f"  [{'OK' if info_correct else 'FAIL'}] information_query blocks Stage 2")
    
    return file_correct and browser_correct and info_correct


def test_multi_json_detection():
    """Test that multi-JSON responses are rejected."""
    print("\n" + "="*60)
    print("TEST 3: Multi-JSON Detection")
    print("="*60)
    
    from models.providers.base import BaseLLMProvider
    
    # Create a mock provider for testing
    class MockProvider(BaseLLMProvider):
        def generate(self, prompt, schema=None):
            return {}
    
    provider = MockProvider()
    
    # Single JSON should work
    single_json = '{"tool": "files.create_folder", "params": {"path": "test"}}'
    try:
        result = provider._parse_response(single_json)
        single_ok = result.get("tool") == "files.create_folder"
        print(f"  [OK] Single JSON parsed correctly")
    except Exception as e:
        single_ok = False
        print(f"  [FAIL] Single JSON failed: {e}")
    
    # Multi-JSON should fail
    multi_json = '''{"tool": "files.create_folder", "params": {"path": "nvidia"}}
{"tool": "files.create_file", "params": {"path": "nvidia/test.txt"}}'''
    
    try:
        result = provider._parse_response(multi_json)
        multi_ok = False
        print(f"  [FAIL] Multi-JSON was accepted (should reject)")
    except ValueError as e:
        if "Multi-JSON detected" in str(e):
            multi_ok = True
            print(f"  [OK] Multi-JSON correctly rejected")
        else:
            multi_ok = False
            print(f"  [FAIL] Wrong error: {e}")
    except Exception as e:
        multi_ok = False
        print(f"  [FAIL] Unexpected error: {e}")
    
    return single_ok and multi_ok


if __name__ == "__main__":
    print("\n" + "#"*60)
    print("# DEPENDENT MULTI-STEP GOAL FIX VERIFICATION")
    print("#"*60)
    
    results = []
    results.append(("QueryClassifier dependency", test_query_classifier_dependency_detection()))
    results.append(("Stage 2 domain lock", test_stage2_domain_lock()))
    results.append(("Multi-JSON detection", test_multi_json_detection()))
    
    print("\n" + "="*60)
    print("VERIFICATION SUMMARY")
    print("="*60)
    
    all_pass = True
    for name, passed in results:
        status = "[OK] PASS" if passed else "[X] FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_pass = False
    
    print("\n" + "="*60)
    if all_pass:
        print("ALL FIXES VERIFIED")
    else:
        print("SOME FIXES NEED WORK")
    print("="*60)
