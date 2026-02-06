# 🤖 AURA - Agentic Desktop Assistant

A **local-first** AI assistant for Windows that bridges the gap between natural language and desktop automation. AURA uses a **Goal-Oriented** architecture to understand intent, resolve dependencies, and execute deterministic actions safely.

> **"LLMs should reason, Code should execute."**

---

## 🌟 Key Features

- **🧠 Hybrid Architecture**: Combines fast rule-based routing with deep semantic reasoning.
- **🛡️ Deterministic Safety**: Tools are Python-based "system calls" (not generated code). No `exec()` or terminal hallucination.
- **🔗 Dependency Awareness**: Understands *"create folder X and put file Y inside"* as a connected sequence, not just two random actions.
- **🎯 Parametric Goals**: Commands are parsed into structured data `(domain: browser, verb: navigate, params: {...})` for precision.
- **⚡ Two-Speed Execution**:
  - **Single Path**: Fast, direct execution for simple queries (`"open spotify"`).
  - **Multi Path**: Full reasoning engine for complex, multi-step workflows.

---

## �️ Capabilities

### 🌐 Browser Automation
Powered by Playwright. Can navigate, click, type, read text, and wait for elements.
- *"Go to google.com and search for 'python tutorials'"*
- *"Open youtube and play the first video"*

### � File System Control
Safe manipulation of files and directories with relative path awareness.
- *"Create a 'projects' folder on D drive"*
- *"Move all text files from Downloads to Documents"*

### 🖥️ System Management
Native Windows integration.
- *"Launch Notepad"*
- *"Mute the volume"*
- *"Take a screenshot"*
- *"Snap this window to the left"*

---

## 🧠 System Architecture

AURA operates on a **Router-Executor** model.

```
User Input
    ↓
[QueryClassifier] → (Single vs Multi?)
    ↓
    ├── If SIMPLE (Single Goal):
    │   [IntentAgent] → "browser_control"
    │   [ToolResolver] → "browsers.navigate"
    │   [Executor] → RUN
    │
    └── If COMPLEX (Multi-Step / Dependent):
        [GoalInterpreter] → Semantically parses goals & dependencies
        [GoalOrchestrator] → Builds execution DAG
        [GoalPlanner] → Defines exact parameters (selectors, paths)
        [Executor] → RUN (in dependency order)
```

### The "Brain" Components
- **QueryClassifier**: The gatekeeper. Decides if a query needs deep thought or fast action.
- **GoalInterpreter**: Extracts structured goals (e.g. `domain="file", verb="create", scope="inside:project"`).
- **GoalPlanner**: The architect. Converts abstract goals into concrete tool calls with validated arguments.
- **ToolResolver**: The bridge. Maps abstract intents to actual Python functions.

---

## 🚀 Getting Started

### Prerequisites
- **OS**: Windows 10/11
- **Python**: 3.11+
- **Browser**: Chromium (via Playwright)
- **API Key**: Gemini (recommended), or OpenAI/Anthropic/Ollama.

### Installation

1. **Clone & Setup**
   ```bash
   git clone https://github.com/AlexxBenny/auraaiv3.git
   cd auraaiv3
   python -m venv venv
   .\venv\Scripts\activate
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

3. **Configure API**
   ```powershell
   $env:GEMINI_API_KEY="your_api_key_here"
   ```

4. **Run**
   ```bash
   # CLI Mode
   python main.py
   ```

---

## 📖 Usage Patterns

### Simple Commands (Single Path)
Direct commands are executed immediately.
- `open chrome`
- `volume up`
- `what time is it?`

### Complex Workflows (Multi Path)
AURA plans these out before executing.
- `create a folder named 'logs' and create a file 'error.txt' inside it`
  *(AURA understands the file must be created AFTER the folder)*
  
- `go to github.com, wait for the search bar, and search for 'aura'`
  *(AURA injects the correct CSS selectors and waits for state changes)*

---

## 📁 Project Structure

| Directory | Purpose |
|-----------|---------|
| **`agents/`** | The "Brain". Interpreters, Planners, Classifiers. |
| **`core/`** | The "Spine". Orchestration, Tool Resolution, Pipelines. |
| **`tools/`** | The "Hands". Actual Python functions for Browser/Files/System. |
| **`config/`** | Model and Runtime configurations. |
| **`docs/`** | Detailed architectural contracts. |

---

## 🛡️ Safety Principles

1. **Planner Authority**: The AI Planner defines *what* to do. The execution layer strictly follows it. No "thinking" during execution.
2. **Fail-Fast Validation**: Invalid parameters (e.g. non-existent drive, malformed URL) cause immediate stop.
3. **Domain Locking**: A file operation cannot accidentally click a link. A browser operation cannot delete a file.

---

## 📄 License

MIT License. Built with ❤️ for the Agentic AI future.

