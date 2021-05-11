from ifcopenshell.file import file

from bim2sim.task.base import Task, ITask
from bim2sim.kernel.element import ProductBased
from bim2sim.workflow import Workflow


class Inspect(ITask):
    """Analyses IFC and creates Element instances.
    Elements are stored in .instances dict with guid as key"""

    reads = ('ifc',)
    touches = ('instances',)

    def __init__(self):
        super().__init__()
        self.instances = {}
        pass

    def run(self, workflow: Workflow, ifc: file):
        self.logger.info("Creates python representation of relevant ifc types")

        load(self.paths.finder)

        for ifc_type in workflow.relevant_ifc_types:
            try:
                entities = ifc.by_type(ifc_type)
                for entity in entities:
                    element = Element.factory(entity, ifc_type)
                    self.instances[element.guid] = element
            except RuntimeError:
                pass
        self.logger.info("Found %d building elements", len(self.instances))

        return self.instances,
