from bim2sim.workflow import Workflow
from bim2sim.ifc2python import elements


class Recognition (Workflow):
    """Recognition of the space, zone-like instances"""

    def __init__(self):
        super().__init__()
        self.instances_tz = {}

    @Workflow.log
    def run(self, ifc, hvac_instances):
        self.logger.info("Creates python representation of relevant ifc types")

        spaces = ifc.by_type('IfcSpace')
        # del spaces[5] #problem mit Flur - Vereinhaus
        for space in spaces:
            representation = elements.ThermalZone.add_elements_space(space, hvac_instances)
            self.instances_tz[representation.guid] = representation


class Inspect(Workflow):
    """Analyses IFC, creates Element instances and connects them.

    elements are stored in .instances dict with guid as key"""

    def __init__(self):
        super().__init__()
        self.instances_bps = {}

    @Workflow.log
    def run(self, ifc, relevant_ifc_types):
        self.logger.info("Creates python representation of relevant ifc types")
