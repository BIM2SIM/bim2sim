"""
Blender integration API endpoints.

Handles:
- Blender connection status
- Sending visualization commands to Blender
- Receiving updates from Blender
"""

import logging
from flask import request, jsonify

from . import api_bp

logger = logging.getLogger(__name__)

# Will be set by server.py
blender_server = None


def set_blender_server(server):
    """Set the global Blender TCP server instance."""
    global blender_server
    blender_server = server


@api_bp.route('/blender/status', methods=['GET'])
def get_blender_status():
    """Get Blender connection status."""
    try:
        if not blender_server:
            return jsonify({
                'connected': False,
                'error': 'Blender server not initialized'
            }), 503

        client_info = blender_server.get_client_info()

        return jsonify({
            'server_running': blender_server.running,
            'client_connected': blender_server.is_client_connected(),
            'client_info': client_info,
            'host': blender_server.host,
            'port': blender_server.port
        })

    except Exception as e:
        logger.error(f"Error getting Blender status: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/blender/highlight', methods=['POST'])
def send_highlight_command():
    """Send highlight command to Blender."""
    try:
        if not blender_server or not blender_server.is_client_connected():
            return jsonify({'error': 'Blender not connected'}), 503

        data = request.get_json()

        # Validate
        if 'guid' not in data:
            return jsonify({'error': 'Missing required field: guid'}), 400

        guid = data['guid']
        zoom = data.get('zoom', True)
        hide_others = data.get('hide_others', False)

        # Send command
        success = blender_server.send_highlight_command(guid, zoom, hide_others)

        if success:
            return jsonify({'message': 'Highlight command sent'}), 200
        else:
            return jsonify({'error': 'Failed to send command'}), 500

    except Exception as e:
        logger.error(f"Error sending highlight command: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/blender/reset_view', methods=['POST'])
def send_reset_view_command():
    """Send reset view command to Blender."""
    try:
        if not blender_server or not blender_server.is_client_connected():
            return jsonify({'error': 'Blender not connected'}), 503

        success = blender_server.send_reset_view_command()

        if success:
            return jsonify({'message': 'Reset view command sent'}), 200
        else:
            return jsonify({'error': 'Failed to send command'}), 500

    except Exception as e:
        logger.error(f"Error sending reset view command: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/blender/send_command', methods=['POST'])
def send_custom_command():
    """Send custom command to Blender."""
    try:
        if not blender_server or not blender_server.is_client_connected():
            return jsonify({'error': 'Blender not connected'}), 503

        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        success = blender_server.send_message(data)

        if success:
            return jsonify({'message': 'Command sent'}), 200
        else:
            return jsonify({'error': 'Failed to send command'}), 500

    except Exception as e:
        logger.error(f"Error sending custom command: {e}")
        return jsonify({'error': str(e)}), 500