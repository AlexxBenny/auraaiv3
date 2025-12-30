"""New Assistant - Orchestrates agentic loop

This replaces the old assistant.py that used exec(generated_code)
"""

import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from .agent_loop import AgentLoop
from .context import SessionContext
from tools.registry import get_registry
from tools.system.screenshot import TakeScreenshot


class Assistant:
    """New agentic assistant - NO code execution"""
    
    def __init__(self):
        # Initialize agent loop
        self.agent_loop = AgentLoop()
        
        # Register tools
        self._register_tools()
        
        logging.info("Assistant initialized (agentic mode)")
    
    def _register_tools(self):
        """Register all available tools"""
        registry = get_registry()
        
        # Register system tools
        registry.register(TakeScreenshot())
        
        logging.info(f"Registered {len(registry.list_all())} tools")
    
    def start(self):
        """Start the assistant"""
        print("🤖 AURA Agentic Assistant Starting...")
        print("=" * 50)
        print("Mode: Agentic (NO code execution)")
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
                
                # Process through agentic loop
                result = self.agent_loop.process(user_input)
                
                # Display result
                self._display_result(result)
                
        except KeyboardInterrupt:
            print("\n👋 Assistant stopped by user")
        except Exception as e:
            logging.error(f"Error in main loop: {e}")
            print(f"❌ Error: {e}")
    
    def _display_result(self, result: Dict[str, Any]):
        """Display execution result"""
        final_status = result.get("final_status")
        
        if final_status == "requires_new_skill":
            print(f"\n⚠️  {result.get('message', 'New skill required')}")
            
            # Display proposal details
            proposal = result.get("proposal", {})
            validation = result.get("validation", {})
            proposal_id = result.get("proposal_id")
            
            if proposal:
                tool_name = proposal.get("proposed_tool", {}).get("name", "unknown")
                description = proposal.get("proposed_tool", {}).get("description", "")
                print(f"   Proposed Tool: {tool_name}")
                print(f"   Description: {description}")
                if proposal_id:
                    print(f"   Proposal ID: {proposal_id}")
            
            if validation:
                if not validation.get("valid"):
                    print(f"   Validation Errors: {', '.join(validation.get('errors', []))}")
                if validation.get("warnings"):
                    print(f"   Warnings: {', '.join(validation.get('warnings', []))}")
            
            scaffold_path = result.get("scaffold_path")
            if scaffold_path:
                print(f"   Scaffold generated: {scaffold_path}")
            
            print("   Review proposals in: ~/.aura/procedural_memory.json")
        
        elif final_status == "success":
            print("\n✅ Task completed successfully!")
            execution = result.get("execution", {})
            if execution.get("results"):
                for step_result in execution["results"]:
                    tool_result = step_result.get("result", {})
                    if "path" in tool_result:
                        print(f"   📁 {tool_result['path']}")
                    if "message" in tool_result:
                        print(f"   ℹ️  {tool_result['message']}")
        
        elif final_status == "retry_needed":
            print("\n🔄 Retry recommended")
            evaluation = result.get("evaluation", {})
            print(f"   Reason: {evaluation.get('retry_reason', 'Unknown')}")
        
        else:
            print("\n❌ Task failed")
            execution = result.get("execution", {})
            if execution.get("errors"):
                for error in execution["errors"]:
                    print(f"   Error: {error.get('error', 'Unknown error')}")


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

