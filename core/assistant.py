"""New Assistant - Orchestrates JARVIS architecture

This replaces the old assistant.py that used exec(generated_code)
Updated for JARVIS architecture (no effects, eligibility, Qdrant)
"""

import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from .orchestrator import Orchestrator
from .context import SessionContext
from tools.registry import get_registry
from tools.loader import load_all_tools


class Assistant:
    """JARVIS-style assistant - NO code execution, intent-based routing"""
    
    def __init__(self):
        # Auto-discover and register all tools
        self._register_tools()
        
        # Initialize orchestrator (JARVIS mode)
        self.orchestrator = Orchestrator()
        
        logging.info("Assistant initialized (JARVIS mode)")
    
    def _register_tools(self):
        """Auto-discover and register all available tools"""
        discovered = load_all_tools()
        registry = get_registry()
        
        logging.info(f"Auto-registered {len(discovered)} tools from discovery")
    
    def start(self):
        """Start the assistant"""
        print("🤖 AURA Assistant (JARVIS Mode)")
        print("=" * 50)
        print("Mode: Intent-based routing (JARVIS)")
        print(f"Available tools: {len(get_registry().list_all())}")
        print()
        
        # Main loop
        try:
            while True:
                # Get user input
                user_input = input("\n💬 Enter command (or 'exit' to quit): ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ["exit", "quit", "stop"]:
                    print("👋 Goodbye!")
                    break
                
                # Process through orchestrator
                result = self.orchestrator.process(user_input)
                
                # Display result
                self._display_result(result)
                
        except KeyboardInterrupt:
            print("\n👋 Assistant stopped by user")
        except Exception as e:
            logging.error(f"Error in main loop: {e}")
            print(f"❌ Error: {e}")
    
    def _display_result(self, result: Dict[str, Any]):
        """Display execution result"""
        status = result.get("status", "unknown")
        result_type = result.get("type", "unknown")
        
        # Clarification response (decision=ask terminal state)
        if result_type == "clarification" or status == "clarification_needed":
            question = result.get("question", result.get("response", "Could you please clarify?"))
            print(f"\n❓ {question}")
            return
        
        # Information response
        if result_type == "information":
            response = result.get("response", "No response provided")
            print(f"\n💬 {response}")
            return
        
        # Fallback response
        if result_type == "fallback":
            response = result.get("response", "")
            if result.get("status") == "clarification_needed":
                print(f"\n❓ {response}")
            else:
                print(f"\n💬 {response}")
            return
        
        # Action result
        if result_type == "action":
            if status == "success":
                # ISSUE 2 FIX: Response is now REQUIRED for success
                # Missing response is a bug in ResponsePipeline, not a feature
                response = result.get("response")
                if not response:
                    # Defensive: generate minimal response if pipeline failed
                    import logging
                    logging.error(f"ResponsePipeline bug: no response for {result.get('tool')}")
                    response = f"Completed {result.get('tool', 'action').split('.')[-1].replace('_', ' ')}"
                
                print(f"\n✅ {response}")
                
                # Show additional info if provided
                action_result = result.get("result", {})
                if action_result.get("path"):
                    print(f"   Path: {action_result['path']}")
                    
            elif status == "blocked":
                # Generate response for blocked status via pipeline if not present
                response = result.get("response")
                if response:
                    print(f"\n⚠️  {response}")
                else:
                    print(f"\n⚠️  Action blocked: {result.get('reason')}")
                if result.get("suggestion"):
                    print(f"   Suggestion: {result['suggestion']}")
            elif status == "refused":
                # Confirmation gate
                response = result.get("response")
                if response:
                    print(f"\n⚠️  {response}")
                else:
                    print(f"\n⚠️  Action refused - confirmation required")
            else:
                print(f"\n❌ Action failed: {result.get('error', 'Unknown error')}")
            return
        
        # Multi result
        if result_type == "multi":
            results = result.get("results", [])
            summary = result.get("summary", f"{len(results)} actions")
            
            if status == "success":
                print(f"\n✅ All actions completed! ({summary})")
            elif status == "partial":
                print(f"\n⚠️  Some actions failed ({summary})")
            elif status == "blocked":
                print(f"\n⚠️  Actions blocked")
                for issue in result.get("issues", []):
                    print(f"   • {issue.get('issue')}")
            else:
                print(f"\n❌ Actions failed")
                if result.get("unresolved"):
                    for u in result["unresolved"]:
                        print(f"   • {u['description']}: {u['reason']}")
            
            # Show individual results
            for r in results:
                status_icon = "✅" if r.get("status") == "success" else "❌"
                print(f"   {status_icon} {r.get('id', '?')}: {r.get('tool', 'unknown')}")
            return
        
        # Fallback for unknown result types
        print(f"\n📋 Result: status={status}, type={result_type}")
        if result.get("response"):
            print(f"   {result['response']}")


def main():
    """Main entry point"""
    try:
        assistant = Assistant()
        assistant.start()
        return 0
    except Exception as e:
        logging.error(f"Failed to start assistant: {e}")
        print(f"❌ Failed to start: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
