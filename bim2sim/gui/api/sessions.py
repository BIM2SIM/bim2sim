"""
Session management API endpoints.

Handles:
- Creating sessions
- Loading sessions
- Saving session state
- Resuming sessions
"""

import logging
from flask import request, jsonify

from . import api_bp
from ..session_manager import SessionManager

logger = logging.getLogger(__name__)

# Global session manager instance
session_manager = SessionManager()


@api_bp.route('/sessions', methods=['GET'])
def list_sessions():
    """List all sessions, optionally filtered by project."""
    try:
        project_id = request.args.get('project_id')

        sessions = session_manager.list_sessions(project_id=project_id)

        return jsonify({
            'sessions': [
                {
                    'session_id': s.session_id,
                    'project_id': s.project_id,
                    'project_name': s.project_name,
                    'created_at': s.created_at,
                    'updated_at': s.updated_at,
                    'status': s.status
                }
                for s in sessions
            ],
            'total': len(sessions)
        })

    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/sessions', methods=['POST'])
def create_session():
    """Create a new session."""
    try:
        data = request.get_json()

        required = ['project_id', 'project_name', 'project_config']
        for field in required:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400

        session_id = session_manager.create_session(
            project_id=data['project_id'],
            project_name=data['project_name'],
            project_config=data['project_config']
        )

        return jsonify({
            'session_id': session_id,
            'status': 'created'
        }), 201

    except Exception as e:
        logger.error(f"Error creating session: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/sessions/<session_id>', methods=['GET'])
def get_session(session_id):
    """Get session details."""
    try:
        session_data = session_manager.load_session(session_id)

        if not session_data:
            return jsonify({'error': 'Session not found'}), 404

        return jsonify(session_data)

    except Exception as e:
        logger.error(f"Error getting session {session_id}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/sessions/<session_id>', methods=['PUT'])
def update_session(session_id):
    """Update session data."""
    try:
        data = request.get_json()

        # Load existing session
        session_data = session_manager.load_session(session_id)

        if not session_data:
            return jsonify({'error': 'Session not found'}), 404

        # Update fields (merge)
        if 'project_config' in data:
            session_data['project_config'].update(data['project_config'])

        if 'execution_state' in data:
            session_data['execution_state'].update(data['execution_state'])

        if 'decisions' in data:
            session_data['decisions'].update(data['decisions'])

        # Save
        success = session_manager.save_session(session_id, session_data)

        if not success:
            return jsonify({'error': 'Failed to save session'}), 500

        return jsonify({'message': 'Session updated'}), 200

    except Exception as e:
        logger.error(f"Error updating session {session_id}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/sessions/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    """Delete a session."""
    try:
        success = session_manager.delete_session(session_id)

        if not success:
            return jsonify({'error': 'Session not found'}), 404

        return jsonify({'message': 'Session deleted'}), 200

    except Exception as e:
        logger.error(f"Error deleting session {session_id}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/sessions/<session_id>/summary', methods=['GET'])
def get_session_summary(session_id):
    """Get session summary (metadata + stats)."""
    try:
        summary = session_manager.get_session_summary(session_id)

        if not summary:
            return jsonify({'error': 'Session not found'}), 404

        return jsonify(summary)

    except Exception as e:
        logger.error(f"Error getting session summary {session_id}: {e}")
        return jsonify({'error': str(e)}), 500