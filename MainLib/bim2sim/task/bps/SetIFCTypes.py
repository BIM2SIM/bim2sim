from bim2sim.task.base import ITask


class SetIFCTypes(ITask):
    """Set list of relevant IFC types"""
    touches = ('relevant_ifc_types',)

    def run(self, workflow):
        IFC_TYPES = workflow.relevant_ifc_types
        return IFC_TYPES,
