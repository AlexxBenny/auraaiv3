# AURA Tools Reference

> Complete reference of all 61 registered tools, their capabilities, and usage patterns.

---

## Quick Stats

| Metric | Value |
|--------|-------|
| **Total Tools** | 61 |
| **Domains** | 15 |
| **High Risk** | 4 (delete, shutdown) |
| **Read-Only** | 12 (state queries) |

---

## Domain Overview

```
files.* (12 tools)       → File/folder CRUD operations
system.audio.* (7)       → Volume, media controls
system.state.* (8)       → Battery, window, disk, memory (READ-ONLY)
system.window.* (8)      → Snap, minimize, maximize, switch
system.apps.* (4)        → Launch, focus, close
system.input.* (4)       → Keyboard, mouse
system.desktop.* (4)     → Night light, icons, recycle bin
system.display.* (3)     → Screenshot, brightness, OCR
system.power.* (3)       → Lock, sleep, shutdown
system.virtual_desktop.* (3) → Desktop switching
system.clipboard.* (2)   → Read/write clipboard
system.network.* (1)     → Airplane mode
memory.* (1)             → Facts recall
browsers.* (1)           → (Not implemented)
```

---

## Tools by Domain

### files.* (12 tools)

| Tool | Risk | Description |
|------|------|-------------|
| `files.create_file` | low | Create file with optional content |
| `files.create_folder` | low | Create directory |
| `files.append_file` | low | Append to existing file |
| `files.read_file` | none | Read file content |
| `files.write_file` | medium | Overwrite file content |
| `files.copy` | low | Copy file/folder |
| `files.move` | medium | Move file/folder |
| `files.rename` | medium | Rename file/folder |
| `files.delete_file` | **high** | Permanently delete file |
| `files.delete_folder` | **high** | Delete folder (recursive) |
| `files.get_info` | none | File/folder metadata |
| `files.list_directory` | none | List directory contents |

---

### system.audio.* (7 tools)

| Tool | Description |
|------|-------------|
| `system.audio.get_volume` | Read current volume (0-100) |
| `system.audio.set_volume` | Set volume level |
| `system.audio.mute` | Mute audio |
| `system.audio.unmute` | Unmute audio |
| `system.audio.media_play_pause` | Toggle play/pause (global) |
| `system.audio.media_next` | Next track |
| `system.audio.media_previous` | Previous track |

> **Context Opportunity**: These tools work globally regardless of focused app. The media controls can be routed when the LLM detects media context.

---

### system.state.* (8 tools) — READ-ONLY

| Tool | Returns |
|------|---------|
| `system.state.get_active_window` | Focused window title, process, PID, bounds |
| `system.state.get_battery` | Battery %, charging status |
| `system.state.get_time` | Current system time |
| `system.state.get_date` | Current system date |
| `system.state.get_disk_usage` | Disk space per drive |
| `system.state.get_memory_usage` | RAM usage |
| `system.state.get_network_status` | WiFi/Ethernet, IP addresses |
| `system.state.get_execution_context` | Screen lock, idle time |

> **Context Opportunity**: These tools provide the exact data that could enrich `ContextSnapshot`. Currently only `AmbientMemory` uses similar APIs directly - these tools could be invoked to refresh context on-demand.

---

### system.window.* (8 tools)

| Tool | Description |
|------|-------------|
| `system.window.minimize` | Minimize active window |
| `system.window.maximize` | Maximize active window |
| `system.window.minimize_all` | Show desktop (Win+D) |
| `system.window.snap_left` | Snap left (Win+Left) |
| `system.window.snap_right` | Snap right (Win+Right) |
| `system.window.switch` | Alt+Tab |
| `system.window.close` | Alt+F4 |
| `system.window.task_view` | Open Task View |

---

### system.apps.* (4 tools)

| Tool | Description |
|------|-------------|
| `system.apps.launch.shell` | Launch GUI app (native shell) |
| `system.apps.launch.path` | Launch CLI tool (PATH resolution) |
| `system.apps.focus` | Bring app to foreground |
| `system.apps.request_close` | Polite close request |

---

### system.input.* (4 tools)

| Tool | Risk | Description |
|------|------|-------------|
| `system.input.keyboard.type` | medium | Type text string |
| `system.input.keyboard.press` | medium | Press key combo |
| `system.input.mouse.click` | medium | Click at coordinates |
| `system.input.mouse.move` | medium | Move cursor |

> ⚠️ **Safety**: Input tools are never used as fallback (domain-locked).

---

### system.desktop.* (4 tools)

| Tool | Description |
|------|-------------|
| `system.desktop.set_night_light` | Toggle blue light filter |
| `system.desktop.toggle_icons` | Show/hide desktop icons |
| `system.desktop.restart_explorer` | Restart Windows shell |
| `system.desktop.empty_recycle_bin` | **Destructive** - empties trash |

---

### system.display.* (3 tools)

| Tool | Description |
|------|-------------|
| `system.display.take_screenshot` | Capture screen to file |
| `system.display.set_brightness` | Set display brightness |
| `system.display.find_text` | OCR - locate text on screen |

---

### system.power.* (3 tools)

| Tool | Risk | Description |
|------|------|-------------|
| `system.power.lock` | medium | Lock workstation |
| `system.power.sleep` | medium | Enter sleep mode |
| `system.power.shutdown` | **high** | Shutdown (requires confirm) |

---

### system.virtual_desktop.* (3 tools)

| Tool | Description |
|------|-------------|
| `system.virtual_desktop.get_current` | Get current desktop number |
| `system.virtual_desktop.switch` | Switch to desktop N |
| `system.virtual_desktop.move_window_to_desktop` | Move window to desktop |

---

### system.clipboard.* (2 tools)

| Tool | Description |
|------|-------------|
| `system.clipboard.read` | Read clipboard text |
| `system.clipboard.write` | Write to clipboard |

---

### system.network.* (1 tool)

| Tool | Description |
|------|-------------|
| `system.network.set_airplane_mode` | Toggle airplane mode |

---

### memory.* (1 tool)

| Tool | Description |
|------|-------------|
| `memory.get_recent_facts` | Recall stored facts |

---

## Context Integration Opportunities

### Currently Unused for Context

The following tools could enhance `ContextSnapshot` but are not currently integrated:

| Tool | Could Provide |
|------|---------------|
| `system.state.get_active_window` | Real-time window focus |
| `system.state.get_battery` | Power state |
| `system.audio.get_volume` | Mute/volume state |

### Recommendation

1. **AmbientMemory already captures** active window and running apps via `psutil`/`win32gui`
2. **Media state missing** - No tool currently exposes "is media playing?"
3. **Battery already available** via `AmbientMemory.get_context()`

### Gap: Media State Detection

**Problem**: No existing tool detects if media is playing/paused.

**Options**:
1. Add `system.audio.get_media_state` tool (Windows Audio Session API)
2. Infer from window title patterns (Spotify shows ▶/⏸ in title)

---

## Tool Contract

All tools inherit from `tools.base.Tool`:

```python
class Tool:
    name: str               # Unique identifier
    description: str        # For LLM understanding
    schema: Dict            # JSON Schema for args
    risk_level: str         # low/medium/high
    side_effects: List[str] # e.g., "modifies_fs"
    requires_focus: bool    # Needs focused window?
    requires_active_app: str # Needs specific app focused?
    is_destructive: bool    # Data loss risk?
    
    def execute(args) -> Dict[str, Any]
```

---

## Tool Registration

Tools are auto-discovered from `tools/` directories:

```
tools/
├── base.py          # Tool base class
├── registry.py      # Central registry
├── loader.py        # Auto-discovery
├── files/           # files.* tools
├── system/          # system.* tools
│   ├── audio/
│   ├── state/
│   ├── apps/
│   └── ...
└── memory/          # memory.* tools
```
