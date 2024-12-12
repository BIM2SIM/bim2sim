"""bim2sim library"""
from importlib.metadata import version

from bim2sim.kernel.decision.console import ConsoleDecisionHandler
from bim2sim.kernel.decision.decisionhandler import DecisionHandler
from bim2sim.project import Project


try:
    __version__ = version("bim2sim")
except Exception:
    __version__ = "unknown"


def run_project(project: Project, handler: DecisionHandler):
    """Run project using decision handler."""
    return handler.handle(project.run(), project.loaded_decisions)
