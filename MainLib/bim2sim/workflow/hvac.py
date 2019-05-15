"""This module holds elements related to hvac workflow"""

import itertools
import json

from bim2sim.workflow import Workflow
from bim2sim.filter import TypeFilter
from bim2sim.ifc2python.aggregation import PipeStrand
from bim2sim.ifc2python.element import Element, ElementEncoder
from bim2sim.ifc2python.hvac import hvac_graph
from bim2sim.export import modelica
from bim2sim.decision import Decision
from bim2sim.project import PROJECT
from bim2sim.ifc2python import finder

IFC_TYPES = (
    'IfcAirTerminal',
    'IfcAirTerminalBox',
    'IfcAirToAirHeatRecovery',
    'IfcBoiler',
    'IfcBurner',
    'IfcChiller',
    'IfcCoil',
    'IfcCompressor',
    'IfcCondenser',
    'IfcCooledBeam',
    'IfcCoolingTower',
    'IfcDamper',
    'IfcDuctFitting',
    'IfcDuctSegment',
    'IfcDuctSilencer',
    'IfcEngine',
    'IfcEvaporativeCooler',
    'IfcEvaporator',
    'IfcFan',
    'IfcFilter',
    'IfcFlowMeter',
    'IfcHeatExchanger',
    'IfcHumidifier',
    'IfcMedicalDevice',
    'IfcPipeFitting',
    'IfcPipeSegment',
    'IfcPump',
    'IfcSpaceHeater',
    'IfcTank',
    'IfcTubeBundle',
    'IfcUnitaryEquipment',
    'IfcValve',
    'IfcVibrationIsolator',
)

class Inspect(Workflow):
    """Analyses IFC, creates Element instances and connects them.

    elements are stored in .instandes dict with guid as key"""

    def __init__(self):
        super().__init__()
        self.logger.info("Creates python representation of relevant ifc types")
        self.instances = {}

    @staticmethod
    def connect_instances(instances, eps=1):
        """Connect ports of instances by computing geometric distance"""
        nr_connections = 0
        # todo add check if IFC has port information -> decision system
        for instance1, instance2 in itertools.combinations(instances, 2):
            for port1 in instance1.ports:
                for port2 in instance2.ports:
                    delta = port1.position - port2.position
                    if max(abs(delta)) < eps:
                        port1.connect(port2)
                        port2.connect(port1)
                        nr_connections += 1

        return nr_connections

    @Workflow.log
    def run(self, ifc, relevant_ifc_types):
        self.logger.info("Creates python representation of relevant ifc types")
        for ifc_type in relevant_ifc_types:
            elements = ifc.by_type(ifc_type)
            for element in elements:
                representation = Element.factory(element)
                self.instances[representation.guid] = representation

        self.logger.info("Found %d relevant elements", len(self.instances))
        self.logger.info("Connecting the relevant elements")
        nr_connections = self.connect_instances(self.instances.values())
        self.logger.info("Found %d connections", nr_connections)


class Prepare(Workflow):
    """Configurate""" #TODO: based on task

    def __init__(self):
        super().__init__()
        self.filters = []

    @Workflow.log
    def run(self, relevant_ifc_types):
        self.logger.info("Setting Filters")
        Element.finder = finder.TemplateFinder()
        Element.finder.load(PROJECT.finder)
        self.filters.append(TypeFilter(relevant_ifc_types))


class MakeGraph(Workflow):
    """Instanciate HvacGraph"""
    #saveable = True #ToDo

    def __init__(self):
        super().__init__()
        self.graph = None

    @Workflow.log
    def run(self, instances: list):
        self.logger.info("Creating graph from IFC elements")
        self.graph = hvac_graph.HvacGraph(instances)

    def serialize(self):
        raise NotImplementedError
        return json.dumps(self.graph.to_serializable(), cls=ElementEncoder)

    def deserialize(self, data):
        raise NotImplementedError
        self.graph.from_serialized(json.loads(data))

class Reduce(Workflow):
    """Reduce number of elements by aggregation"""

    def __init__(self):
        super().__init__()
        self.reduced_instances = []

    @Workflow.log
    def run(self, graph: hvac_graph.HvacGraph):
        self.logger.info("Reducing elements by applying aggregations")
        number_ps = 0
        chains = graph.get_type_chains(PipeStrand.aggregatable_elements)
        for chain in chains:
            number_ps += 1
            pipestrand = PipeStrand("PipeStrand%d"%(number_ps), chain)
            graph.replace(chain, pipestrand)

        self.reduced_instances = graph.get_nodes()
        if __debug__:
            graph.plot(PROJECT.export)


class DetectCycles(Workflow):
    """Detect cycles in graph"""
    #TODO: sth usefull like grouping or medium assignment

    def __init__(self):
        super().__init__()
        self.cycles = None

    @Workflow.log
    def run(self, graph: hvac_graph.HvacGraph):
        self.logger.info("Detecting cycles")
        self.cycles = graph.get_cycles()


class Export(Workflow):
    """Export to Dymola/Modelica"""

    def run(self, instances):
        self.logger.info("Export to Modelica code")
        Decision.load(PROJECT.decisions)

        export_instances = [modelica.Instance.factory(inst) for inst in instances]

        self.logger.info(Decision.summary())
        Decision.decide_collected()
        Decision.save(PROJECT.decisions)

        modelica_model = modelica.Model(
            name="Test", 
            comment="testing", 
            instances=export_instances, 
            connections={},
        )
        print("-"*80)
        print(modelica_model.code())
        print("-"*80)
        modelica_model.save(PROJECT.export)
