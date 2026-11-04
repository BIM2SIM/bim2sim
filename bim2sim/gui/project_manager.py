"""
Project Manager for bim2sim GUI.

Handles:
- Project creation, loading, and deletion
- JSON-based project persistence
- Thread-based project execution with WebGUIDecisionHandler
- SocketIO integration for real-time updates
"""

import json
import logging
import threading
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List, Any
import uuid

logger = logging.getLogger(__name__)


class ProjectManager:
    """Manages bim2sim projects with JSON persistence and execution."""

    def __init__(self, projects_dir: Path = None, socketio=None):
        """
        Initialize Project Manager.

        Args:
            projects_dir: Directory to store project JSON files
            socketio: SocketIO instance for real-time updates
        """
        if projects_dir is None:
            # Default: gui/data/projects/
            projects_dir = Path(__file__).parent / 'data' / 'projects'

        self.projects_dir = Path(projects_dir)
        self.projects_dir.mkdir(parents=True, exist_ok=True)

        # Persisted run history: gui/data/runs/<project_id>/<run_id>.json
        self.runs_dir = self.projects_dir.parent / 'runs'
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self._reconcile_interrupted_runs()

        self.socketio = socketio

        # Active execution threads
        self.active_executions: Dict[str, threading.Thread] = {}

        # Runtime-only status tracking (never persisted to JSON)
        self.project_statuses: Dict[str, str] = {}

        # Reference to Blender TCP server (set by server.py after init)
        self.blender_server = None

        logger.info(f"Project Manager initialized: {self.projects_dir}")

    def list_projects(self) -> List[Dict[str, Any]]:
        """
        List all available projects.

        Returns:
            List of project metadata dicts
        """
        projects = []

        for project_file in self.projects_dir.glob("*.json"):
            try:
                with open(project_file, 'r', encoding='utf-8') as f:
                    project_data = json.load(f)

                # Status is runtime-only, determined from in-memory state
                project_id = project_data.get('id', project_file.stem)
                project_data['status'] = self._get_runtime_status(project_id)

                projects.append(project_data)

            except Exception as e:
                logger.warning(f"Error reading project {project_file.name}: {e}")
                continue

        # Sort by created_at (newest first)
        projects.sort(key=lambda p: p.get('created_at', ''), reverse=True)

        return projects

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Load a single project by ID.

        Args:
            project_id: Project identifier

        Returns:
            Project data dict or None if not found
        """
        project_file = self.projects_dir / f"{project_id}.json"

        if not project_file.exists():
            logger.warning(f"Project not found: {project_id}")
            return None

        try:
            with open(project_file, 'r', encoding='utf-8') as f:
                project_data = json.load(f)

            # Status is runtime-only, determined from in-memory state
            project_data['status'] = self._get_runtime_status(project_id)

            logger.info(f"Loaded project: {project_id}")
            return project_data

        except Exception as e:
            logger.error(f"Error loading project {project_id}: {e}")
            return None

    def create_project(self, project_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new project.

        Args:
            project_data: Project definition with at minimum:
                - name: str
                - ifc_path: str
                - backend: str (e.g. 'aixlib')
                - domain: str (e.g. 'hydraulic')

        Returns:
            Created project data with generated ID
        """
        # Generate ID if not provided
        if 'id' not in project_data:
            project_data['id'] = f"project_{uuid.uuid4().hex[:8]}"

        # Set timestamps
        now = datetime.now().isoformat()
        project_data.setdefault('created_at', now)
        project_data['updated_at'] = now

        # Set default values
        project_data.setdefault('description', '')
        project_data.setdefault('settings', {})

        # Status is runtime-only, not persisted
        project_data.pop('status', None)

        # Save to disk
        project_file = self.projects_dir / f"{project_data['id']}.json"

        try:
            with open(project_file, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Created project: {project_data['id']}")

            # Add status for API response (but not in JSON)
            project_data['status'] = 'idle'
            return project_data

        except Exception as e:
            logger.error(f"Error creating project: {e}")
            raise

    def update_project(self, project_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update project metadata.

        Status changes are stored in memory only, all other fields
        are persisted to JSON.

        Args:
            project_id: Project identifier
            updates: Fields to update

        Returns:
            Success status
        """
        # Handle status updates in memory only
        if 'status' in updates:
            self.project_statuses[project_id] = updates.pop('status')
            logger.info(f"Runtime status for {project_id}: {self.project_statuses[project_id]}")

        # If no remaining updates to persist, we're done
        if not updates:
            return True

        project = self.get_project(project_id)
        if not project:
            return False

        # Update fields
        project.update(updates)
        project['updated_at'] = datetime.now().isoformat()

        # Strip status before saving (should not be in JSON)
        project.pop('status', None)

        # Save
        project_file = self.projects_dir / f"{project_id}.json"

        try:
            with open(project_file, 'w', encoding='utf-8') as f:
                json.dump(project, f, indent=2, ensure_ascii=False)

            logger.info(f"Updated project: {project_id}")
            return True

        except Exception as e:
            logger.error(f"Error updating project {project_id}: {e}")
            return False

    def delete_project(self, project_id: str) -> bool:
        """
        Delete a project.

        Args:
            project_id: Project identifier

        Returns:
            Success status
        """
        # Don't delete if running
        if project_id in self.active_executions:
            thread = self.active_executions[project_id]
            if thread.is_alive():
                logger.warning(f"Cannot delete running project: {project_id}")
                return False

        project_file = self.projects_dir / f"{project_id}.json"

        if not project_file.exists():
            logger.warning(f"Project not found for deletion: {project_id}")
            return False

        try:
            project_file.unlink()
            # Clean up runtime state
            self.project_statuses.pop(project_id, None)
            logger.info(f"Deleted project: {project_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting project {project_id}: {e}")
            return False

    def execute_project(self, project_id: str) -> bool:
        """
        Execute a project in a separate thread.

        Args:
            project_id: Project identifier

        Returns:
            Success status (True if started, False if already running or error)
        """
        # Check if already running
        if project_id in self.active_executions:
            thread = self.active_executions[project_id]
            if thread.is_alive():
                logger.warning(f"Project already running: {project_id}")
                return False

        project = self.get_project(project_id)
        if not project:
            return False

        # Update status
        self.update_project(project_id, {'status': 'running'})

        # Broadcast status change
        if self.socketio:
            self.socketio.emit('project_status_changed', {
                'project_id': project_id,
                'status': 'running',
                'timestamp': time.time()
            })

        # Start execution thread
        thread = threading.Thread(
            target=self._execute_project_thread,
            args=(project,),
            daemon=True,
            name=f"project_{project_id}"
        )
        thread.start()

        self.active_executions[project_id] = thread

        logger.info(f"Started execution of project: {project_id}")
        return True

    def _execute_project_thread(self, project_data: Dict[str, Any]):
        """
        Thread worker for project execution.

        Args:
            project_data: Complete project definition
        """
        project_id = project_data['id']

        # Generate the run_id and tag this thread FIRST, before any other
        # work happens -- otherwise early log lines (directory creation,
        # settings application) would still carry a stale run_id left over
        # from a previous, unfinished execution of the same project
        # (same thread name is reused across runs).
        run_id = uuid.uuid4().hex[:8]
        started_at = datetime.now().isoformat()
        # Overwritten with the effective settings (project + global) once
        # they have been applied; until then the project's own settings.
        effective_settings = project_data.get('settings', {})
        # Set once the run folder exists; recorded so the run history can
        # point to where this run's files (e.g. the export) ended up.
        project_path = None
        try:
            from bim2sim.gui.api.logs import (
                ensure_handler_registered, start_run
            )
            ensure_handler_registered()
            start_run(threading.current_thread().name, project_id, run_id)
        except Exception as e:
            logger.warning(f"Could not register log handler/run: {e}")

        # Write an initial run record right away, so this run is visible
        # in the history immediately -- including if it later hangs
        # (e.g. waiting on decisions) or the process is killed before it
        # ever reaches a final completed/error state.
        self._save_run_record(
            project_id, run_id, 'running', started_at,
            settings_snapshot=project_data.get('settings', {})
        )

        try:
            logger.info(
                f"Executing project in thread: {project_id} "
                f"(run_id={run_id})"
            )

            # Import bim2sim components
            from bim2sim import Project
            from bim2sim.utilities.types import IFCDomain
            from bim2sim.kernel.decision.webgui_decisionhandler import WebGUIDecisionHandler
            import tempfile

            # Create the run folder. With a configured working directory,
            # every run gets its own readable, sortable folder there:
            #   <workspace>/<project_id>/<YYYYMMDD_HHMMSS>_<run_id>
            # Without one (or if it can't be created), fall back to a
            # temporary folder as before.
            project_path = None
            try:
                from bim2sim.gui.api.global_settings import get_workspace_dir
                workspace = get_workspace_dir()
                if workspace:
                    run_folder = (
                        workspace / project_id /
                        f"{datetime.now():%Y%m%d_%H%M%S}_{run_id}"
                    )
                    run_folder.mkdir(parents=True, exist_ok=True)
                    project_path = run_folder
            except Exception as e:
                logger.warning(
                    f"Could not use the configured working directory, "
                    f"falling back to a temporary folder: {e}"
                )

            if project_path is None:
                project_path = Path(
                    tempfile.mkdtemp(prefix=f'bim2sim_{project_id}_')
                )

            logger.info(f"Project directory: {project_path}")

            # Update the stub so even a run that hangs shows its folder
            self._save_run_record(
                project_id, run_id, 'running', started_at,
                settings_snapshot=effective_settings,
                project_path=str(project_path)
            )

            # Parse domain
            domain_str = project_data.get('domain', 'hydraulic')
            domain = getattr(IFCDomain, domain_str, IFCDomain.hydraulic)

            # IFC paths
            ifc_paths = {
                domain: Path(project_data['ifc_path'])
            }

            # Validate IFC path
            if not ifc_paths[domain].exists():
                raise FileNotFoundError(f"IFC file not found: {project_data['ifc_path']}")

            # Send IFC path to Blender for loading (if connected)
            if self.blender_server and self.blender_server.is_client_connected():
                ifc_path_str = str(ifc_paths[domain].resolve())
                logger.info(f"Sending load_ifc command to Blender: {ifc_path_str}")
                self.blender_server.send_load_ifc_command(ifc_path_str)
                # Give Blender time to start loading
                time.sleep(1.0)
            else:
                logger.info("Blender not connected, skipping IFC load command")

            # Create bim2sim project
            backend = project_data.get('backend', 'aixlib')
            project = Project.create(project_path, ifc_paths, backend)

            # Apply settings generically from project data, with global
            # (machine-specific) settings as fallback. 'settings' becomes
            # the effective set, which is also what the run history shows.
            settings = self._apply_settings(
                project, project_data.get('settings', {}))
            effective_settings = settings

            logger.info("Project settings configured")

            # Safety net: re-ensure the handler is still attached, in case
            # bim2sim's own logging setup (triggered during import/Project
            # creation above) reconfigured things. run_id/start_run were
            # already set at the very start of this thread.
            try:
                from bim2sim.gui.api.logs import ensure_handler_registered
                ensure_handler_registered()
            except Exception as e:
                logger.warning(f"Could not re-register log handler: {e}")

            # Create WebGUI DecisionHandler with SocketIO
            handler = WebGUIDecisionHandler(socketio=self.socketio)

            # Execute project with handler
            logger.info("Starting project execution with WebGUIDecisionHandler")
            result = handler.handle(project.run(interactive=False))

            # Project.run() catches task exceptions itself (logs them via
            # logger.exception) and returns 0 on success, -1 on failure --
            # it does NOT raise. So returning normally does not mean the
            # run succeeded; the return code has to be checked.
            failed = result is not None and result != 0

            if failed:
                error_text = (
                    f"bim2sim reported an unsuccessful run (return code "
                    f"{result}). See the log for the cause."
                )
                logger.error(f"Project run was not successful: {project_id}")

                self.update_project(project_id, {'status': 'error'})

                if self.socketio:
                    self.socketio.emit('project_status_changed', {
                        'project_id': project_id,
                        'status': 'error',
                        'timestamp': time.time(),
                        'error': error_text
                    })

                handler.shutdown(success=False)

                self._save_run_record(
                    project_id, run_id, 'error', started_at,
                    settings_snapshot=settings,
                    error=error_text,
                    finished_at=datetime.now().isoformat(),
                    project_path=str(project_path)
                )
            else:
                logger.info(f"Project executed successfully: {project_id}")

                self.update_project(project_id, {'status': 'completed'})

                if self.socketio:
                    self.socketio.emit('project_status_changed', {
                        'project_id': project_id,
                        'status': 'completed',
                        'timestamp': time.time(),
                        'result': str(result)
                    })

                handler.shutdown(success=True)

                self._save_run_record(
                    project_id, run_id, 'completed', started_at,
                    settings_snapshot=settings,
                    finished_at=datetime.now().isoformat(),
                    project_path=str(project_path)
                )

        except Exception as e:
            logger.error(f"Project execution error: {e}")
            import traceback
            traceback.print_exc()

            self.update_project(project_id, {'status': 'error'})

            if self.socketio:
                self.socketio.emit('project_status_changed', {
                    'project_id': project_id,
                    'status': 'error',
                    'timestamp': time.time(),
                    'error': str(e)
                })

            # Shutdown handler if exists
            try:
                from bim2sim.kernel.decision.webgui_decisionhandler import WebGUIDecisionHandler
                handler = WebGUIDecisionHandler.get_instance()
                if handler:
                    handler.shutdown(success=False)
            except:
                pass

            self._save_run_record(
                project_id, run_id, 'error', started_at,
                settings_snapshot=effective_settings,
                error=str(e),
                finished_at=datetime.now().isoformat(),
                project_path=str(project_path) if project_path else None
            )

        finally:
            # Remove from active executions
            if project_id in self.active_executions:
                del self.active_executions[project_id]

            # Clean up thread-to-run log tagging
            try:
                from bim2sim.gui.api.logs import end_run
                end_run(threading.current_thread().name)
            except Exception:
                pass

            logger.info(f"Project thread finished: {project_id}")

    @staticmethod
    def _find_setting(sim_settings, key):
        """Find the Setting definition for a name by walking the MRO."""
        for cls in type(sim_settings).__mro__:
            if key in vars(cls):
                return vars(cls)[key]
        return None

    @staticmethod
    def _same_value(a, b) -> bool:
        """Loose equality that also treats '/x/y' and Path('/x/y') alike."""
        if a == b:
            return True
        try:
            return Path(str(a)) == Path(str(b))
        except Exception:
            return str(a) == str(b)

    def _merge_global_settings(self, project, settings: dict) -> dict:
        """Combine global (machine-specific) settings with project settings.

        Project values win. The exception: a project value that is merely
        the setting's default -- which the project form pre-fills -- is not
        a deliberate choice and must not override a global value.
        """
        try:
            from bim2sim.gui.api.global_settings import (
                load_global_settings, GUI_ONLY_KEYS
            )
            # GUI-only entries (e.g. workspace_dir) are not SimSettings
            global_settings = {
                k: v for k, v in load_global_settings().items()
                if k not in GUI_ONLY_KEYS
            }
        except Exception as e:
            logger.warning(f"Could not load global settings: {e}")
            return dict(settings)

        effective = dict(global_settings)
        for key, value in settings.items():
            if key in global_settings:
                setting_obj = self._find_setting(project.sim_settings, key)
                if (setting_obj is not None
                        and hasattr(setting_obj, 'default')
                        and self._same_value(value, setting_obj.default)):
                    continue  # keep the global value
            effective[key] = value

        used = [k for k in global_settings if effective.get(k) ==
                global_settings[k]]
        if used:
            logger.info(f"Applying global setting(s) as fallback: {used}")
        return effective

    def _apply_settings(self, project, settings: dict) -> dict:
        """Apply settings dict to a bim2sim project's sim_settings.

        Global (machine-specific) settings are applied as a fallback for
        anything the project doesn't set itself. Handles type coercion for
        paths, enums and booleans. Unknown or unsupported settings are
        logged and skipped.

        Returns:
            The effective settings (project + global) that were attempted.
        """
        from bim2sim.sim_settings import (
            PathSetting, BooleanSetting, NumberSetting, ChoiceSetting
        )

        settings = self._merge_global_settings(project, settings)
        effective = dict(settings)

        for key, value in settings.items():
            if value is None or value == '':
                continue

            if not hasattr(project.sim_settings, key):
                logger.debug(f"Setting '{key}' not supported by this backend, skipping")
                continue

            try:
                setting_obj = type(project.sim_settings).__dict__.get(key)
                # Walk MRO to find the setting definition
                if setting_obj is None:
                    for cls in type(project.sim_settings).__mro__:
                        if key in vars(cls):
                            setting_obj = vars(cls)[key]
                            break

                # The form submits every setting with its default value.
                # A value equal to the setting's own default is already in
                # effect, so re-applying it is pointless -- and can even
                # fail: e.g. building_rotation_overwrite has default 0, but
                # bim2sim's validation rejects 0 (minimum is just above 0).
                if (setting_obj is not None
                        and hasattr(setting_obj, 'default')
                        and type(value) is type(setting_obj.default)
                        and value == setting_obj.default):
                    logger.debug(
                        f"Setting '{key}' equals its default ({value!r}), "
                        f"not re-applying")
                    continue

                if isinstance(setting_obj, PathSetting):
                    path = Path(value)
                    # Resolve relative paths against bim2sim root
                    if not path.is_absolute():
                        import bim2sim as b2s
                        path = Path(b2s.__file__).parent.parent / value
                    if path.exists():
                        setattr(project.sim_settings, key, path)
                        logger.info(f"Setting {key} = {path}")
                    else:
                        logger.warning(f"Path not found for '{key}': {path}")

                elif isinstance(setting_obj, BooleanSetting):
                    # Frontend sends booleans correctly, but guard against strings
                    if isinstance(value, str):
                        value = value.lower() in ('true', '1', 'yes')
                    setattr(project.sim_settings, key, bool(value))
                    logger.info(f"Setting {key} = {value}")

                elif isinstance(setting_obj, NumberSetting):
                    setattr(project.sim_settings, key, float(value)
                            if isinstance(value, str) else value)
                    logger.info(f"Setting {key} = {value}")

                elif isinstance(setting_obj, ChoiceSetting):
                    # Enum values come as strings like 'LOD.low'
                    if isinstance(value, str) and '.' in value:
                        from bim2sim.utilities import types
                        enum_type_name, enum_val = value.split('.', 1)
                        enum_type = getattr(types, enum_type_name, None)
                        if enum_type:
                            value = getattr(enum_type, enum_val)
                    setattr(project.sim_settings, key, value)
                    logger.info(f"Setting {key} = {value}")

                else:
                    setattr(project.sim_settings, key, value)
                    logger.info(f"Setting {key} = {value}")

            except Exception as e:
                logger.warning(f"Could not apply setting '{key}' = {value!r}: {e}")

        return effective

    def get_project_status(self, project_id: str) -> Optional[str]:
        """
        Get current project status (runtime only).

        Args:
            project_id: Project identifier

        Returns:
            Status string or None if project doesn't exist
        """
        # Check if project exists at all
        project_file = self.projects_dir / f"{project_id}.json"
        if not project_file.exists():
            return None

        return self._get_runtime_status(project_id)

    def _get_runtime_status(self, project_id: str) -> str:
        """
        Determine project status from runtime state.

        Priority: active thread > in-memory status > 'idle' default.
        """
        # Check active execution threads first
        if project_id in self.active_executions:
            thread = self.active_executions[project_id]
            if thread.is_alive():
                return 'running'
            # Thread finished but not cleaned up yet
            del self.active_executions[project_id]

        # Check in-memory status
        return self.project_statuses.get(project_id, 'idle')

    def _save_run_record(self, project_id: str, run_id: str, status: str,
                          started_at: str, settings_snapshot: dict,
                          error: str = None, finished_at: str = None,
                          project_path: str = None):
        """Persist a project run to disk (create or update).

        Called multiple times per run: once immediately when execution
        starts (status='running', finished_at=None) so in-progress and
        hung runs are visible in the history too, and again when the run
        finishes (status='completed'/'error', finished_at set) to update
        the same record with the final outcome and full logs.

        Args:
            project_id: Project identifier
            run_id: Unique identifier for this specific run
            status: 'running', 'completed', 'error' or 'interrupted'
            started_at: ISO timestamp of when the run started
            settings_snapshot: The settings dict as applied for this run
            error: Error message, if status is 'error'
            finished_at: ISO timestamp of completion, or None if still running
            project_path: Folder the run was executed in (holds the export)
        """
        try:
            from bim2sim.gui.api.logs import get_run_logs
            logs = get_run_logs(project_id, run_id)
        except Exception as e:
            logger.warning(f"Could not retrieve logs for run {run_id}: {e}")
            logs = []

        record = {
            'run_id': run_id,
            'project_id': project_id,
            'status': status,
            'started_at': started_at,
            'finished_at': finished_at,
            'project_path': project_path,
            'settings_snapshot': settings_snapshot,
            'error': error,
            'log_count': len(logs),
            'logs': logs,
        }

        run_dir = self.runs_dir / project_id
        run_dir.mkdir(parents=True, exist_ok=True)
        run_file = run_dir / f"{run_id}.json"

        try:
            with open(run_file, 'w', encoding='utf-8') as f:
                json.dump(record, f, indent=2, ensure_ascii=False,
                          default=str)
            logger.debug(f"Saved run record ({status}): {run_file}")
        except Exception as e:
            logger.error(f"Error saving run record {run_file}: {e}")

    def finalize_run(self, project_id: str, run_id: str, status: str,
                      error: str = None):
        """Finalize a run record from outside the execution thread itself.

        Used when a run is stopped by the user rather than reaching its
        own natural completed/error branch -- loads the existing stub
        record (for started_at/settings_snapshot) and re-saves it with
        the current status and the logs collected so far, instead of
        leaving it stuck with the near-empty snapshot from the initial
        'running' stub write.
        """
        existing = self.get_run(project_id, run_id)
        if not existing:
            logger.warning(
                f"Cannot finalize run {run_id} for {project_id}: "
                f"no existing record found"
            )
            return

        self._save_run_record(
            project_id, run_id, status,
            started_at=existing.get('started_at'),
            settings_snapshot=existing.get('settings_snapshot', {}),
            error=error,
            finished_at=datetime.now().isoformat(),
            project_path=existing.get('project_path')
        )

    def _reconcile_interrupted_runs(self):
        """On startup, mark any run still showing 'running' as interrupted.

        This is a fresh process, so no thread can genuinely still be
        executing a run recorded on disk -- if a run's status is still
        'running', the previous server process must have been stopped
        or crashed while that run was in progress. Without this, such
        runs would remain stuck showing "running" forever.
        """
        if not self.runs_dir.exists():
            return

        count = 0
        for run_file in self.runs_dir.glob('*/*.json'):
            try:
                with open(run_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                if data.get('status') != 'running':
                    continue

                data['status'] = 'interrupted'
                data['error'] = data.get('error') or (
                    'Server was stopped or restarted while this run was '
                    'in progress; final outcome unknown.'
                )
                data['finished_at'] = (
                    data.get('finished_at') or datetime.now().isoformat()
                )

                with open(run_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False,
                              default=str)
                count += 1

            except Exception as e:
                logger.warning(
                    f"Could not reconcile run record {run_file}: {e}"
                )

        if count:
            logger.info(
                f"Marked {count} interrupted run(s) left over from a "
                f"previous session"
            )

    def list_runs(self, project_id: str) -> List[Dict[str, Any]]:
        """List all persisted runs for a project, newest first.

        Log entries are omitted from this listing to keep it light --
        use get_run() to fetch a single run's full logs.
        """
        run_dir = self.runs_dir / project_id
        if not run_dir.exists():
            return []

        runs = []
        for run_file in run_dir.glob('*.json'):
            try:
                with open(run_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                runs.append({k: v for k, v in data.items() if k != 'logs'})
            except Exception as e:
                logger.warning(f"Error reading run record {run_file}: {e}")
                continue

        runs.sort(key=lambda r: r.get('started_at', ''), reverse=True)
        return runs

    def get_run(self, project_id: str, run_id: str) -> Optional[Dict[str, Any]]:
        """Get full details (including logs) of a single persisted run."""
        run_file = self.runs_dir / project_id / f"{run_id}.json"
        if not run_file.exists():
            return None

        try:
            with open(run_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading run record {run_file}: {e}")
            return None