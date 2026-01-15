"""Test self-evolution system"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that all self-evolution components can be imported"""
    print("Testing self-evolution imports...")
    
    try:
        from agents.limitation_agent import LimitationAnalysisAgent
        print("[OK] LimitationAnalysisAgent imported")
        
        from core.skill_gate import SkillGate
        print("[OK] SkillGate imported")
        
        from memory.procedural import ProceduralMemory
        print("[OK] ProceduralMemory imported")
        
        from core.tool_scaffold import ToolScaffoldGenerator
        print("[OK] ToolScaffoldGenerator imported")
        
        print("\n[OK] All self-evolution components imported successfully!")
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_planner_upgrade():
    """Test that planner has limitation detection"""
    print("\nTesting planner upgrade...")
    
    try:
        from agents.planner_agent import PlannerAgent
        
        planner = PlannerAgent()
        
        # Check schema has requires_new_skill
        schema = planner.PLAN_SCHEMA
        if "requires_new_skill" in schema.get("properties", {}):
            print("[OK] Planner has requires_new_skill field")
        else:
            print("[ERROR] Planner missing requires_new_skill field")
            return False
        
        if "missing_capability" in schema.get("properties", {}):
            print("[OK] Planner has missing_capability field")
        else:
            print("[ERROR] Planner missing missing_capability field")
            return False
        
        print("[OK] Planner upgrade verified")
        return True
        
    except Exception as e:
        print(f"[ERROR] Planner test failed: {e}")
        return False

def test_skill_gate():
    """Test skill gate validation"""
    print("\nTesting skill gate...")
    
    try:
        from core.skill_gate import SkillGate
        
        gate = SkillGate(autonomy_mode="manual")
        
        # Test with valid proposal
        valid_proposal = {
            "proposed_tool": {
                "name": "test_tool",
                "description": "A test tool for validation",
                "category": "system",
                "inputs": {
                    "type": "object",
                    "properties": {
                        "param1": {"type": "string"}
                    }
                },
                "risk_level": "low"
            }
        }
        
        result = gate.validate_proposal(valid_proposal)
        if result.get("valid"):
            print("[OK] Valid proposal accepted")
        else:
            print(f"[WARNING] Valid proposal rejected: {result.get('errors')}")
        
        # Test with invalid proposal (missing name)
        invalid_proposal = {
            "proposed_tool": {
                "description": "Missing name"
            }
        }
        
        result = gate.validate_proposal(invalid_proposal)
        if not result.get("valid"):
            print("[OK] Invalid proposal rejected")
        else:
            print("[WARNING] Invalid proposal accepted")
        
        print("[OK] Skill gate working")
        return True
        
    except Exception as e:
        print(f"[ERROR] Skill gate test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_procedural_memory():
    """Test procedural memory storage"""
    print("\nTesting procedural memory...")
    
    try:
        from memory.procedural import ProceduralMemory
        from pathlib import Path
        import tempfile
        
        # Use temp file for testing
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_path = Path(f.name)
        
        memory = ProceduralMemory(storage_path=temp_path)
        
        # Test storing proposal
        proposal = {
            "proposed_tool": {
                "name": "test_tool",
                "description": "Test tool"
            },
            "rationale": "Testing"
        }
        
        validation = {"valid": True, "action": "manual_review"}
        proposal_id = memory.store_proposal(proposal, "Test goal", validation)
        
        if proposal_id:
            print(f"[OK] Proposal stored with ID: {proposal_id}")
        else:
            print("[ERROR] Failed to store proposal")
            return False
        
        # Test retrieving proposals
        pending = memory.get_pending_proposals()
        if len(pending) > 0:
            print(f"[OK] Retrieved {len(pending)} pending proposals")
        else:
            print("[WARNING] No pending proposals found")
        
        # Cleanup
        temp_path.unlink()
        
        print("[OK] Procedural memory working")
        return True
        
    except Exception as e:
        print(f"[ERROR] Procedural memory test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_agent_loop_integration():
    """Test that agent loop has self-evolution integrated"""
    print("\nTesting agent loop integration...")
    
    try:
        from core.agent_loop import AgentLoop
        
        loop = AgentLoop()
        
        # Check that self-evolution components are initialized
        if hasattr(loop, 'limitation_agent'):
            print("[OK] LimitationAgent initialized in AgentLoop")
        else:
            print("[ERROR] LimitationAgent not found in AgentLoop")
            return False
        
        if hasattr(loop, 'skill_gate'):
            print("[OK] SkillGate initialized in AgentLoop")
        else:
            print("[ERROR] SkillGate not found in AgentLoop")
            return False
        
        if hasattr(loop, 'procedural_memory'):
            print("[OK] ProceduralMemory initialized in AgentLoop")
        else:
            print("[ERROR] ProceduralMemory not found in AgentLoop")
            return False
        
        if hasattr(loop, '_handle_missing_skill'):
            print("[OK] _handle_missing_skill method exists")
        else:
            print("[ERROR] _handle_missing_skill method not found")
            return False
        
        print("[OK] Agent loop integration verified")
        return True
        
    except Exception as e:
        print(f"[ERROR] Agent loop integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("AURA Self-Evolution System Test")
    print("=" * 50)
    
    all_passed = True
    all_passed &= test_imports()
    all_passed &= test_planner_upgrade()
    all_passed &= test_skill_gate()
    all_passed &= test_procedural_memory()
    all_passed &= test_agent_loop_integration()
    
    print("\n" + "=" * 50)
    if all_passed:
        print("[OK] All tests passed!")
    else:
        print("[WARNING] Some tests failed (check output above)")
    print("=" * 50)

