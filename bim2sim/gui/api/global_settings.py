"""
Global (machine-specific) settings API.

Some SimSettings depend on the machine rather than on the project, e.g.
where EnergyPlus or the AixLib Modelica library is installed. Entering
them in every single project is tedious and error-prone, so they can be
stored once here. They are applied to every project run as a fallback;
values set in the project itself take precedence (see
ProjectManager._apply_settings).

Stored in gui/data/global_settings.json as a flat name -> value mapping.
Names that a backend doesn't support are skipped when applying, so any
SimSettings name can be stored here safely.
"""

import json
import logging
from pathlib import Path

from flask import jsonify, request

from . import api_bp

logger = logging.getLogger(__name__)

# gui/api/global_settings.py -> gui/data/global_settings.json
SETTINGS_FILE = Path(__file__).parent.parent / 'data' / 'global_settings.json'

# Keys that configure the GUI itself rather than a bim2sim SimSetting. They
# are stored alongside the others but must never be applied to sim_settings
# or end up in a run's simulation-settings snapshot.
GUI_ONLY_KEYS = {'workspace_dir', 'blender_path'}

# Suggested entries shown in the frontend. Anything else can be added as a
# custom entry (e.g. Dymola-related settings).
KNOWN_GLOBAL_SETTINGS = [
    {
        'name': 'workspace_dir',
        'label': 'Working directory',
        'description': 'Folder where project runs are created, one subfolder '
                       'per run (<project>/<timestamp>_<run id>). If empty, '
                       'a temporary folder is used, which is hard to find '
                       'and cleaned up by the system eventually.',
        'placeholder': 'D:/bim2sim_runs',
        'is_path': True,
        'create_if_missing': True,
    },
    {
        'name': 'ep_install_path',
        'label': 'EnergyPlus installation path',
        'description': 'Folder containing Energy+.idd '
                       '(EnergyPlus and Comfort backends).',
        'placeholder': 'D:/Software/EnergyPlus/',
        'is_path': True,
    },
    {
        'name': 'blender_path',
        'label': 'Blender executable',
        'description': 'blender.exe of the Blender installation that has '
                       'Bonsai and the bim2sim add-on enabled. Used by '
                       '"Start Blender". If empty, common install '
                       'locations are searched.',
        'placeholder': 'C:/Program Files/Blender Foundation/Blender 4.2/blender.exe',
        'is_path': True,
    },
    {
        'name': 'path_aixlib',
        'label': 'AixLib Modelica library',
        'description': 'The package.mo inside the cloned AixLib repo, i.e. '
                       '.../AixLib/AixLib/package.mo, not the repo folder '
                       '(TEASER backend, only needed for Dymola simulation).',
        'placeholder': 'C:/path/to/AixLib/AixLib/package.mo',
        'is_path': True,
    },
]


def load_global_settings() -> dict:
    """Read the stored global settings (empty dict if none/unreadable)."""
    if not SETTINGS_FILE.exists():
        return {}
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning(f"Could not read global settings: {e}")
        return {}


def save_global_settings(settings: dict):
    """Write the global settings, dropping empty values."""
    cleaned = {
        str(k).strip(): v for k, v in settings.items()
        if str(k).strip() and v is not None and str(v).strip() != ''
    }
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)
    return cleaned


def get_workspace_dir():
    """The configured working directory as a Path, or None if unset."""
    value = load_global_settings().get('workspace_dir')
    if not value or not str(value).strip():
        return None
    try:
        return Path(str(value).strip()).expanduser()
    except Exception:
        return None


def _path_checks(settings: dict) -> dict:
    """For settings flagged as paths, report whether the path exists."""
    checks = {}
    for entry in KNOWN_GLOBAL_SETTINGS:
        name = entry['name']
        if entry['is_path'] and settings.get(name):
            try:
                checks[name] = Path(str(settings[name])).exists()
            except Exception:
                checks[name] = False
    return checks


@api_bp.route('/global-settings', methods=['GET'])
def get_global_settings():
    """GET /api/global-settings - Stored values plus suggested entries."""
    settings = load_global_settings()
    return jsonify({
        'settings': settings,
        'known': KNOWN_GLOBAL_SETTINGS,
        'path_checks': _path_checks(settings),
    })


@api_bp.route('/global-settings', methods=['PUT'])
def put_global_settings():
    """PUT /api/global-settings - Replace all stored global settings."""
    try:
        data = request.get_json()
        if not data or not isinstance(data.get('settings'), dict):
            return jsonify({'error': "Expected {'settings': {...}}"}), 400

        cleaned = save_global_settings(data['settings'])
        logger.info(f"Saved {len(cleaned)} global setting(s)")

        return jsonify({
            'settings': cleaned,
            'known': KNOWN_GLOBAL_SETTINGS,
            'path_checks': _path_checks(cleaned),
        })
    except Exception as e:
        logger.error(f"Error saving global settings: {e}")
        return jsonify({'error': str(e)}), 500