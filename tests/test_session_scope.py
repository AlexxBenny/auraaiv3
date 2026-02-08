import sys
sys.path.insert(0, ".")

from core.orchestrator import Orchestrator
from agents.goal_orchestrator import PlanGraph
from types import SimpleNamespace
from agents.goal_interpreter import Goal, MetaGoal
from agents.goal_orchestrator import OrchestrationResult
from tools.registry import get_registry

def test_manual_kill_multi_action_uses_single_session(monkeypatch):
    """Manual browser kill -> multi-action plan -> exactly one session creation"""
    orchestrator = Orchestrator()

    # Build two simple planned actions (as lightweight objects)
    a1 = SimpleNamespace(action_id="a1", intent="browser_control", description="nav one", args={"url":"https://one"}, action_class="browser")
    a2 = SimpleNamespace(action_id="a2", intent="browser_control", description="nav two", args={"url":"https://two"}, action_class="browser")

    nodes = {"n1": a1, "n2": a2}
    execution_order = ["n1", "n2"]
    goal_map = {0: ["n1", "n2"]}
    plan_graph = PlanGraph(nodes=nodes, edges={"n1": [], "n2": []}, goal_map=goal_map, execution_order=execution_order, total_actions=2)

    orch_result = OrchestrationResult(status="success", plan_graph=plan_graph)

    # Monkeypatch orchestrator's interpreter and orchestrator.orchestrate to return our plan
    # Use a valid browser verb to avoid Goal validation errors
    monkeypatch.setattr(orchestrator.goal_interpreter, "interpret", lambda ui, qc_output=None, context=None: MetaGoal(meta_type="single", goals=(Goal(domain="browser", verb="navigate"),), dependencies=()))
    monkeypatch.setattr(orchestrator.goal_orchestrator, "orchestrate", lambda meta_goal, context=None, capabilities=None, execution_summary=None: orch_result)

    # Register the real Navigate tool so registry lookup works (it declares requires_session=True)
    from tools.browsers.navigate import Navigate
    registry = get_registry()
    if not registry.has("browsers.navigate"):
        registry.register(Navigate())
    else:
        # Ensure existing registered tool declares requires_session for the test
        existing = registry.get("browsers.navigate")
        try:
            setattr(existing, "requires_session", True)
        except Exception:
            pass

    # Map all resolved tools to 'browsers.navigate'
    monkeypatch.setattr("core.tool_resolver.ToolResolver.resolve", lambda self, description, intent, context, action_class=None: {"tool":"browsers.navigate", "params": {}})

    # Spy on BrowserSessionManager.get_or_create
    from core.browser_session_manager import BrowserSessionManager
    created = {"count":0}
    fake_session = SimpleNamespace(session_id="S1")
    monkeypatch.setattr(BrowserSessionManager, "get_or_create", lambda self, session_id=None, browser_type=None: (created.__setitem__("count", created["count"]+1) or fake_session))
    # Make get_session return our fake session when requested
    monkeypatch.setattr(BrowserSessionManager, "get_session", lambda self, sid: fake_session if sid == "S1" else None)

    # Fake tool implementation - return the session_id that was injected into params
    navigate_tool = registry.get("browsers.navigate")
    monkeypatch.setattr(navigate_tool, "execute", lambda args: {"status":"success", "session_id": args.get("session_id"), "content": args.get("url")})

    # Execute the plan via orchestrator
    result = orchestrator._process_goal("do two navigations", context={})

    # Assert exactly one session was created
    assert created["count"] == 1, f"Expected exactly one session creation, got {created['count']}"

    # Assert both actions used same session_id
    results = result.get("results", [])
    session_ids = [r.get("result", {}).get("session_id") for r in results]
    assert all(sid == "S1" for sid in session_ids), f"Expected all session_ids to be S1, got {session_ids}"


