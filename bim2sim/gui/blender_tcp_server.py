"""
TCP Server for Blender integration.

Handles:
- Accepting connections from Blender clients
- Sending highlight/visualization commands
- Receiving status updates from Blender
- Managing multiple client connections
"""

import socket
import threading
import json
import logging
from typing import Optional, Dict, Any, Callable
import time

logger = logging.getLogger(__name__)


class BlenderTCPServer:
    """TCP Server for Blender client connections."""

    def __init__(self, host: str = 'localhost', port: int = 65432):
        """
        Initialize Blender TCP Server.

        Args:
            host: Host address to bind to
            port: Port to listen on
        """
        self.host = host
        self.port = port
        self.server_socket: Optional[socket.socket] = None
        self.client_socket: Optional[socket.socket] = None
        self.client_address: Optional[tuple] = None
        self.running = False
        self.accepting_thread: Optional[threading.Thread] = None
        self.client_thread: Optional[threading.Thread] = None

        # Callbacks
        self.on_client_connected: Optional[Callable] = None
        self.on_client_disconnected: Optional[Callable] = None
        self.on_message_received: Optional[Callable] = None

        # Client info
        self.client_info: Dict[str, Any] = {}

        logger.info(f"Blender TCP Server initialized on {host}:{port}")

    def start(self) -> bool:
        """
        Start the TCP server.

        Returns:
            Success status
        """
        if self.running:
            logger.warning("Server is already running")
            return False

        try:
            # Create socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Bind and listen
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(1)  # Only one Blender client at a time

            self.running = True

            # Start accepting connections in background
            self.accepting_thread = threading.Thread(
                target=self._accept_connections,
                daemon=True,
                name="BlenderTCPAcceptor"
            )
            self.accepting_thread.start()

            logger.info(f"Blender TCP Server started on {self.host}:{self.port}")
            return True

        except Exception as e:
            logger.error(f"Failed to start Blender TCP Server: {e}")
            self.running = False
            return False

    def stop(self):
        """Stop the TCP server and close all connections."""
        logger.info("Stopping Blender TCP Server...")
        self.running = False

        # Close client connection
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
            self.client_socket = None
            self.client_address = None

        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
            self.server_socket = None

        logger.info("Blender TCP Server stopped")

    def _accept_connections(self):
        """Accept incoming client connections (runs in background thread)."""
        while self.running:
            try:
                if not self.server_socket:
                    break

                logger.info("Waiting for Blender client connection...")

                # Accept connection (blocking)
                self.server_socket.settimeout(1.0)  # Timeout to check self.running

                try:
                    client_socket, client_address = self.server_socket.accept()
                except socket.timeout:
                    continue  # Check self.running again

                logger.info(f"Blender client connected from {client_address}")

                # Store client info
                self.client_socket = client_socket
                self.client_address = client_address

                # Trigger callback
                if self.on_client_connected:
                    try:
                        self.on_client_connected(client_address)
                    except Exception as e:
                        logger.error(f"Error in on_client_connected callback: {e}")

                # Start client handler thread
                self.client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, client_address),
                    daemon=True,
                    name="BlenderTCPClient"
                )
                self.client_thread.start()

            except Exception as e:
                if self.running:  # Only log if not shutting down
                    logger.error(f"Error accepting connection: {e}")
                break

    def _handle_client(self, client_socket: socket.socket, client_address: tuple):
        """
        Handle messages from a connected client.

        Args:
            client_socket: Connected client socket
            client_address: Client address tuple
        """
        logger.info(f"Started client handler for {client_address}")

        try:
            while self.running and client_socket:
                # Set timeout for receiving
                client_socket.settimeout(1.0)

                try:
                    # Receive data
                    data = client_socket.recv(4096)

                    if not data:
                        logger.info(f"Client {client_address} disconnected")
                        break

                    # Decode message
                    message = data.decode('utf-8')
                    logger.debug(f"Received from client: {message[:100]}...")

                    # Parse JSON
                    try:
                        message_data = json.loads(message)

                        # Trigger callback
                        if self.on_message_received:
                            try:
                                self.on_message_received(message_data)
                            except Exception as e:
                                logger.error(f"Error in on_message_received callback: {e}")

                    except json.JSONDecodeError as e:
                        logger.warning(f"Invalid JSON from client: {e}")

                except socket.timeout:
                    continue  # Check self.running again

        except Exception as e:
            logger.error(f"Error handling client {client_address}: {e}")

        finally:
            # Cleanup
            logger.info(f"Client handler for {client_address} ended")

            try:
                client_socket.close()
            except:
                pass

            # Clear client info
            if self.client_socket == client_socket:
                self.client_socket = None
                self.client_address = None

            # Trigger callback
            if self.on_client_disconnected:
                try:
                    self.on_client_disconnected(client_address)
                except Exception as e:
                    logger.error(f"Error in on_client_disconnected callback: {e}")

    def send_message(self, message: Dict[str, Any]) -> bool:
        """
        Send a message to the connected Blender client.

        Args:
            message: Message data (will be JSON-encoded)

        Returns:
            Success status
        """
        if not self.is_client_connected():
            logger.warning("No client connected, cannot send message")
            return False

        try:
            # Encode as JSON
            message_json = json.dumps(message)
            message_bytes = message_json.encode('utf-8')

            # Send
            self.client_socket.sendall(message_bytes)
            logger.debug(f"Sent to client: {message_json[:100]}...")

            return True

        except Exception as e:
            logger.error(f"Error sending message to client: {e}")
            return False

    def send_highlight_command(self, guid: str, zoom: bool = True, hide_others: bool = False) -> bool:
        """
        Send a highlight command to Blender.

        Args:
            guid: GlobalId of element to highlight
            zoom: Whether to zoom to the element
            hide_others: Whether to hide other elements

        Returns:
            Success status
        """
        message = {
            'command': 'highlight',
            'guid': guid,
            'zoom': zoom,
            'hide_others': hide_others
        }
        return self.send_message(message)

    def send_reset_view_command(self) -> bool:
        """
        Send a reset view command to Blender.

        Returns:
            Success status
        """
        message = {
            'command': 'reset_view'
        }
        return self.send_message(message)

    def send_load_ifc_command(self, ifc_path: str) -> bool:
        """
        Send a load IFC command to Blender.

        Tells the Blender addon to load the specified IFC file
        via Bonsai if it is not already loaded.

        Args:
            ifc_path: Absolute path to the IFC file

        Returns:
            Success status
        """
        message = {
            'command': 'load_ifc',
            'ifc_path': ifc_path
        }
        logger.info(f"Sending load_ifc command: {ifc_path}")
        return self.send_message(message)

    def is_client_connected(self) -> bool:
        """Check if a Blender client is currently connected."""
        return self.client_socket is not None and self.client_address is not None

    def get_client_info(self) -> Optional[Dict[str, Any]]:
        """
        Get information about the connected client.

        Returns:
            Client info dict or None if no client connected
        """
        if not self.is_client_connected():
            return None

        return {
            'address': self.client_address,
            'connected': True,
            **self.client_info
        }