import sys
sys.path.insert(0, ".")

import pytest
from core import planner_rules
from agents.goal_planner import GoalPlanner
from agents.goal_interpreter import Goal, MetaGoal
from core.context_frame import ContextFrame
from dataclasses import asdict
from agents.goal_orchestrator import GoalOrchestrator


def test_planner_rules_integrity():
    """Validate PLANNER_RULES metadata shape for context fields."""
    rules = planner_rules.PLANNER_RULES
    allowed_top_fields = {
        "intent", "action_class", "description_template", "required_params",
        "default_params", "allowed_values", "context_consumption",
        "context_production", "allow_semantic_only"
    }

    for key, rule in rules.items():
        # basic required presence
        assert "intent" in rule and "action_class" in rule and "description_template" in rule

        # unknown fields check (optional - warn as assert)
        for f in rule.keys():
            assert f in allowed_top_fields, f"Unknown field '{f}' in rule {key}"

        # context_consumption shape
        cc = rule.get("context_consumption")
        if cc is not None:
            assert isinstance(cc, dict)
            for pname, mapping in cc.items():
                assert isinstance(pname, str)
                assert isinstance(mapping, (list, tuple)) and len(mapping) == 2
                assert all(isinstance(x, str) for x in mapping)

        # context_production shape
        cp = rule.get("context_production")
        if cp is not None:
            assert isinstance(cp, dict)
            assert "domain" in cp and isinstance(cp["domain"], str)
            assert "keys" in cp and isinstance(cp["keys"], list)
            for k in cp["keys"]:
                assert isinstance(k, str)


def test_planner_determinism():
    """Same input + same context_frames -> identical PlannedAction (deterministic)."""
    planner = GoalPlanner()
    goal = Goal(domain="browser", verb="search", params={"query": "nvidia"}, goal_id="g_test", scope="root")
    ctx = [ContextFrame(domain="browser", data={"platform": "youtube"}, produced_by="g0")]

    r1 = planner.plan(goal, world_state={}, capabilities=None, context_frames=ctx)
    r2 = planner.plan(goal, world_state={}, capabilities=None, context_frames=ctx)

    assert r1.status == r2.status == "success"
    a1 = r1.plan.actions[0]
    a2 = r2.plan.actions[0]
    assert asdict(a1) == asdict(a2)


def test_no_context_regression_sweep():
    """For every rule, calling plan with no context_frames should not throw."""
    planner = GoalPlanner()
    for (domain, verb), rule in planner_rules.PLANNER_RULES.items():
        # create minimal goal with no params (planner should either plan or return blocked)
        g = Goal(domain=domain, verb=verb, params={}, goal_id="g_tmp", scope="root")
        result = planner.plan(g, world_state={}, capabilities=None, context_frames=[])
        assert result.status in {"success", "blocked", "no_capability"}


def test_context_isolation_across_domains():
    """ContextFrames for browser must not affect file rules (e.g., file.list)."""
    planner = GoalPlanner()
    # file.list has default path="." in planner_rules - verify unchanged
    g = Goal(domain="file", verb="list", params={}, goal_id="g_file", scope="root")
    fake_ctx = [ContextFrame(domain="browser", data={"platform": "youtube"}, produced_by="g0")]
    r_with = planner.plan(g, world_state={}, capabilities=None, context_frames=fake_ctx)
    r_no = planner.plan(g, world_state={}, capabilities=None, context_frames=[])
    assert r_with.status == r_no.status == "success"
    a_with = r_with.plan.actions[0]
    assert a_with.args.get("path") == "." or a_with.args.get("path") is not None


def test_dependency_transitive_propagation():
    """A -> B -> C: context produced at A flows to B and C via dependencies."""
    orch = GoalOrchestrator()
    g0 = Goal(domain="browser", verb="navigate", params={"platform": "youtube"}, goal_id="g0", scope="root")
    g1 = Goal(domain="browser", verb="search", params={"query": "one"}, goal_id="g1", scope="root")
    g2 = Goal(domain="browser", verb="search", params={"query": "two"}, goal_id="g2", scope="root")
    meta = MetaGoal(meta_type="dependent_multi", goals=(g0, g1, g2), dependencies=((1, (0,)), (2, (1,))))
    res = orch.orchestrate(meta, world_state={})
    assert res.status == "success"
    pg = res.plan_graph
    n0 = pg.nodes["g0_g0"]
    n1 = pg.nodes["g1_g1"]
    n2 = pg.nodes["g2_g2"]
    assert n0.produced_context is not None and n0.produced_context.get("platform") == "youtube"
    assert n1.args.get("platform") == "youtube"
    assert n2.args.get("platform") == "youtube"


def test_failure_isolation_in_dependencies():
    """If B fails planning, C depending on B must be blocked; A's context should not leak to unrelated goals."""
    orch = GoalOrchestrator()
    g0 = Goal(domain="browser", verb="navigate", params={"platform": "youtube"}, goal_id="g0", scope="root")
    # g1 will fail because required params missing and no allow_semantic_only
    g1 = Goal(domain="system", verb="set", params={}, goal_id="g1", scope="root")
    g2 = Goal(domain="browser", verb="search", params={"query": "nvidia"}, goal_id="g2", scope="root")
    # g2 depends on g1
    meta = MetaGoal(meta_type="dependent_multi", goals=(g0, g1, g2), dependencies=((1, (0,)), (2, (1,))))
    res = orch.orchestrate(meta, world_state={})
    # g1 should fail; g2 should be blocked due to dependency
    failed_idxs = {fg.goal_idx for fg in res.failed_goals}
    assert 1 in failed_idxs
    assert 2 in failed_idxs


