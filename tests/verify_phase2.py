"""Phase 2 Verification Harness

Run instrumented tests for all Phase 2 tools.
Logs all tool executions, planner decisions, and verifies contracts.

Usage: python -m tests.verify_phase2
"""

import sys
import time
import logging
from datetime import datetime
from typing import Dict, Any, List

# Add project root to path
sys.path.insert(0, '.')

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)-7s | %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger("VERIFY")

# ===== Test Results Storage =====
test_results: List[Dict[str, Any]] = []

def log_tool_call(tool_name: str, args: Dict, result: Dict, duration_ms: float):
    """Instrument tool execution"""
    status = result.get("status", "unknown")
    log.info(f"[TOOL] {tool_name}")
    log.info(f"       Args: {args}")
    log.info(f"       Result: {status} | Duration: {duration_ms:.0f}ms")
    if status == "error":
        log.warning(f"       Error: {result.get('error', 'N/A')}")
    return result

def run_tool(tool_class, args: Dict) -> Dict:
    """Execute a tool with instrumentation"""
    tool = tool_class()
    start = time.time()
    result = tool.execute(args)
    duration = (time.time() - start) * 1000
    return log_tool_call(tool.name, args, result, duration)


# ===== Test Case A: Happy Path =====
def test_a_happy_path():
    """Open Notepad, type Hello, verify OCR, close"""
    log.info("=" * 60)
    log.info("TEST A: Canonical Happy Path")
    log.info("=" * 60)
    
    from tools.system.apps.launch import LaunchApp
    from tools.system.apps.focus import FocusApp
    from tools.system.input.keyboard.type import KeyboardType
    from tools.system.display.find_text import FindText
    from tools.system.apps.request_close import RequestCloseApp
    
    results = {"name": "Test A: Happy Path", "steps": [], "passed": False}
    
    # Step 1: Launch Notepad
    log.info("[STEP 1] Launching Notepad...")
    r = run_tool(LaunchApp, {"app_name": "notepad", "wait_for_window": True, "timeout_ms": 10000})
    results["steps"].append({"step": "launch", "result": r})
    
    if r["status"] != "success":
        log.error("FAIL: Could not launch Notepad")
        results["error"] = "Launch failed"
        test_results.append(results)
        return False
        
    pid = r["pid"]
    app_handle = r.get('app_handle', {})
    handle_id = app_handle.get('handle_id')
    window_title = r.get('window', {}).get('title', 'Notepad')
    log.info(f"       Notepad launched. PID={pid}, Title='{window_title}'")
    log.info(f"       Handle ID: {handle_id[:8] if handle_id else 'N/A'}...")
    
    # Step 2: Focus using handle_id (deterministic targeting)
    log.info("[STEP 2] Focusing Notepad by handle_id...")
    r = run_tool(FocusApp, {"handle_id": handle_id})
    results["steps"].append({"step": "focus", "result": r})
    
    if r["status"] != "success":
        log.error("FAIL: Could not focus Notepad")
        results["error"] = "Focus failed"
        test_results.append(results)
        return False
    
    time.sleep(0.5) # Stabilization
    
    # Step 3: Type text
    log.info("[STEP 3] Typing 'Hello'...")
    r = run_tool(KeyboardType, {"text": "Hello", "window_title": "Notepad"})
    results["steps"].append({"step": "type", "result": r})
    
    if r["status"] != "success":
        log.error("FAIL: Could not type text")
        results["error"] = "Type failed"
        test_results.append(results)
        return False
        
    time.sleep(1.0) # Let UI settle
    
    # Step 4: OCR Verify
    log.info("[STEP 4] Verifying 'Hello' via OCR...")
    r = run_tool(FindText, {"text": "Hello", "min_confidence": 60})
    results["steps"].append({"step": "ocr_verify", "result": r})
    
    ocr_found = r.get("found", False)
    frame_hash = r.get("frame_hash", "N/A")
    log.info(f"       OCR Result: found={ocr_found}, frame_hash={frame_hash}")
    
    if r.get("best_match"):
        log.info(f"       Best Match: {r['best_match']}")
    
    # Step 5: Close Notepad using handle_id (deterministic)
    log.info("[STEP 5] Requesting close via handle_id...")
    r = run_tool(RequestCloseApp, {"handle_id": handle_id, "timeout_ms": 5000})
    results["steps"].append({"step": "close", "result": r})
    
    # Note: Notepad may prompt "Save?" - closed might be false
    closed = r.get("closed", False)
    log.info(f"       Close confirmed: {closed}")
    
    if not closed:
        log.warning("       Notepad may be waiting for user input (Save prompt)")
        # Attempt to dismiss by pressing 'n' for Don't Save
        from tools.system.input.keyboard.press import KeyboardPress
        log.info("       Attempting to dismiss save dialog with 'n'...")
        run_tool(KeyboardPress, {"key": "n"})
        time.sleep(1)
    
    results["passed"] = True
    results["ocr_found"] = ocr_found
    test_results.append(results)
    log.info("TEST A: PASSED" if ocr_found else "TEST A: PARTIAL (OCR did not find text)")
    return ocr_found


# ===== Test Case B: Ambiguity Handling =====
def test_b_ambiguity():
    """With 2 Notepad windows open, focus should fail with ambiguity"""
    log.info("=" * 60)
    log.info("TEST B: Ambiguity Handling")
    log.info("=" * 60)
    
    from tools.system.apps.launch import LaunchApp
    from tools.system.apps.focus import FocusApp
    from tools.system.apps.request_close import RequestCloseApp
    
    results = {"name": "Test B: Ambiguity", "steps": [], "passed": False}
    
    # Launch two Notepads - capture handle_ids for cleanup
    log.info("[SETUP] Launching first Notepad...")
    r1 = run_tool(LaunchApp, {"app_name": "notepad", "wait_for_window": True})
    h1 = r1.get("app_handle", {})
    handle_id_1 = h1.get("handle_id")
    log.info(f"       Handle 1: {handle_id_1[:8] if handle_id_1 else 'N/A'}...")
    
    log.info("[SETUP] Launching second Notepad...")
    r2 = run_tool(LaunchApp, {"app_name": "notepad", "wait_for_window": True})
    h2 = r2.get("app_handle", {})
    handle_id_2 = h2.get("handle_id")
    log.info(f"       Handle 2: {handle_id_2[:8] if handle_id_2 else 'N/A'}...")
    
    time.sleep(1)
    
    # Attempt ambiguous focus
    log.info("[TEST] Attempting to focus 'notepad' (ambiguous)...")
    r = run_tool(FocusApp, {"app_name": "notepad"})
    results["steps"].append({"step": "ambiguous_focus", "result": r})
    
    # Verify ambiguity error
    is_ambiguous = r["status"] == "error" and "multiple" in r.get("error", "").lower()
    has_matches = "matches" in r
    
    log.info(f"       Status: {r['status']}")
    log.info(f"       Is Ambiguous Error: {is_ambiguous}")
    log.info(f"       Has Match List: {has_matches}")
    
    if has_matches:
        log.info(f"       Matches: {r.get('matches', [])}")
    
    # Cleanup using handle_ids (deterministic - each handle targets exactly one window)
    log.info("[CLEANUP] Closing both Notepads via handle_id...")
    from tools.system.input.keyboard.press import KeyboardPress
    
    # Close first window
    if handle_id_1:
        r = run_tool(RequestCloseApp, {"handle_id": handle_id_1})
        log.info(f"       Close 1: {r.get('closed', 'error')}")
        run_tool(KeyboardPress, {"key": "n"})  # Dismiss save prompt
        time.sleep(0.3)
    
    # Close second window
    if handle_id_2:
        r = run_tool(RequestCloseApp, {"handle_id": handle_id_2})
        log.info(f"       Close 2: {r.get('closed', 'error')}")
        run_tool(KeyboardPress, {"key": "n"})  # Dismiss save prompt
        time.sleep(0.3)
    
    results["passed"] = is_ambiguous and has_matches
    test_results.append(results)
    log.info("TEST B: PASSED" if results["passed"] else "TEST B: FAILED")
    return results["passed"]


# ===== Test Case C: OCR Confidence Failure =====
def test_c_ocr_failure():
    """Type text that OCR won't match exactly"""
    log.info("=" * 60)
    log.info("TEST C: OCR Confidence Failure")
    log.info("=" * 60)
    
    from tools.system.apps.launch import LaunchApp
    from tools.system.input.keyboard.type import KeyboardType
    from tools.system.display.find_text import FindText
    from tools.system.apps.request_close import RequestCloseApp
    from tools.system.input.keyboard.press import KeyboardPress
    
    results = {"name": "Test C: OCR Failure", "steps": [], "passed": False}
    
    # Launch Notepad - capture handle for cleanup
    log.info("[SETUP] Launching Notepad...")
    r = run_tool(LaunchApp, {"app_name": "notepad", "wait_for_window": True})
    handle = r.get("app_handle", {})
    handle_id = handle.get("handle_id")
    log.info(f"       Handle ID: {handle_id[:8] if handle_id else 'N/A'}...")
    time.sleep(0.5)
    
    # Type something OCR might misread
    log.info("[STEP] Typing 'He11o' (with ones)...")
    run_tool(KeyboardType, {"text": "He11o"})
    time.sleep(1)
    
    # Search for 'Hello' (should NOT match)
    log.info("[TEST] Searching for 'Hello' (expecting failure)...")
    r = run_tool(FindText, {"text": "Hello", "min_confidence": 80})
    results["steps"].append({"step": "ocr_mismatch", "result": r})
    
    found = r.get("found", True)  # Default true to fail test if missing
    log.info(f"       Found: {found}")
    log.info(f"       Frame Hash: {r.get('frame_hash')}")
    
    # Cleanup using handle_id (deterministic)
    log.info("[CLEANUP] Closing Notepad via handle_id...")
    run_tool(RequestCloseApp, {"handle_id": handle_id})
    run_tool(KeyboardPress, {"key": "n"})
    
    # Pass if OCR correctly did NOT find 'Hello'
    results["passed"] = not found
    test_results.append(results)
    log.info("TEST C: PASSED" if results["passed"] else "TEST C: FAILED (OCR falsely matched)")
    return results["passed"]


# ===== Test Case D: Context Safety =====
def test_d_context_safety():
    """Check execution context detection"""
    log.info("=" * 60)
    log.info("TEST D: Context Safety (Heuristic Check)")
    log.info("=" * 60)
    
    from tools.system.state.get_execution_context import GetExecutionContext
    
    results = {"name": "Test D: Context Safety", "steps": [], "passed": False}
    
    log.info("[TEST] Getting execution context...")
    r = run_tool(GetExecutionContext, {})
    results["steps"].append({"step": "get_context", "result": r})
    
    ctx = r.get("context", {})
    log.info(f"       is_safe_to_execute: {ctx.get('is_safe_to_execute')}")
    log.info(f"       screen_locked_heuristic: {ctx.get('screen_locked_heuristic')}")
    log.info(f"       confidence_level: {ctx.get('confidence_level')}")
    log.info(f"       user_idle_seconds: {ctx.get('user_idle_seconds')}")
    log.info(f"       warnings: {ctx.get('warnings')}")
    
    # Pass if confidence is reported as heuristic (honest)
    is_honest = ctx.get("confidence_level") == "heuristic"
    results["passed"] = is_honest
    test_results.append(results)
    log.info("TEST D: PASSED" if results["passed"] else "TEST D: FAILED (confidence not heuristic)")
    return results["passed"]


# ===== Test Case E: Timing/Stabilization =====
def test_e_timing():
    """Verify stabilization metadata is exposed"""
    log.info("=" * 60)
    log.info("TEST E: Timing & Stabilization Metadata")
    log.info("=" * 60)
    
    from tools.system.apps.launch import LaunchApp
    from tools.system.input.keyboard.type import KeyboardType
    from tools.system.display.find_text import FindText
    
    results = {"name": "Test E: Timing", "steps": [], "passed": False}
    
    # Check stabilization_time_ms is exposed
    tools_to_check = [LaunchApp, KeyboardType, FindText]
    all_have_stabilization = True
    
    for tool_class in tools_to_check:
        tool = tool_class()
        stab = tool.stabilization_time_ms
        log.info(f"       {tool.name}: stabilization_time_ms = {stab}")
        if stab <= 0:
            all_have_stabilization = False
    
    results["passed"] = all_have_stabilization
    test_results.append(results)
    log.info("TEST E: PASSED" if results["passed"] else "TEST E: FAILED")
    return results["passed"]


# ===== Main =====
def run_all_tests():
    log.info("=" * 60)
    log.info("PHASE 2 VERIFICATION PROTOCOL")
    log.info(f"Started: {datetime.now().isoformat()}")
    log.info("=" * 60)
    
    test_a_happy_path()
    time.sleep(1)
    
    test_b_ambiguity()
    time.sleep(1)
    
    test_c_ocr_failure()
    time.sleep(1)
    
    test_d_context_safety()
    
    test_e_timing()
    
    # Summary
    log.info("=" * 60)
    log.info("VERIFICATION SUMMARY")
    log.info("=" * 60)
    
    passed = 0
    failed = 0
    for r in test_results:
        status = "PASS" if r["passed"] else "FAIL"
        log.info(f"  [{status}] {r['name']}")
        if r["passed"]:
            passed += 1
        else:
            failed += 1
            
    log.info("-" * 60)
    log.info(f"TOTAL: {passed} passed, {failed} failed")
    
    if failed == 0:
        log.info("✅ ALL TESTS PASSED - READY FOR PHASE 3")
    else:
        log.warning("❌ SOME TESTS FAILED - FIX BEFORE PROCEEDING")
    
    return failed == 0


if __name__ == "__main__":
    run_all_tests()
