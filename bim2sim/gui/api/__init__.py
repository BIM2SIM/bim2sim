"""API package for bim2sim GUI."""

from flask import Blueprint

# Create API blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api')

# Import routes - use absolute imports to avoid circular dependencies
try:
    from bim2sim.gui.api import projects  # Project management
    from bim2sim.gui.api import decisions  # Decision handling
    from bim2sim.gui.api import sessions
    from bim2sim.gui.api import blender
    from bim2sim.gui.api import backends  # Backend/Settings introspection
    from bim2sim.gui.api import logs      # Log viewer
    from bim2sim.gui.api import global_settings  # Machine-specific settings
    from bim2sim.gui.api import blender_launcher  # Start Blender from the GUI
except ImportError as e:
    import logging
    logging.error(f"Failed to import API routes: {e}")

__all__ = ['api_bp']