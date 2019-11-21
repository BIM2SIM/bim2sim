import ifcopenshell
import ifcopenshell.geom

from bim2sim.workflow import Workflow


IFC_TYPES = (
    'IfcSpace',
    'IfcZone'
)


class Recognition (Workflow):
    """Recognition of the space, zone-like instances"""

    def __init__(self):
        super().__init__()
        self.instances_bps = {}

    @Workflow.log
    def run(self, ifc, relevant_ifc_types):
        self.logger.info("Creates python representation of relevant ifc types")

        settings = ifcopenshell.geom.settings()
        walls = ifc.by_type('IfcWall')
        storeys_elements = {}
        tolerance = [[0.5, 0.5], [0.5, -0.5], [-0.5, -0.5], [-0.5, 0.5]]

        spaces = ifc.by_type('IfcSpace')
        print("")
