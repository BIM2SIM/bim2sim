from bim2sim.task.base import ITask
from bim2sim.workflow import Workflow


class SetIFCTypes(ITask):
    """Set list of relevant IFC types"""
    touches = ('relevant_ifc_types',)

    def run(self, workflow: Workflow):
        IFC_TYPES = workflow.relevant_ifc_types
        return IFC_TYPES,
