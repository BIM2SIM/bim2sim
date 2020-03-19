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
from bim2sim.kernel.finder import TemplateFinder
from bim2sim.enrichment_data import element_input_json
from bim2sim.enrichment_data.data_class import DataClass
from bim2sim.decision import ListDecision
import math



class Inspect(Task):
    """Analyses IFC and creates Element instances.
    Elements are stored in .instances dict with guid as key"""

    def __init__(self, workflow):
        super().__init__()
        self.instances = {}
        self.workflow = workflow

    @Task.log
    def run(self, ifc):
        self.logger.info("Creates python representation of relevant ifc types")

        Project = ifc.by_type('IfcProject')[0]
        TrueNorth = Project.RepresentationContexts[0].TrueNorth.DirectionRatios
        tn_angle = -math.degrees(math.atan(TrueNorth[0]/TrueNorth[1]))

        Element.finder = finder.TemplateFinder()
        Element.finder.load(PROJECT.finder)
        for ifc_type in self.workflow.relevant_ifc_types:
            entities = ifc.by_type(ifc_type)
            for entity in entities:
                element = Element.factory(entity, ifc_type)
                if ifc_type == 'IfcWall':
                    print(element.ifc_type, element.guid, element.orientation)
                self.instances[element.guid] = element

        self.logger.info("Found %d building elements", len(self.instances))
