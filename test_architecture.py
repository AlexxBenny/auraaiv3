"""Quick test to verify architecture is set up correctly"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")
    
    try:
        from models.model_manager import get_model_manager
        print("[OK] ModelManager imported")
        
        from tools.registry import get_registry
        print("[OK] ToolRegistry imported")
        
        from tools.base import Tool
        print("[OK] Tool base class imported")
        
        from tools.system.screenshot import TakeScreenshot
        print("[OK] TakeScreenshot tool imported")
        
        from agents.intent_agent import IntentAgent
        print("[OK] IntentAgent imported")
        
        from agents.planner_agent import PlannerAgent
        print("[OK] PlannerAgent imported")
        
        from agents.critic_agent import CriticAgent
        print("[OK] CriticAgent imported")
        
        from execution.executor import ToolExecutor
        print("[OK] ToolExecutor imported")
        
        from core.agent_loop import AgentLoop
        print("[OK] AgentLoop imported")
        
        from core.assistant import Assistant
        print("[OK] Assistant imported")
        
        print("\n[OK] All imports successful!")
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_tool_registry():
    """Test tool registry"""
    print("\nTesting tool registry...")
    
    try:
        from tools.registry import get_registry
        from tools.system.screenshot import TakeScreenshot
        
        registry = get_registry()
        registry.register(TakeScreenshot())
        
        assert registry.has("take_screenshot"), "Tool not registered"
        assert registry.get("take_screenshot") is not None, "Tool not found"
        
        print("[OK] Tool registry working")
        return True
        
    except Exception as e:
        print(f"[ERROR] Tool registry test failed: {e}")
        return False

def test_model_manager():
    """Test model manager"""
    print("\nTesting model manager...")
    
    try:
        from models.model_manager import get_model_manager
        
        manager = get_model_manager()
        
        # These will fail if API keys are missing, but structure should work
        intent_model = manager.get_intent_model()
        planner_model = manager.get_planner_model()
        critic_model = manager.get_critic_model()
        
        print("[OK] ModelManager working")
        print(f"   Intent model: {type(intent_model).__name__}")
        print(f"   Planner model: {type(planner_model).__name__}")
        print(f"   Critic model: {type(critic_model).__name__}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] ModelManager test failed: {e}")
        print("   (This is OK if API keys are not set)")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("AURA Architecture Test")
    print("=" * 50)
    
    all_passed = True
    all_passed &= test_imports()
    all_passed &= test_tool_registry()
    all_passed &= test_model_manager()
    
    print("\n" + "=" * 50)
    if all_passed:
        print("[OK] All tests passed!")
    else:
        print("[WARNING] Some tests failed (check output above)")
    print("=" * 50)

