"""Ambient Memory - Background system state tracker

JARVIS Architecture Role:
- Continuous background monitoring (every 5s)
- Provides rich context for intelligent behavior
- NEVER blocks execution (non-blocking, fail-soft)

Tracks:
- Active/recent windows
- Running processes
- System state (battery, CPU, memory)
- Activity patterns

Storage:
- Rolling window: last 1 hour
- Persisted to ~/.aura/ambient_state.json
"""

import threading
import time
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
from collections import deque


class AmbientMemory:
    """Background system state tracker for contextual intelligence.
    
    INVARIANT: Must NEVER block execution.
    If capture fails -> continue with stale/empty context.
    """
    
    POLL_INTERVAL = 5.0  # seconds
    RETENTION_MINUTES = 60
    MAX_SNAPSHOTS = 720  # 1 hour at 5s intervals
    
    def __init__(self, storage_path: Optional[Path] = None):
        if storage_path is None:
            storage_path = Path.home() / ".aura" / "ambient_state.json"
        
        self.storage_path = storage_path
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Rolling window of snapshots
        self.snapshots: deque = deque(maxlen=self.MAX_SNAPSHOTS)
        
        # Current aggregate state
        self.current_state: Dict[str, Any] = {}
        
        # Background thread
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # Lock for thread-safe access
        self._lock = threading.RLock()
        
        # Load persisted state
        self._load()
        
        logging.info("AmbientMemory initialized")
    
    def start(self):
        """Start background monitoring."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logging.info("AmbientMemory monitoring started")
    
    def stop(self):
        """Stop background monitoring."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        self._persist()
        logging.info("AmbientMemory monitoring stopped")
    
    def _monitor_loop(self):
        """Background monitoring loop."""
        persist_counter = 0
        
        while self._running:
            try:
                snapshot = self._capture_snapshot()
                
                with self._lock:
                    self.snapshots.append(snapshot)
                    self.current_state = self._aggregate_state()
                
                # Persist every 12 snapshots (~1 minute)
                persist_counter += 1
                if persist_counter >= 12:
                    self._persist()
                    persist_counter = 0
                    
            except Exception as e:
                # Non-blocking - log and continue
                logging.debug(f"AmbientMemory capture failed: {e}")
            
            time.sleep(self.POLL_INTERVAL)
    
    def _capture_snapshot(self) -> Dict[str, Any]:
        """Capture current system state."""
        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "windows": {},
            "processes": [],
            "system": {}
        }
        
        # Active window
        try:
            import win32gui
            import win32process
            import psutil
            
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                title = win32gui.GetWindowText(hwnd)
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                try:
                    proc = psutil.Process(pid)
                    snapshot["windows"]["active"] = {
                        "title": title,
                        "process": proc.name(),
                        "pid": pid,
                        "hwnd": hwnd
                    }
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    snapshot["windows"]["active"] = {
                        "title": title,
                        "pid": pid,
                        "hwnd": hwnd
                    }
        except Exception as e:
            logging.debug(f"Window capture failed: {e}")
        
        # Running processes (top 20 by memory)
        try:
            import psutil
            
            procs = []
            for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
                try:
                    info = proc.info
                    if info.get('memory_info'):
                        procs.append({
                            "name": info['name'],
                            "pid": info['pid'],
                            "memory_mb": round(info['memory_info'].rss / (1024 * 1024), 1)
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            procs.sort(key=lambda x: x['memory_mb'], reverse=True)
            snapshot["processes"] = procs[:20]
        except Exception as e:
            logging.debug(f"Process capture failed: {e}")
        
        # System state
        try:
            import psutil
            
            # Battery
            battery = psutil.sensors_battery()
            if battery:
                snapshot["system"]["battery"] = {
                    "percent": battery.percent,
                    "plugged": battery.power_plugged
                }
            
            # CPU and memory
            snapshot["system"]["cpu_percent"] = psutil.cpu_percent(interval=None)
            snapshot["system"]["memory_percent"] = psutil.virtual_memory().percent
        except Exception as e:
            logging.debug(f"System state capture failed: {e}")
        
        return snapshot
    
    def _aggregate_state(self) -> Dict[str, Any]:
        """Aggregate recent snapshots into current state."""
        if not self.snapshots:
            return {}
        
        recent = list(self.snapshots)[-12:]  # Last minute
        
        # Recent unique windows
        recent_windows = {}
        for snap in recent:
            active = snap.get("windows", {}).get("active", {})
            if active.get("title"):
                # Use title as key to dedupe
                recent_windows[active["title"]] = active
        
        # Current running apps (from latest snapshot)
        latest = recent[-1] if recent else {}
        running_apps = [p["name"] for p in latest.get("processes", [])[:10]]
        
        # System summary
        system = latest.get("system", {})
        
        return {
            "active_window": latest.get("windows", {}).get("active", {}),
            "recent_windows": list(recent_windows.values())[-5:],
            "running_apps": running_apps,
            "battery": system.get("battery", {}),
            "cpu_percent": system.get("cpu_percent", 0),
            "memory_percent": system.get("memory_percent", 0),
            "snapshot_count": len(self.snapshots)
        }
    
    def get_context(self) -> Dict[str, Any]:
        """Get current context for LLM consumption.
        
        Thread-safe, non-blocking.
        """
        with self._lock:
            return {
                **self.current_state,
                "last_updated": datetime.now().isoformat()
            }
    
    def get_recent_activity(self, minutes: int = 5) -> List[Dict]:
        """Get activity from last N minutes."""
        cutoff = datetime.now() - timedelta(minutes=minutes)
        
        with self._lock:
            return [
                s for s in self.snapshots
                if datetime.fromisoformat(s["timestamp"]) > cutoff
            ]
    
    def _load(self):
        """Load persisted state."""
        if not self.storage_path.exists():
            return
        
        try:
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
            
            # Only load snapshots from last hour
            cutoff = datetime.now() - timedelta(minutes=self.RETENTION_MINUTES)
            loaded = 0
            
            for snap in data.get("snapshots", []):
                try:
                    ts = datetime.fromisoformat(snap["timestamp"])
                    if ts > cutoff:
                        self.snapshots.append(snap)
                        loaded += 1
                except (ValueError, KeyError):
                    pass
            
            self.current_state = self._aggregate_state()
            logging.debug(f"AmbientMemory loaded {loaded} snapshots")
            
        except Exception as e:
            logging.debug(f"Failed to load AmbientMemory: {e}")
    
    def _persist(self):
        """Persist to disk (non-blocking)."""
        try:
            with self._lock:
                snapshots_copy = list(self.snapshots)
            
            with open(self.storage_path, 'w') as f:
                json.dump({
                    "version": "1.0",
                    "snapshot_count": len(snapshots_copy),
                    "snapshots": snapshots_copy
                }, f)
                
        except Exception as e:
            logging.debug(f"Failed to persist AmbientMemory: {e}")


# Singleton instance
_ambient_memory: Optional[AmbientMemory] = None


def get_ambient_memory() -> AmbientMemory:
    """Get or create the global AmbientMemory instance."""
    global _ambient_memory
    if _ambient_memory is None:
        _ambient_memory = AmbientMemory()
        _ambient_memory.start()
    return _ambient_memory


def get_context() -> Dict[str, Any]:
    """Convenience function to get current context."""
    return get_ambient_memory().get_context()
