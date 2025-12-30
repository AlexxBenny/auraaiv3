"""Runtime Configuration Loader

Loads and manages runtime mode selection.
Runtime modes: local, hosted, hybrid
"""

import yaml
import logging
from pathlib import Path
from typing import Optional


def get_runtime_mode() -> str:
    """Get current runtime mode
    
    Returns:
        Runtime mode: 'local', 'hosted', or 'hybrid'
        
    If config/runtime.yaml doesn't exist, prompts user once and persists choice.
    """
    config_path = Path(__file__).parent.parent / "config" / "runtime.yaml"
    
    # Load existing config if it exists
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f) or {}
            mode = config.get("runtime", {}).get("mode", "local")
            
            # Validate mode
            if mode in ["local", "hosted", "hybrid"]:
                logging.info(f"Runtime mode loaded: {mode}")
                return mode
            else:
                logging.warning(f"Invalid runtime mode '{mode}', defaulting to 'local'")
                return "local"
        except Exception as e:
            logging.error(f"Error loading runtime config: {e}, defaulting to 'local'")
            return "local"
    
    # Config doesn't exist - prompt user once
    print("\n" + "=" * 50)
    print("AURA Runtime Mode Selection")
    print("=" * 50)
    print("Select runtime mode:")
    print("1. Local (Ollama, no API keys)")
    print("2. Hosted (Cloud APIs)")
    print("3. Hybrid (Local + Hosted fallback)")
    print()
    
    while True:
        try:
            choice = input("Enter choice (1-3) [default: 1]: ").strip()
            
            if not choice:
                choice = "1"
            
            if choice == "1":
                mode = "local"
                break
            elif choice == "2":
                mode = "hosted"
                break
            elif choice == "3":
                mode = "hybrid"
                break
            else:
                print("Invalid choice. Please enter 1, 2, or 3.")
                continue
        except (EOFError, KeyboardInterrupt):
            print("\nDefaulting to 'local' mode")
            mode = "local"
            break
    
    # Persist choice
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w') as f:
            yaml.dump({"runtime": {"mode": mode}}, f)
        logging.info(f"Runtime mode saved: {mode}")
    except Exception as e:
        logging.error(f"Error saving runtime config: {e}")
    
    return mode

