"""
Start Blender from the GUI and report the state of that process.

The GUI server starts Blender as a normal subprocess. Whether Blender is
*connected* to bim2sim is a separate question, answered by the TCP server
(see blender_tcp_server.py); this module only knows whether the process it
started is still alive.

The executable comes from the global setting 'blender_path' (see
global_settings.py). If that is not set, common install locations are
searched.

Endpoints:
    POST /api/blender/launch          start Blender (best-effort auto-connect),
                                      optionally with a project whose IFC is
                                      loaded as soon as Blender connects
    GET  /api/blender/process         state of the process started by this server
    POST /api/blender/load-ifc        load a project's IFC in a connected Blender
    POST /api/blender/refresh-status  ask Blender to report its status again
"""

import logging
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from flask import jsonify, request

from . import api_bp

logger = logging.getLogger(__name__)

# Set by server.py so we can tell whether Blender is already connected
_blender_server = None

# IFC to load as soon as Blender connects (set when starting Blender with a
# project, or when the user asks for a load while Blender is still starting)
_pending_ifc: Optional[str] = None

# The process this server started (None if never started)
_process: Optional[subprocess.Popen] = None
_launched_at: Optional[float] = None

# Executed inside Blender shortly after startup. A timer is used so the
# window and all add-ons are fully up before the operator runs. Every
# failure is printed to Blender's console instead of raising, so a missing
# add-on never breaks Blender's startup -- the user can still press
# "Connect" manually.
AUTO_CONNECT_CODE = """
import bpy

def _bim2sim_auto_connect():
    try:
        bpy.ops.bim2sim.connect()
    except Exception as exc:
        print("bim2sim auto-connect failed:", exc)
    return None

bpy.app.timers.register(_bim2sim_auto_connect, first_interval=4.0)
"""


def set_blender_server(server):
    """Give the launcher access to the TCP server (connection state)."""
    global _blender_server
    _blender_server = server


def _version_key(path: Path):
    """Sort key from a folder name like 'Blender 4.2' -> (4, 2)."""
    match = re.search(r'(\d+(?:\.\d+)*)', path.parent.name)
    if not match:
        return ()
    return tuple(int(part) for part in match.group(1).split('.'))


def find_blender_executable() -> Optional[Path]:
    """Locate blender: configured path first, then common locations."""
    # 1. Configured in the Settings tab
    try:
        from bim2sim.gui.api.global_settings import load_global_settings
        configured = load_global_settings().get('blender_path')
    except Exception:
        configured = None

    if configured and str(configured).strip():
        candidate = Path(str(configured).strip()).expanduser()
        return candidate if candidate.is_file() else None

    # 2. Common install locations
    if sys.platform.startswith('win'):
        roots = {
            Path(os.environ.get('ProgramFiles', r'C:\Program Files')),
            Path(r'C:\Program Files'),
        }
        found = []
        for root in roots:
            found.extend(root.glob('Blender Foundation/Blender*/blender.exe'))
        if found:
            return max(found, key=_version_key)
    elif sys.platform == 'darwin':
        mac = Path('/Applications/Blender.app/Contents/MacOS/Blender')
        if mac.is_file():
            return mac

    # 3. On the PATH (Linux, or a custom setup on any OS)
    on_path = shutil.which('blender')
    return Path(on_path) if on_path else None


def _process_running() -> bool:
    return _process is not None and _process.poll() is None


def get_process_state() -> dict:
    """State of the Blender process started by this server."""
    running = _process_running()
    return {
        'running': running,
        'pid': _process.pid if running else None,
        'seconds_since_launch': (
            round(time.time() - _launched_at, 1)
            if running and _launched_at else None
        ),
    }


def _project_ifc_path(project_id: str) -> Optional[str]:
    """The IFC path stored in a project, or None if unknown.

    Read from the stored project so the request never has to carry a path.
    """
    try:
        from bim2sim.gui.api import projects as projects_api
        manager = projects_api._project_manager
        project = manager.get_project(project_id) if manager else None
        return project.get('ifc_path') if project else None
    except Exception as e:
        logger.warning(f"Could not look up project {project_id}: {e}")
        return None


def load_ifc_in_blender(ifc_path: str):
    """Tell a connected Blender to load an IFC file.

    Returns:
        (payload, http_status)
    """
    if _blender_server is None or not _blender_server.is_client_connected():
        return {'status': 'not_connected',
                'error': 'Blender is not connected.'}, 409

    path = Path(str(ifc_path))
    if not path.is_file():
        return {'status': 'not_found',
                'error': f'IFC file not found: {ifc_path}'}, 404

    if not _blender_server.send_load_ifc_command(str(path.resolve())):
        return {'status': 'failed',
                'error': 'Could not send the command to Blender.'}, 500

    return {'status': 'sent', 'path': str(path.resolve())}, 200


def on_blender_connected():
    """Called by server.py when Blender connects: send a pending IFC."""
    global _pending_ifc
    ifc_path, _pending_ifc = _pending_ifc, None
    if not ifc_path:
        return

    payload, status = load_ifc_in_blender(ifc_path)
    if status == 200:
        logger.info(f"Sent pending IFC to Blender: {ifc_path}")
    else:
        logger.warning(
            f"Could not load pending IFC {ifc_path}: {payload.get('error')}")


def launch_blender(auto_connect: bool = True, ifc_path: Optional[str] = None):
    """Start Blender, optionally loading an IFC once it has connected.

    Args:
        auto_connect: try to connect automatically after startup
        ifc_path: IFC to load as soon as Blender is connected

    Returns:
        (payload, http_status)
    """
    global _process, _launched_at, _pending_ifc

    if _blender_server is not None and _blender_server.is_client_connected():
        if ifc_path:
            return load_ifc_in_blender(ifc_path)
        return {'status': 'already_connected',
                'message': 'Blender is already connected.'}, 200

    # Remember the IFC even if Blender is already running but not yet
    # connected: it is sent the moment the user connects.
    if ifc_path:
        _pending_ifc = ifc_path

    if _process_running():
        return {'status': 'already_running',
                'message': 'Blender was already started and is still '
                           'running.', **get_process_state()}, 200

    executable = find_blender_executable()
    if executable is None:
        return {
            'status': 'not_found',
            'error': "Blender executable not found. Set 'Blender "
                     "executable' in the Settings tab.",
        }, 404

    command = [str(executable)]
    if auto_connect:
        command += ['--python-expr', AUTO_CONNECT_CODE]

    try:
        _process = subprocess.Popen(command)
        _launched_at = time.time()
    except Exception as e:
        logger.error(f"Could not start Blender ({executable}): {e}")
        return {'status': 'failed', 'error': f'Could not start Blender: {e}'}, 500

    logger.info(f"Started Blender (pid {_process.pid}): {executable}")
    return {
        'status': 'started',
        'message': 'Blender is starting.',
        'executable': str(executable),
        **get_process_state(),
    }, 200


@api_bp.route('/blender/launch', methods=['POST'])
def api_launch_blender():
    """POST /api/blender/launch - Start Blender.

    Optional body: {"auto_connect": true, "project_id": "..."}. With a
    project_id, that project's IFC is loaded once Blender has connected.
    """
    data = request.get_json(silent=True) or {}

    ifc_path = None
    project_id = data.get('project_id')
    if project_id:
        ifc_path = _project_ifc_path(project_id)
        if not ifc_path:
            return jsonify({'status': 'unknown_project',
                            'error': f'Project not found: {project_id}'}), 404

    payload, status = launch_blender(
        auto_connect=bool(data.get('auto_connect', True)),
        ifc_path=ifc_path)
    return jsonify(payload), status


@api_bp.route('/blender/load-ifc', methods=['POST'])
def api_load_ifc():
    """POST /api/blender/load-ifc - Load a project's IFC in Blender.

    Body: {"project_id": "..."}. The path comes from the stored project.
    """
    data = request.get_json(silent=True) or {}
    project_id = data.get('project_id')
    if not project_id:
        return jsonify({'error': 'project_id is required'}), 400

    ifc_path = _project_ifc_path(project_id)
    if not ifc_path:
        return jsonify({'status': 'unknown_project',
                        'error': f'Project not found: {project_id}'}), 404

    payload, status = load_ifc_in_blender(ifc_path)
    return jsonify(payload), status


@api_bp.route('/blender/refresh-status', methods=['POST'])
def api_refresh_status():
    """POST /api/blender/refresh-status - Ask Blender to report its status.

    Used after a page reload: Blender only reports on connect, so a freshly
    opened GUI would not know which IFC is loaded.
    """
    if _blender_server is None or not _blender_server.is_client_connected():
        return jsonify({'status': 'not_connected'}), 409
    _blender_server.send_message({'command': 'request_status'})
    return jsonify({'status': 'requested'})


@api_bp.route('/blender/process', methods=['GET'])
def api_blender_process():
    """GET /api/blender/process - State of the process this server started."""
    return jsonify(get_process_state())