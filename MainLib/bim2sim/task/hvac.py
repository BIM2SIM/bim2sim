"""This module holds tasks related to hvac"""

import itertools
import json
import os
import logging
from itertools import chain

import numpy as np

from bim2sim.task.base import Task, ITask
from bim2sim.workflow import LOD
from bim2sim.filter import TypeFilter, TextFilter
from bim2sim.kernel.aggregation import Aggregation, PipeStrand, UnderfloorHeating, \
    ParallelPump, ParallelSpaceHeater
from bim2sim.kernel.element import Element, ElementEncoder, BasePort
from bim2sim.kernel.hvac import hvac_graph
from bim2sim.export import modelica
from bim2sim.decision import Decision, ListDecision
from bim2sim.project import PROJECT
from bim2sim.kernel import finder
from bim2sim.enrichment_data.data_class import DataClass
from bim2sim.enrichment_data import element_input_json


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
    'IfcDistributionChamberElement',
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
    #'IfcUnitaryEquipment',
    'IfcValve',
    'IfcVibrationIsolator',
    #'IfcHeatPump'
)


class SetIFCTypesHVAC(ITask):
    touches = ('relevant_ifc_types', )

    def run(self, workflow):
        return IFC_TYPES,


class Inspect(ITask):
    """Analyses IFC, creates Element instances and connects them.

    elements are stored in .instances dict with guid as key"""

    reads = ('ifc', 'filters')
    touches = ('instances', )

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
    def connections_by_relation(ports, include_conflicts=False):
        """Inspects IFC relations of ports"""
        logger = logging.getLogger('IFCQualityReport')
        connections = []
        for port in ports:
            connected_ports = \
                [conn.RelatingPort for conn in port.ifc.ConnectedFrom] \
                + [conn.RelatedPort for conn in port.ifc.ConnectedTo]
            if connected_ports:
                other_port = None
                if len(connected_ports) > 1:
                    # conflicts
                    logger.warning("%s has multiple connections", port.ifc)
                    possibilities = []
                    for connected_port in connected_ports:
                        possible_port = port.get_object(connected_port.GlobalId)

                        if possible_port.parent is not None:
                            possibilities.append(possible_port)

                    # solving conflics
                    if include_conflicts:
                        for poss in possibilities:
                            connections.append((port, poss))
                    else:
                        if len(possibilities) == 1:
                            other_port = possibilities[0]
                            logger.info("Solved by ignoring deleted connection.")
                        else:
                            logger.error("Unable to solve conflicting connections. "
                                         "Continue without connecting %s", port.ifc)
                else:
                    # explicit
                    other_port = port.get_object(
                        connected_ports[0].GlobalId)
                if other_port:
                    if port.parent and other_port.parent:
                        connections.append((port, other_port))
                    else:
                        logger.debug(
                            "Not connecting ports without parent (%s, %s)",
                            port, other_port)
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

    @staticmethod
    def check_element_ports(elements):
        """Checks position of all ports for each element"""
        logger = logging.getLogger('IFCQualityReport')
        for ele in elements:
            for port_a, port_b in itertools.combinations(ele.ports, 2):
                if np.allclose(port_a.position, port_b.position,
                               rtol=1e-7, atol=1):
                    logger.warning("Poor quality of elements %s: "
                                   "Overlapping ports (%s and %s @%s)",
                                   ele.ifc, port_a.guid, port_b.guid,
                                   port_a.position)

                    conns = Inspect.connections_by_relation(
                        [port_a, port_b], include_conflicts=True)
                    all_ports = [port for conn in conns for port in conn]
                    other_ports = [port for port in all_ports
                                   if port not in [port_a, port_b]]
                    if port_a in all_ports and port_b in all_ports \
                        and len(set(other_ports)) == 1:
                        # both ports connected to same other port -> merge ports
                        logger.info("Removing %s and set %s as SINKANDSOURCE.",
                                    port_b.ifc, port_a.ifc)
                        ele.ports.remove(port_b)
                        port_b.parent = None
                        port_a.flow_direction = 0
                        port_a.flow_master = True

    @staticmethod
    def connections_by_boundingbox(open_ports, elements):
        """Search for open ports in elements bounding boxes

        This is especialy usefull for vessel like elements with variable
        number of ports (and bad ifc export) or proxy elements.
        Missing ports on element side are created on demand."""
        # ToDo:
        connections = []
        return connections

    @Task.log
    def accept_valids(self, entities_dict, warn=True, force=False):
        """Instantiate ifc_entities using given element class.
        Resulting instances are validated (if not force) ans added to self.instances on success."""
        valid, invalid = [], []
        result_dict = {}
        for ifc_type, entities in entities_dict.items():
            remaining = []
            result_dict[ifc_type] = remaining
            for entity in entities:
                element = Element.factory(entity, ifc_type)
                if element.validate() or force:
                    valid.append(entity)
                    self.instances[element.guid] = element
                elif force:
                    valid.append(entity)
                    self.instances[element.guid] = element
                    if warn:
                        self.logger.warning("Validation failed for %s %s but instantiated anyway", ifc_type, element)
                else:
                    if warn:
                        self.logger.warning("Validation failed for %s %s", ifc_type, element)
                    invalid.append(entity)
                    remaining.append(entity)
                    element.discard()

        return valid, invalid

    def filter_by_text(self, text_filter, ifc_entities):
        """Filter ifc elements using given TextFilter. Ambiguous results are solved by decisions"""
        entities_dict, unknown_entities = text_filter.run(ifc_entities)
        answers = {}
        for k, v in entities_dict.items():
            if len(v) > 1:
                ListDecision(
                    "Found following Matches:",
                    # TODO: filter_for_text_fracments() already called in text_filter.run()
                    choices=[[cls, "Match: '" + ",".join(cls.filter_for_text_fracments(k)) + "' in " + " or ".join(
                        ["'%s'" % txt for txt in [k.Name, k.Description] if txt])] for cls in v],
                    output=self.answers,
                    output_key=k,
                    global_key="%s.%s" % (k.is_a(), k.GlobalId),
                    allow_skip=True, allow_load=True, allow_save=True,
                    collect=True, quick_decide=not True)
            elif len(v) == 1:
                answers[k] = v[0]

        Decision.decide_collected()

        result_entity_dict = {}
        for ifc_entity, element_classes in entities_dict.items():
            cls = answers.get(ifc_entity)
            if cls:
                lst = result_entity_dict.setdefault(cls.ifc_type, [])
                lst.append(ifc_entity)
            else:
                unknown_entities.append(ifc_entity)

        return result_entity_dict, unknown_entities

    def set_class_by_user(self, unknown_entities):
        """Ask user for every given ifc_entity to specify matching element class"""
        answers = {}
        for ifc_entity in unknown_entities:
            ListDecision(
                "Found unidentified Element of %s (Name: %s, Description: %s):" % (
                ifc_entity.is_a(), ifc_entity.Name, ifc_entity.Description),
                choices=[ifc_type for ifc_type in Element._ifc_classes.keys()],
                output=answers,
                output_key=ifc_entity,
                global_key="%s.%s" % (ifc_entity.is_a(), ifc_entity.GlobalId),
                allow_skip=True, allow_load=True, allow_save=True,
                collect=True, quick_decide=not True)
        Decision.decide_collected()

        result_entity_dict = {}
        ignore = []
        for ifc_entity, ifc_type in answers.items():

            if ifc_type is None:
                ignore.append(ifc_entity)
            else:
                lst = result_entity_dict.setdefault(ifc_type, [])
                lst.append(ifc_entity)

        return result_entity_dict, ignore

    @Task.log
    def run(self, workflow, ifc, filters):
        self.logger.info("Creates python representation of relevant ifc types")

        # filter by type
        initial_filter = filters[0]  #ToDo: TypeFilter must be first if the following Filter should also search in this types!
        initial_entities_dict, unknown_entities = initial_filter.run(ifc)
        valids, invalids = self.accept_valids(initial_entities_dict)
        unknown_entities.extend(invalids)

        for f in filters[1:]:

            if isinstance(f, TextFilter):
                # filter by text fracments
                class_dict, unknown_entities = self.filter_by_text(f, unknown_entities)
                valids, invalids = self.accept_valids(class_dict)
                unknown_entities.extend(invalids)
            else:
                raise NotImplementedError()

        self.logger.info("Found %d relevant elements", len(self.instances))
        self.logger.info("Found %d ifc_entities that could not be identified and transformed into a python element.",
                         len(unknown_entities))

        #Identification of remaining Elements through the user
        class_dict, unknown_entities = self.set_class_by_user(unknown_entities)
        valids, invalids = self.accept_valids(class_dict, force=True)
        if invalids:
            self.logger.info("Removed %d entities with no class set", len(invalids))

        # answers = {}
        # for ifc_entity in unknown_entities:
        #     for ifc_element in v:
        #         ListDecision(
        #             "Found unidentified Element of %s (Name: %s, Description: %s):" % (ifc_entity, ifc_element.Name, ifc_element.Description),
        #             choices=[[ifc_type, element] for ifc_type, element in Element._ifc_classes.items()],
        #             output=answers,
        #             output_key=ifc_element,
        #             global_key="%s.%s" % (ifc_element.is_a(), ifc_element.GlobalId),
        #             allow_skip=True, allow_load=True, allow_save=True, allow_overwrite=True,
        #             collect=True, quick_decide=not True)
        #         Decision.decide_collected()
        #
        # for a, v in answers.items():
        #     representation = Element.factory(a, v[0]) if v else None
        #     if representation:
        #         self.instances[representation.guid] = representation
        #         entities_dict[a.is_a()].remove(a)

        self.logger.info("Created %d elements", len(self.instances))

        # connections
        self.logger.info("Checking ports of elements ...")
        self.check_element_ports(self.instances.values())
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
        unconnected = [port for port in BasePort.objects.values()
                       if not port.is_connected()]
        nr_unconnected = len(unconnected)
        nr_connected = nr_total - nr_unconnected
        self.logger.info("In total %d of %d ports are connected.",
                         nr_connected, nr_total)
        if nr_total > nr_connected:
            self.logger.warning("%d ports are not connected!", nr_unconnected)

        unconnected_elements = {uc.parent for uc in unconnected}
        if unconnected_elements:
            # TODO:
            bb_connections = self.connections_by_boundingbox(unconnected, unconnected_elements)
            self.logger.warning("Connecting by bounding box is not implemented.")

        # TODO: manualy add / modify connections
        return self.instances,


class Enrich(Task):
    def __init__(self):
        super().__init__()
        self.enrich_data = {}
        self.enriched_instances = {}

    def enrich_instance(self, instance, enrich_parameter, parameter_value):

        json_data = DataClass()

        attrs_enrich = element_input_json.load_element_class(instance, enrich_parameter, parameter_value, json_data)

        return attrs_enrich

    @Task.log
    def run(self, instances, enrich_parameter, parameter_value):
        # enrichment_parameter --> Class
        self.logger.info("Enrichment of the elements with: \n" + enrich_parameter + " as \"Enrich Parameter\"\n"
                         + parameter_value + " as \"parameter value\" \n")
        for instance in instances:
            enrichment_data = self.enrich_instance(instances[instance], enrich_parameter, parameter_value)
            setattr(instances[instance], "enrichment_data", enrichment_data)

        self.logger.info("Applied successfully attributes enrichment on elements")
        # runs all enrich methods


class Prepare(ITask):
    """Configurate"""  # TODO: based on task

    reads = ('relevant_ifc_types', )
    touches = ('filters', )

    @Task.log
    def run(self, workflow, relevant_ifc_types):
        self.logger.info("Setting Filters")
        Element.finder = finder.TemplateFinder()
        Element.finder.load(PROJECT.finder)
        filters = [TypeFilter(relevant_ifc_types), TextFilter(relevant_ifc_types)]
        # self.filters.append(TextFilter(['IfcBuildingElementProxy', 'IfcUnitaryEquipment']))
        return filters,


class MakeGraph(ITask):
    """Instantiate HvacGraph"""

    reads = ('instances', )
    touches = ('graph', )

    @Task.log
    def run(self, workflow, instances):
        self.logger.info("Creating graph from IFC elements")
        graph = hvac_graph.HvacGraph(instances.values())
        return graph,

    def serialize(self):
        raise NotImplementedError
        return json.dumps(self.graph.to_serializable(), cls=ElementEncoder)

    def deserialize(self, data):
        raise NotImplementedError
        self.graph.from_serialized(json.loads(data))


class Reduce(ITask):
    """Reduce number of elements by aggregation"""

    reads = ('graph', )
    touches = ('reduced_instances', 'connections')

    @Task.log
    def run(self, workflow, graph: hvac_graph.HvacGraph):
        self.logger.info("Reducing elements by applying aggregations")
        number_of_nodes_old = len(graph.element_graph.nodes)
        number_ps = 0
        number_fh = 0
        number_pipes = 0
        number_pp = 0
        number_psh = 0

        # Parallel pumps aggregation
        cycles = graph.get_cycles()
        for cycle in cycles:
            parallelpump = ParallelPump.create_on_match("ParallelPump%d" % (number_pp + 1), cycle)
            if parallelpump:
                number_pp += 1
                graph.merge(
                    mapping=parallelpump.get_replacement_mapping(),
                    inner_connections=parallelpump.get_inner_connections())
            # parallelspaceheater = ParallelSpaceHeater.create_on_match("ParallelSpaceHeater%d" % (number_psh + 1), cycle)
            # if parallelspaceheater:
            #     number_psh += 1
            #     graph.merge(
            #         mapping=parallelspaceheater.get_replacement_mapping(),
            #         inner_connections=parallelspaceheater.get_inner_connections())

        self.logger.info("Applied %d aggregations as \"ParallelPump\"", number_pp)

        chains = graph.get_type_chains(PipeStrand.aggregatable_elements, include_singles=True)
        for chain in chains:
            underfloorheating = UnderfloorHeating.create_on_match("UnderfloorHeating%d" % (number_fh + 1), chain)
            if underfloorheating:
                number_fh += 1
                graph.merge(
                    mapping=underfloorheating.get_replacement_mapping(),
                    inner_connections=underfloorheating.get_inner_connections())
            else:
                if workflow.pipes == LOD.full:
                    pass
                elif workflow.pipes == LOD.medium:
                    if len(chain) <= 1:
                        continue
                    number_ps += 1
                    pipestrand = PipeStrand("PipeStrand%d" % (number_ps), chain)
                    graph.merge(
                        mapping=pipestrand.get_replacement_mapping(),
                        inner_connections=pipestrand.get_inner_connections())
                elif workflow.pipes == LOD.low:
                    mapping, connections = Aggregation.get_empty_mapping(chain)
                    graph.merge(
                        mapping=mapping,
                        inner_connections=connections,
                    )
                    number_pipes += len(set(k.parent for k, v in mapping.items() if v is None))

        self.logger.info("Applied %d aggregations as \"PipeStrand\"", number_ps)
        self.logger.info("Applied %d aggregations as \"UnderfloorHeating\"", number_fh)
        self.logger.info("Removed %d pipe-like elements", number_pipes)

        # self.logger.info("Setting flow_sides")
        # # this might help for other reduce methods like finding parallel pumps etc. else only for nice plotting
        # self.set_flow_sides(graph)

        number_of_nodes_new = len(graph.element_graph.nodes)
        self.logger.info(
            "Applied %d aggregations which reduced"
            + " number of elements from %d to %d.",
            number_ps + number_fh + number_pp, number_of_nodes_old, number_of_nodes_new)
        reduced_instances = graph.elements
        connections = graph.get_connections()

        #Element.solve_requests()

        if __debug__:
            self.logger.info("Plotting graph ...")
            graph.plot(PROJECT.export)
            graph.plot(PROJECT.export, ports=True)

        return reduced_instances, connections

    @staticmethod
    def set_flow_sides(graph):
        """Set flow_side for ports in graph based on known flow_sides"""
        # TODO: needs testing!
        # TODO: at least one master element required
        accepted = []
        while True:
            unset_port = None
            for port in graph.get_nodes():
                if port.flow_side == 0 and graph.graph[port] and port not in accepted:
                    unset_port = port
                    break
            if unset_port:
                side, visited, masters = graph.recurse_set_unknown_sides(unset_port)
                if side in (-1, 1):
                    # apply suggestions
                    for port in visited:
                        port.flow_side = side
                elif side == 0:
                    # TODO: ask user?
                    accepted.extend(visited)
                elif masters:
                    # ask user to fix conflicts (and retry in next while loop)
                    for port in masters:
                        decision = BoolDecision("Use %r as VL (y) or RL (n)?" % port)
                        use = decision.decide()
                        if use:
                            port.flow_side = 1
                        else:
                            port.flow_side = -1
                else:
                    # can not be solved (no conflicting masters)
                    # TODO: ask user?
                    accepted.extend(visited)
            else:
                # done
                logging.info("Flow_side set")
                break


class DetectCycles(ITask):
    """Detect cycles in graph"""

    reads = ('graph', )
    touches = ('cycles', )

    # TODO: sth usefull like grouping or medium assignment

    @Task.log
    def run(self, workflow, graph: hvac_graph.HvacGraph):
        self.logger.info("Detecting cycles")
        cycles = graph.get_cycles()
        return cycles,


class Export(ITask):
    """Export to Dymola/Modelica"""

    reads = ('libraries', 'instances', 'connections')
    final = True

    def run(self, workflow, libraries, instances, connections):
        self.logger.info("Export to Modelica code")

        modelica.Instance.init_factory(libraries)
        export_instances = {inst: modelica.Instance.factory(inst) for inst in instances.values()}

        Element.solve_requested_decisions()

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
        # print("-"*80)
        # print(modelica_model.code())
        # print("-"*80)
        modelica_model.save(PROJECT.export)
