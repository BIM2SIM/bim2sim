"""This module holds elements related to hvac workflow"""

import itertools
import json

from bim2sim.workflow import Workflow
from bim2sim.filter import TypeFilter
from bim2sim.ifc2python.aggregation import PipeStrand
from bim2sim.ifc2python.element import Element, ElementEncoder, BasePort
from bim2sim.ifc2python.hvac import hvac_graph
from bim2sim.export import modelica
from bim2sim.decision import Decision
from bim2sim.project import PROJECT
from bim2sim.ifc2python import finder
from bim2sim.enrichtment_data.data_class import DataClass, Enrich_class
from bim2sim.enrichtment_data import element_input_json




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

    elements are stored in .instances dict with guid as key"""

    def __init__(self):
        super().__init__()
        self.instances = {}
        pass

    @staticmethod
    def port_distance(port1, port2):
        """Returns distance (x,y,z delta) of ports

        :returns: None if port position ist not available"""
        try:
            delta = port1.position - port2.position
        except AttributeError:
            delta = None
        return delta

    #@staticmethod
    #def connect_old(instances, eps=1):
    #    """Connect ports of instances by computing geometric distance"""
    #    nr_connections = 0
    #    # todo add check if IFC has port information -> decision system
    #    for instance1, instance2 in itertools.combinations(instances, 2):
    #        for port1 in instance1.ports:
    #            if port1.is_connected():
    #                continue
    #            for port2 in instance2.ports:
    #                if port2.is_connected():
    #                    continue
    #                delta = self.port_distance(port1, port2)
    #                if max(abs(delta)) < eps:
    #                    port1.connect(port2)
    #                    #port2.connect(port1)
    #                    nr_connections += 1

    #    return nr_connections

    @staticmethod
    def connections_by_position(ports, eps=1):
        """Connect ports of instances by computing geometric distance"""
        connections = []
        for port1, port2 in itertools.combinations(ports, 2):
            delta = Inspect.port_distance(port1, port2)
            if delta is None:
                continue
            if max(abs(delta)) < eps:
                connections.append((port1, port2))
        return connections

    @staticmethod
    def connections_by_relation(ports):
        """Inspects IFC relations of ports"""
        connections = []
        for port in ports:
            if port.ifc.ConnectedFrom:
                other_port = port.get_object(
                    port.ifc.ConnectedFrom[0].RelatingPort.GlobalId)
                if other_port:
                    connections.append((port, other_port))
        return connections

    @staticmethod
    def confirm_connections_position(connections, eps=1):
        """Checks distance between port positions

        :return: tuple of lists of connections
        (confirmed, unconfirmed, rejected)"""
        confirmed = []
        unconfirmed = []
        rejected = []
        for port1, port2 in connections:
            delta = Inspect.port_distance(port1, port2)
            if delta is None:
                unconfirmed.append((port1, port2))
            elif max(abs(delta)) < eps:
                confirmed.append((port1, port2))
            else:
                rejected.append((port1, port2))
        return confirmed, unconfirmed, rejected

    @Workflow.log
    def run(self, ifc, relevant_ifc_types):
        self.logger.info("Creates python representation of relevant ifc types")
        for ifc_type in relevant_ifc_types:
            elements = ifc.by_type(ifc_type)
            for element in elements:
                representation = Element.factory(element)
                self.instances[representation.guid] = representation
        self.logger.info("Found %d relevant elements", len(self.instances))

        # connections
        self.logger.info("Connecting the relevant elements")
        self.logger.info(" - Connecting by relations ...")
        test = BasePort.objects
        rel_connections = self.connections_by_relation(
            BasePort.objects.values())
        self.logger.info(" - Found %d potential connections.",
                         len(rel_connections))

        self.logger.info(" - Checking positions of connections ...")
        confirmed, unconfirmed, rejected = \
            self.confirm_connections_position(rel_connections)
        self.logger.info(" - %d connections are confirmed and %d rejected. " \
            + "%d can't be confirmed.",
                         len(confirmed), len(rejected), len(unconfirmed))
        for port1, port2 in confirmed + unconfirmed:
            # unconfirmed have no position data and cant be connected by position
            port1.connect(port2)

        unconnected_ports = (port for port in BasePort.objects.values()
                             if not port.is_connected())
        self.logger.info(" - Connecting remaining ports by position ...")
        pos_connections = self.connections_by_position(unconnected_ports)
        self.logger.info(" - Found %d additional connections.",
                         len(pos_connections))
        for port1, port2 in pos_connections:
            port1.connect(port2)

        nr_total = len(BasePort.objects)
        nr_unconnected = sum(1 for port in BasePort.objects.values()
                             if not port.is_connected())
        nr_connected = nr_total - nr_unconnected
        self.logger.info("In total %d of %d ports are connected.",
                         nr_connected, nr_total)
        if nr_total > nr_connected:
            self.logger.warning("%d ports are not connected!", nr_unconnected)


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
    """Instantiate HvacGraph"""
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
        self.connections = []

    @Workflow.log
    def run(self, graph: hvac_graph.HvacGraph):
        self.logger.info("Reducing elements by applying aggregations")
        number_of_nodes_old = len(graph.element_graph.nodes)
        number_ps = 0
        chains = graph.get_type_chains(PipeStrand.aggregatable_elements)
        for chain in chains:
            number_ps += 1
            pipestrand = PipeStrand("PipeStrand%d"%(number_ps), chain)
            graph.merge(
                mapping=pipestrand.get_replacement_mapping(),
                inner_connections=pipestrand.get_inner_connections())
        number_of_nodes_new = len(graph.element_graph.nodes)

        cycles = graph.get_cycles()
        element_cycle = "SpaceHeater"

        for cycle in cycles:
            length_cycle = len(cycle)
            cycle.append([])
            for port in cycle[:length_cycle]:
                if "PipeFitting" in str(port):
                    cycle[length_cycle].append(port)

            length_cycle = len(cycle)
            if cycle[length_cycle - 1][0].parent == cycle[length_cycle - 1][-1].parent:
                cycle[length_cycle - 1].insert(0, cycle[length_cycle - 1][-1])
                cycle[length_cycle - 1].pop()

            for item in cycle[length_cycle - 1][0::2]:
                index_a = cycle[length_cycle - 1].index(item)
                if item.flow_direction != cycle[length_cycle - 1][index_a + 1].flow_direction:
                    cycle[length_cycle - 1][index_a] = 0
                    cycle[length_cycle - 1][index_a + 1] = 0
            i = 0
            length = len(cycle[length_cycle - 1])
            while i < length:
                if cycle[length_cycle - 1][i] == 0:
                    cycle[length_cycle - 1].remove(cycle[length_cycle - 1][i])
                    length = length - 1
                    continue
                i = i + 1
        i = 0
        length = len(cycles)
        while i < length:
            length_a = len(cycles[i])
            aux = cycles[i][length_a - 1]
            if len(cycles[i][length_a - 1]) != 4:
                cycles.remove(cycles[i])
                length = length - 1
                continue
            i = i + 1
        New_cycles = []
        n_cycle = 0
        for cycle in cycles:
            New_cycles.append([])
            len_aux = len(cycle)-1
            cycle.append([])
            cycle[len(cycle)-1].append([])
            cycle[len(cycle)-1].append([])
            for port in cycle[:len_aux]:
                if cycle.index(cycle[len_aux][1]) < cycle.index(port) < cycle.index(cycle[len_aux][2]):
                    cycle[len(cycle) - 1][1].append(port)
                elif (cycle.index(port) < cycle.index(cycle[len_aux][0])) and (port not in cycle[len_aux]):
                    cycle[len(cycle)-1][0].append(port)
                elif (cycle.index(port) > cycle.index(cycle[len_aux][3])) and (port not in cycle[len_aux]):
                    cycle[len(cycle) - 1][0].append(port)

            n_item = 0
            for item in cycle[-1]:
                New_cycles[n_cycle].append([])
                New_cycles[n_cycle][n_item].append(cycle[len_aux][0].parent)
                for port in item[0::2]:
                    New_cycles[n_cycle][n_item].append(port.parent)
                New_cycles[n_cycle][n_item].append(cycle[len_aux][2].parent)
                n_item += 1
            n_cycle += 1

        for cycle in New_cycles:
            for strand in cycle:
                n_element = 0
                for item in strand:
                    if element_cycle in str(item):
                        n_element += 1
                if n_element == 0:
                    New_cycles[New_cycles.index(cycle)] = 0
                    break
        i = 0
        length = len(New_cycles)
        while i < length:
            if New_cycles[i] == 0:
                New_cycles.remove(New_cycles[i])
                length = length - 1
                continue
            i = i + 1

        for cycle in New_cycles:
            for strand in cycle:
                index_element = 0
                for item in strand:
                    if element_cycle in str(item):
                        index_element = strand.index(item)
                number_ps += 1
                pipestrand = PipeStrand("PipeStrand%d" % (number_ps), strand[:index_element])
                graph.merge(
                        mapping=pipestrand.get_replacement_mapping(),
                        inner_connections=pipestrand.get_inner_connections())
                number_ps += 1
                pipestrand = PipeStrand("PipeStrand%d" % (number_ps), strand[index_element+1:])
                graph.merge(
                        mapping=pipestrand.get_replacement_mapping(),
                        inner_connections=pipestrand.get_inner_connections())






        self.logger.info(
            "Applied %d aggregations which reduced"
            + " number of elements from %d to %d.",
            number_ps, number_of_nodes_old, number_of_nodes_new)
        self.reduced_instances = graph.elements
        self.connections = graph.get_connections()

        if __debug__:
            self.logger.info("Plotting graph ...")
            graph.plot(PROJECT.export)

class Enrich(Workflow):
    def __init__(self):
        super().__init__()
        self.enrich_data = {}
        self.enriched_instances = {}

    @Workflow.log
    def enrich_instance(self, instance, build_year, enrichment_parameter):

        json_data = DataClass()
        enrich_data = Enrich_class()

        if enrichment_parameter == "ifc":
            if not hasattr(instance, "ifc_type"):
                self.logger.info("Enrichment parameter does not work with"
                                 "the selected instance -- probe \"class\" as "
                                 "enrichment parameter")
            else:
                element_input_json.load_element_ifc(enrich_data,
                                                    instance.ifc_type,
                                                    build_year,
                                                    json_data)
                attrs_enrich = vars(enrich_data)
                element_input_json.enrich_by_buildyear(self, attrs_enrich, instance)

        elif enrichment_parameter == "class":
            class_instance = str(instance.__class__)[
                             str(instance.__class__).rfind(".") + 1:str(instance.__class__).rfind("'")]
            element_input_json.load_element_class(enrich_data,
                                                  class_instance,
                                                  build_year,
                                                  json_data)
            attrs_enrich = vars(enrich_data)
            element_input_json.enrich_by_buildyear(self, attrs_enrich, instance)
        else:
            self.logger.warning("Parameter invalid")

        # target: the instances in the inspect.instances dict are filled up
        # with the data from the json file
    def run(self, instances, build_year, enrichment_parameter):
        self.logger.info("Enrichment of the elements")
        enriched_instances = instances
        for instance in enriched_instances:
            if hasattr(instance, "elements"):
                for subinstance in instance.elements:
                    self.enrich_instance(subinstance, build_year, enrichment_parameter)
            # elif instance.ifc_type == 'IfcTank':
            #     print("Error here")
            else:
                self.enrich_instance(instance, build_year, enrichment_parameter)
        self.enriched_instances = enriched_instances
            # runs all enrich methods


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

    def run(self, libraries, instances, connections):
        self.logger.info("Export to Modelica code")
        Decision.load(PROJECT.decisions)

        modelica.Instance.init_factory(libraries)
        export_instances = {inst: modelica.Instance.factory(inst) for inst in instances}

        self.logger.info(Decision.summary())
        Decision.decide_collected()
        Decision.save(PROJECT.decisions)

        connection_port_names = []
        for connection in connections:
            instance0 = export_instances[connection[0].parent]
            port_name0 = instance0.get_full_port_name(connection[0])
            instance1 = export_instances[connection[1].parent]
            port_name1 = instance1.get_full_port_name(connection[1])
            connection_port_names.append((port_name0, port_name1))

        self.logger.info(
            "Creating Modelica model with %d model instances and %d connections.",
            len(export_instances), len(connection_port_names))

        modelica_model = modelica.Model(
            name="Test",
            comment="testing",
            instances=export_instances.values(),
            connections=connection_port_names,
        )
        #print("-"*80)
        #print(modelica_model.code())
        #print("-"*80)
        modelica_model.save(PROJECT.export)
