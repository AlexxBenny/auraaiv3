"""List all registered tools"""
from tools.loader import load_all_tools
load_all_tools()

from tools.registry import get_registry
registry = get_registry()
tools = registry.list_all()

print(f"Total tools: {len(tools)}\n")

# Group by domain
domains = {}
for name, data in sorted(tools.items()):
    parts = name.split(".")
    domain = ".".join(parts[:2]) if len(parts) > 1 else parts[0]
    if domain not in domains:
        domains[domain] = []
    domains[domain].append((name, data))

for domain, tool_list in sorted(domains.items()):
    print(f"\n=== {domain} ({len(tool_list)} tools) ===")
    for name, data in tool_list:
        desc = data.get("description", "")[:60]
        risk = data.get("risk_level", "unknown")
        print(f"  {name}: [{risk}] {desc}...")
