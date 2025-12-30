"""Tool Auto-Discovery Loader

Recursively scans tools/ directory and automatically discovers and registers all Tool subclasses.
This eliminates manual registration and enables scalable tool organization.
"""

import importlib
import inspect
import logging
from pathlib import Path
from typing import List, Type, Dict
from .base import Tool
from .registry import get_registry


class ToolLoader:
    """Automatically discovers and registers tools from the tools/ directory"""
    
    def __init__(self, tools_root: Path = None):
        """Initialize loader
        
        Args:
            tools_root: Root directory for tools (default: tools/ relative to this file)
        """
        if tools_root is None:
            tools_root = Path(__file__).parent
        self.tools_root = tools_root.resolve()
        self.registry = get_registry()
        logging.info(f"ToolLoader initialized with root: {self.tools_root}")
    
    def discover_all(self) -> Dict[str, Tool]:
        """Discover and register all tools
        
        Returns:
            Dict mapping tool names to Tool instances
            
        Raises:
            ValueError: If duplicate tool names are found
        """
        discovered_tools: Dict[str, Tool] = {}
        
        # Find all Python files in tools/ directory
        python_files = list(self.tools_root.rglob("*.py"))
        
        # Filter out special files
        excluded = {"__init__.py", "base.py", "registry.py", "loader.py"}
        tool_files = [
            f for f in python_files
            if f.name not in excluded and not f.name.startswith("_")
        ]
        
        logging.info(f"Scanning {len(tool_files)} potential tool files...")
        
        for tool_file in tool_files:
            try:
                tools = self._load_tools_from_file(tool_file)
                for tool in tools:
                    tool_name = tool.name
                    
                    # Check for duplicates
                    if tool_name in discovered_tools:
                        raise ValueError(
                            f"Duplicate tool name '{tool_name}' found:\n"
                            f"  - {discovered_tools[tool_name].__class__.__module__}\n"
                            f"  - {tool.__class__.__module__}"
                        )
                    
                    discovered_tools[tool_name] = tool
                    logging.debug(f"Discovered tool: {tool_name}")
                    
            except Exception as e:
                logging.warning(f"Failed to load tools from {tool_file}: {e}")
                continue
        
        # Register all discovered tools
        for tool_name, tool in discovered_tools.items():
            try:
                self.registry.register(tool)
                logging.info(f"Registered tool: {tool_name}")
            except ValueError as e:
                # Tool already registered (shouldn't happen due to duplicate check)
                logging.warning(f"Tool {tool_name} already registered: {e}")
        
        logging.info(f"Auto-discovery complete: {len(discovered_tools)} tools registered")
        return discovered_tools
    
    def _load_tools_from_file(self, file_path: Path) -> List[Tool]:
        """Load all Tool subclasses from a Python file
        
        Args:
            file_path: Path to Python file
            
        Returns:
            List of Tool instances found in the file
        """
        tools = []
        
        # Convert file path to module path
        # e.g., tools/system/display/take_screenshot.py -> tools.system.display.take_screenshot
        # Calculate relative to tools_root (which is the tools/ directory)
        relative_path = file_path.relative_to(self.tools_root)
        module_parts = list(self.tools_root.parts[-1:]) + list(relative_path.with_suffix("").parts)
        module_name = ".".join(module_parts)
        
        try:
            # Import the module
            module = importlib.import_module(module_name)
            
            # Find all Tool subclasses in the module
            for name, obj in inspect.getmembers(module, inspect.isclass):
                # Skip if not a Tool subclass or is the Tool base class itself
                if not issubclass(obj, Tool) or obj is Tool:
                    continue
                
                # Skip if imported from elsewhere
                if obj.__module__ != module_name:
                    continue
                
                # Instantiate the tool
                try:
                    tool_instance = obj()
                    if isinstance(tool_instance, Tool):
                        tools.append(tool_instance)
                except Exception as e:
                    logging.warning(f"Failed to instantiate {name} from {module_name}: {e}")
                    
        except Exception as e:
            logging.error(f"Failed to import {module_name}: {e}")
        
        return tools


def load_all_tools() -> Dict[str, Tool]:
    """Convenience function to discover and register all tools
    
    Returns:
        Dict of discovered tools
    """
    loader = ToolLoader()
    return loader.discover_all()

