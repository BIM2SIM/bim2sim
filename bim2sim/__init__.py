"""bim2sim library"""

from bim2sim.kernel.decision.console import ConsoleDecisionHandler
from bim2sim.kernel.decision.decisionhandler import DecisionHandler
from bim2sim.project import Project


def run_project(project: Project, handler: DecisionHandler):
    """Run project using decision handler."""
    return handler.handle(project.run(), project.loaded_decisions)
