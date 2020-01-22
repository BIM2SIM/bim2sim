from bim2sim.task import Task
from bim2sim.kernel import elements
from bim2sim.decision import DictDecision, ListDecision, RealDecision, BoolDecision
from bim2sim.kernel.element import Element

IFC_TYPES = {
    'IfcSpace'
}


class Inspect(Task):
    """Analyses IFC, creates Element instances and connects them.

    elements are stored in .instances dict with guid as key"""

    def __init__(self):
        super().__init__()
        self.instances = {}

    @Task.log
    def run(self, task, ifc, relevant_ifc_types):
        self.logger.info("Creates python representation of relevant ifc types")
        instances = self.recognize_zone_semantic(ifc, relevant_ifc_types)
        if len(instances) == 0:
            self.logger.warning("Found no spaces by semantic detection")
            decision = BoolDecision("Try to detect zones by geometrical?")
            use = decision.decide()
            if use:
                self.recognize_zone_geometrical()
            else:
                # todo abort program, because of missing zones/spaces
                raise NotImplementedError

        self.logger.info("Found %d space entities", len(self.instances))

    @Task.log
    def recognize_zone_semantic(self, ifc, relevant_ifc_types):
        """Recognizes zones/spaces in ifc file by semantic detection for
        IfcSpace entities"""
        self.logger.info("Create zones by semantic detection")
        # todo integrate filter here (make filter system task independent
        #  before)
        for ifc_type in relevant_ifc_types:
            entities = ifc.by_type(ifc_type)
            for entity in entities:
                element = Element.factory(entity, ifc_type)
                self.instances[element.guid] = element
        self.logger.info("Found %d spaces", len(self.instances))

    @Task.log
    def recognize_zone_geometrical(self):
        """Recognizes zones/spaces by geometric detection"""
        raise NotImplementedError

    @Task.log
    def bind_elements_to_zone(self):
        """Binds the different elements to the belonging zones"""
        raise NotImplementedError
