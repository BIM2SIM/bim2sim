"""
Project management API endpoints.

Handles:
- Listing projects
- Getting project details
- Creating projects
- Executing projects
- Deleting projects
- Run history
"""

import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from flask import request, jsonify

from . import api_bp

logger = logging.getLogger(__name__)

# Global project manager instance (set by server.py)
_project_manager = None


def set_project_manager(manager):
    """Set the global project manager instance."""
    global _project_manager
    _project_manager = manager
    logger.info("Project manager set for API")


@api_bp.route('/projects', methods=['GET'])
def list_projects():
    """GET /api/projects - List all projects."""
    try:
        if not _project_manager:
            return jsonify({'error': 'Project manager not initialized'}), 500

        projects = _project_manager.list_projects()

        return jsonify({
            'projects': projects,
            'count': len(projects)
        })

    except Exception as e:
        logger.error(f"Error listing projects: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/projects/<project_id>', methods=['GET'])
def get_project(project_id):
    """GET /api/projects/<id> - Get single project."""
    try:
        if not _project_manager:
            return jsonify({'error': 'Project manager not initialized'}), 500

        project = _project_manager.get_project(project_id)

        if not project:
            return jsonify({'error': 'Project not found'}), 404

        return jsonify(project)

    except Exception as e:
        logger.error(f"Error getting project {project_id}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/projects', methods=['POST'])
def create_project():
    """POST /api/projects - Create new project."""
    try:
        if not _project_manager:
            return jsonify({'error': 'Project manager not initialized'}), 500

        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Validate required fields
        required_fields = ['name', 'ifc_path', 'backend']
        missing = [f for f in required_fields if f not in data]

        if missing:
            return jsonify({
                'error': f'Missing required fields: {", ".join(missing)}'
            }), 400

        # Create project
        project = _project_manager.create_project(data)

        return jsonify(project), 201

    except Exception as e:
        logger.error(f"Error creating project: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/projects/<project_id>', methods=['PUT', 'PATCH'])
def update_project(project_id):
    """PUT/PATCH /api/projects/<id> - Update project."""
    try:
        if not _project_manager:
            return jsonify({'error': 'Project manager not initialized'}), 500

        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Don't allow changing ID
        if 'id' in data:
            del data['id']

        success = _project_manager.update_project(project_id, data)

        if not success:
            return jsonify({'error': 'Project not found'}), 404

        # Return updated project
        project = _project_manager.get_project(project_id)
        return jsonify(project)

    except Exception as e:
        logger.error(f"Error updating project {project_id}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/projects/<project_id>', methods=['DELETE'])
def delete_project(project_id):
    """DELETE /api/projects/<id> - Delete project."""
    try:
        if not _project_manager:
            return jsonify({'error': 'Project manager not initialized'}), 500

        success = _project_manager.delete_project(project_id)

        if not success:
            return jsonify({'error': 'Project not found or is running'}), 400

        return jsonify({'message': f'Project {project_id} deleted'})

    except Exception as e:
        logger.error(f"Error deleting project {project_id}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/projects/<project_id>/execute', methods=['POST'])
def execute_project(project_id):
    """POST /api/projects/<id>/execute - Execute project."""
    try:
        if not _project_manager:
            return jsonify({'error': 'Project manager not initialized'}), 500

        success = _project_manager.execute_project(project_id)

        if not success:
            return jsonify({
                'error': 'Project not found or already running'
            }), 400

        return jsonify({
            'message': f'Project {project_id} execution started',
            'project_id': project_id,
            'status': 'running'
        })

    except Exception as e:
        logger.error(f"Error executing project {project_id}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/projects/<project_id>/status', methods=['GET'])
def get_project_status(project_id):
    """GET /api/projects/<id>/status - Get project execution status."""
    try:
        if not _project_manager:
            return jsonify({'error': 'Project manager not initialized'}), 500

        status = _project_manager.get_project_status(project_id)

        if not status:
            return jsonify({'error': 'Project not found'}), 404

        # Add thread info
        thread_alive = False
        if project_id in _project_manager.active_executions:
            thread = _project_manager.active_executions[project_id]
            thread_alive = thread.is_alive()

        return jsonify({
            'project_id': project_id,
            'status': status,
            'thread_alive': thread_alive
        })

    except Exception as e:
        logger.error(f"Error getting project status {project_id}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/projects/<project_id>/debug', methods=['GET'])
def debug_project(project_id):
    """GET /api/projects/<id>/debug - Debug project execution."""
    try:
        if not _project_manager:
            return jsonify({'error': 'Project manager not initialized'}), 500

        project = _project_manager.get_project(project_id)

        if not project:
            return jsonify({'error': 'Project not found'}), 404

        # Thread info
        thread_info = {
            'exists': project_id in _project_manager.active_executions,
            'alive': False,
            'name': None
        }

        if project_id in _project_manager.active_executions:
            thread = _project_manager.active_executions[project_id]
            thread_info['alive'] = thread.is_alive()
            thread_info['name'] = thread.name

        # Handler info
        handler_info = {
            'exists': False,
            'is_waiting': False,
            'pending_count': 0
        }

        try:
            from bim2sim.kernel.decision.webgui_decisionhandler import WebGUIDecisionHandler
            handler = WebGUIDecisionHandler.get_instance()

            if handler:
                handler_info['exists'] = True
                handler_info['is_waiting'] = handler.is_waiting
                handler_info['pending_count'] = len(handler.pending_decisions_data)
        except:
            pass

        return jsonify({
            'project': {
                'id': project['id'],
                'name': project['name'],
                'status': project.get('status', 'unknown')
            },
            'thread': thread_info,
            'handler': handler_info
        })

    except Exception as e:
        logger.error(f"Error debugging project {project_id}: {e}")
        import traceback
        return jsonify({
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


@api_bp.route('/projects/<project_id>/stop', methods=['POST'])
def stop_project(project_id):
    """POST /api/projects/<id>/stop - Stop a running project."""
    try:
        if not _project_manager:
            return jsonify({'error': 'Project manager not initialized'}), 500

        project = _project_manager.get_project(project_id)
        if not project:
            return jsonify({'error': 'Project not found'}), 404

        # Shutdown handler if exists
        try:
            from bim2sim.kernel.decision.webgui_decisionhandler import WebGUIDecisionHandler
            handler = WebGUIDecisionHandler.get_instance()
            if handler:
                logger.info(f"Shutting down handler for project {project_id}")
                handler.shutdown(success=False)
        except Exception as e:
            logger.warning(f"Error shutting down handler: {e}")

        # Finalize the run record with logs collected so far -- without
        # this, a stopped run would be left stuck with the near-empty
        # stub snapshot written when it started.
        try:
            from bim2sim.gui.api.logs import get_active_run_id
            run_id = get_active_run_id(project_id)
            if run_id:
                _project_manager.finalize_run(
                    project_id, run_id, status='stopped',
                    error='Stopped by user'
                )
                logger.info(f"Finalized run record {run_id} as stopped")
        except Exception as e:
            logger.warning(f"Could not finalize run record on stop: {e}")

        # Remove from active executions (auch wenn Thread tot ist)
        if project_id in _project_manager.active_executions:
            thread = _project_manager.active_executions[project_id]
            logger.info(f"Thread for project {project_id}: alive={thread.is_alive()}")
            del _project_manager.active_executions[project_id]

        # Update status (WICHTIG: auch wenn Thread nicht existiert)
        _project_manager.update_project(project_id, {'status': 'idle'})

        # Broadcast status change
        if _project_manager.socketio:
            _project_manager.socketio.emit('project_status_changed', {
                'project_id': project_id,
                'status': 'idle',
                'timestamp': time.time(),
                'message': 'Project stopped by user'
            })

        logger.info(f"Project {project_id} stopped successfully")

        return jsonify({
            'message': f'Project {project_id} stopped',
            'project_id': project_id,
            'status': 'idle'
        })

    except Exception as e:
        logger.error(f"Error stopping project {project_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@api_bp.route('/projects/<project_id>/runs', methods=['GET'])
def list_project_runs(project_id):
    """GET /api/projects/<id>/runs - List past runs for a project.

    Returns run metadata (status, timing, settings snapshot) without the
    full log entries -- use /runs/<run_id> for that.
    """
    try:
        if not _project_manager:
            return jsonify({'error': 'Project manager not initialized'}), 500

        runs = _project_manager.list_runs(project_id)

        return jsonify({
            'project_id': project_id,
            'runs': runs,
            'count': len(runs)
        })

    except Exception as e:
        logger.error(f"Error listing runs for project {project_id}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/projects/<project_id>/runs/<run_id>', methods=['GET'])
def get_project_run(project_id, run_id):
    """GET /api/projects/<id>/runs/<run_id> - Get full run details.

    Includes the complete log entries for this specific run.
    """
    try:
        if not _project_manager:
            return jsonify({'error': 'Project manager not initialized'}), 500

        run = _project_manager.get_run(project_id, run_id)

        if not run:
            return jsonify({'error': 'Run not found'}), 404

        return jsonify(run)

    except Exception as e:
        logger.error(f"Error getting run {run_id} for project {project_id}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/projects/<project_id>/runs/<run_id>/open-folder',
              methods=['POST'])
def open_run_folder(project_id, run_id):
    """POST /api/projects/<id>/runs/<run_id>/open-folder

    Opens the run's folder in the system file manager. The path is taken
    from the stored run record, never from the request, so only folders
    that belong to a recorded run can be opened. Only meaningful when the
    server runs on the same machine as the user (the local-tool case).
    """
    try:
        if not _project_manager:
            return jsonify({'error': 'Project manager not initialized'}), 500

        run = _project_manager.get_run(project_id, run_id)
        if not run:
            return jsonify({'error': 'Run not found'}), 404

        folder = run.get('project_path')
        if not folder:
            return jsonify({'error': 'No folder recorded for this run'}), 404

        path = Path(folder)
        if not path.is_dir():
            return jsonify({
                'error': f'Folder no longer exists: {folder}'
            }), 404

        if sys.platform.startswith('win'):
            os.startfile(str(path))
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', str(path)])
        else:
            subprocess.Popen(['xdg-open', str(path)])

        return jsonify({'message': 'Folder opened', 'path': str(path)})

    except Exception as e:
        logger.error(f"Error opening folder for run {run_id}: {e}")
        return jsonify({'error': str(e)}), 500