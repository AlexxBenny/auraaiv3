"""Verification tests for GoalPlanner file_operation support"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_file_operation_planning():
    """Test file_operation goal planning."""
    print("\n" + "="*60)
    print("TEST: GoalPlanner file_operation Support")
    print("="*60)
    
    from agents.goal_interpreter import Goal
    from agents.goal_planner import GoalPlanner
    
    planner = GoalPlanner()
    all_pass = True
    
    # Test 1: Create folder
    print("\n1. Create folder goal:")
    goal1 = Goal(
        goal_type="file_operation",
        action="create",
        object_type="folder",
        target="D:\\nvidia",
        goal_id="g0"
    )
    result1 = planner.plan(goal1)
    
    if result1.status == "success" and result1.plan.actions[0].tool == "files.create_folder":
        print(f"  [OK] create folder -> files.create_folder")
        print(f"       args: {result1.plan.actions[0].args}")
    else:
        print(f"  [FAIL] status={result1.status}, expected files.create_folder")
        all_pass = False
    
    # Test 2: Create file
    print("\n2. Create file goal:")
    goal2 = Goal(
        goal_type="file_operation",
        action="create",
        object_type="file",
        target="D:\\nvidia\\test.txt",
        goal_id="g1"
    )
    result2 = planner.plan(goal2)
    
    if result2.status == "success" and result2.plan.actions[0].tool == "files.create_file":
        args = result2.plan.actions[0].args
        if args.get("create_parents") == True:
            print(f"  [OK] create file -> files.create_file with create_parents=True")
        else:
            print(f"  [FAIL] create_parents not set")
            all_pass = False
    else:
        print(f"  [FAIL] status={result2.status}, expected files.create_file")
        all_pass = False
    
    # Test 3: Action normalization (mkdir -> create)
    print("\n3. Action normalization (mkdir -> create folder):")
    goal3 = Goal(
        goal_type="file_operation",
        action="mkdir",  # Should normalize to "create"
        target="D:\\test_folder",
        goal_id="g2"
    )
    result3 = planner.plan(goal3)
    
    if result3.status == "success" and result3.plan.actions[0].tool == "files.create_folder":
        print(f"  [OK] mkdir action normalized to create folder")
    else:
        print(f"  [FAIL] mkdir not normalized correctly")
        all_pass = False
    
    # Test 4: Dynamic action IDs
    print("\n4. Dynamic action IDs:")
    action_id1 = result1.plan.actions[0].action_id
    action_id2 = result2.plan.actions[0].action_id
    
    if action_id1 != action_id2:
        print(f"  [OK] Unique action IDs: {action_id1}, {action_id2}")
    else:
        print(f"  [FAIL] Action IDs not unique: {action_id1}")
        all_pass = False
    
    # Test 5: Object type inference from path
    print("\n5. Object type inference:")
    goal5 = Goal(
        goal_type="file_operation",
        action="create",
        target="D:\\inferred_folder",  # No extension = folder
        goal_id="g4"
    )
    result5 = planner.plan(goal5)
    
    goal6 = Goal(
        goal_type="file_operation",
        action="create", 
        target="D:\\inferred.txt",  # Has extension = file
        goal_id="g5"
    )
    result6 = planner.plan(goal6)
    
    if result5.plan.actions[0].tool == "files.create_folder":
        print(f"  [OK] No extension -> folder")
    else:
        print(f"  [FAIL] Should infer folder")
        all_pass = False
    
    if result6.plan.actions[0].tool == "files.create_file":
        print(f"  [OK] Has extension -> file")
    else:
        print(f"  [FAIL] Should infer file")
        all_pass = False
    
    return all_pass


if __name__ == "__main__":
    print("\n" + "#"*60)
    print("# GOALPLANNER FILE_OPERATION VERIFICATION")
    print("#"*60)
    
    passed = test_file_operation_planning()
    
    print("\n" + "="*60)
    if passed:
        print("ALL TESTS PASSED - file_operation ready")
    else:
        print("SOME TESTS FAILED - fix before proceeding")
    print("="*60)
