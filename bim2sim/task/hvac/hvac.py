"""This module holds tasks related to hvac"""

import itertools
import json
import logging
from datetime import datetime
from typing import Generator, Iterable, Tuple

import numpy as np
import networkx as nx

from bim2sim.kernel.elements import hvac
from bim2sim.task.base import ITask
from bim2sim.kernel.aggregation import PipeStrand, UnderfloorHeating, ParallelPump
from bim2sim.kernel.aggregation import Consumer, ConsumerHeatingDistributorModule, GeneratorOneFluid
from bim2sim.kernel.element import ProductBased, ElementEncoder, Port
from bim2sim.kernel.hvac import hvac_graph
from bim2sim.export import modelica
from bim2sim.decision import DecisionBunch
from bim2sim.enrichment_data import element_input_json
from bim2sim.decision import RealDecision, BoolDecision
from bim2sim.utilities.common_functions import get_type_building_elements_hvac
from bim2sim.kernel.hvac.hvac_graph import HvacGraph
from bim2sim.workflow import Workflow

quality_logger = logging.getLogger('bim2sim.QualityReport')


class ConnectElements(ITask):
    """Analyses IFC, creates element instances and connects them.
    Elements are stored in instances dict with guid as key"""

    reads = ('instances',)
    touches = ('instances',)

    def __init__(self):
        super().__init__()
        self.instances = {}
        pass

    def run(self, workflow: Workflow, instances: dict) -> dict:
        """

        Args:
            workflow: the used workflow
            instances: dictionary of elements with guid as key

        Returns:
            instances: dictionary of elements with guid as key
        """
        self.logger.info("Connect elements")

        # Check ports
        self.logger.info("Checking ports of elements ...")
        self.check_element_ports(instances)
        # Make connections by relation
        self.logger.info("Connecting the relevant elements")
        self.logger.info(" - Connecting by relations ...")
        all_ports = [port for item in instances.values() for port in item.ports]
        rel_connections = self.connections_by_relation(all_ports)
        self.logger.info(" - Found %d potential connections.", len(rel_connections))
        # Check connections
        self.logger.info(" - Checking positions of connections ...")
        confirmed, unconfirmed, rejected = self.confirm_connections_position(rel_connections)
        self.logger.info(" - %d connections are confirmed and %d rejected. %d can't be confirmed.",
                         len(confirmed), len(rejected), len(unconfirmed))
        for port1, port2 in confirmed + unconfirmed:
            # Unconfirmed ports have no position data and can not be connected by position
            port1.connect(port2)
        # Connect unconnected ports by position
        unconnected_ports = (port for port in all_ports if not port.is_connected())
        self.logger.info(" - Connecting remaining ports by position ...")
        pos_connections = self.connections_by_position(unconnected_ports)
        self.logger.info(" - Found %d additional connections.", len(pos_connections))
        for port1, port2 in pos_connections:
            port1.connect(port2)
        # Get number of connected and unconnected ports
        nr_total = len(all_ports)
        unconnected = [port for port in all_ports if not port.is_connected()]
        nr_unconnected = len(unconnected)
        nr_connected = nr_total - nr_unconnected
        self.logger.info("In total %d of %d ports are connected.", nr_connected, nr_total)
        if nr_total > nr_connected:
            self.logger.warning("%d ports are not connected!", nr_unconnected)
        # Connect by bounding box TODO: implement
        unconnected_elements = {uc.parent for uc in unconnected}
        if unconnected_elements:
            bb_connections = self.connections_by_boundingbox(unconnected, unconnected_elements)
            self.logger.warning("Connecting by bounding box is not implemented.")
        # Check inner connections
        yield from self.check_inner_connections(instances.values())

        # TODO: manually add / modify connections
        return instances,

    @staticmethod
    def check_element_ports(elements: dict):
        """Checks position of all ports for each element.

        Args:
            elements: dictionary of elements to be checked
        """
        for ele in elements.values():
            for port_a, port_b in itertools.combinations(ele.ports, 2):
                if np.allclose(port_a.position, port_b.position, rtol=1e-7, atol=1):
                    quality_logger.warning("Poor quality of elements %s: "
                                           "Overlapping ports (%s and %s @%s)",
                                           ele.ifc, port_a.guid, port_b.guid, port_a.position)
                    connections = ConnectElements.connections_by_relation([port_a, port_b], include_conflicts=True)
                    all_ports = [port for connection in connections for port in connection]
                    other_ports = [port for port in all_ports if port not in [port_a, port_b]]
                    if port_a in all_ports and port_b in all_ports and len(set(other_ports)) == 1:
                        # Both ports connected to same other port -> merge ports
                        quality_logger.info("Removing %s and set %s as SINKANDSOURCE.", port_b.ifc, port_a.ifc)
                        ele.ports.remove(port_b)
                        port_b.parent = None
                        port_a.flow_direction = 0
                        port_a.flow_master = True

    @staticmethod
    def connections_by_relation(ports: list, include_conflicts: bool = False) -> list:
        """Connect ports of instances by IFC relations.

        Args:
            ports: list of ports to be connected
            include_conflicts: if true, conflicts are tried to solve

        Returns:
            connections: list of tuples of ports that are connected
        """
        connections = []
        port_mapping = {port.guid: port for port in ports}
        for port in ports:
            if not port.ifc:
                continue
            connected_ports = [conn.RelatingPort for conn in port.ifc.ConnectedFrom] + [conn.RelatedPort for conn in
                                                                                        port.ifc.ConnectedTo]
            if connected_ports:
                other_port = None
                if len(connected_ports) > 1:
                    # conflicts
                    quality_logger.warning("%s has multiple connections", port.ifc)
                    possibilities = []
                    for connected_port in connected_ports:
                        possible_port = port_mapping.get(
                            connected_port.GlobalId)

                        if possible_port.parent is not None:
                            possibilities.append(possible_port)

                    # solving conflicts
                    if include_conflicts:
                        for poss in possibilities:
                            connections.append((port, poss))
                    else:
                        if len(possibilities) == 1:
                            other_port = possibilities[0]
                            quality_logger.info("Solved by ignoring deleted connection.")
                        else:
                            quality_logger.error("Unable to solve conflicting connections. "
                                                 "Continue without connecting %s", port.ifc)
                else:
                    # explicit
                    other_port = port_mapping.get(connected_ports[0].GlobalId)
                if other_port:
                    if port.parent and other_port.parent:
                        connections.append((port, other_port))
                    else:
                        quality_logger.debug("Not connecting ports without parent (%s, %s)", port, other_port)
        return connections

    @staticmethod
    def confirm_connections_position(connections: list, eps: float = 1):
        """Checks distance between port positions.
        If distance < eps, the connection is confirmed otherwise rejected.

        Args:
            connections: list of connections to be checked
            eps: distance tolerance for which connections are either confirmed or rejected

        Returns:
            tuple of lists of connections (confirmed, unconfirmed, rejected)
        """
        confirmed = []
        unconfirmed = []
        rejected = []
        for port1, port2 in connections:
            delta = ConnectElements.port_distance(port1, port2)
            if delta is None:
                unconfirmed.append((port1, port2))
            elif max(abs(delta)) < eps:
                confirmed.append((port1, port2))
            else:
                rejected.append((port1, port2))
        return confirmed, unconfirmed, rejected

    @staticmethod
    def port_distance(port1: Port, port2: Port) -> np.array:
        """Calculates distance (delta in x, y, z) of ports.

        Args:
            port1: the first port
            port2: the seconds port

        Returns:
            delta: distance between port1 and port2 in x, y, z coordinates
        """
        try:
            delta = port1.position - port2.position
        except AttributeError:
            delta = None
        return delta

    @staticmethod
    def connections_by_position(ports: Generator, eps: float = 10) -> list:
        """Connect ports of instances by computing geometric distance

        Args:
            ports:
            eps: distance tolerance for which ports are connected

        Returns: list of tuples of ports that are connected

        """
        graph = nx.Graph()
        for port1, port2 in itertools.combinations(ports, 2):
            if port1.parent == port2.parent:
                continue
            delta = ConnectElements.port_distance(port1, port2)
            if delta is None:
                continue
            abs_delta = max(abs(delta))
            if abs_delta < eps:
                graph.add_edge(port1, port2, delta=abs_delta)

        # verify
        conflicts = [port for port, deg in graph.degree() if deg > 1]
        for port in conflicts:
            candidates = sorted(graph.edges(port, data=True), key=lambda t: t[2].get('delta', eps))
            # initially there are at least two candidates, but there will be less, if previous conflicts belong to them
            if len(candidates) <= 1:
                # no action required
                continue
            quality_logger.warning(
                "Found %d geometrically close ports around %s. Details: %s",
                len(candidates), port, candidates)
            if candidates[0][2]['delta'] < candidates[1][2]['delta']:
                # keep first
                first = 1
                quality_logger.info(
                    "Accept closest ports with delta %d as connection (%s - %s)",
                    candidates[0][2]['delta'], candidates[0][0], candidates[0][1])
            else:
                # remove all
                first = 0
                quality_logger.warning(
                    "No connection determined, because there are no two "
                    "closest ports.")
            for cand in candidates[first:]:
                graph.remove_edge(cand[0], cand[1])

        return list(graph.edges())

    @staticmethod
    def check_inner_connections(instances: Iterable[ProductBased]) -> Generator[DecisionBunch, None, None]:
        """Check inner connections of HVACProducts.

        Args:
            instances:
        Returns:

        """
        # TODO: if a lot of decisions occur, it would help to merge DecisionBunches before yielding them
        for instance in instances:
            if isinstance(instance, hvac.HVACProduct) \
                    and not instance.inner_connections:
                yield from instance.decide_inner_connections()

    @staticmethod
    def connections_by_boundingbox(open_ports, elements):
        """Search for open ports in elements bounding boxes.

        This is especially useful for vessel like elements with variable
        number of ports (and bad ifc export) or proxy elements.
        Missing ports on element side are created on demand."""

        # TODO: implement
        connections = []
        return connections


class Enrich(ITask):
    def __init__(self):
        super().__init__()
        self.enrich_data = {}
        self.enriched_instances = {}

    @staticmethod
    def enrich_instance(instance, json_data):
        attrs_enrich = element_input_json.load_element_class(instance, json_data)
        return attrs_enrich

    def run(self, instances):
        json_data = get_type_building_elements_hvac()

        # enrichment_parameter --> Class
        self.logger.info("Enrichment of the elements...")
        # general question -> year of construction, all elements
        decision = RealDecision("Enter value for the construction year",
                                validate_func=lambda x: isinstance(x, float),
                                global_key="Construction year",
                                allow_skip=False)
        yield DecisionBunch([decision])
        delta = float("inf")
        year_selected = None
        for year in json_data.element_bind["statistical_years"]:
            if abs(year - decision.value) < delta:
                delta = abs(year - decision.value)
                year_selected = int(year)
        enrich_parameter = year_selected
        # specific question -> each instance
        for instance in instances:
            enrichment_data = self.enrich_instance(instances[instance], json_data)
            if bool(enrichment_data):
                instances[instance].enrichment["enrichment_data"] = \
                    enrichment_data
                instances[instance].enrichment["enrich_parameter"] = \
                    enrich_parameter
                instances[instance].enrichment["year_enrichment"] = \
                    enrichment_data["statistical_year"][str(enrich_parameter)]

        self.logger.info("Applied successfully attributes enrichment on elements")


class MakeGraph(ITask):
    """Instantiate HVACGraph"""

    reads = ('instances', )
    touches = ('graph', )

    def run(self, workflow: Workflow, instances: dict):
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
    """Reduce number of elements by aggregation."""

    reads = ('graph',)
    touches = ('graph',)

    def run(self, workflow: Workflow, graph: HvacGraph) -> (HvacGraph, ):
        self.logger.info("Reducing elements by applying aggregations")

        aggregations = [
            UnderfloorHeating,
            Consumer,
            PipeStrand,
            ParallelPump,
            ConsumerHeatingDistributorModule,
            GeneratorOneFluid,
            # ParallelSpaceHeater,
        ]

        statistics = {}
        number_of_elements_before = len(graph.elements)

        for agg_class in aggregations:
            name = agg_class.__name__
            self.logger.info("Aggregating '%s' ...", name)
            matches, metas = agg_class.find_matches(graph)
            i = 0
            for match, meta in zip(matches, metas):
                # TODO: See #167
                # outer_connections = agg_class.get_edge_ports2(graph, match)
                try:
                    agg = agg_class(match, **meta)
                except Exception as ex:
                    self.logger.exception("Instantiation of '%s' failed", name)
                else:
                    graph.merge(
                        mapping=agg.get_replacement_mapping(),
                        inner_connections=agg.inner_connections
                    )
                    i += 1
            statistics[name] = i
        number_of_elements_after = len(graph.elements)

        log_str = "Aggregations reduced number of elements from %d to %d:" % \
                  (number_of_elements_before, number_of_elements_after)
        for aggregation, count in statistics.items():
            log_str += "\n  - %s: %d" % (aggregation, count)
        self.logger.info(log_str)

        if __debug__:
            self.logger.info("Plotting graph ...")
            graph.plot(self.paths.export)
            graph.plot(self.paths.export, ports=True)

        return graph,

    @staticmethod
    def set_flow_sides(graph: HvacGraph):
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
                side, visited, masters = graph.recurse_set_unknown_sides(
                    unset_port)
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
                        decision = BoolDecision(
                            "Use %r as VL (y) or RL (n)?" % port)
                        yield DecisionBunch([decision])
                        use = decision.value
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

    reads = ('graph',)
    touches = ('cycles',)

    # TODO: sth useful like grouping or medium assignment

    def run(self, workflow: Workflow, graph: HvacGraph) -> tuple:
        self.logger.info("Detecting cycles")
        cycles = graph.get_cycles()
        return cycles,


class Export(ITask):
    """Export to Dymola/Modelica"""

    reads = ('libraries', 'graph')
    final = True

    def run(self, workflow: Workflow, libraries: tuple, graph: HvacGraph):
        self.logger.info("Export to Modelica code")
        reduced_instances = graph.elements

        connections = graph.get_connections()

        modelica.Instance.init_factory(libraries)
        export_instances = {inst: modelica.Instance.factory(inst) for inst in reduced_instances}

        yield from ProductBased.get_pending_attribute_decisions(reduced_instances)

        for instance in export_instances.values():
            instance.collect_params()

        connection_port_names = self.create_connections(graph, export_instances)

        self.logger.info(
            "Creating Modelica model with %d model instances and %d connections.",
            len(export_instances), len(connection_port_names))

        modelica_model = modelica.Model(
            name="BIM2SIM",
            comment=f"Autogenerated by BIM2SIM on {datetime.now():%Y-%m-%d %H:%M:%S%z}",
            instances=list(export_instances.values()),
            connections=connection_port_names,
        )
        modelica_model.save(self.paths.export)

    @staticmethod
    def create_connections(graph: HvacGraph, export_instances: dict) -> list:
        """
        Creates a list of connections for the corresponding modelica model.

        Args:
            graph: the HVAC graph
            export_instances: the modelica instances

        Returns:
           connection_port_names: list of tuple of port names that are connected
        """
        connection_port_names = []
        distributors_n = {}
        distributors_ports = {}
        for port_a, port_b in graph.edges:
            if port_a.parent is port_b.parent:
                # ignore inner connections
                continue
            instances = {'a': export_instances[port_a.parent],
                         'b': export_instances[port_b.parent]}
            ports_name = {'a': instances['a'].get_full_port_name(port_a),
                          'b': instances['b'].get_full_port_name(port_b)}
            if any(isinstance(e.element, hvac.Distributor) for e in instances.values()):
                for key, inst in instances.items():
                    if type(inst.element) is hvac.Distributor:
                        distributor = (key, inst)
                        distributor_port = ports_name[key]
                    else:
                        other_inst = inst
                        other_port = ports_name[key]

                ports_name[distributor[0]] = distributor[1].get_new_port_name(
                    distributor[1], other_inst, distributor_port, other_port,
                    distributors_n, distributors_ports)

            connection_port_names.append((ports_name['a'], ports_name['b']))

        for distributor in distributors_n:
            distributor.params['n'] = int(distributors_n[distributor] / 2 - 1)

        return connection_port_names
