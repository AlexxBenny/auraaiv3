#!/usr/bin/env python3
"""TDA v3 Verification Test Script

Runs the 4 mandatory test sets and logs output for diagnosis.
"""

import sys
import os
import logging
from pathlib import Path
from datetime import datetime

# Setup for AURA imports - tests dir is inside project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Configure logging to capture everything
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Suppress noisy loggers
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

OUTPUT_FILE = PROJECT_ROOT / "tests" / "tda_verification_output.txt"


def write_log(f, message: str):
    """Write to both file and stdout."""
    print(message)
    f.write(message + "\n")


def run_test(f, orchestrator, test_name: str, user_input: str, expected: dict):
    """Run a single test and log results."""
    write_log(f, f"\n{'='*70}")
    write_log(f, f"TEST: {test_name}")
    write_log(f, f"INPUT: \"{user_input}\"")
    write_log(f, f"{'='*70}")
    
    try:
        # Access gate directly for explicit logging
        gate_result = orchestrator.gate.classify(user_input)
        write_log(f, f"\n[GATE] Classification: {gate_result}")
        write_log(f, f"[GATE] Expected: {expected.get('gate', 'unknown')}")
        
        if gate_result != expected.get('gate'):
            write_log(f, f"⚠️  GATE MISMATCH: got '{gate_result}', expected '{expected.get('gate')}'")
        else:
            write_log(f, f"✅ GATE: Correct")
        
        # Run full orchestration
        write_log(f, f"\n[PROCESSING] Running full orchestration...")
        result = orchestrator.process(user_input)
        
        # Log results
        write_log(f, f"\n[RESULT SUMMARY]")
        
        if "overall_status" in result:
            # Multi-subtask result
            write_log(f, f"  Decomposition Applied: {result.get('decomposition_applied')}")
            write_log(f, f"  Overall Status: {result.get('overall_status')}")
            write_log(f, f"  Subtask Count: {result.get('subtask_count')}")
            
            for sr in result.get("subtask_results", []):
                write_log(f, f"    - {sr.get('subtask_id')}: {sr.get('status')}")
                if sr.get('reason'):
                    write_log(f, f"      Reason: {sr.get('reason')}")
            
            summary = result.get("summary", {})
            write_log(f, f"  Summary: succeeded={summary.get('succeeded')}, failed={summary.get('failed')}, skipped={summary.get('skipped')}")
        else:
            # Single subtask result (compatible format)
            write_log(f, f"  Final Status: {result.get('final_status')}")
            intent = result.get("intent", {})
            write_log(f, f"  Intent: {intent.get('intent', 'unknown')}")
            
            plan = result.get("plan", {})
            write_log(f, f"  Action Type: {plan.get('action_type', 'unknown')}")
            write_log(f, f"  Effects Count: {len(plan.get('effects', []))}")
            write_log(f, f"  Steps Count: {len(plan.get('steps', []))}")
            
            if plan.get("refused"):
                write_log(f, f"  REFUSED: {plan.get('refusal', {})}")
            
            if result.get("response"):
                write_log(f, f"  Response: {result.get('response')[:200]}...")
        
        write_log(f, f"\n✅ TEST COMPLETED")
        return result
        
    except Exception as e:
        write_log(f, f"\n❌ TEST FAILED WITH EXCEPTION: {e}")
        import traceback
        write_log(f, traceback.format_exc())
        return None


def main():
    # Ensure output directory exists
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        write_log(f, "=" * 70)
        write_log(f, "TDA v3 VERIFICATION TEST RESULTS")
        write_log(f, f"Timestamp: {datetime.now().isoformat()}")
        write_log(f, "=" * 70)
        
        # Initialize orchestrator
        write_log(f, "\n[INIT] Loading SubtaskOrchestrator...")
        try:
            # CRITICAL: Must load tools BEFORE creating orchestrator
            # Otherwise registry is empty and all tool lookups fail
            from tools.loader import load_all_tools
            discovered = load_all_tools()
            write_log(f, f"[INIT] Loaded {len(discovered)} tools into registry")
            
            from core.orchestrator import SubtaskOrchestrator
            orchestrator = SubtaskOrchestrator()
            write_log(f, "[INIT] ✅ SubtaskOrchestrator loaded successfully")
        except Exception as e:
            write_log(f, f"[INIT] ❌ Failed to load: {e}")
            import traceback
            write_log(f, traceback.format_exc())
            return 1
        
        # =====================================================================
        # TEST SET 1: Gate correctness (structural only)
        # =====================================================================
        write_log(f, "\n\n" + "#" * 70)
        write_log(f, "# TEST SET 1: Gate Correctness (Structural Only)")
        write_log(f, "#" * 70)
        
        run_test(f, orchestrator, "1.1 Simple App Launch", 
                 "open chrome", {"gate": "single"})
        
        run_test(f, orchestrator, "1.2 Simple Question",
                 "what time is it", {"gate": "single"})
        
        run_test(f, orchestrator, "1.3 Simple Action",
                 "take a screenshot", {"gate": "single"})
        
        # =====================================================================
        # TEST SET 2: Decomposition sanity
        # =====================================================================
        write_log(f, "\n\n" + "#" * 70)
        write_log(f, "# TEST SET 2: Decomposition Sanity")
        write_log(f, "#" * 70)
        
        run_test(f, orchestrator, "2.1 Multi-Goal Decomposition",
                 "open chrome and take a screenshot", {"gate": "multi"})
        
        # =====================================================================
        # TEST SET 3: Failure isolation
        # =====================================================================
        write_log(f, "\n\n" + "#" * 70)
        write_log(f, "# TEST SET 3: Failure Isolation (Critical)")
        write_log(f, "#" * 70)
        
        run_test(f, orchestrator, "3.1 Partial Success",
                 "open chrome, delete system32, take a screenshot", {"gate": "multi"})
        
        # =====================================================================
        # TEST SET 4: Ambiguity tolerance
        # =====================================================================
        write_log(f, "\n\n" + "#" * 70)
        write_log(f, "# TEST SET 4: Ambiguity Tolerance")
        write_log(f, "#" * 70)
        
        run_test(f, orchestrator, "4.1 Ambiguous Request",
                 "open the document", {"gate": "single"})
        
        # =====================================================================
        # POST-MORTEM CHECK
        # =====================================================================
        write_log(f, "\n\n" + "#" * 70)
        write_log(f, "# POST-MORTEM MEMORY CHECK")
        write_log(f, "#" * 70)
        
        try:
            stats = orchestrator.postmortem.get_statistics()
            write_log(f, f"\nPostMortem Statistics: {stats}")
            
            recent = orchestrator.postmortem.get_recent_failures(limit=5)
            write_log(f, f"Recent Failures: {len(recent)} records")
            for r in recent:
                write_log(f, f"  - {r.outcome}: {r.subtask_description[:50]}...")
        except Exception as e:
            write_log(f, f"PostMortem check failed: {e}")
        
        write_log(f, "\n\n" + "=" * 70)
        write_log(f, "VERIFICATION COMPLETE")
        write_log(f, f"Results saved to: {OUTPUT_FILE}")
        write_log(f, "=" * 70)
    
    print(f"\n📄 Results written to: {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
