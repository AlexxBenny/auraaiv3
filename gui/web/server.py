#!/usr/bin/env python3
"""AURA Web GUI Server

Bridges the web interface with AURA's Orchestrator via GUIAdapter.

This server:
- Serves the modern web GUI (HTML/CSS/JS)
- Provides WebSocket connection for real-time communication
- Routes all commands through GUIAdapter → Orchestrator
- Never exposes internal logs to the GUI

Based on AURA-main/aura_modern_gui/server.py, modified for JARVIS architecture.
"""

import asyncio
import json
import logging
import os
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from aiohttp import web
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    print("⚠️  aiohttp not found. Install with: pip install aiohttp")

# Import GUIAdapter - this is the ONLY connection to AURA internals
try:
    from gui.adapter import get_gui_adapter
    ADAPTER_AVAILABLE = True
except ImportError as e:
    ADAPTER_AVAILABLE = False
    print(f"⚠️  GUIAdapter not available: {e}")


class AuraWebServer:
    """Web server for AURA GUI.
    
    Routes all commands through GUIAdapter.
    GUI only sees UserResponse, never internal logs.
    """
    
    def __init__(self, host: str = "localhost", port: int = 8080):
        self.host = host
        self.port = port
        self.static_dir = Path(__file__).parent
        self.websockets = set()
        self.session_start = datetime.now()
        self.command_count = 0
        self.backend_ready = False  # Track initialization state
        
        # Setup logging (goes to terminal, not GUI)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger("AuraWebServer")
    
    async def index_handler(self, request):
        """Serve the main HTML page."""
        index_path = self.static_dir / "index.html"
        if index_path.exists():
            return web.FileResponse(index_path)
        return web.Response(text="AURA GUI not found", status=404)
    
    async def static_handler(self, request):
        """Serve static files (CSS, JS)."""
        filename = request.match_info['filename']
        filepath = self.static_dir / filename
        
        if filepath.exists() and filepath.is_file():
            return web.FileResponse(filepath)
        return web.Response(text=f"File not found: {filename}", status=404)
    
    async def websocket_handler(self, request):
        """Handle WebSocket connections for real-time communication."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        self.websockets.add(ws)
        self.logger.info(f"New WebSocket connection. Total: {len(self.websockets)}")
        
        # Send ready signal immediately if backend is initialized
        if self.backend_ready:
            await ws.send_json({
                "type": "ready",
                "message": "AURA backend ready"
            })
        
        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        response = await self.handle_message(data, ws)
                        await ws.send_json(response)
                    except json.JSONDecodeError:
                        await ws.send_json({
                            "type": "error",
                            "message": "Invalid JSON format"
                        })
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    self.logger.error(f"WebSocket error: {ws.exception()}")
        finally:
            self.websockets.discard(ws)
            self.logger.info(f"WebSocket disconnected. Total: {len(self.websockets)}")
        
        return ws
    
    async def handle_message(self, data: Dict[str, Any], ws=None) -> Dict[str, Any]:
        """Process incoming messages from the web GUI."""
        msg_type = data.get("type", "")
        content = data.get("content", "")
        
        if msg_type == "command":
            return await self.process_command(content, ws)
        elif msg_type == "status":
            return self.get_status()
        else:
            return {
                "type": "error",
                "message": f"Unknown message type: {msg_type}"
            }
    
    async def process_command(self, message: str, ws=None) -> Dict[str, Any]:
        """Process command through GUIAdapter with progress streaming.
        
        This is the ONLY entry point to AURA's Orchestrator.
        Progress messages are streamed via WebSocket as they occur.
        The final response is a UserResponse - safe for GUI.
        """
        self.command_count += 1
        self.logger.info(f"Processing command #{self.command_count}: {message[:50]}...")
        
        if not ADAPTER_AVAILABLE:
            return {
                "type": "error",
                "message": "AURA backend not available. Please check installation."
            }
        
        try:
            # Capture the current event loop BEFORE entering executor thread
            loop = asyncio.get_event_loop()
            
            # Define async progress callback
            async def send_progress(text: str):
                if ws and not ws.closed:
                    await ws.send_json({
                        "type": "progress",
                        "message": text
                    })
            
            # Wrapper to safely send progress from sync executor thread
            # Uses captured loop (not asyncio.get_event_loop() which fails in threads)
            def on_progress(text: str):
                try:
                    future = asyncio.run_coroutine_threadsafe(send_progress(text), loop)
                    # Don't wait for result - fire and forget for progress
                except Exception as e:
                    pass  # Silent fail for progress (not critical)
            
            # Get adapter and process with progress callback
            adapter = get_gui_adapter()
            response = await adapter.process(message, on_progress=on_progress if ws else None)
            
            # Convert UserResponse to WebSocket format
            return response.to_websocket()
            
        except Exception as e:
            # Log internally (terminal), return safe error to GUI
            self.logger.error(f"Error processing command: {e}")
            return {
                "type": "error",
                "message": "An unexpected error occurred. Please try again."
            }
    
    def get_status(self) -> Dict[str, Any]:
        """Return system status."""
        return {
            "type": "status",
            "data": {
                "adapter_available": ADAPTER_AVAILABLE,
                "session_start": self.session_start.isoformat(),
                "command_count": self.command_count
            }
        }
    
    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast a message to all connected WebSocket clients."""
        if self.websockets:
            await asyncio.gather(
                *[ws.send_json(message) for ws in self.websockets if not ws.closed]
            )
    
    def create_app(self) -> web.Application:
        """Create the aiohttp application."""
        app = web.Application()
        
        app.router.add_get('/', self.index_handler)
        app.router.add_get('/ws', self.websocket_handler)
        app.router.add_get('/{filename}', self.static_handler)
        
        return app
    
    def run(self, open_browser: bool = True):
        """Start the server."""
        if not AIOHTTP_AVAILABLE:
            print("❌ Cannot start server: aiohttp is required")
            print("   Install with: pip install aiohttp")
            return
        
        # EAGER INITIALIZATION - Load everything BEFORE opening browser
        # This ensures user can't send commands before backend is ready
        print("🔄 Initializing AURA backend...")
        print("   Loading tools and models (this may take a moment)...")
        
        if ADAPTER_AVAILABLE:
            try:
                adapter = get_gui_adapter()
                # Force initialization by accessing orchestrator property
                _ = adapter.orchestrator
                self.backend_ready = True
                print("✅ Backend initialized successfully!")
            except Exception as e:
                self.logger.error(f"Backend initialization failed: {e}")
                print(f"⚠️  Backend initialization failed: {e}")
                print("   GUI will start but commands may not work.")
        else:
            print("⚠️  GUIAdapter not available. GUI will start in demo mode.")
        
        app = self.create_app()
        
        print(f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     █████╗ ██╗   ██╗██████╗  █████╗                         ║
║    ██╔══██╗██║   ██║██╔══██╗██╔══██╗                        ║
║    ███████║██║   ██║██████╔╝███████║                        ║
║    ██╔══██║██║   ██║██╔══██╗██╔══██║                        ║
║    ██║  ██║╚██████╔╝██║  ██║██║  ██║                        ║
║    ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝                        ║
║                                                              ║
║         Web GUI - JARVIS Architecture                       ║
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║   🌐 Server: http://{self.host}:{self.port}                          ║
║   📡 WebSocket: ws://{self.host}:{self.port}/ws                      ║
║   ✅ Backend: {"READY" if self.backend_ready else "NOT READY"}                                      ║
║                                                              ║
║   Press Ctrl+C to stop                                       ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")
        
        if open_browser:
            webbrowser.open(f"http://{self.host}:{self.port}")
        
        web.run_app(app, host=self.host, port=self.port, print=None)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="AURA Web GUI Server")
    parser.add_argument("--host", default="localhost", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser")
    
    args = parser.parse_args()
    
    server = AuraWebServer(host=args.host, port=args.port)
    server.run(open_browser=not args.no_browser)


if __name__ == "__main__":
    main()
