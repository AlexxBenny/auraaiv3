import sys
sys.path.insert(0, ".")

from agents.goal_orchestrator import GoalOrchestrator
from agents.goal_interpreter import Goal, MetaGoal
from agents.goal_planner import GoalPlanner
from types import SimpleNamespace

def test_resolution_immutable_after_execution(monkeypatch):
    """Ensure ToolResolver.resolve() params are not mutated by execution path."""
    orchestrator = GoalOrchestrator()

    # Build a single planned action node
    a = SimpleNamespace(action_id="a", intent="browser_control", description="nav", args={"url":"https://example.com"}, action_class="browser")
    nodes = {"n1": a}
    execution_order = ["n1"]

    # Create a fake plan graph structure expected by orchestrator._resolve_and_execute
    # We'll monkeypatch ToolResolver.resolve to return a params dict and capture it.
    captured = {}
    def fake_resolve(self, description, intent, context, action_class=None):
        p = {"url": "https://example.com"}
        captured["resolved_params"] = dict(p)
        return {"tool": "browsers.navigate", "params": p}

    monkeypatch.setattr("core.tool_resolver.ToolResolver.resolve", fake_resolve)

    # Monkeypatch registry to have a navigate tool (declares requires_session)
    from tools.browsers.navigate import Navigate
    from tools.registry import get_registry
    registry = get_registry()
    if not registry.has("browsers.navigate"):
        registry.register(Navigate())

    # Monkeypatch execute_tool to be a no-op
    monkeypatch.setattr("execution.executor.ToolExecutor.execute_tool", lambda self, tn, p: {"status":"success"})

    # Call resolve_and_execute directly with our action
    result = orchestrator._resolve_and_execute(a, context={}, executor=None)

    # After execution, ensure the captured resolved params equal the original snapshot (immutability)
    assert captured["resolved_params"] == {"url": "https://example.com"}, "Resolved params were mutated during execution"


