# AURA Code Flow - main.py vs main_gui.py

## Correct Flow (main.py)

```
main.py
    ↓
    from core.assistant import main
    ↓
core/assistant.py::main()
    ↓
    Assistant()
    ↓
    Assistant.__init__()
        ↓
        1. self._register_tools()  ← CRITICAL STEP
            ↓
            load_all_tools()       ← Discovers all tools/ folder
            get_registry()         ← Registers them in ToolRegistry
            ↓
            Logs: "Auto-registered X tools from discovery"
        ↓
        2. self.orchestrator = Orchestrator()
            ↓
            Logs: "Initializing Orchestrator (JARVIS mode)"
    ↓
    assistant.start()
        ↓
        Main REPL loop: input() → orchestrator.process() → _display_result()
```

## Broken Flow (main_gui.py - BEFORE FIX)

```
main_gui.py
    ↓
    gui/web/server.py::AuraWebServer
    ↓
    gui/adapter.py::GUIAdapter.process()
        ↓
        Orchestrator()  ← MISSING: load_all_tools() not called!
        ↓
        Logs: "No tools registered in system"
```

## Fixed Flow (main_gui.py - AFTER FIX)

```
main_gui.py
    ↓
    gui/web/server.py::AuraWebServer.run()
        ↓
        1. Print "Initializing AURA backend..."
        ↓
        2. get_gui_adapter().orchestrator  ← EAGER INIT
            ↓
            load_all_tools()  ← Loads 59 tools
            Orchestrator()    ← Creates orchestrator
        ↓
        3. self.backend_ready = True
        ↓
        4. Print banner
        ↓
        5. webbrowser.open()  ← Browser opens AFTER init
        ↓
        6. web.run_app()
            ↓
            On WebSocket connect:
                Send {type: "ready"}  ← Tells frontend to enable input
```

## Key Insight

The `Orchestrator` class does NOT load tools itself. It assumes tools are already registered via `ToolRegistry`. The `Assistant` class handles this initialization, but `GUIAdapter` bypassed it.

## Fix Required

In `gui/adapter.py`, the `orchestrator` property must call `load_all_tools()` before creating `Orchestrator`:

```python
from tools.loader import load_all_tools

@property
def orchestrator(self) -> Orchestrator:
    if self._orchestrator is None:
        load_all_tools()  # ← ADD THIS
        self._orchestrator = Orchestrator()
    return self._orchestrator
```
