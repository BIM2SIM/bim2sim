"""This module holds elements related to hvac workflow"""

from bim2sim.workflow import Workflow
from bim2sim.filter import TypeFilter
from bim2sim.ifc2python.element import Element
from bim2sim.ifc2python import hvac
from bim2sim.ifc2python.hvac import hvac_graph
from bim2sim.export import modelica
from bim2sim.decision import Decision
from bim2sim.project import PROJECT

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
    verbose_description = "Creates python representation of relevant ifc types"

    def __init__(self):
        super().__init__()
        self.instances = {}

    @Workflow.log
    def run(self, ifc, relevant_ifc_types):

        for ifc_type in relevant_ifc_types:
            elements = ifc.by_type(ifc_type)
            for element in elements:
                representation = Element.factory(element)
                self.instances[representation.guid] = representation

        self.logger.info("Found %d relevant elements", len(self.instances))
        self.logger.info("Connecting the relevant elements")
        nr_connections = hvac.connect_instances(self.instances.values())
        self.logger.info("Found %d connections", nr_connections)


class Prepare(Workflow):
    verbose_description = "Setting Filters"

    def __init__(self):
        super().__init__()
        self.filters = []

    @Workflow.log
    def run(self, relevant_ifc_types):

        self.filters.append(TypeFilter(relevant_ifc_types))


class DetectCycles(Workflow):
    """"""
    verbose_description = "Creating graph and detect cycles"

    def __init__(self):
        super().__init__()
        self.graph = None

    @Workflow.log
    def run(self, instances:list):
        hvacgraph = hvac_graph.HvacGraph(instances)
        hvacgraph.create_cycles()
        self.graph = hvacgraph

class Reduce(Workflow):
    verbose_description = "Reducing elements by applieing aggregations"

    def __init__(self):
        super().__init__()
        self.reduced_instances = None

    def run(self, graph):
        graph.find_aggregations(graph.hvac_graph, 'pipes')
        graph.plot_graph(graph.hvac_graph, True)
        self.reduced_instances = graph.aggregated_instances

class Export(Workflow):
    verbose_description = "Export to Modelica code"

    def run(self, instances):
        Decision.load(PROJECT.decisions)

        export_instances = [modelica.Instance.factory(inst) for inst in instances]

        self.logger.info(Decision.summary())
        Decision.decide_collected()
        Decision.save(PROJECT.decisions)

        modelica_model = modelica.Model(name="Test", comment="testing", instances=export_instances, connections={})
        print("-"*80)
        print(modelica_model.code())
        print("-"*80)
        modelica_model.save(PROJECT.export)
