import sys
sys.path.insert(0, ".")

from agents.goal_orchestrator import GoalOrchestrator
from agents.goal_interpreter import Goal, MetaGoal
from core.context_frame import ContextFrame
import urllib.parse


def test_dependent_context_propagation_and_injection(monkeypatch):
    """A -> B where A produces platform=youtube and B consumes it."""
    orchestrator = GoalOrchestrator()

    g0 = Goal(domain="browser", verb="navigate", params={"platform": "youtube"}, goal_id="g0", scope="root")
    g1 = Goal(domain="browser", verb="search", params={"query": "nvidia"}, goal_id="g1", scope="root")

    meta = MetaGoal(meta_type="dependent_multi", goals=(g0, g1), dependencies=((1, (0,)),))

    result = orchestrator.orchestrate(meta, world_state={})
    assert result.status == "success", f"orchestrate failed: {result}"
    pg = result.plan_graph

    # Node ids: prefixed with goal index -> g0_g0 and g1_g1
    n0 = pg.nodes.get("g0_g0")
    n1 = pg.nodes.get("g1_g1")
    assert n0 is not None and n1 is not None

    # Planner A produced ContextFrame
    assert getattr(n0, "produced_context", None) is not None
    assert n0.produced_context.domain == "browser"
    assert n0.produced_context.get("platform") == "youtube"

    # Planner B consumed context (platform filled) and constructed URL
    assert n1.args.get("platform") == "youtube"
    assert "youtube.com" in n1.args.get("url")
    assert urllib.parse.quote("nvidia", safe="") in n1.args.get("url")

    # Verify orchestrator injects URL into tool params when resolving/executing
    captured = {}

    def fake_resolve(self, description, intent, context, action_class=None):
        return {"tool": "browsers.navigate", "params": {}}

    def fake_execute(tool_name, params):
        captured["tool"] = tool_name
        captured["params"] = params
        return {"status": "success", "url": params.get("url"), "session_id": "s", "content": params.get("url")}

    monkeypatch.setattr("core.tool_resolver.ToolResolver.resolve", fake_resolve)
    monkeypatch.setattr("execution.executor.ToolExecutor.execute_tool", lambda self, tn, p: fake_execute(tn, p))

    # Call resolve_and_execute on the planned action (n1)
    res = orchestrator._resolve_and_execute(n1, context={})
    assert captured.get("params", {}).get("url") == n1.args.get("url")
    assert "youtube.com" in captured["params"]["url"]


def test_independent_isolation(monkeypatch):
    """A -> independent B: B must not receive A's context (uses planner default google)."""
    orchestrator = GoalOrchestrator()

    g0 = Goal(domain="browser", verb="navigate", params={"platform": "youtube"}, goal_id="g0", scope="root")
    g1 = Goal(domain="browser", verb="search", params={"query": "nvidia"}, goal_id="g1", scope="root")

    meta = MetaGoal(meta_type="independent_multi", goals=(g0, g1), dependencies=())

    result = orchestrator.orchestrate(meta, world_state={})
    assert result.status == "success"
    pg = result.plan_graph

    n1 = pg.nodes.get("g1_g1")
    assert n1 is not None
    # Should use planner default (google) since no dependency
    assert n1.args.get("platform") == "google"
    assert "google.com" in n1.args.get("url")


def test_explicit_param_precedence(monkeypatch):
    """If B explicitly sets platform=google, it should keep google despite upstream youtube."""
    orchestrator = GoalOrchestrator()

    g0 = Goal(domain="browser", verb="navigate", params={"platform": "youtube"}, goal_id="g0", scope="root")
    g1 = Goal(domain="browser", verb="search", params={"platform": "google", "query": "nvidia"}, goal_id="g1", scope="root")

    meta = MetaGoal(meta_type="dependent_multi", goals=(g0, g1), dependencies=((1, (0,)),))

    result = orchestrator.orchestrate(meta, world_state={})
    assert result.status == "success"
    pg = result.plan_graph

    n1 = pg.nodes.get("g1_g1")
    assert n1 is not None
    # Explicit param should win
    assert n1.args.get("platform") == "google"
    assert "google.com" in n1.args.get("url")


