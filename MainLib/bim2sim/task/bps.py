"""This module holds tasks related to bps"""

import itertools
import json

from bim2sim.task import Task
from bim2sim.filter import TypeFilter
from bim2sim.kernel.element import Element, ElementEncoder, BasePort
# from bim2sim.ifc2python.bps import ...
from bim2sim.export import modelica
from bim2sim.decision import Decision
from bim2sim.project import PROJECT
from bim2sim.kernel import finder


IFC_TYPES = (
    'IfcWallElementedCase',
    'IfcWallStandardCase',
    'IfcWall',
    'IfcWindow',
    'IfcSlab',
    'IFcBuilding'
)


class Inspect(Task):
    """Analyses IFC, creates Element instances and connects them.

    elements are stored in .instances dict with guid as key"""


    def __init__(self):
        super().__init__()
        self.instances = {}

    @Task.log
    def run(self, ifc, relevant_ifc_types):
        self.logger.info("Creates python representation of relevant ifc types")
        for ifc_type in relevant_ifc_types:
            elements = ifc.by_type(ifc_type)
            for element in elements:
                representation = Element.factory(element)
                self.instances[representation.guid] = representation
        self.logger.info("Found %d relevant elements", len(self.instances))

