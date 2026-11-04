"""
Main GUI Server for bim2sim.

Provides:
- HTTP server for web interface
- WebSocket for real-time updates
- Static file serving
- Project management integration
"""

import logging
import webbrowser
import threading
import time
from pathlib import Path
from flask import Flask, send_from_directory, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS

logger = logging.getLogger(__name__)


class GUIServer:
    """Main GUI Server managing HTTP, WebSocket and static files."""

    def __init__(self, host='localhost', port=8080):
        """
        Initialize GUI Server.

        Args:
            host: Host to bind to
            port: Port to bind to
        """
        self.host = host
        self.port = port
        self.running = False

        # Register frontend log handler as early as possible
        try:
            from bim2sim.gui.api.logs import register_log_handler
            register_log_handler()
            logger.info("Frontend log handler registered")
        except Exception as e:
            logger.warning(f"Could not register log handler: {e}")

        # Flask app setup
        static_folder = Path(__file__).parent / 'static'
        self.app = Flask(
            __name__,
            static_folder=str(static_folder),
            template_folder=str(static_folder)
        )

        # CORS for development
        CORS(self.app)

        # SocketIO setup
        self.socketio = SocketIO(
            self.app,
            cors_allowed_origins="*",
            async_mode='threading'
        )

        # Initialize Project Manager
        from bim2sim.gui.project_manager import ProjectManager
        self.project_manager = ProjectManager(socketio=self.socketio)
        logger.info("Project Manager initialized")

        # Register API blueprint
        try:
            from bim2sim.gui.api import api_bp
            self.app.register_blueprint(api_bp)
            logger.info("API blueprint registered")

            # Set project manager for API
            from bim2sim.gui.api import projects as projects_api
            projects_api.set_project_manager(self.project_manager)
            logger.info("Project Manager connected to API")

        except ImportError as e:
            logger.error(f"Failed to register API blueprint: {e}")

        # Initialize Blender TCP Server
        from bim2sim.gui.blender_tcp_server import BlenderTCPServer
        from bim2sim.gui.api import blender as blender_api

        self.blender_server = BlenderTCPServer(host='localhost', port=65432)
        blender_api.set_blender_server(self.blender_server)

        # Launcher needs the TCP server to know if Blender is connected
        from bim2sim.gui.api import blender_launcher
        blender_launcher.set_blender_server(self.blender_server)

        # Set callbacks
        self.blender_server.on_client_connected = self._on_blender_connected
        self.blender_server.on_client_disconnected = self._on_blender_disconnected
        self.blender_server.on_message_received = self._on_blender_message

        # Start Blender TCP server
        if self.blender_server.start():
            logger.info("Blender TCP Server started successfully")
        else:
            logger.error("Failed to start Blender TCP Server")

        # Connect Blender server to Project Manager for IFC loading
        self.project_manager.blender_server = self.blender_server
        logger.info("Blender TCP Server connected to Project Manager")

        # Register routes
        self._register_routes()
        self._register_socketio_events()

        # Thread for server
        self.server_thread = None

        logger.info(f"GUI Server initialized on {host}:{port}")
        logger.info(f"Static folder: {static_folder}")

    def _register_routes(self):
        """Register HTTP routes."""

        @self.app.route('/')
        def index():
            """Serve main HTML page."""
            return send_from_directory(self.app.static_folder, 'index.html')

        # Explizit JS-Dateien servieren
        @self.app.route('/js/<path:filename>')
        def serve_js(filename):
            """Serve JavaScript files."""
            js_folder = Path(self.app.static_folder) / 'js'
            logger.debug(f"Serving JS: {js_folder / filename}")
            return send_from_directory(
                js_folder,
                filename,
                mimetype='application/javascript'
            )

        # Explizit CSS-Dateien servieren
        @self.app.route('/css/<path:filename>')
        def serve_css(filename):
            """Serve CSS files."""
            css_folder = Path(self.app.static_folder) / 'css'
            logger.debug(f"Serving CSS: {css_folder / filename}")
            return send_from_directory(
                css_folder,
                filename,
                mimetype='text/css'
            )

        @self.app.route('/health')
        def health():
            """Health check endpoint."""
            return jsonify({
                'status': 'ok',
                'version': '1.0.0',
                'server': 'bim2sim-gui'
            })

        # API status endpoint with real Blender connection status
        @self.app.route('/api/status')
        def api_status():
            """Get server status."""
            blender_connected = False
            blender_info = None

            if self.blender_server:
                blender_connected = self.blender_server.is_client_connected()
                if blender_connected:
                    blender_info = self.blender_server.get_client_info()

            # Check for active projects
            active_project = None
            if self.project_manager:
                projects = self.project_manager.list_projects()
                running = [p for p in projects if p.get('status') == 'running']
                if running:
                    active_project = running[0]['id']

            return jsonify({
                'server_running': True,
                'blender_connected': blender_connected,
                'blender_info': blender_info,
                'active_project': active_project
            })

    def _register_socketio_events(self):
        """Register WebSocket event handlers."""

        @self.socketio.on('connect')
        def handle_connect():
            """Handle client connection."""
            client_id = request.sid if hasattr(request, 'sid') else 'unknown'
            logger.info(f"Client connected: {client_id}")
            emit('server_message', {
                'type': 'connected',
                'message': 'Connected to bim2sim GUI server'
            })

        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Handle client disconnection."""
            logger.info("Client disconnected")

        @self.socketio.on('ping')
        def handle_ping(data):
            """Handle ping from client."""
            emit('pong', {'timestamp': data.get('timestamp')})

    def start(self, open_browser=True):
        """
        Start the GUI server.

        Args:
            open_browser: If True, open browser automatically
        """
        if self.running:
            logger.warning("Server is already running")
            return

        self.running = True

        # Open browser in separate thread
        if open_browser:
            threading.Timer(
                1.5,
                lambda: webbrowser.open(f'http://{self.host}:{self.port}')
            ).start()

        logger.info(f"Starting GUI server on http://{self.host}:{self.port}")
        logger.info("Press CTRL+C to stop the server")

        try:
            # Run server (blocking)
            self.socketio.run(
                self.app,
                host=self.host,
                port=self.port,
                debug=False,
                use_reloader=False
            )
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
        except Exception as e:
            logger.error(f"Server error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.running = False

    def stop(self):
        """Stop the GUI server."""
        if not self.running:
            logger.warning("Server is not running")
            return
        # Stop Blender TCP server
        if hasattr(self, 'blender_server') and self.blender_server:
            self.blender_server.stop()
        logger.info("Stopping GUI server...")
        self.running = False

    def broadcast(self, event, data):
        """
        Broadcast message to all connected clients.

        Args:
            event: Event name
            data: Data to send
        """
        if not self.running:
            logger.warning("Cannot broadcast, server not running")
            return

        self.socketio.emit(event, data)
        logger.debug(f"Broadcasted {event}: {data}")

    def _on_blender_connected(self, address):
        """Callback when Blender client connects."""
        logger.info(f"Blender connected from {address}")
        # Broadcast to WebSocket clients
        self.socketio.emit('blender_connected', {
            'address': str(address),
            'timestamp': time.time()
        })

        # Send an IFC that was requested while Blender was still starting
        try:
            from bim2sim.gui.api import blender_launcher
            blender_launcher.on_blender_connected()
        except Exception as e:
            logger.error(f"Error sending pending IFC to Blender: {e}")

    def _on_blender_disconnected(self, address):
        """Callback when Blender client disconnects."""
        logger.info(f"Blender disconnected from {address}")
        # Broadcast to WebSocket clients
        self.socketio.emit('blender_disconnected', {
            'address': str(address),
            'timestamp': time.time()
        })

    def _on_blender_message(self, message):
        """Callback when message received from Blender."""
        logger.debug(f"Message from Blender: {message}")
        # Broadcast to WebSocket clients
        self.socketio.emit('blender_message', message)


def run_gui_server(host='localhost', port=8080, open_browser=True):
    """
    Convenience function to run GUI server.

    Args:
        host: Host to bind to
        port: Port to bind to
        open_browser: Open browser automatically
    """
    server = GUIServer(host=host, port=port)
    server.start(open_browser=open_browser)


if __name__ == '__main__':
    # For testing
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    run_gui_server()