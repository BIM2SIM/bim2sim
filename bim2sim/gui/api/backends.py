"""
Backend and SimSettings introspection API.

Uses bim2sim's own plugin discovery (bim2sim.plugins.available_plugins /
load_plugin) instead of a hardcoded backend list, so newly installed
plugins are picked up automatically.
"""

import logging
from flask import jsonify
from . import api_bp

logger = logging.getLogger(__name__)

# Cosmetic overrides only -- discovery itself is fully dynamic.
# If a plugin isn't listed here, a generic label/domain is derived.
LABEL_OVERRIDES = {
    'aixlib': 'AixLib (Hydraulic)',
    'teaser': 'TEASER (Building Performance)',
    'energyplus': 'EnergyPlus (Building Energy)',
    'comfort': 'Comfort (Thermal Comfort)',
    'lca': 'LCA (Life Cycle Assessment)',
    'hkesim': 'HKESim (Hydraulic)',
}
DOMAIN_OVERRIDES = {
    'aixlib': 'hydraulic',
    'hkesim': 'hydraulic',
    'teaser': 'arch',
    'energyplus': 'arch',
    'comfort': 'arch',
    'lca': 'arch',
}

# Simple in-process cache: backend name -> Plugin class
_plugin_cache = {}


def _discover_backend_names():
    """Return backend names (without 'bim2sim_' prefix) via bim2sim's
    own plugin discovery mechanism."""
    from bim2sim.plugins import available_plugins

    names = []
    for module_name in available_plugins():
        name = module_name
        if name.startswith('bim2sim_'):
            name = name[len('bim2sim_'):]
        # Skip the generic template plugin, not meant for end users
        if name == 'template':
            continue
        names.append(name)
    return sorted(set(names))


def _load_plugin_class(backend_name):
    """Load and cache the Plugin class for a backend name."""
    if backend_name in _plugin_cache:
        return _plugin_cache[backend_name]

    from bim2sim.plugins import load_plugin

    try:
        plugin_cls = load_plugin(backend_name)
        _plugin_cache[backend_name] = plugin_cls
        return plugin_cls
    except Exception as e:
        logger.warning(f"Cannot load plugin '{backend_name}': {e}")
        return None


def _serialize_setting(setting):
    """Convert a Setting instance to a JSON-serializable dict."""
    from bim2sim.sim_settings import (
        BooleanSetting, ChoiceSetting, NumberSetting, PathSetting
    )

    data = {
        'name': setting.name,
        'description': setting.description or '',
        'default': None,
        'for_frontend': setting.for_webapp,
        'mandatory': setting.mandatory,
        'any_string': setting.any_string,
    }

    if isinstance(setting, BooleanSetting):
        data['type'] = 'boolean'
        data['default'] = setting.default
    elif isinstance(setting, NumberSetting):
        data['type'] = 'number'
        data['default'] = setting.default
        data['min_value'] = setting.min_value
        data['max_value'] = setting.max_value
        if data['max_value'] == float('inf'):
            data['max_value'] = None
    elif isinstance(setting, ChoiceSetting):
        data['type'] = 'choice'
        data['multiple_choice'] = setting.multiple_choice
        choices = {}
        if setting.choices:
            for key, desc in setting.choices.items():
                choices[str(key)] = desc
        data['choices'] = choices
        if isinstance(setting.default, list):
            data['default'] = [str(d) for d in setting.default]
        elif setting.default is not None:
            data['default'] = str(setting.default)
    elif isinstance(setting, PathSetting):
        data['type'] = 'path'
        if setting.default is not None:
            data['default'] = str(setting.default)
    else:
        data['type'] = 'string'
        data['default'] = setting.default

    return data


def _get_all_settings(settings_class):
    """Get all settings from a SimSettings class hierarchy.

    Returns a dict mapping setting name to (setting, is_base) tuples.
    is_base=True means the setting is defined in a core base class
    (BaseSimSettings, BuildingSimSettings or PlantSimSettings) --
    i.e. it's a "General" setting shared across all plugins, regardless
    of how deep the plugin's own class hierarchy is.
    """
    from bim2sim.sim_settings import Setting, BaseSimSettings

    try:
        from bim2sim.sim_settings import BuildingSimSettings, PlantSimSettings
        base_classes = {BaseSimSettings, BuildingSimSettings, PlantSimSettings}
    except ImportError:
        base_classes = {BaseSimSettings}

    settings = {}
    for cls in reversed(settings_class.__mro__):
        for attr_name in vars(cls):
            attr = getattr(cls, attr_name, None)
            if isinstance(attr, Setting):
                is_base = cls in base_classes
                settings[attr_name] = (attr, is_base)

    return settings


@api_bp.route('/backends', methods=['GET'])
def list_backends():
    """GET /api/backends - List available backends via plugin discovery."""
    backends = []

    try:
        names = _discover_backend_names()
    except Exception as e:
        logger.error(f"Plugin discovery failed: {e}")
        return jsonify({'backends': [], 'error': str(e)})

    for name in names:
        plugin_cls = _load_plugin_class(name)
        available = plugin_cls is not None

        label = LABEL_OVERRIDES.get(name, name.replace('_', ' ').title())
        domain = DOMAIN_OVERRIDES.get(name, 'arch')

        backends.append({
            'name': name,
            'label': label,
            'domain': domain,
            'available': available
        })

    return jsonify({'backends': backends})


@api_bp.route('/backends/<backend>/settings', methods=['GET'])
def get_backend_settings(backend):
    """GET /api/backends/<backend>/settings - Get settings schema."""
    plugin_cls = _load_plugin_class(backend)
    if not plugin_cls:
        return jsonify({
            'error': f'Cannot load plugin: {backend}',
            'base_settings': [],
            'plugin_settings': []
        }), 200

    settings_class = plugin_cls.sim_settings
    if not settings_class:
        return jsonify({
            'error': f'Plugin {backend} defines no sim_settings',
            'base_settings': [],
            'plugin_settings': []
        }), 200

    try:
        all_settings = _get_all_settings(settings_class)

        base_settings = []
        plugin_settings = []

        for name, (setting, is_base) in sorted(all_settings.items()):
            serialized = _serialize_setting(setting)
            if is_base:
                base_settings.append(serialized)
            else:
                plugin_settings.append(serialized)

        label = LABEL_OVERRIDES.get(backend, backend.replace('_', ' ').title())
        domain = DOMAIN_OVERRIDES.get(backend, 'arch')

        return jsonify({
            'backend': backend,
            'label': label,
            'domain': domain,
            'base_settings': base_settings,
            'plugin_settings': plugin_settings,
            'total': len(base_settings) + len(plugin_settings)
        })

    except Exception as e:
        logger.error(f"Error getting settings for {backend}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500