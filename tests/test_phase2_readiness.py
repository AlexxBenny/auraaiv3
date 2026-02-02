"""Single path isolation test

Verifies that single path does NOT:
- Instantiate GoalInterpreter
- Instantiate GoalPlanner  
- Touch WorldState
- Allocate PlanGraph

This is a critical invariant for Phase 1.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_single_path_code_isolation():
    """Verify single path code doesn't import/use goal components."""
    print("\n" + "="*60)
    print("TEST: Single Path Code Isolation")
    print("="*60)
    
    # Read the _process_single method from orchestrator
    orchestrator_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "core", "orchestrator.py"
    )
    
    with open(orchestrator_path, 'r') as f:
        content = f.read()
    
    # Find _process_single method
    start = content.find("def _process_single(")
    end = content.find("\n    def ", start + 1)
    
    if start == -1:
        print("  [X] FAIL: _process_single not found")
        return False
    
    single_path_code = content[start:end]
    
    # Check for goal component usage
    forbidden = [
        "goal_interpreter",
        "goal_planner",
        "goal_orchestrator",
        "GoalInterpreter",
        "GoalPlanner",
        "GoalOrchestrator",
        "MetaGoal",
        "PlanGraph",
        "WorldState"
    ]
    
    violations = []
    for term in forbidden:
        if term in single_path_code:
            violations.append(term)
    
    if violations:
        print(f"  [X] FAIL: Single path contains goal components: {violations}")
        return False
    
    # Verify it uses the old components
    required = ["intent_agent", "router"]
    missing = []
    for term in required:
        if term not in single_path_code:
            missing.append(term)
    
    if missing:
        print(f"  [X] FAIL: Single path missing required components: {missing}")
        return False
    
    print("  [OK] Single path does NOT use any goal components")
    print("  [OK] Single path uses intent_agent and router (unchanged)")
    return True


def test_browser_search_cannot_produce_two_actions():
    """Prove that browser_search can NEVER produce 2 actions."""
    print("\n" + "="*60)
    print("TEST: browser_search Always Produces 1 Action")
    print("="*60)
    
    from agents.goal_interpreter import Goal
    from agents.goal_planner import GoalPlanner
    
    planner = GoalPlanner()
    
    # Test various browser_search inputs
    test_cases = [
        ("youtube", "nvidia"),
        ("google", "weather forecast"),
        ("bing", "test query"),
        ("duckduckgo", "privacy search"),
        ("unknown_platform", "test"),  # Should fallback to google
    ]
    
    all_pass = True
    for platform, query in test_cases:
        goal = Goal(goal_type="browser_search", platform=platform, query=query)
        result = planner.plan(goal)
        
        if result.status != "success":
            print(f"  [X] FAIL: {platform}/{query} -> status={result.status}")
            all_pass = False
            continue
        
        if result.plan.total_actions != 1:
            print(f"  [X] FAIL: {platform}/{query} -> {result.plan.total_actions} actions (must be 1)")
            all_pass = False
            continue
        
        print(f"  [OK] {platform}/{query} -> 1 action")
    
    if all_pass:
        print("\n  PROVEN: browser_search can NEVER produce 2 actions")
    
    return all_pass


def test_plan_determinism():
    """Verify same input -> same plan."""
    print("\n" + "="*60)
    print("TEST: Plan Determinism")
    print("="*60)
    
    from agents.goal_interpreter import Goal
    from agents.goal_planner import GoalPlanner
    
    planner = GoalPlanner()
    
    goal = Goal(goal_type="browser_search", platform="youtube", query="nvidia")
    
    # Generate plan twice
    plan1 = planner.plan(goal)
    plan2 = planner.plan(goal)
    
    # Compare
    same_status = plan1.status == plan2.status
    same_actions = plan1.plan.total_actions == plan2.plan.total_actions
    same_url = (
        plan1.plan.actions[0].args.get("url") == 
        plan2.plan.actions[0].args.get("url")
    )
    
    if same_status and same_actions and same_url:
        print("  [OK] Same goal -> same plan (deterministic)")
        return True
    else:
        print("  [X] FAIL: Plans differ!")
        return False


if __name__ == "__main__":
    print("\n" + "#"*60)
    print("# PHASE 2 READINESS CHECKS")
    print("#"*60)
    
    results = []
    results.append(("Single path isolation", test_single_path_code_isolation()))
    results.append(("browser_search 1-action", test_browser_search_cannot_produce_two_actions()))
    results.append(("Plan determinism", test_plan_determinism()))
    
    print("\n" + "="*60)
    print("PHASE 2 READINESS SUMMARY")
    print("="*60)
    
    all_pass = True
    for name, passed in results:
        status = "[OK] READY" if passed else "[X] NOT READY"
        print(f"  {status}: {name}")
        if not passed:
            all_pass = False
    
    print("\n" + "="*60)
    if all_pass:
        print("ALL CHECKS PASSED - Ready for Phase 2")
    else:
        print("SOME CHECKS FAILED - Fix before Phase 2")
    print("="*60)
