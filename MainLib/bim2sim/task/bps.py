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

        Element.finder = finder.TemplateFinder()
        Element.finder.load(PROJECT.finder)
        for ifc_type in self.workflow.relevant_ifc_types:
            # not every ifc file has the same relevant ifc types - wrapper problem
            try:
                entities = ifc.by_type(ifc_type)
                for entity in entities:
                    element = Element.factory(entity, ifc_type)
                    try:
                        if element.is_external is True:
                            print(element.ifc_type, element.guid, element.orientation)
                    except AttributeError:
                        pass
                    self.instances[element.guid] = element
            except RuntimeError:
                pass

        self.logger.info("Found %d building elements", len(self.instances))
