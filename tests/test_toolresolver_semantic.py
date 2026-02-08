import sys
sys.path.insert(0, ".")

from core.tool_resolver import ToolResolver

def test_resolver_rejects_semantic_params(monkeypatch):
    """If LLM emits semantic params for a semantic tool, resolver must raise."""
    resolver = ToolResolver()

    # Simulate model.generate returning semantic params for browsers.navigate
    def fake_generate(prompt, schema=None):
        return {"tool": "browsers.navigate", "params": {"url": "https://example.com"}, "confidence": 0.9}

    resolver.model.generate = fake_generate

    try:
        resolver._resolve_with_tools("navigate to x", "browser_control", {}, [{"name":"browsers.navigate","description":"nav","schema":{}}], stage=1)
        assert False, "Expected resolver to raise on semantic params"
    except AssertionError:
        pass

def test_resolver_returns_empty_params_for_semantic_tool(monkeypatch):
    """If LLM returns tool without semantic params, resolver returns params == {} for semantic tool."""
    resolver = ToolResolver()

    def fake_generate(prompt, schema=None):
        return {"tool": "browsers.navigate", "params": {}, "confidence": 0.9}

    resolver.model.generate = fake_generate

    res = resolver._resolve_with_tools("navigate", "browser_control", {}, [{"name":"browsers.navigate","description":"nav","schema":{}}], stage=1)
    assert res.get("params") == {}


