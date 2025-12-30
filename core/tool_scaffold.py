"""Tool Scaffold Generator - Creates template files for new tools

Supports hierarchical tool organization with namespaced identifiers.
"""

import logging
from pathlib import Path
from typing import Dict, Any


class ToolScaffoldGenerator:
    """Generates tool template files (NOT executable code)"""
    
    def __init__(self, tools_dir: Path = None):
        if tools_dir is None:
            tools_dir = Path(__file__).parent.parent / "tools"
        self.tools_dir = tools_dir
    
    def generate_scaffold(self, proposal: Dict[str, Any]) -> Path:
        """Generate a tool scaffold file with hierarchical path support
        
        Args:
            proposal: Tool proposal from LimitationAnalysisAgent
            
        Returns:
            Path to generated scaffold file
        """
        proposed_tool = proposal.get("proposed_tool", {})
        tool_name = proposed_tool.get("name", "unknown_tool")
        description = proposed_tool.get("description", "")
        category = proposed_tool.get("category", "other")
        inputs_schema = proposed_tool.get("inputs", {})
        
        # Infer hierarchical path from tool name
        # e.g., "system.display.set_brightness" -> tools/system/display/set_brightness.py
        # e.g., "files.move" -> tools/files/move.py
        file_path, import_path = self._infer_path_from_name(tool_name)
        scaffold_path = self.tools_dir / file_path
        
        # Create directory structure
        scaffold_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Calculate relative import depth
        depth = len(file_path.parent.parts) - 1  # Subtract "tools" from count
        base_import = "." * (depth + 1) + "base"
        
        # Generate Python template
        template = f'''"""Tool: {tool_name}

{description}

Category: {category}
Risk Level: {proposed_tool.get("risk_level", "medium")}
Side Effects: {", ".join(proposed_tool.get("side_effects", []))}
OS Permissions: {", ".join(proposed_tool.get("os_permissions", []))}
"""

from typing import Dict, Any
from {base_import} import Tool


class {self._to_class_name(tool_name.split(".")[-1])}(Tool):
    """{description}"""
    
    @property
    def name(self) -> str:
        return "{tool_name}"
    
    @property
    def description(self) -> str:
        return "{description}"
    
    @property
    def schema(self) -> Dict[str, Any]:
        return {self._format_schema(inputs_schema)}
    
    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the tool
        
        TODO: Implement this method
        - Validate args match schema
        - Perform the actual operation
        - Return structured result with 'status' key
        
        Returns:
            {{"status": "success" | "error", ...}}
        """
        if not self.validate_args(args):
            return {{
                "status": "error",
                "error": "Invalid arguments"
            }}
        
        # TODO: Implement tool logic here
        # This is deterministic Python only - NO AI
        
        raise NotImplementedError("Tool not implemented yet")
        
        # Example return:
        # return {{
        #     "status": "success",
        #     "result": "..."
        # }}
'''
        
        # Write scaffold file
        with open(scaffold_path, 'w') as f:
            f.write(template)
        
        logging.info(f"Tool scaffold generated: {scaffold_path}")
        return scaffold_path
    
    def _infer_path_from_name(self, tool_name: str) -> tuple[Path, str]:
        """Infer file path and import path from namespaced tool name
        
        Args:
            tool_name: Fully-qualified tool name (e.g., "system.display.set_brightness")
            
        Returns:
            Tuple of (file_path, import_path)
            file_path: Path relative to tools_dir (e.g., "system/display/set_brightness.py")
            import_path: Python import path (e.g., "tools.system.display.set_brightness")
        """
        parts = tool_name.split(".")
        
        if len(parts) < 2:
            # Fallback: put in "other" category
            file_path = Path("other") / f"{tool_name}.py"
            import_path = f"tools.other.{tool_name}"
        else:
            # Map category to directory
            category = parts[0]
            tool_file = parts[-1]
            
            # Build path: category/subcategory/.../tool.py
            if len(parts) > 2:
                # Has subcategory
                subcategory = parts[1]
                file_path = Path(category) / subcategory / f"{tool_file}.py"
                import_path = f"tools.{category}.{subcategory}.{tool_file}"
            else:
                # Just category
                file_path = Path(category) / f"{tool_file}.py"
                import_path = f"tools.{category}.{tool_file}"
        
        return file_path, import_path
    
    def _to_class_name(self, tool_name: str) -> str:
        """Convert snake_case to PascalCase"""
        return ''.join(word.capitalize() for word in tool_name.split('_'))
    
    def _format_schema(self, schema: Dict[str, Any]) -> str:
        """Format JSON schema as Python dict string"""
        import json
        return json.dumps(schema, indent=8)

