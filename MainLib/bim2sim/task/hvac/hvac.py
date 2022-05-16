"""This module holds tasks related to hvac"""

import itertools
import json
import logging
from datetime import datetime
from typing import Generator, Iterable

import numpy as np
import networkx as nx

from bim2sim.kernel.elements.hvac import HVACProduct
from bim2sim.task.base import ITask
from bim2sim.filter import TypeFilter
from bim2sim.kernel.aggregation import PipeStrand, UnderfloorHeating,\
    ParallelPump
from bim2sim.kernel.aggregation import Consumer, ConsumerHeatingDistributorModule
from bim2sim.kernel.element import ProductBased, ElementEncoder, Port
from bim2sim.kernel.hvac import hvac_graph
from bim2sim.export import modelica
from bim2sim.decision import Decision, DecisionBunch
from bim2sim.enrichment_data import element_input_json
from bim2sim.decision import RealDecision, BoolDecision
from bim2sim.utilities.common_functions import get_type_building_elements_hvac


quality_logger = logging.getLogger('bim2sim.QualityReport')


class ConnectElements(ITask):
    """Analyses IFC, creates Element instances and connects them.

    elements are stored in .instances dict with guid as key"""

    reads = ('instances',)
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
    def connections_by_position(ports, eps=10):
        """Connect ports of instances by computing geometric distance"""
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
            quality_logger.warning("Found %d geometrically close ports around %s. Details: %s",
                           len(candidates), port, candidates)
            if candidates[0][2]['delta'] < candidates[1][2]['delta']:
                # keep first
                first = 1
                quality_logger.info("Accept closest ports with delta as connection (%s - %s)",
                            candidates[0][2]['delta'], candidates[0][0], candidates[0][1])
            else:
                # remove all
                first = 0
                quality_logger.warning("No connection determined, because there are no two closest ports.")
            for cand in candidates[first:]:
                graph.remove_edge(cand[0], cand[1])

        return list(graph.edges())

    @staticmethod
    def connections_by_relation(ports, include_conflicts=False):
        """Inspects IFC relations of ports"""
        connections = []
        port_mapping = {port.guid: port for port in ports}
        for port in ports:
            if not port.ifc:
                continue
            connected_ports = \
                [conn.RelatingPort for conn in port.ifc.ConnectedFrom] \
                + [conn.RelatedPort for conn in port.ifc.ConnectedTo]
            if connected_ports:
                other_port = None
                if len(connected_ports) > 1:
                    # conflicts
                    quality_logger.warning("%s has multiple connections", port.ifc)
                    possibilities = []
                    for connected_port in connected_ports:
                        possible_port = port_mapping.get(connected_port.GlobalId)

                        if possible_port.parent is not None:
                            possibilities.append(possible_port)

                    # solving conflics
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
                    other_port = port_mapping.get(
                        connected_ports[0].GlobalId)
                if other_port:
                    if port.parent and other_port.parent:
                        connections.append((port, other_port))
                    else:
                        quality_logger.debug(
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
            delta = ConnectElements.port_distance(port1, port2)
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
        for ele in elements:
            for port_a, port_b in itertools.combinations(ele.ports, 2):
                if np.allclose(port_a.position, port_b.position,
                               rtol=1e-7, atol=1):
                    quality_logger.warning("Poor quality of elements %s: "
                                           "Overlapping ports (%s and %s @%s)",
                                           ele.ifc, port_a.guid, port_b.guid,
                                           port_a.position)

                    conns = ConnectElements.connections_by_relation(
                        [port_a, port_b], include_conflicts=True)
                    all_ports = [port for conn in conns for port in conn]
                    other_ports = [port for port in all_ports
                                   if port not in [port_a, port_b]]
                    if port_a in all_ports and port_b in all_ports \
                        and len(set(other_ports)) == 1:
                        # both ports connected to same other port -> merge ports
                        quality_logger.info("Removing %s and set %s as SINKANDSOURCE.",
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

    def run(self, workflow, instances):
        self.logger.info("Connect elements")
        self.instances = instances  # TODO: remove self.instances

        # connections
        self.logger.info("Checking ports of elements ...")
        self.check_element_ports(self.instances.values())
        self.logger.info("Connecting the relevant elements")
        self.logger.info(" - Connecting by relations ...")

        all_ports = [port for item in self.instances.values() for port in item.ports]
        rel_connections = self.connections_by_relation(
            all_ports)
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

        unconnected_ports = (port for port in all_ports
                             if not port.is_connected())
        self.logger.info(" - Connecting remaining ports by position ...")
        pos_connections = self.connections_by_position(unconnected_ports)
        self.logger.info(" - Found %d additional connections.",
                         len(pos_connections))
        for port1, port2 in pos_connections:
            port1.connect(port2)

        nr_total = len(all_ports)
        unconnected = [port for port in all_ports
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

        # inner connections
        yield from self.check_inner_connections(instances.values())

        # TODO: manualy add / modify connections
        return self.instances,

    def check_inner_connections(self, instances: Iterable[ProductBased])\
            -> Generator[DecisionBunch, None, None]:
        """Check inner connections of HVACProducts."""
        # If a lot of decisions occur, it would help to merge DecisionBunches
        # before yielding them
        for instance in instances:
            if isinstance(instance, HVACProduct) \
                    and not instance.inner_connections:
                yield from instance.decide_inner_connections()


class Enrich(ITask):
    def __init__(self):
        super().__init__()
        self.enrich_data = {}
        self.enriched_instances = {}

    def enrich_instance(self, instance, json_data):

        attrs_enrich = element_input_json.load_element_class(instance, json_data)

        return attrs_enrich

    def run(self, instances):
        json_data = get_type_building_elements_hvac()

        # enrichment_parameter --> Class
        self.logger.info("Enrichment of the elements...")
        # general question -> year of construction, all elements
        decision = RealDecision("Enter value for the construction year",
                                validate_func=lambda x: isinstance(x, float),  # TODO
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
                instances[instance].enrichment["enrichment_data"] = enrichment_data
                instances[instance].enrichment["enrich_parameter"] = enrich_parameter
                instances[instance].enrichment["year_enrichment"] = enrichment_data["statistical_year"][str(enrich_parameter)]

        self.logger.info("Applied successfully attributes enrichment on elements")
        # runs all enrich methods


class Prepare(ITask):  # Todo: obsolete
    """Configurate"""  # TODO: based on task

    reads = ('relevant_ifc_types', )
    touches = ('filters', )

    def run(self, workflow, relevant_ifc_types):
        self.logger.info("Setting Filters")
        # filters = [TypeFilter(relevant_ifc_types), TextFilter(relevant_ifc_types, ['Description'])]
        filters = [TypeFilter(relevant_ifc_types)]
        # self.filters.append(TextFilter(['IfcBuildingElementProxy', 'IfcUnitaryEquipment']))
        return filters,


class Enrich(ITask):

    reads = ('instances',)
    touches = ('instances', )

    def run(self, workflow, instances):
        #     def get_from_enrichment(bind, name):
        #         # TODO convert this former enrichment method from
        #         #  attribute.py to working enrichment for attributes of HVAC
        #         #  similar to the approach of "enrich_bldg_templ.py"
        #         value = None
        #         if hasattr(bind, 'enrichment') and bind.enrichment:
        #             attrs_enrich = bind.enrichment["enrichment_data"]
        #             if "enrich_decision" not in bind.enrichment:
        #                 # check if want to enrich instance
        #                 enrichment_decision = BoolDecision(
        #                     question="Do you want for %s_%s to be enriched" % (type(bind).__name__, bind.guid),
        #                     collect=False, global_key='%s_%s.Enrichment_Decision' % (type(bind).__name__, bind.guid),
        #                     allow_load=True, allow_save=True)
        #                 enrichment_decision.decide()
        #                 enrichment_decision.stored_decisions.clear()
        #                 bind.enrichment["enrich_decision"] = enrichment_decision.value
        #
        #             if bind.enrichment["enrich_decision"]:
        #                 # enrichment via incomplete data (has enrich parameter value)
        #                 if name in attrs_enrich:
        #                     value = attrs_enrich[name]
        #                     if value is not None:
        #                         return value
        #                 if "selected_enrichment_data" not in bind.enrichment:
        #                     options_enrich_parameter = list(attrs_enrich.keys())
        #                     decision1 = ListDecision("Select an Enrich Parameter to continue",
        #                                              choices=options_enrich_parameter,
        #                                              global_key="%s_%s.Enrich_Parameter" % (type(bind).__name__, bind.guid),
        #                                              allow_skip=True, allow_load=True, allow_save=True,
        #                                              collect=False, quick_decide=not True)
        #                     decision1.decide()
        #                     decision1.stored_decisions.clear()
        #
        #                     if decision1.value == 'statistical_year':
        #                         # 3. check if general enrichment - construction year
        #                         bind.enrichment["selected_enrichment_data"] = bind.enrichment["year_enrichment"]
        #                     else:
        #                         # specific enrichment (enrichment parameter and values)
        #                         decision2 = RealDecision("Enter value for the parameter %s" % decision1.value,
        #                                                  validate_func=lambda x: isinstance(x, float),  # TODO
        #                                                  global_key="%s_%s.%s_Enrichment" % (type(bind).__name__, bind.guid, name),
        #                                                  allow_skip=False, allow_load=True, allow_save=True,
        #                                                  collect=False, quick_decide=False)
        #                         decision2.decide()
        #                         delta = float("inf")
        #                         decision2_selected = None
        #                         for ele in attrs_enrich[decision1.value]:
        #                             if abs(int(ele) - decision2.value) < delta:
        #                                 delta = abs(int(ele) - decision2.value)
        #                                 decision2_selected = int(ele)
        #
        #                         bind.enrichment["selected_enrichment_data"] = attrs_enrich[str(decision1.value)][
        #                             str(decision2_selected)]
        #                 value = bind.enrichment["selected_enrichment_data"][name]
        #         return value
        return instances


class MakeGraph(ITask):
    """Instantiate HvacGraph"""

    reads = ('instances', )
    touches = ('graph', )

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
    touches = ('graph',)

    def run(self, workflow, graph: hvac_graph.HvacGraph):
        self.logger.info("Reducing elements by applying aggregations")
        number_of_nodes_old = len(graph.element_graph.nodes)
        number_ps = 0
        number_fh = 0
        number_pipes = 0
        number_pp = 0
        number_psh = 0

        aggregations = [
            UnderfloorHeating,
            Consumer,
            PipeStrand,
            ParallelPump,
            ConsumerHeatingDistributorModule
            # ParallelSpaceHeater,
        ]

        statistics = {}
        n_elements_before = len(graph.elements)

        # TODO: LOD

        for agg_class in aggregations:
            name = agg_class.__name__
            self.logger.info("Aggregating '%s' ...", name)
            name_builder = '{} {}'
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
        n_elements_after = len(graph.elements)

        # Log output
        log_str = "Aggregations reduced number of elements from %d to %d:" % \
                  (n_elements_before, n_elements_after)
        for aggregation, count in statistics.items():
            log_str += "\n  - %s: %d" % (aggregation, count)
        self.logger.info(log_str)

        if __debug__:
            self.logger.info("Plotting graph ...")
            graph.plot(self.paths.export)
            graph.plot(self.paths.export, ports=True)

        return graph,

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

    reads = ('graph', )
    touches = ('cycles', )

    # TODO: sth usefull like grouping or medium assignment

    def run(self, workflow, graph: hvac_graph.HvacGraph):
        self.logger.info("Detecting cycles")
        cycles = graph.get_cycles()
        return cycles,


class Export(ITask):
    """Export to Dymola/Modelica"""

    reads = ('libraries', 'graph')
    final = True

    def run(self, workflow, libraries, graph: hvac_graph.HvacGraph):
        self.logger.info("Export to Modelica code")

        modelica.Instance.init_factory(libraries)
        export_instances = {inst: modelica.Instance.factory(inst) for inst in graph.elements}

        yield ProductBased.get_pending_attribute_decisions(export_instances)

        for instance in export_instances.values():
            instance.collect_params()

        connection_port_names = self.create_connections(graph, export_instances)

        self.logger.info(
            "Creating Modelica model with %d model instances and %d connections.",
            len(export_instances), len(connection_port_names))

        modelica_model = modelica.Model(
            name="BIM2SIM",
            comment=f"Autogenerated by BIM2SIM on {datetime.now():%Y-%m-%d %H:%M:%S%z}",
            instances=export_instances.values(),
            connections=connection_port_names,
        )
        # print("-"*80)
        # print(modelica_model.code())
        # print("-"*80)
        modelica_model.save(self.paths.export)

    def create_connections(self, graph, export_instances):
        connection_port_names = []
        for port_a, port_b in graph.edges:
            if port_a.parent is port_b.parent:
                # ignore inner connections
                continue
            instance_a = export_instances[port_a.parent]
            port_a_name = instance_a.get_full_port_name(port_a)
            instance_b = export_instances[port_b.parent]
            port_b_name = instance_b.get_full_port_name(port_b)
            connection_port_names.append((port_a_name, port_b_name))
        return connection_port_names
