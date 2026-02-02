"""Unit tests for goal-oriented architecture (no model dependencies)

Tests:
1. GoalPlanner browser_search merging (core logic)
2. Data structure contracts
3. URL building
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_goal_dataclass():
    """Test Goal dataclass immutability."""
    print("\n" + "="*60)
    print("TEST 1: Goal dataclass")
    print("="*60)
    
    from agents.goal_interpreter import Goal
    
    goal = Goal(
        goal_type="browser_search",
        platform="youtube",
        query="nvidia"
    )
    
    print(f"  Goal created: {goal.goal_type}, {goal.platform}, {goal.query}")
    
    # Test immutability
    try:
        goal.query = "test"  # Should fail
        print("  ✗ Goal is mutable (bad)")
        return False
    except Exception:
        print("  ✓ Goal is immutable (frozen)")
        return True


def test_metagoal_validation():
    """Test MetaGoal invariants."""
    print("\n" + "="*60)
    print("TEST 2: MetaGoal validation")
    print("="*60)
    
    from agents.goal_interpreter import Goal, MetaGoal
    
    # Valid single
    try:
        meta = MetaGoal(
            meta_type="single",
            goals=(Goal(goal_type="browser_search", platform="youtube", query="nvidia"),),
            dependencies=()
        )
        print("  ✓ Single MetaGoal valid")
    except Exception as e:
        print(f"  ✗ Single MetaGoal invalid: {e}")
        return False
    
    # Valid independent_multi
    try:
        meta = MetaGoal(
            meta_type="independent_multi",
            goals=(
                Goal(goal_type="app_launch", target="chrome"),
                Goal(goal_type="app_launch", target="spotify")
            ),
            dependencies=()
        )
        print("  ✓ Independent multi valid")
    except Exception as e:
        print(f"  ✗ Independent multi invalid: {e}")
        return False
    
    return True


def test_planner_browser_search():
    """Test GoalPlanner browser_search merging - THE KEY TEST."""
    print("\n" + "="*60)
    print("TEST 3: GoalPlanner browser_search MERGING")
    print("="*60)
    
    from agents.goal_interpreter import Goal
    from agents.goal_planner import GoalPlanner
    
    planner = GoalPlanner()
    
    # THE LITMUS TEST
    goal = Goal(
        goal_type="browser_search",
        platform="youtube",
        query="nvidia"
    )
    
    result = planner.plan(goal)
    
    print(f"  Input: browser_search(youtube, nvidia)")
    print(f"  Status: {result.status}")
    
    if result.plan:
        print(f"  Total actions: {result.plan.total_actions}")
        if result.plan.actions:
            url = result.plan.actions[0].args.get("url", "")
            print(f"  URL: {url}")
    
    # THE KEY ASSERTION
    success = (
        result.status == "success" and
        result.plan is not None and
        result.plan.total_actions == 1 and  # MUST be 1
        "youtube.com" in result.plan.actions[0].args.get("url", "") and
        "nvidia" in result.plan.actions[0].args.get("url", "")
    )
    
    print(f"\n✓ MERGED: 1 action with full URL" if success else "✗ NOT MERGED")
    return success


def test_planner_navigate():
    """Test GoalPlanner browser_navigate."""
    print("\n" + "="*60)
    print("TEST 4: GoalPlanner browser_navigate")
    print("="*60)
    
    from agents.goal_interpreter import Goal
    from agents.goal_planner import GoalPlanner
    
    planner = GoalPlanner()
    
    goal = Goal(
        goal_type="browser_navigate",
        target="google.com"
    )
    
    result = planner.plan(goal)
    
    print(f"  Input: browser_navigate(google.com)")
    print(f"  Status: {result.status}")
    
    if result.plan and result.plan.actions:
        url = result.plan.actions[0].args.get("url", "")
        print(f"  URL: {url}")
    
    success = (
        result.status == "success" and
        result.plan is not None and
        "google.com" in result.plan.actions[0].args.get("url", "") and
        "https://" in result.plan.actions[0].args.get("url", "")
    )
    
    print(f"\n✓ Navigate with https" if success else "✗ Failed")
    return success


def test_planner_app_launch():
    """Test GoalPlanner app_launch."""
    print("\n" + "="*60)
    print("TEST 5: GoalPlanner app_launch")
    print("="*60)
    
    from agents.goal_interpreter import Goal
    from agents.goal_planner import GoalPlanner
    
    planner = GoalPlanner()
    
    goal = Goal(
        goal_type="app_launch",
        target="notepad"
    )
    
    result = planner.plan(goal)
    
    print(f"  Input: app_launch(notepad)")
    print(f"  Status: {result.status}")
    
    if result.plan and result.plan.actions:
        app = result.plan.actions[0].args.get("app_name", "")
        print(f"  App: {app}")
    
    success = result.status == "success" and result.plan is not None
    print(f"\n✓ App launch planned" if success else "✗ Failed")
    return success


def test_plan_dataclass():
    """Test Plan and PlannedAction contracts."""
    print("\n" + "="*60)
    print("TEST 6: Plan dataclass contracts")
    print("="*60)
    
    from agents.goal_planner import Plan, PlannedAction
    
    # Valid plan
    action = PlannedAction(
        action_id="a1",
        tool="system.apps.launch.shell",
        args={"app_name": "chrome", "url": "https://youtube.com"},
        expected_effect="browser_open"
    )
    
    plan = Plan(
        actions=[action],
        goal_achieved_by="a1",
        total_actions=1
    )
    
    print(f"  Plan created: {plan.total_actions} action(s)")
    print(f"  ✓ Plan contract satisfied")
    
    # Test invalid plan (wrong goal_achieved_by)
    try:
        bad_plan = Plan(
            actions=[action],
            goal_achieved_by="a99",  # Doesn't exist
            total_actions=1
        )
        print("  ✗ Invalid plan allowed (bad)")
        return False
    except AssertionError:
        print("  ✓ Invalid goal_achieved_by rejected")
        return True


def test_orchestrator_single_passthrough():
    """Test GoalOrchestrator single goal passthrough."""
    print("\n" + "="*60)
    print("TEST 7: GoalOrchestrator single passthrough")
    print("="*60)
    
    from agents.goal_interpreter import Goal, MetaGoal
    from agents.goal_orchestrator import GoalOrchestrator
    
    orchestrator = GoalOrchestrator()
    
    meta_goal = MetaGoal(
        meta_type="single",
        goals=(Goal(goal_type="browser_search", platform="youtube", query="nvidia"),),
        dependencies=()
    )
    
    result = orchestrator.orchestrate(meta_goal)
    
    print(f"  Input: single(browser_search)")
    print(f"  Status: {result.status}")
    
    if result.plan_graph:
        print(f"  Total actions: {result.plan_graph.total_actions}")
    
    success = (
        result.status == "success" and
        result.plan_graph is not None and
        result.plan_graph.total_actions == 1
    )
    
    print(f"\n✓ Single passthrough works" if success else "✗ Failed")
    return success


def test_orchestrator_independent_multi():
    """Test GoalOrchestrator independent_multi."""
    print("\n" + "="*60)
    print("TEST 8: GoalOrchestrator independent_multi")
    print("="*60)
    
    from agents.goal_interpreter import Goal, MetaGoal
    from agents.goal_orchestrator import GoalOrchestrator
    
    orchestrator = GoalOrchestrator()
    
    meta_goal = MetaGoal(
        meta_type="independent_multi",
        goals=(
            Goal(goal_type="app_launch", target="chrome"),
            Goal(goal_type="app_launch", target="spotify")
        ),
        dependencies=()
    )
    
    result = orchestrator.orchestrate(meta_goal)
    
    print(f"  Input: independent_multi(chrome, spotify)")
    print(f"  Status: {result.status}")
    
    if result.plan_graph:
        print(f"  Total actions: {result.plan_graph.total_actions}")
        print(f"  Goals in map: {list(result.plan_graph.goal_map.keys())}")
    
    success = (
        result.status == "success" and
        result.plan_graph is not None and
        result.plan_graph.total_actions == 2
    )
    
    print(f"\n✓ Independent multi works" if success else "✗ Failed")
    return success


if __name__ == "__main__":
    print("\n" + "#"*60)
    print("# GOAL ARCHITECTURE UNIT TESTS (no model deps)")
    print("#"*60)
    
    results = []
    
    results.append(("Goal dataclass", test_goal_dataclass()))
    results.append(("MetaGoal validation", test_metagoal_validation()))
    results.append(("Planner browser_search", test_planner_browser_search()))
    results.append(("Planner navigate", test_planner_navigate()))
    results.append(("Planner app_launch", test_planner_app_launch()))
    results.append(("Plan dataclass", test_plan_dataclass()))
    results.append(("Orchestrator single", test_orchestrator_single_passthrough()))
    results.append(("Orchestrator multi", test_orchestrator_independent_multi()))
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    all_passed = True
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("ALL TESTS PASSED!")
        print("Goal architecture Phase 1 implementation verified.")
    else:
        print("SOME TESTS FAILED")
    print("="*60)
