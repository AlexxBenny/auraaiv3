#!/usr/bin/env python3
"""AURA - Agentic Desktop Assistant

New entry point - uses agentic loop instead of code generation
"""

import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Load runtime mode at startup
from core.runtime import get_runtime_mode

if __name__ == "__main__":
    runtime_mode = get_runtime_mode()
    print(f"Runtime mode: {runtime_mode}\n")
    
    from core.assistant import main
    sys.exit(main())

