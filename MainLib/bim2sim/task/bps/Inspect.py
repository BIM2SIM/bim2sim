from bim2sim.task.base import Task, ITask
from bim2sim.project import PROJECT
from bim2sim.decision import BoolDecision
from bim2sim.kernel.element import Element


class Inspect(ITask):
    """Analyses IFC and creates Element instances.
    Elements are stored in .instances dict with guid as key"""

    reads = ('ifc',)
    touches = ('instances',)

    def __init__(self):
        super().__init__()
        self.instances = {}
        pass

    @Task.log
    def run(self, workflow, ifc):
        self.logger.info("Creates python representation of relevant ifc types")

        Element.finder.load(PROJECT.finder)

        workflow.relevant_ifc_types = self.use_doors(workflow.relevant_ifc_types)
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

    @staticmethod
    def use_doors(relevant_ifc_types):
        ifc_list = list(relevant_ifc_types)
        doors_decision = BoolDecision(question="Do you want for the doors to be considered on the bps analysis?",
                                      collect=False, global_key="Bps_Doors",
                                      allow_skip=False, allow_load=True, allow_save=True, quick_decide=not True
                                      )
        doors_decision.decide()
        if not doors_decision.value:
            ifc_list.remove('IfcDoor')
        return tuple(ifc_list)
