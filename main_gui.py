#!/usr/bin/env python3
"""AURA Web GUI Entry Point

Starts the AURA assistant with a modern web interface.

Usage:
    python main_gui.py              # Opens browser
    python main_gui.py --no-browser # No auto-open
    python main_gui.py --port 3000  # Custom port

This is separate from main.py (terminal interface).
Both use the same Orchestrator underneath.
"""

import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging (goes to terminal, not GUI)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)


def main():
    """Start the web GUI server."""
    try:
        from gui.web.server import main as server_main
        server_main()
        return 0
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Make sure aiohttp is installed: pip install aiohttp")
        return 1
    except KeyboardInterrupt:
        print("\n👋 Server stopped")
        return 0
    except Exception as e:
        logging.error(f"Server error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
