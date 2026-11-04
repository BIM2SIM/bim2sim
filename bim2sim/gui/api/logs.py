"""
Log API endpoint.

Buffers bim2sim log output for the frontend log viewer.
The buffer is populated by ensure_handler_registered(), which
must be called both at startup and before each project execution
to survive bim2sim's own logging configuration.
"""

import logging
from datetime import datetime
from flask import jsonify, request
from . import api_bp

_log_buffer = []
MAX_LOG_ENTRIES = 500

# Loggers we report status for in /logs/debug (informational only)
_TARGET_LOGGERS = [
    '',           # root
    'bim2sim',
    'bim2sim.gui',
    'bim2sim.kernel',
    'bim2sim.tasks',
    'werkzeug',
]

# Loggers we actually attach the handler to. IMPORTANT: only the root
# logger -- since propagate=True bubbles every record up the ancestor
# chain (e.g. bim2sim.gui.project_manager -> bim2sim.gui -> bim2sim ->
# root), attaching the same handler instance to multiple loggers in
# that chain causes emit() to fire once per level the record passes
# through, producing duplicate entries (observed as 3x duplication).
# Attaching only at root avoids this while still catching everything,
# as long as nothing in the chain sets propagate=False.
_ATTACH_LOGGERS = ['']

# Recurring, low-value messages -- polling requests and connection-wait
# spam. These are marked as noise and hidden from /api/logs by default,
# but stay in the buffer so they're available if explicitly requested
# (e.g. when debugging the Blender TCP connection itself).
_NOISE_SUBSTRINGS = (
    'GET /api/status',
    'GET /api/logs',
    'GET /api/decisions',
    'Waiting for Blender client connection',
)


# Maps thread name -> {'project_id': ..., 'run_id': ...}, so log entries
# emitted from a project's execution thread can be tagged with which
# project/run they belong to. Set via start_run()/end_run(), called from
# project_manager.py around each execution.
_thread_run_map = {}


def start_run(thread_name: str, project_id: str, run_id: str):
    """Associate a thread with a project run, for log tagging."""
    _thread_run_map[thread_name] = {
        'project_id': project_id,
        'run_id': run_id,
    }


def end_run(thread_name: str):
    """Remove the thread-to-run association once execution finishes."""
    _thread_run_map.pop(thread_name, None)


def get_run_logs(project_id: str, run_id: str):
    """Return all buffered log entries for a specific project run.

    Used by project_manager.py to persist a run's logs to disk once
    execution finishes. Includes noise entries (unlike the /api/logs
    endpoint's default), since this is the permanent record.
    """
    return [
        l for l in _log_buffer
        if l.get('project_id') == project_id and l.get('run_id') == run_id
    ]


def get_active_run_id(project_id: str):
    """Return the run_id currently associated with a project's execution
    thread, if any. Used when stopping a project, so the in-progress run
    record can be finalized with the logs collected so far instead of
    being left as an empty/near-empty stub."""
    for info in _thread_run_map.values():
        if info.get('project_id') == project_id:
            return info.get('run_id')
    return None


def _is_noise(message: str) -> bool:
    return any(s in message for s in _NOISE_SUBSTRINGS)


class FrontendLogHandler(logging.Handler):
    """Handler that stores records in the shared buffer."""

    def emit(self, record):
        try:
            # NOTE: formatTime() belongs to logging.Formatter, not
            # logging.Handler -- calling self.formatTime() here would
            # silently raise AttributeError on every call and get
            # swallowed by the except clause below, meaning nothing
            # ever reaches the buffer despite the handler being
            # correctly registered. Use datetime directly instead.
            message = record.getMessage()
            # getMessage() does not include exception info. Without this,
            # a failed task shows only "Task ... failed!" and the actual
            # cause (the traceback) is lost -- exactly the information
            # needed to investigate why a run did not succeed.
            if record.exc_info and record.exc_info[0] is not None:
                message += '\n' + logging.Formatter().formatException(
                    record.exc_info)
            elif record.exc_text:
                message += '\n' + record.exc_text

            entry = {
                'time': datetime.fromtimestamp(record.created).strftime('%H:%M:%S'),
                'level': record.levelname,
                'logger': record.name,
                'message': message,
            }
            entry['noise'] = _is_noise(entry['message'])
            run_info = _thread_run_map.get(record.threadName)
            entry['project_id'] = run_info['project_id'] if run_info else None
            entry['run_id'] = run_info['run_id'] if run_info else None
            _log_buffer.append(entry)
            if len(_log_buffer) > MAX_LOG_ENTRIES:
                del _log_buffer[:-MAX_LOG_ENTRIES]
        except Exception as e:
            # Don't swallow silently anymore -- print so it's at least
            # visible in the console if something goes wrong here again.
            print(f"[FrontendLogHandler] emit() failed: {e}")


# Single shared handler instance
_handler = FrontendLogHandler()
_handler.setLevel(logging.DEBUG)


def ensure_handler_registered():
    """Attach our handler to the root logger only.

    Safe to call multiple times -- skips if already attached.
    Call this at server startup AND before each project execution.

    Also checks the watched loggers for propagate=False, which would
    prevent their records from ever reaching the root handler; if found,
    the handler is attached there too as a fallback (accepting the small
    risk of duplicates for that specific branch, which is still better
    than missing logs entirely).
    """
    root = logging.getLogger('')
    if not any(isinstance(h, FrontendLogHandler) for h in root.handlers):
        root.addHandler(_handler)
    if root.level == logging.NOTSET or root.level > logging.DEBUG:
        root.setLevel(logging.DEBUG)

    for name in _TARGET_LOGGERS:
        if name == '':
            continue
        lgr = logging.getLogger(name)
        if lgr.level == logging.NOTSET:
            lgr.setLevel(logging.DEBUG)
        if not lgr.propagate:
            # Fallback: this branch would never reach root, attach directly
            if not any(isinstance(h, FrontendLogHandler) for h in lgr.handlers):
                lgr.addHandler(_handler)


# Alias used by server.py
register_log_handler = ensure_handler_registered


@api_bp.route('/logs', methods=['GET'])
def get_logs():
    """GET /api/logs - Return recent log entries.

    By default, recurring low-value entries (polling requests, Blender
    connection-wait spam) are hidden. Pass ?show_noise=true to include them.
    Pass ?project_id=... and/or ?run_id=... to scope to a single project run.
    """
    level = request.args.get('level', 'all').upper()
    limit = int(request.args.get('limit', 300))
    show_noise = request.args.get('show_noise', 'false').lower() == 'true'
    project_id = request.args.get('project_id')
    run_id = request.args.get('run_id')

    logs = list(_log_buffer)
    if not show_noise:
        logs = [l for l in logs if not l.get('noise')]
    if project_id:
        logs = [l for l in logs if l.get('project_id') == project_id]
    if run_id:
        logs = [l for l in logs if l.get('run_id') == run_id]
    logs = logs[-limit:]

    if level != 'ALL':
        level_num = getattr(logging, level, None)
        if level_num is not None:
            logs = [l for l in logs
                    if logging.getLevelName(l['level']) >= level_num]

    return jsonify({'logs': logs, 'total': len(_log_buffer)})


@api_bp.route('/logs', methods=['DELETE'])
def delete_logs():
    """DELETE /api/logs - Clear the log buffer."""
    _log_buffer.clear()
    return jsonify({'message': 'Log buffer cleared'})


@api_bp.route('/logs/debug', methods=['GET'])
def debug_logs():
    """GET /api/logs/debug - Show handler registration status."""
    status = {}
    for name in _TARGET_LOGGERS:
        lgr = logging.getLogger(name)
        status[name or 'root'] = {
            'level': logging.getLevelName(lgr.level),
            'handlers': [type(h).__name__ for h in lgr.handlers],
            'propagate': lgr.propagate,
            'has_frontend_handler': any(
                isinstance(h, FrontendLogHandler) for h in lgr.handlers
            )
        }
    return jsonify({
        'buffer_size': len(_log_buffer),
        'loggers': status
    })