"""Module for aggregation and simplifying elements"""
import logging
import math
from functools import partial
from typing import Sequence, List, Union, Iterable, Tuple, Set, Dict
import re

import numpy as np
import networkx as nx

from bim2sim.kernel.element import ProductBased, Port
from bim2sim.kernel.elements.hvac import HVACPort, HVACProduct
from bim2sim.kernel.elements import hvac, bps
from bim2sim.kernel import elements, attribute
from bim2sim.kernel.hvac.hvac_graph import HvacGraph
from bim2sim.kernel.units import ureg
from bim2sim.utilities.common_functions import filter_instances
from bim2sim.decision import ListDecision, BoolDecision, DecisionBunch
from bim2sim.decorators import cached_property

logger = logging.getLogger(__name__)


def verify_edge_ports(func):
    """Decorator to verify edge ports"""

    def wrapper(agg_instance, *args, **kwargs):
        ports = func(agg_instance, *args, **kwargs)
        # inner_ports =
        # [port for ele in agg_instance.elements for port in ele.ports]
        for port in ports:
            if not port.connection:
                continue
            if port.connection.parent in agg_instance.elements:
                raise AssertionError("%s (%s) is not an edge port of %s" % (
                    port, port.guid, agg_instance))
        return ports

    return wrapper


class HVACAggregationPort(HVACPort):
    """Port for Aggregation"""
    guid_prefix = 'AggPort'

    def __init__(self, originals, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # TODO / TBD: DJA: can one Port replace multiple? what about position?
        if not type(originals) == list:
            originals = [originals]
        if not all(isinstance(n, hvac.HVACPort) for n in originals):
            raise TypeError("originals must by HVACPorts")
        self.originals = originals

    # def determine_flow_side(self):
    # return self.original.determine_flow_side()

    def calc_position(self):
        """Position of original port"""
        return self.originals.position


class AggregationMixin:
    guid_prefix = 'Agg'
    multi = ()
    aggregatable_elements: Set[ProductBased] = set()

    def __init__(self, elements: Sequence[ProductBased], *args, **kwargs):
        if self.aggregatable_elements:
            received = {type(ele) for ele in elements}
            mismatch = received - self.aggregatable_elements
            if mismatch:
                raise AssertionError("Can't aggregate %s from elements: %s" %
                                     (self.__class__.__name__, mismatch))
        # TODO: make guid reproduceable unique for same aggregation elements
        #  e.g. hash of all (ordered?) element guids?
        #  Needed for save/load decisions on aggregations
        self.elements = elements
        for model in self.elements:
            model.aggregation = self
        super().__init__(*args, **kwargs)

    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if ProductBased not in cls.__bases__:
            # raise AssertionError("%s only supports sub classes of ProductBased" % cls)
            logger.error("%s only supports sub classes of ProductBased", cls)

        # TODO: this are only temporary checks
        if hasattr(cls, 'ifc_type'):
            logger.warning("Obsolete use of 'ifc_type' in %s" % cls)
        if hasattr(cls, 'predefined_types'):
            logger.warning("Obsolete use of 'predefined_types' in %s" % cls)

    def calc_position(self):
        """Position based on first and last element"""
        try:
            return (self.elements[0].position + self.elements[-1].position) / 2
            # return sum(ele.position for ele in self.elements) / len(self.elements)
        except:
            return None

    # def request(self, name):
    #     # broadcast request to all nested elements
    #     # if one attribute included in multi_calc is requested, all multi_calc attributes are needed
    #
    #     if name in self.multi:
    #         names = self.multi
    #     else:
    #         names = (name,)
    #
    #     # for ele in self.elements:
    #     #     for n in names:
    #     #         ele.request(n)
    #     decisions = DecisionBunch()
    #     for n in names:
    #         decisions.append(super().request(n))
    #     return decisions

    def source_info(self) -> str:
        return f'[{", ".join(e.source_info() for e in self.elements)}]'

    def __repr__(self):
        return "<%s (aggregation of %d elements)>" % (
            self.__class__.__name__, len(self.elements))

    def __str__(self):
        return "%s" % self.__class__.__name__


class HVACAggregationMixin(AggregationMixin):
    def __init__(self, element_graph, *args, outer_connections=None, **kwargs):
        # TODO: handle outer_connections from meta
        self.outer_connections = outer_connections  # WORKAROUND
        # make get_ports signature match ProductBased.get_ports
        self.get_ports = partial(self.get_ports, element_graph)
        super().__init__(list(element_graph.nodes), *args, **kwargs)

    @verify_edge_ports
    def get_ports(self, graph) -> List[HVACPort]:
        # TBD: use of outer_connections
        if not self.outer_connections:
            edge_ports = self.get_edge_ports(graph)
            ports = [HVACAggregationPort(port, parent=self)
                     for port in edge_ports]
        else:
            ports = [HVACAggregationPort(port, parent=self)
                     for port in self.outer_connections]
        return ports

    @classmethod
    def get_empty_mapping(cls, elements: Iterable[ProductBased]):
        """Get information to remove elements
        :returns tuple of
            mapping dict with original ports as values and None as keys
            connection list of outer connections"""
        ports = [port for element in elements for port in element.ports]
        mapping = {port: None for port in ports}
        # TODO: len > 1, optimize
        external_ports = []
        for port in ports:
            if port.connection and port.connection.parent not in elements:
                external_ports.append(port.connection)

        mapping[external_ports[0].connection] = external_ports[1]
        mapping[external_ports[1].connection] = external_ports[0]
        connections = []  # (external_ports[0], external_ports[1])

        return mapping, connections

    def get_replacement_mapping(self) \
            -> Dict[HVACPort, Union[HVACAggregationPort, None]]:
        """Get replacement dict for existing ports."""
        mapping = {port: None for element in self.elements
                   for port in element.ports}
        for port in self.ports:
            for original in port.originals:
                mapping[original] = port
        return mapping

    @classmethod
    def get_edge_ports(cls, graph) -> List[HVACPort]:
        """Finds and returns the original edge ports of element graph."""
        raise NotImplementedError()

    # TODO: get edge ports based on graph. See #167
    @classmethod
    def get_edge_ports2(cls, graph: HvacGraph, match: HvacGraph) -> List[
        HVACPort]:
        """Get edge ports based on graph."""
        # edges of g excluding all relations to s
        e1 = graph.subgraph(graph.nodes - match.nodes).edges
        # all edges related to s
        e2 = graph.edges - e1
        # related to s but not s exclusive
        e3 = e2 - match.edges
        return e3

    @classmethod
    def get_edge_ports_of_strait(cls, graph) -> List[HVACPort]:
        """
        Finds and returns the edge ports of element graph
        with exactly one strait chain of connected elements.

        :return list of ports:
        """

        edge_elements = [v for v, d in graph.degree() if d == 1]
        if len(edge_elements) != 2:
            raise AttributeError("Graph elements are not connected strait")

        edge_ports = set()
        ports = [p for e in edge_elements for p in e.ports]
        # first check for connections to outside
        for port in ports:
            if port.connection and port.connection.parent not in graph.nodes:
                edge_ports.add(port)
        # then check for unconnected edge ports
        for port in ports:
            if not port.connection:
                if not set(port.parent.ports) & edge_ports:
                    # no port of parent is an edge port
                    # take first ignore others
                    # TODO: see #169 this is a dirty workaround
                    edge_ports.add(port)
                else:
                    logger.warning("Ignoring superfluous unconnected ports in "
                                   "edge port detection of %s", cls)

        if len(edge_ports) > 2:
            raise AttributeError("Graph elements are not only (2 port) pipes")
        return list(edge_ports)

    @classmethod
    def find_matches(cls, graph: HvacGraph) \
            -> Tuple[List[nx.Graph], List[dict]]:
        """Find all matches for Aggregation in element graph
        :returns: matches, metas"""
        raise NotImplementedError(
            "Method %s.find_matches not implemented" % cls.__name__)

    def _calc_has_pump(self, name) -> bool:
        """Calculate if aggregation has pumps"""
        has_pump = False
        for ele in self.elements:
            if hvac.Pump is ele.__class__:
                has_pump = True
                break
        return has_pump


class PipeStrand(HVACAggregationMixin, hvac.Pipe):
    """Aggregates pipe strands"""
    aggregatable_elements = {hvac.Pipe, hvac.PipeFitting, hvac.Valve}
    multi = ('length', 'diameter')

    @classmethod
    def get_edge_ports(cls, graph):
        return cls.get_edge_ports_of_strait(graph)

    @attribute.multi_calc
    def _calc_avg(self):
        """Calculates the total length and average diameter of all pipe-like
         elements."""
        total_length = 0
        avg_diameter = 0
        diameter_times_length = 0

        for pipe in self.elements:
            length = getattr(pipe, "length")
            diameter = getattr(pipe, "diameter")
            if not (length and diameter):
                logger.warning("Ignored '%s' in aggregation", pipe)
                continue

            diameter_times_length += diameter * length
            total_length += length

        if total_length != 0:
            avg_diameter = diameter_times_length / total_length

        result = dict(
            length=total_length,
            diameter=avg_diameter
        )
        return result

    @classmethod
    def find_matches(cls, graph) -> [list, list]:
        """
        Find all matches for PipeStrand in element graph

        Args:
            graph: element_graph that should be checked for PipeStrand

        Returns:
            element_graphs:
                List of element_graphs that hold a PipeStrand
            metas:
                List of dict with metas information. One element for each
                element_graph.

        Raises:
            None
        """
        element_graph = graph.element_graph
        chains = HvacGraph.get_type_chains(element_graph,
                                           cls.aggregatable_elements,
                                           include_singles=True)
        element_graphs = [element_graph.subgraph(chain) for chain in chains if
                          len(chain) > 1]
        metas = [{} for x in element_graphs]  # no metadata calculated
        return element_graphs, metas

    diameter = attribute.Attribute(
        description="Average diameter of aggregated pipe",
        functions=[_calc_avg],
        unit=ureg.millimeter,
        dependant_instances='elements'
    )

    length = attribute.Attribute(
        description="Length of aggregated pipe",
        functions=[_calc_avg],
        unit=ureg.meter,
        dependant_instances='elements'
    )


class UnderfloorHeating(PipeStrand):
    """Aggregates Underfloor heating, normal pitch (spacing) between
    pipes is between 0.1m and 0.2m"""

    @classmethod
    def find_matches(cls, graph: {HvacGraph.element_graph}) -> \
            [list, list]:
        """
        Find matches of Underfloor heating.

        Args:
            graph: element_graph that should be checked for Underfloor heating

        Returns:
            element_graphs:
                List of element_graphs that hold a Underfloor heating
            metas:
                List of dict with metas information. One element for each
                element_graph.

        Raises:
            None
        """
        element_graph = graph.element_graph
        chains = HvacGraph.get_type_chains(element_graph,
                                           cls.aggregatable_elements,
                                           include_singles=True)
        element_graphs = []
        metas = []
        for chain in chains:
            meta = cls.check_conditions(chain)
            if meta:
                metas.append(meta)
                element_graphs.append(element_graph.subgraph(chain))
        return element_graphs, metas

    @staticmethod
    def check_number_of_elements(uh_elements: nx.classes.reportviews.NodeView,
                                 tolerance: int = 20) -> bool:
        """
        Check if the targeted pipe strand has more than 20 elements.

        Args:
            uh_elements: possible pipe strand to be an Underfloor heating
            tolerance: integer tolerance value to check pipe strand

        Returns:
            None: if check fails
            True: if check succeeds
        """
        return len(uh_elements) >= tolerance

    @staticmethod
    def check_pipe_strand_horizontality(ports_coors: np.ndarray,
                                        tolerance: float = 0.8) -> bool:
        """
        Check if the pipe strand is located horizontally -- parallel to
        the floor and most elements are in the same z plane
        Args:
            ports_coors: array with pipe strand port coordinates
            tolerance: float tolerance to check pipe strand horizontality

        Returns:
            None: if check fails
            True: if check succeeds
        """
        counts = np.unique(ports_coors[:, 2], return_counts=True)
        # TODO: cluster z coordinates
        idx_max = np.argmax(counts[1])
        return counts[1][idx_max] / ports_coors.shape[0] >= tolerance

    @staticmethod
    def get_pipe_strand_attributes(ports_coors: np.ndarray,
                                   uh_elements: nx.classes.reportviews.NodeView
                                   ) -> [*(ureg.Quantity,) * 5]:
        """
        Get pipe strand attributes in order to proceed with the following
        checkpoints
        Args:
            ports_coors: array with pipe strand port coordinates
            uh_elements: possible pipe strand to be an Underfloor heating

        Returns:
            heating_area: Underfloor heating area,
            total_length: Underfloor heating total pipe length,
            avg_diameter: Average Underfloor heating diameter,
            dist_x: Underfloor heating dimension in x,
            dist_y:Underfloor heating dimension in y
        """
        total_length = sum(segment.length for segment in uh_elements if
                           segment.length is not None)
        avg_diameter = (sum(segment.diameter ** 2 * segment.length for segment
                            in uh_elements if segment.length is not
                            None) / total_length) ** 0.5
        length_unit = total_length.u
        x_coord, y_coord = ports_coors[:, 0], ports_coors[:, 1]
        min_x = ports_coors[np.argmin(x_coord)][:2]
        max_x = ports_coors[np.argmax(x_coord)][:2]
        min_y = ports_coors[np.argmin(y_coord)][:2]
        max_y = ports_coors[np.argmax(y_coord)][:2]
        if min_x[1] == max_x[1] or min_y[0] == max_y[0]:
            dist_x = (max_x[0] - min_x[0]) * length_unit
            dist_y = (max_y[1] - min_y[1]) * length_unit
            heating_area = (dist_x * dist_y)
        else:
            dist_x = (np.linalg.norm(min_y - max_x)) * length_unit
            dist_y = (np.linalg.norm(min_y - min_x)) * length_unit
            heating_area = (dist_x * dist_y)

        return heating_area, total_length, avg_diameter, dist_x, dist_y

    @staticmethod
    def get_ufh_type():
        # ToDo: function to obtain the underfloor heating form based on issue
        #  #211
        raise NotImplementedError

    @classmethod
    def get_pipe_strand_spacing(cls,
                                uh_elements: nx.classes.reportviews.NodeView,
                                dist_x: ureg.Quantity,
                                dist_y: ureg.Quantity,
                                tolerance: int = 10) -> [*(ureg.Quantity,) * 2]:
        """
        Sorts the pipe elements according to their angle in the horizontal
        plane. Necessary to calculate subsequently the underfloor heating
        spacing
        Args:
            uh_elements: possible pipe strand to be an Underfloor heating
            dist_x: Underfloor heating dimension in x
            dist_y: Underfloor heating dimension in y
            tolerance: integer tolerance to get pipe strand spacing

        Returns:
            x_spacing: Underfloor heating pitch in x,
            y_spacing: Underfloor heating pitch in y
        """
        # ToDo: what if multiple pipe elements on the same line? Collinear
        #  algorithm, issue #211
        orientations = {}
        for element in uh_elements:
            if type(element) is hvac.Pipe:
                a = abs(element.ports[0].position[1] -
                        element.ports[1].position[1])
                b = abs(element.ports[0].position[0] -
                        element.ports[1].position[0])
                if b != 0:
                    theta = int(math.degrees(math.atan(a / b)))
                else:
                    theta = 90
                if theta not in orientations:
                    orientations[theta] = []
                orientations[theta].append(element)
        for orient in orientations.copy():
            if len(orientations[orient]) < tolerance:
                del orientations[orient]
        orientations = list(sorted(orientations.items()))
        x_spacing = dist_x / (len(orientations[0][1]) - 1)
        y_spacing = dist_y / (len(orientations[1][1]) - 1)
        return x_spacing, y_spacing

    @staticmethod
    def check_heating_area(heating_area: ureg.Quantity,
                           tolerance: ureg.Quantity =
                           1e6 * ureg.millimeter ** 2) -> bool:
        """
        Check if the total area of the underfloor heating is greater than
        the tolerance value - just as safety factor

        Args:
            heating_area: Underfloor heating area,
            tolerance: Quantity tolerance to check heating area

        Returns:
            None: if check fails
            True: if check succeeds
        """
        return heating_area >= tolerance

    @staticmethod
    def check_spacing(x_spacing: ureg.Quantity,
                      y_spacing: ureg.Quantity,
                      tolerance: tuple = (90 * ureg.millimeter,
                                          210 * ureg.millimeter)) -> bool:
        """
        Check if the spacing between adjacent elements with the same
        orientation is between the tolerance values
        Args:
            x_spacing: Underfloor heating pitch in x
            y_spacing: Underfloor heating pitch in y
            tolerance: tuple tolerance to check underfloor heating spacing

        Returns:
            None: if check fails
            True: if check succeeds
        """
        if not ((tolerance[0] < x_spacing < tolerance[1])
                or (tolerance[0] < y_spacing < tolerance[1])):
            return
        return True

    @staticmethod
    def check_kpi(total_length: ureg.Quantity,
                  avg_diameter: ureg.Quantity,
                  heating_area: ureg.Quantity,
                  tolerance: tuple = (0.09, 0.01)) -> bool:
        """
        Check if the quotient between the cross sectional area of the pipe
        strand (x-y plane) and the total heating area is between the
        tolerance values - area density for underfloor heating

        Args:
            total_length: Underfloor heating total pipe length,
            avg_diameter: Average Underfloor heating diameter,
            heating_area: Underfloor heating area,
            tolerance: tuple tolerance to check underfloor heating kpi

        Returns:
            None: if check fails
            True: if check succeeds
        """
        kpi_criteria = (total_length * avg_diameter) / heating_area
        return tolerance[0] > kpi_criteria > tolerance[1]

    @classmethod
    def check_conditions(cls,
                         uh_elements: nx.classes.reportviews.NodeView) -> dict:
        """
        Checks ps_elements and returns instance of UnderfloorHeating if all
        following criteria are fulfilled:
            0. minimum of 20 elements
            1. the pipe strand is located horizontally
            2. the pipe strand elements located in an specific z-coordinate
            3. the spacing tolerance
            4. underfloor heating area tolerance
            5. kpi criteria

        Args:
            uh_elements: possible pipe strand to be an Underfloor heating

        Returns:
            None: if check fails
            meta: dict with calculated values if check succeeds
        """
        # TODO: use only floor heating pipes and not connecting pipes
        if not cls.check_number_of_elements(uh_elements):
            return
        ports_coors = np.array(
            [p.position for e in uh_elements for p in e.ports])
        if not cls.check_pipe_strand_horizontality(ports_coors):
            return

        heating_area, total_length, avg_diameter, dist_x, dist_y = \
            cls.get_pipe_strand_attributes(ports_coors, uh_elements)
        x_spacing, y_spacing = cls.get_pipe_strand_spacing(uh_elements, dist_x,
                                                           dist_y)

        if not cls.check_heating_area(heating_area):
            return
        if not cls.check_spacing(x_spacing, y_spacing):
            return
        if not cls.check_kpi(total_length, avg_diameter, heating_area):
            return

        meta = dict(
            length=total_length,
            diameter=avg_diameter,
            heating_area=heating_area,
            x_spacing=x_spacing,
            y_spacing=y_spacing
        )
        return meta

    def is_consumer(self):
        return True

    heating_area = attribute.Attribute(
        unit=ureg.meter ** 2,
        description='Heating area',
    )
    x_spacing = attribute.Attribute(
        unit=ureg.meter,
        description='Spacing in x',
    )
    y_spacing = attribute.Attribute(
        unit=ureg.meter,
        description='Spacing in y',
    )
    rated_power = attribute.Attribute(
        unit=ureg.kilowatt,
        description="rated power"
    )
    rated_mass_flow = attribute.Attribute(
        description="Rated mass flow of pump",
        unit=ureg.kg / ureg.s,
    )


class ParallelPump(HVACAggregationMixin, hvac.Pump):
    """Aggregates pumps in parallel"""
    aggregatable_elements = {
        hvac.Pump, hvac.Pipe, hvac.PipeFitting, PipeStrand}
    multi = ('rated_power', 'rated_height', 'rated_volume_flow', 'diameter',
             'diameter_strand', 'length')

    def get_ports(self, graph):
        ports = []
        edge_ports = self.get_edge_ports(graph)
        # simple case with two edge ports
        if len(edge_ports) == 2:
            for port in edge_ports:
                ports.append(HVACAggregationPort(port, parent=self))
        # more than two edge ports
        else:
            # get list of ports to be merged to one aggregation port
            parents = set((parent for parent in (port.connection.parent for
                                                 port in edge_ports)))
            originals_dict = {}
            for parent in parents:
                originals_dict[parent] = [port for port in edge_ports if
                                          port.connection.parent == parent]
            for originals in originals_dict.values():
                ports.append(HVACAggregationPort(originals, parent=self))
        return ports

    def get_edge_ports(self, graph):
        """
        Finds and returns all edge ports of element graph.

        :return list of ports:
        """
        # detect elements with at least 3 ports
        # todo detection via number of ports is not safe, because pumps and
        #  other elements can  have additional signal ports and count as
        #  edge_elements. current workaround: check for pumps seperatly
        edge_elements = [
            node for node in graph.nodes if (len(node.ports) > 2 and
                                             node.__class__.__name__ != 'Pump')]

        if len(edge_elements) > 2:
            graph = self.merge_additional_junctions(graph)

        edge_outer_ports = []
        edge_inner_ports = []

        # get all elements in graph, also if in aggregation
        elements_in_graph = []
        for node in graph.nodes:
            elements_in_graph.append(node)
            if hasattr(node, 'elements'):
                for element in node.elements:
                    elements_in_graph.append(element)

        # get all ports that are connected to outer elements
        for port in (p for e in edge_elements for p in e.ports):
            if not port.connection:
                continue  # end node
            if port.connection.parent not in elements_in_graph:
                edge_outer_ports.append(port)
            elif port.connection.parent in elements_in_graph:
                edge_inner_ports.append(port)

        if len(edge_outer_ports) < 2:
            raise AttributeError("Found less than two edge ports")
        # simple case: no other elements connected to junction nodes
        elif len(edge_outer_ports) == 2:
            edge_ports = edge_outer_ports
        # other elements, not in aggregation, connected to junction nodes
        else:
            edge_ports = [port.connection for port in edge_inner_ports]
            parents = set(parent for parent in (port.connection.parent for
                                                port in edge_ports))
            for parent in parents:
                aggr_ports = [port for port in edge_inner_ports if
                              port.parent == parent]
                if not isinstance(parent.aggregation, AggregatedPipeFitting):
                    AggregatedPipeFitting(nx.subgraph(
                        graph, parent), aggr_ports)
                else:
                    for port in aggr_ports:
                        HVACAggregationPort(
                            originals=port, parent=parent.aggregation)
        return edge_ports

    @attribute.multi_calc
    def _calc_avg(self) -> dict:
        """Calculates the total length and average diameter of all pump-like
         elements."""
        avg_diameter_strand = 0
        total_length = 0
        diameter_times_length = 0

        for item in self.not_pump_elements:
            if hasattr(item, "diameter") and hasattr(item, "length"):
                length = item.length
                diameter = item.diameter
                if not (length and diameter):
                    logger.info("Ignored '%s' in aggregation", item)
                    continue

                diameter_times_length += length * diameter
                total_length += length
            else:
                logger.info("Ignored '%s' in aggregation", item)

        if total_length != 0:
            avg_diameter_strand = diameter_times_length / total_length

        result = dict(
            length=total_length,
            diameter_strand=avg_diameter_strand
        )
        return result

    def get_replacement_mapping(self) \
            -> Dict[HVACPort, Union[HVACAggregationPort, None]]:
        mapping = super().get_replacement_mapping()

        # TODO: cant this be solved in find_matches?
        # search for aggregations made during the parallel pump construction
        new_aggregations = [element.aggregation for element in self.elements if
                            element.aggregation is not self]
        for port in (p for a in new_aggregations for p in a.ports):
            for original in port.originals:
                mapping[original] = port
        return mapping

    @classmethod
    def merge_additional_junctions(cls, graph):
        """ Find additional junctions inside the parallel pump network and
        merge them into each other to create a simplified network."""

        # check if additional junctions exist
        add_junctions, metas = AggregatedPipeFitting.find_matches(graph)
        i = 0
        for junction, meta in zip(add_junctions, metas):
            # todo maybe add except clause
            aggrPipeFitting = AggregatedPipeFitting(junction, **meta)
            i += 1
        return graph

    @cached_property
    def pump_elements(self) -> list:
        """list of pump-like elements present on the aggregation"""
        return [ele for ele in self.elements if isinstance(ele, hvac.Pump)]

    def _calc_rated_power(self, name) -> ureg.Quantity:
        """Calculate the rated power adding the rated power of the pump-like
        elements"""
        return sum([ele.rated_power for ele in self.pump_elements])

    rated_power = attribute.Attribute(
        unit=ureg.kilowatt,
        description="rated power",
        functions=[_calc_rated_power],
        dependant_instances='pump_elements'
    )

    def _calc_rated_height(self, name) -> ureg.Quantity:
        """Calculate the rated height, using the maximal rated height of
        the pump-like elements"""
        return max([ele.rated_height for ele in self.pump_elements])

    rated_height = attribute.Attribute(
        description='rated height',
        functions=[_calc_rated_height],
        unit=ureg.meter,
        dependant_instances='pump_elements'
    )

    def _calc_volume_flow(self, name) -> ureg.Quantity:
        """Calculate the volume flow, adding the volume flow of the pump-like
        elements"""
        return sum([ele.rated_volume_flow for ele in self.pump_elements])

    rated_volume_flow = attribute.Attribute(
        description='rated volume flow',
        functions=[_calc_volume_flow],
        unit=ureg.meter ** 3 / ureg.hour,
        dependant_instances='pump_elements'
    )

    def _calc_diameter(self, name) -> ureg.Quantity:
        """Calculate the diameter, using the pump-like elements diameter"""
        return sum(item.diameter ** 2 for item in self.pump_elements) ** 0.5

    diameter = attribute.Attribute(
        description='diameter',
        functions=[_calc_diameter],
        unit=ureg.millimeter,
        dependant_instances='pump_elements'
    )

    @cached_property
    def not_pump_elements(self) -> list:
        """list of not-pump-like elements present on the aggregation"""
        return [ele for ele in self.elements if not isinstance(ele, hvac.Pump)]

    length = attribute.Attribute(
        description='length of aggregated pipe elements',
        functions=[_calc_avg],
        unit=ureg.meter,
        dependant_instances='not_pump_elements'
    )

    diameter_strand = attribute.Attribute(
        description='average diameter of aggregated pipe elements',
        functions=[_calc_avg],
        unit=ureg.millimeter,
        dependant_instances='not_pump_elements'
    )

    @classmethod
    def find_matches(cls, graph) -> \
            [list, list]:
        """
        Find matches of Parallel pumps.

        Args:
            graph: element_graph that should be checked for Parallel pumps

        Returns:
            element_graphs:
                List of element_graphs that hold a Parallel pumps
            metas:
                List of dict with metas information. One element for each
                element_graph.

        Raises:
            None
        """
        element_graph = graph.element_graph
        wanted = {hvac.Pump}
        inerts = cls.aggregatable_elements - wanted
        parallels = HvacGraph.get_parallels(
            element_graph, wanted, inerts, grouping={'rated_power': 'equal'},
            grp_threshold=1)
        metas = [{} for x in parallels]  # no metadata calculated
        return parallels, metas


class AggregatedPipeFitting(HVACAggregationMixin, hvac.PipeFitting):
    """Aggregates PipeFittings. Used in two cases:
        - Merge multiple PipeFittings into one aggregates
        - Use a single PipeFitting and create a aggregated PipeFitting where
        some ports are aggregated (aggr_ports argument)
    """
    aggregatable_elements = {hvac.Pipe, hvac.PipeFitting, PipeStrand}
    threshold = None

    def __init__(self, element_graph, aggr_ports=None, *args, **kwargs):
        self.get_ports = partial(self.get_ports, aggr_ports)
        super().__init__(element_graph, *args, **kwargs)

    def get_ports(self, aggr_ports, graph):  # TBD
        ports = []
        edge_ports = self.get_edge_ports(graph)
        # create aggregation ports for all edge ports
        for edge_port in edge_ports:
            if aggr_ports:
                if edge_port not in aggr_ports:
                    ports.append(HVACAggregationPort(edge_port, parent=self))
            else:
                ports.append(HVACAggregationPort(edge_port, parent=self))
        # create combined aggregation port for all ports in aggr_ports
        if aggr_ports:
            ports.append(HVACAggregationPort(aggr_ports, parent=self))
        return ports

    @classmethod
    def get_edge_ports(cls, graph):
        edge_elements = [
            node for node in graph.nodes if len(node.ports) > 2]

        edge_ports = []
        # get all ports that are connected to outer elements
        for port in (p for e in edge_elements for p in e.ports):
            if not port.connection:
                continue  # end node
            if port.connection.parent not in graph.nodes:
                edge_ports.append(port)

        if len(edge_ports) < 2:
            raise AttributeError("Found less than two edge ports")

        return edge_ports

    @classmethod
    def find_matches(cls, graph) -> \
            [list, list]:
        """
        Find matches of ggregated pipe fitting.

        Args:
            graph: element_graph that should be checked for aggregated pipe
            fitting

        Returns:
            element_graphs:
                List of element_graphs that hold an aggregated pipe
            fitting
            metas:
                List of dict with metas information. One element for each
                element_graph.

        Raises:
            None
        """
        wanted = {elements.hvac.PipeFitting}
        innerts = cls.aggregatable_elements - wanted
        connected_fittings = HvacGraph.get_connections_between(
            graph, wanted, innerts)
        metas = [{} for x in connected_fittings]  # no metadata calculated
        return connected_fittings, metas


class ParallelSpaceHeater(HVACAggregationMixin, hvac.SpaceHeater):
    """Aggregates Space heater in parallel"""

    aggregatable_elements = {hvac.SpaceHeater, hvac.Pipe,
                             hvac.PipeFitting, PipeStrand}

    def get_ports(self, graph):
        return self._get_start_and_end_ports()

    @verify_edge_ports
    def _get_start_and_end_ports(self):
        """
        Finds external ports of aggregated group
        :return ports:
        """
        total_ports = {}
        # all possible beginning and end of the cycle (always pipe fittings), pumps counting
        for port in self.elements:
            if isinstance(port.parent, hvac.PipeFitting):
                if port.parent.guid in total_ports:
                    total_ports[port.parent.guid].append(port)
                else:
                    total_ports[port.parent.guid] = []
                    total_ports[port.parent.guid].append(port)
        # 2nd filter, beginning and end of the cycle (parallel check)
        final_ports = []
        for k, ele in total_ports.items():
            if ele[0].flow_direction == ele[1].flow_direction:
                # final_ports.append(ele[0].parent)
                final_ports.append(ele[0])
                final_ports.append(ele[1])

        agg_ports = []
        # first port
        for ele in final_ports[0].parent.ports:
            if ele not in final_ports:
                port = ele
                port.aggregated_parent = self
                agg_ports.append(port)
        # last port
        for ele in final_ports[-1].parent.ports:
            if ele not in final_ports:
                port = ele
                port.aggregated_parent = self
                agg_ports.append(port)
        return agg_ports

    @classmethod
    def get_edge_ports(cls, graph) -> List[HVACPort]:
        pass  # TODO

    @classmethod
    def find_matches(cls, graph: HvacGraph) \
            -> Tuple[List[nx.Graph], List[dict]]:
        pass  # TODO

    @attribute.multi_calc
    def _calc_avg(self):
        """Calculates the total length and average diameter of all not-pump-like
         elements."""
        avg_diameter_strand = 0
        total_length = 0
        diameter_times_length = 0

        for element in self.not_pump_elements:
            if hasattr(element, "diameter") and hasattr(element, "length"):
                length = element.length
                diameter = element.diameter
                if not (length and diameter):
                    logger.warning("Ignored '%s' in aggregation", element)
                    continue

                diameter_times_length += diameter * length
                total_length += length

            else:
                logger.warning("Ignored '%s' in aggregation", element)

        if total_length != 0:
            avg_diameter_strand = diameter_times_length / total_length

        result = dict(
            diameter_strand=avg_diameter_strand,
            length=total_length,
        )
        return result

    @cached_property
    def pump_elements(self) -> list:
        """list of pump-like elements present on the aggregation"""
        return [ele for ele in self.elements if isinstance(ele, hvac.Pump)]

    @cached_property
    def not_pump_elements(self) -> list:
        """list of not-pump-like elements present on the aggregation"""
        return [ele for ele in self.elements if not isinstance(ele, hvac.Pump)]

    def _calc_rated_power(self, name) -> ureg.Quantity:
        """Calculate the rated power adding the rated power of the pump-like
        elements"""
        return sum([ele.rated_power for ele in self.pump_elements])

    rated_power = attribute.Attribute(
        description="rated power",
        unit=ureg.kilowatt,
        functions=[_calc_rated_power],
        dependant_instances='pump_elements'
    )

    def _calc_rated_height(self, name) -> ureg.Quantity:
        """Calculate the rated height power, using the maximal rated height of
        the pump-like elements"""
        return max([ele.rated_height for ele in self.pump_elements])

    rated_height = attribute.Attribute(
        description="rated height",
        unit=ureg.meter,
        functions=[_calc_rated_height],
        dependant_instances='pump_elements'
    )

    def _calc_volume_flow(self, name) -> ureg.Quantity:
        """Calculate the volume flow, adding the volume flow of the pump-like
        elements"""
        return sum([ele.rated_volume_flow for ele in self.pump_elements])

    rated_volume_flow = attribute.Attribute(
        description="rated volume flow",
        unit=ureg.meter ** 3 / ureg.hour,
        functions=[_calc_volume_flow],
        dependant_instances='pump_elements'
    )

    def _calc_mass_flow(self, name) -> ureg.Quantity:
        """Calculate the mass flow, adding the mass flow of the pump-like
        elements"""
        return sum([ele.rated_mass_flow for ele in self.pump_elements])

    rated_mass_flow = attribute.Attribute(
        description="Rated mass flow of pump",
        unit=ureg.kg / ureg.s,
        functions=[_calc_mass_flow],
        dependant_instances='pump_elements'
    )

    def _calc_diameter(self, name) -> ureg.Quantity:
        """Calculate the diameter, using the pump-like elements diameter"""
        return sum(
            item.diameter ** 2 for item in self.pump_elements) ** 0.5

    diameter = attribute.Attribute(
        description="diameter",
        unit=ureg.millimeter,
        functions=[_calc_diameter],
        dependant_instances='pump_elements'
    )
    length = attribute.Attribute(
        description="length of aggregated pipe elements",
        unit=ureg.meter,
        functions=[_calc_avg],
        dependant_instances='not_pump_elements'
    )
    diameter_strand = attribute.Attribute(
        description="average diameter of aggregated pipe elements",
        functions=[_calc_avg],
        unit=ureg.millimeter,
        dependant_instances='not_pump_elements'
    )

    @classmethod
    def create_on_match(cls, cycle):  # TODO: obsolete, use find_matches
        """reduce the found cycles, to just the cycles that fulfill the next criteria:
            1. it's a parallel cycle (the two strands have the same flow direction)
            2. it has one or more pumps in each strand
            finally it creates a list with the founded cycles with the next lists:
            'elements', 'up_strand', 'low_strand', 'ports'
            """
        p_instance = "SpaceHeater"
        n_element = 0
        total_ports = {}
        new_cycle = {}
        # all possible beginning and end of the cycle (always pipe fittings), pumps counting
        for port in cycle:
            if isinstance(port.parent, getattr(elements, p_instance)):
                n_element += 1
            if isinstance(port.parent, hvac.PipeFitting):
                if port.parent.guid in total_ports:
                    total_ports[port.parent.guid].append(port)
                else:
                    total_ports[port.parent.guid] = []
                    total_ports[port.parent.guid].append(port)
        # 1st filter, cycle has more than 2 pump-ports, 1 pump
        if n_element >= 4:
            new_cycle["elements"] = list(
                dict.fromkeys([v.parent for v in cycle]))
        else:
            return
        # 2nd filter, beginning and end of the cycle (parallel check)
        final_ports = []
        for k, ele in total_ports.items():
            if ele[0].flow_direction == ele[1].flow_direction:
                final_ports.append(ele[0])
                final_ports.append(ele[1])
        if len(final_ports) < 4:
            return
        # Strand separation - upper & lower
        upper = []
        lower = []
        for elem in new_cycle["elements"]:
            if new_cycle["elements"].index(final_ports[1].parent) \
                    < new_cycle["elements"].index(elem) < new_cycle[
                "elements"].index(final_ports[2].parent):
                upper.append(elem)
            else:
                lower.append(elem)
        # 3rd Filter, each strand has one or more pumps
        check_up = str(dict.fromkeys(upper))
        check_low = str(dict.fromkeys(lower))

        instance = cls(cycle)
        instance._elements = new_cycle["elements"]
        instance._up_strand = upper
        instance._low_strand = lower

        if (p_instance in check_up) and (p_instance in check_low):
            return instance


class Consumer(HVACAggregationMixin, hvac.HVACProduct):
    """Aggregates Consumer system boarder"""
    multi = ('has_pump', 'rated_power', 'rated_pump_power', 'rated_height',
             'rated_volume_flow', 'temperature_inlet',
             'temperature_outlet', 'volume', 'description')

    aggregatable_elements = {
        hvac.SpaceHeater, hvac.Pipe,
        hvac.PipeFitting, hvac.Junction,
        hvac.Pump, hvac.Valve, hvac.ThreeWayValve,
        PipeStrand, ParallelSpaceHeater, UnderfloorHeating}
    whitelist = [hvac.SpaceHeater, ParallelSpaceHeater, UnderfloorHeating]
    blacklist = [hvac.Chiller, hvac.Boiler,
                 hvac.CoolingTower]

    @classmethod
    def get_edge_ports(cls, graph) -> List[HVACPort]:
        pass  # TODO

    @classmethod
    def find_matches(cls, graph: HvacGraph) \
            -> Tuple[List[nx.Graph], List[dict]]:
        """
        Find matches of consumer.

        Args:
            graph: element_graph that should be checked for consumer
            fitting

        Returns:
            element_graphs:
                List of element_graphs that hold a consumer
            metas:
                List of dict with metas information. One element for each
                element_graph.

        Raises:
            None
        """
        boarder_class = {hvac.Distributor}
        # innerts = set(cls.aggregatable_elements) - wanted

        boarder_class = set(boarder_class)

        element_graph = graph.element_graph
        _element_graph = element_graph.copy()

        # remove blocking nodes
        remove = {node for node in _element_graph.nodes if
                  node.__class__ in boarder_class}
        _element_graph.remove_nodes_from(remove)

        # identify outer connections
        remove_ports = [port for ele in remove for port in ele.ports]
        outer_connections = {}
        for port in remove_ports:
            outer_connections.update(
                {neighbor.parent: (port, neighbor) for neighbor in
                 graph.neighbors(port) if
                 neighbor not in remove_ports})

        sub_graphs = nx.connected_components(
            _element_graph)  # get_parallels(graph, wanted, innerts)

        consumer_cycles = []
        metas = []
        generator_cycles = []

        for sub in sub_graphs:
            # check for generator in sub_graphs
            generator = {node for node in sub if
                         node.__class__ in cls.blacklist}
            if generator:
                # check for consumer in generator subgraph
                gen_con = {node for node in sub if
                           node.__class__ in cls.whitelist}
                if gen_con:
                    # ToDO: Consumer separieren
                    a = 1
                    pass
                else:
                    pass
                    # pure generator subgraph
                    # subgraph = graph.subgraph(sub)
                    # generator_cycles.append(subgraph)
            else:
                consumer_cycle = {node for node in sub if
                                  node.__class__ in cls.whitelist}
                if consumer_cycle:
                    subgraph = _element_graph.subgraph(sub)
                    outer_con = [outer_connections[ele][1] for ele in sub if
                                 ele in outer_connections]
                    consumer_cycles.append(subgraph)
                    metas.append({'outer_connections': outer_con})

        return consumer_cycles, metas

    @attribute.multi_calc
    def _calc_avg_pump(self):
        """Calculates the parameters of all pump-like elements."""
        volume = None

        for ele in self.not_pump_elements:
            if hasattr(ele, "length"):  # ToDO: Parallel?
                length = ele.length
                if not (length):
                    logger.warning("Ignored '%s' in aggregation", ele)
                    continue

            else:
                logger.warning("Ignored '%s' in aggregation", ele)

        #  Volumen zusammenrechnen
        volume = 1

        result = dict(
            volume=volume
        )
        return result

    @cached_property
    def pump_elements(self) -> list:
        """list of pump-like elements present on the aggregation"""
        return [ele for ele in self.elements if isinstance(ele, hvac.Pump)]

    @cached_property
    def not_pump_elements(self) -> list:
        """list of not-pump-like elements present on the aggregation"""
        return [ele for ele in self.elements if not isinstance(ele, hvac.Pump)]

    def _calc_TControl(self, name):
        return True  # ToDo: Look at Boiler Aggregation - David

    @cached_property
    def whitelist_elements(self) -> list:
        """list of whitelist elements present on the aggregation"""
        return [ele for ele in self.elements if type(ele) in self.whitelist]

    def _calc_rated_power(self, name) -> ureg.Quantity:
        """Calculate the rated power adding the rated power of the whitelist
        elements"""
        return sum([ele.rated_power for ele in self.whitelist_elements])

    rated_power = attribute.Attribute(
        description="rated power",
        unit=ureg.kilowatt,
        functions=[_calc_rated_power],
        dependant_instances='whitelist_elements'
    )

    has_pump = attribute.Attribute(
        description="Cycle has a pumpsystem",
        functions=[HVACAggregationMixin._calc_has_pump]
    )

    def _calc_rated_pump_power(self, name) -> ureg.Quantity:
        """Calculate the rated pump power adding the rated power of the
        pump-like elements"""
        return sum([ele.rated_power for ele in self.pump_elements])

    rated_pump_power = attribute.Attribute(
        description="rated pump power",
        unit=ureg.kilowatt,
        functions=[_calc_rated_pump_power],
        dependant_instances='pump_elements'
    )

    def _calc_volume_flow(self, name) -> ureg.Quantity:
        """Calculate the volume flow, adding the volume flow of the pump-like
        elements"""
        return sum([ele.rated_volume_flow for ele in self.pump_elements])

    rated_volume_flow = attribute.Attribute(
        description="rated volume flow",
        unit=ureg.meter ** 3 / ureg.hour,
        functions=[_calc_volume_flow],
        dependant_instances='pump_elements'
    )

    def _calc_flow_temperature(self, name) -> ureg.Quantity:
        """Calculate the flow temperature, using the flow temperature of the
        whitelist elements"""
        return sum(ele.flow_temperature.to_base_units() for ele
                   in self.whitelist_elements) / len(self.whitelist_elements)

    flow_temperature = attribute.Attribute(
        description="temperature inlet",
        unit=ureg.kelvin,
        functions=[_calc_flow_temperature],
        dependant_instances='whitelist_elements'
    )

    def _calc_return_temperature(self, name) -> ureg.Quantity:
        """Calculate the return temperature, using the return temperature of the
        whitelist elements"""
        return sum(ele.return_temperature.to_base_units() for ele
                   in self.whitelist_elements) / len(self.whitelist_elements)

    return_temperature = attribute.Attribute(
        description="temperature outlet",
        unit=ureg.kelvin,
        functions=[_calc_return_temperature],
        dependant_instances='whitelist_elements'
    )

    def _calc_dT_water(self, name):
        """water dt of consumer"""
        return self.flow_temperature - self.return_temperature

    dT_water = attribute.Attribute(
        description="Nominal temperature difference",
        unit=ureg.kelvin,
        functions=[_calc_dT_water],
        dependant_attributes=['return_temperature', 'flow_temperature']
    )

    def _calc_body_mass(self, name):
        """heat capacity of consumer"""
        return sum(ele.body_mass for ele in self.whitelist_elements)

    body_mass = attribute.Attribute(
        description="Body mass of Consumer",
        functions=[_calc_body_mass],
        unit=ureg.kg,
    )

    def _calc_heat_capacity(self, name):
        """heat capacity of consumer"""
        return sum(ele.heat_capacity * ele.body_mass for ele in
                   self.whitelist_elements) / self.body_mass

    heat_capacity = attribute.Attribute(
        description="Heat capacity of Consumer",
        functions=[_calc_heat_capacity],
        unit=ureg.joule / ureg.kelvin,
    )

    def _calc_demand_type(self, name):
        """demand type of consumer"""
        return 1 if self.dT_water > 0 else -1

    demand_type = attribute.Attribute(
        description="Type of demand if 1 - heating, if -1 - cooling",
        functions=[_calc_demand_type],
        dependant_attributes=['dT_water']
    )

    volume = attribute.Attribute(
        description="volume",
        unit=ureg.meter ** 3,
        # functions=[_calc_avg_pump]
    )

    def _calc_rated_height(self, name) -> ureg.Quantity:
        """Calculate the rated height power, using the maximal rated height of
        the pump-like elements"""
        return max([ele.rated_height for ele in self.pump_elements])

    rated_height = attribute.Attribute(
        description="rated volume flow",
        unit=ureg.meter,
        functions=[_calc_rated_height],
        dependant_instances='pump_elements'
    )

    def _calc_description(self, name) -> str:
        """Obtains the aggregation description using the whitelist elements"""
        con_types = {}
        for ele in self.whitelist_elements:
            if type(ele) not in con_types:
                con_types[type(ele)] = 0
            con_types[type(ele)] += 1

        return ', '.join(['{1} x {0}'.format(k.__name__, v) for k, v
                          in con_types.items()])

    description = attribute.Attribute(
        description="String with number of Consumers",
        functions=[_calc_description],
        dependant_instances='whitelist_elements'
    )

    t_controll = attribute.Attribute(
        description="Bool for temperature controll cycle.",
        functions=[_calc_TControl]
    )


class ConsumerHeatingDistributorModule(HVACAggregationMixin,
                                       hvac.HVACProduct):  # ToDo: Export Aggregation HKESim
    """Aggregates Consumer system boarder"""
    multi = (
        'medium', 'use_hydraulic_separator', 'hydraulic_separator_volume',
        'temperature_inlet', 'temperature_outlet')
    # ToDo: Abused to not just sum attributes from elements

    aggregatable_elements = {hvac.SpaceHeater, hvac.Pipe, hvac.PipeFitting, hvac.Distributor, PipeStrand,
                             ParallelSpaceHeater, Consumer}
    whitelist = [hvac.SpaceHeater, ParallelSpaceHeater, UnderfloorHeating, Consumer]
    blacklist = [hvac.Chiller, hvac.Boiler, hvac.CoolingTower]

    def __init__(self, element_graph, *args, **kwargs):
        self.undefined_consumer_ports = kwargs.pop('undefined_consumer_ports',
                                                   None)  # TODO: Richtig sO? WORKAROUND
        self._consumer_cycles = kwargs.pop('consumer_cycles', None)
        self.consumers = []
        for consumer in self._consumer_cycles:
            for con in consumer:  # ToDo: darf nur ein Consumer sein
                self.consumers.append(con)
        self.open_consumer_pairs = self._register_open_consumerports()

        super().__init__(element_graph, *args, **kwargs)

    def get_ports(self, graph) -> List[HVACPort]:
        ports = super().get_ports(graph)
        for con_ports in self.open_consumer_pairs:
            ports.append(HVACAggregationPort(con_ports[0], parent=self))
            ports.append(HVACAggregationPort(con_ports[1], parent=self))
        return ports

    @classmethod
    def get_edge_ports(cls, graph) -> List[HVACPort]:
        pass  # TODO

    def _register_open_consumerports(self):

        consumer_ports = []
        if (len(self.undefined_consumer_ports) % 2) == 0:
            for i in range(0, int(len(self.undefined_consumer_ports) / 2)):
                consumer_ports.append(
                    (self.undefined_consumer_ports[2 * i][0],
                     self.undefined_consumer_ports[2 * i + 1][0]))
        else:
            raise NotImplementedError(
                "Odd Number of loose ends at the distributor.")
        return consumer_ports

    @classmethod
    def find_matches(cls, graph) -> [list, list]:
        """
        Find matches of consumer heating distributor module.

        Args:
            graph: element_graph that should be checked for consumer heating
            distributor module.

        Returns:
            element_graphs:
                List of element_graphs that hold a consumer heating distributor
                module
            metas:
                List of dict with metas information. One element for each
                element_graph.

        Raises:
            None
        """
        boarder_class = {hvac.Distributor}
        element_graph = graph.element_graph
        results = []
        remove = {node for node in element_graph.nodes
                  if type(node) in boarder_class}
        metas = []
        for dist in remove:
            _element_graph = element_graph.copy()
            consumer_cycles = []
            # remove blocking nodes
            _element_graph.remove_nodes_from({dist})
            # identify outer connections
            remove_ports = dist.ports
            outer_connections = {}
            metas.append({'outer_connections': [],
                          'undefined_consumer_ports': [],
                          'consumer_cycles': []})

            for port in remove_ports:
                outer_connections.update(
                    {neighbor.parent: (port, neighbor) for neighbor in
                     graph.neighbors(port) if
                     neighbor not in remove_ports})

            sub_graphs = nx.connected_components(
                _element_graph)  # get_parallels(graph, wanted, innerts)

            for sub in sub_graphs:
                # check for generator in sub_graphs
                generator = {node for node in sub if
                             node.__class__ in cls.blacklist}
                if generator:
                    # check for consumer in generator subgraph
                    gen_con = {node for node in sub if
                               node.__class__ in cls.whitelist}
                    if gen_con:
                        # ToDO: Consumer separieren
                        pass
                    else:
                        outer_con = [outer_connections[ele][1] for ele in sub if
                                     ele in outer_connections]
                        if outer_con:
                            metas[-1]['outer_connections'].extend(outer_con)
                        # pure generator subgraph
                        # subgraph = graph.subgraph(sub)
                        # generator_cycles.append(subgraph)
                else:
                    consumer_cycle = {node for node in sub if
                                      node.__class__ in cls.whitelist}
                    if consumer_cycle:
                        subgraph = _element_graph.subgraph(sub)
                        consumer_cycles.extend(subgraph.nodes)
                        metas[-1]['consumer_cycles'].append(subgraph.nodes)
                    else:
                        outer_con = [outer_connections[ele] for ele in sub if
                                     ele in outer_connections]
                        if outer_con:
                            metas[-1]['undefined_consumer_ports'].extend(
                                outer_con)

            subnodes = [dist, *consumer_cycles]

            result = element_graph.subgraph(subnodes)
            results.append(result)

        return results, metas

    @attribute.multi_calc
    def _calc_avg(self):
        result = dict(
            medium=None,
            use_hydraulic_separator=False,
            hydraulic_separator_volume=1,
        )
        return result

    medium = attribute.Attribute(
        description="Medium of the DestributerCycle",
        functions=[_calc_avg]
    )

    @cached_property
    def whitelist_elements(self) -> list:
        """list of whitelist elements present on the aggregation"""
        return [ele for ele in self.elements if type(ele) in self.whitelist]

    def _calc_flow_temperature(self, name) -> list:
        """Calculate the flow temperature, using the flow temperature of the
        whitelist elements"""
        return [ele.flow_temperature.to_base_units() for ele
                in self.whitelist_elements]

    flow_temperature = attribute.Attribute(
        description="temperature inlet",
        unit=ureg.kelvin,
        functions=[_calc_flow_temperature],
        dependant_instances='whitelist_elements'
    )

    def _calc_return_temperature(self, name) -> list:
        """Calculate the return temperature, using the return temperature of the
        whitelist elements"""
        return [ele.return_temperature.to_base_units() for ele
                in self.whitelist_elements]

    return_temperature = attribute.Attribute(
        description="temperature outlet",
        unit=ureg.kelvin,
        functions=[_calc_return_temperature],
        dependant_instances='whitelist_elements'
    )

    def _calc_dT_water(self, name):
        """water dt of consumer"""
        return [ele.dT_water.to_base_units() for ele
                in self.whitelist_elements]

    dT_water = attribute.Attribute(
        description="Nominal temperature difference",
        unit=ureg.kelvin,
        functions=[_calc_dT_water],
        dependant_instances='whitelist_elements'
    )

    def _calc_body_mass(self, name):
        """heat capacity of consumer"""
        return [ele.body_mass for ele in self.whitelist_elements]

    body_mass = attribute.Attribute(
        description="Body mass of Consumer",
        functions=[_calc_body_mass],
        unit=ureg.kg,
    )

    def _calc_heat_capacity(self, name):
        """heat capacity of consumer"""
        return [ele.heat_capacity for ele in self.whitelist_elements]

    heat_capacity = attribute.Attribute(
        description="Heat capacity of Consumer",
        functions=[_calc_heat_capacity],
        unit=ureg.joule / ureg.kelvin,
    )

    def _calc_demand_type(self, name):
        """demand type of consumer"""
        return [ele.demand_type for ele in self.whitelist_elements]

    demand_type = attribute.Attribute(
        description="Type of demand if 1 - heating, if -1 - cooling",
        functions=[_calc_demand_type],
        dependant_instances='whitelist_elements'
    )

    def calc_mass_flow(self, name):
        """Returns the mass flow, in the form of a list with the mass flow of
        the whitelist-like elements"""
        return [ele.rated_mass_flow for ele in self.whitelist_elements]

    rated_mass_flow = attribute.Attribute(
        description="rated mass flow",
        functions=[calc_mass_flow],
        unit=ureg.kg / ureg.s,
        dependant_instances='whitelist_elements'
    )

    use_hydraulic_separator = attribute.Attribute(
        description="boolean if there is a hdydraulic seperator",
        functions=[_calc_avg]
    )

    hydraulic_separator_volume = attribute.Attribute(
        description="Volume of the hdydraulic seperator",
        functions=[_calc_avg],
        unit=ureg.m ** 3,
    )

    def _calc_rated_power(self, name):
        """Returns the rated power, as a list of the rated power of the
        whitelist_elements elements"""
        return [ele.rated_power for ele in self.whitelist_elements]

    rated_power = attribute.Attribute(
        description="Rated heating power of all consumers",
        unit=ureg.kilowatt,
        functions=[_calc_rated_power],
        dependant_instances='whitelist_elements'
    )


class AggregatedThermalZone(AggregationMixin, bps.ThermalZone):
    """Aggregates thermal zones"""
    aggregatable_elements = {bps.ThermalZone}

    def __init__(self, elements, *args, **kwargs):
        super().__init__(elements, *args, **kwargs)
        # self.get_disaggregation_properties()
        self.bound_elements = self.bind_elements()
        self.storeys = self.bind_storeys()
        self.description = ''
        # todo lump usage conditions of existing zones

    def bind_elements(self):
        """elements binder for the resultant thermal zone"""
        bound_elements = []
        for tz in self.elements:
            for inst in tz.bound_elements:
                if inst not in bound_elements:
                    bound_elements.append(inst)
        return bound_elements

    def bind_storeys(self):
        storeys = []
        for tz in self.elements:
            for storey in tz.storeys:
                if storey not in storeys:
                    storeys.append(storey)
                if self not in storey.thermal_zones:
                    storey.thermal_zones.append(self)
                if tz in storey.thermal_zones:
                    storey.thermal_zones.remove(tz)
        return storeys

    @classmethod
    def find_matches(cls, groups, instances, finder):
        """creates a new thermal zone aggregation instance
         based on a previous filtering"""
        new_aggregations = []
        thermal_zones = filter_instances(instances, 'ThermalZone')
        total_area = sum(i.gross_area for i in thermal_zones)
        for group, group_elements in groups.items():
            if group == 'one_zone_building':
                name = "Aggregated_%s" % group
                cls.create_aggregated_tz(name, group, group_elements, finder,
                                         new_aggregations, instances)
            elif group == 'not_bind':
                # last criterion no similarities
                area = sum(i.gross_area for i in groups[group])
                if area / total_area <= 0.05:
                    # Todo: usage and conditions criterion
                    name = "Aggregated_not_neighbors"
                    cls.create_aggregated_tz(name, group, group_elements,
                                             finder, new_aggregations,
                                             instances)
            else:
                # first criterion based on similarities
                # todo reuse this if needed but currently it doesn't seem so
                # group_name = re.sub('[\'\[\]]', '', group)
                group_name = group
                name = "Aggregated_%s" % group_name.replace(', ', '_')
                cls.create_aggregated_tz(name, group, group_elements, finder,
                                         new_aggregations, instances)
        return new_aggregations

    @classmethod
    def create_aggregated_tz(cls, name, group, group_elements, finder,
                             new_aggregations, instances):
        instance = cls(group_elements, finder=finder)
        instance.name = name
        instance.description = group
        new_aggregations.append(instance)
        for tz in instance.elements:
            if tz.guid in instances:
                del instances[tz.guid]
        instances[instance.guid] = instance

    def _calc_net_volume(self, name) -> ureg.Quantity:
        """Calculate the thermal zone net volume"""
        return sum(tz.net_volume for tz in self.elements if
                   tz.net_volume is not None)

    net_volume = attribute.Attribute(
        functions=[_calc_net_volume],
        unit=ureg.meter ** 3,
        dependant_instances='elements'
    )

    def _intensive_calc(self, name) -> ureg.Quantity:
        """intensive properties getter - volumetric mean
        intensive_attributes = ['t_set_heat', 't_set_cool', 'height',  'AreaPerOccupant', 'typical_length',
        'typical_width', 'T_threshold_heating', 'activity_degree_persons', 'fixed_heat_flow_rate_persons',
        'internal_gains_moisture_no_people', 'T_threshold_cooling', 'ratio_conv_rad_persons', 'machines',
        'ratio_conv_rad_machines', 'lighting_power', 'ratio_conv_rad_lighting', 'infiltration_rate',
        'max_user_infiltration', 'min_ahu', 'max_ahu', 'persons']"""
        prop_sum = sum(
            getattr(tz, name) * tz.net_volume for tz in self.elements if
            getattr(tz, name) is not None and tz.net_volume is not None)
        return prop_sum / self.net_volume

    def _intensive_list_calc(self, name) -> list:
        """intensive list properties getter - volumetric mean
        intensive_list_attributes = ['heating_profile', 'cooling_profile', 'persons_profile', 'machines_profile',
         'lighting_profile', 'max_overheating_infiltration', 'max_summer_infiltration',
         'winter_reduction_infiltration']"""
        list_attrs = {'heating_profile': 24, 'cooling_profile': 24,
                      'persons_profile': 24,
                      'machines_profile': 24, 'lighting_profile': 24,
                      'max_overheating_infiltration': 2,
                      'max_summer_infiltration': 3,
                      'winter_reduction_infiltration': 3}
        length = list_attrs[name]
        aux = []
        for x in range(0, length):
            aux.append(sum(
                getattr(tz, name)[x] * tz.net_volume for tz in self.elements
                if getattr(tz, name) is not None and tz.net_volume is not None)
                       / self.net_volume)
        return aux

    def _extensive_calc(self, name) -> ureg.Quantity:
        """extensive properties getter
        intensive_attributes = ['gross_area', 'net_area', 'volume']"""
        return sum(getattr(tz, name) for tz in self.elements if
                   getattr(tz, name) is not None)

    def _bool_calc(self, name) -> bool:
        """bool properties getter
        bool_attributes = ['with_cooling', 'with_heating', 'with_ahu']"""
        # todo: log
        prop_bool = False
        for tz in self.elements:
            prop = getattr(tz, name)
            if prop is not None:
                if prop:
                    prop_bool = True
                    break
        return prop_bool

    def _get_tz_usage(self, name) -> str:
        """usage properties getter"""
        return self.elements[0].usage

    usage = attribute.Attribute(
        functions=[_get_tz_usage],
    )
    # t_set_heat = attribute.Attribute(
    #     functions=[_intensive_calc],
    #     unit=ureg.degC
    # )
    # todo refactor this to remove redundancy for units
    t_set_heat = bps.ThermalZone.t_set_heat.to_aggregation(_intensive_calc)

    t_set_cool = attribute.Attribute(
        functions=[_intensive_calc],
        unit=ureg.degC,
        dependant_instances='elements'
    )
    t_ground = attribute.Attribute(
        functions=[_intensive_calc],
        unit=ureg.degC,
        dependant_instances='elements'
    )
    net_area = attribute.Attribute(
        functions=[_extensive_calc],
        unit=ureg.meter ** 2,
        dependant_instances='elements'
    )
    gross_area = attribute.Attribute(
        functions=[_extensive_calc],
        unit=ureg.meter ** 2,
        dependant_instances='elements'
    )
    gross_volume = attribute.Attribute(
        functions=[_extensive_calc],
        unit=ureg.meter ** 3,
        dependant_instances='elements'
    )
    height = attribute.Attribute(
        functions=[_intensive_calc],
        unit=ureg.meter,
        dependant_instances='elements'
    )
    AreaPerOccupant = attribute.Attribute(
        functions=[_intensive_calc],
        unit=ureg.meter ** 2,
        dependant_instances='elements'
    )
    # use conditions
    with_cooling = attribute.Attribute(
        functions=[_bool_calc],
        dependant_instances='elements'
    )
    with_heating = attribute.Attribute(
        functions=[_bool_calc],
        dependant_instances='elements'
    )
    with_ahu = attribute.Attribute(
        functions=[_bool_calc],
        dependant_instances='elements'
    )
    heating_profile = attribute.Attribute(
        functions=[_intensive_list_calc],
        dependant_instances='elements'
    )
    cooling_profile = attribute.Attribute(
        functions=[_intensive_list_calc],
        dependant_instances='elements'
    )
    persons = attribute.Attribute(
        functions=[_intensive_calc],
        dependant_instances='elements'
    )
    typical_length = attribute.Attribute(
        functions=[_intensive_calc],
        dependant_instances='elements'
    )
    typical_width = attribute.Attribute(
        functions=[_intensive_calc],
        dependant_instances='elements'
    )
    T_threshold_heating = attribute.Attribute(
        functions=[_intensive_calc],
        dependant_instances='elements'
    )
    activity_degree_persons = attribute.Attribute(
        functions=[_intensive_calc],
        dependant_instances='elements'
    )
    fixed_heat_flow_rate_persons = attribute.Attribute(
        functions=[_intensive_calc],
        dependant_instances='elements'
    )
    internal_gains_moisture_no_people = attribute.Attribute(
        functions=[_intensive_calc],
        dependant_instances='elements'
    )
    T_threshold_cooling = attribute.Attribute(
        functions=[_intensive_calc],
        dependant_instances='elements'
    )
    ratio_conv_rad_persons = attribute.Attribute(
        functions=[_intensive_calc],
        dependant_instances='elements'
    )
    machines = attribute.Attribute(
        functions=[_intensive_calc],
        dependant_instances='elements'
    )
    ratio_conv_rad_machines = attribute.Attribute(
        functions=[_intensive_calc],
        dependant_instances='elements'
    )
    lighting_power = attribute.Attribute(
        functions=[_intensive_calc],
        dependant_instances='elements'
    )
    ratio_conv_rad_lighting = attribute.Attribute(
        functions=[_intensive_calc],
        dependant_instances='elements'
    )
    use_constant_infiltration = attribute.Attribute(
        functions=[_bool_calc],
        dependant_instances='elements'
    )
    infiltration_rate = attribute.Attribute(
        functions=[_intensive_calc],
        dependant_instances='elements'
    )
    max_user_infiltration = attribute.Attribute(
        functions=[_intensive_calc],
        dependant_instances='elements'
    )
    max_overheating_infiltration = attribute.Attribute(
        functions=[_intensive_list_calc],
        dependant_instances='elements'
    )
    max_summer_infiltration = attribute.Attribute(
        functions=[_intensive_list_calc],
        dependant_instances='elements'
    )
    winter_reduction_infiltration = attribute.Attribute(
        functions=[_intensive_list_calc],
        dependant_instances='elements'
    )
    min_ahu = attribute.Attribute(
        functions=[_intensive_calc],
        dependant_instances='elements'
    )
    max_ahu = attribute.Attribute(
        functions=[_intensive_calc],
        dependant_instances='elements'
    )
    with_ideal_thresholds = attribute.Attribute(
        functions=[_bool_calc],
        dependant_instances='elements'
    )
    persons_profile = attribute.Attribute(
        functions=[_intensive_list_calc],
        dependant_instances='elements'
    )
    machines_profile = attribute.Attribute(
        functions=[_intensive_list_calc],
        dependant_instances='elements'
    )
    lighting_profile = attribute.Attribute(
        functions=[_intensive_list_calc],
        dependant_instances='elements'
    )


class GeneratorOneFluid(HVACAggregationMixin, hvac.HVACProduct):
    """Aggregates generator modules with only one fluid cycle (CHPs, Boilers,
    ...) Not for Chillers or Heatpumps!"""
    aggregatable_elements = {
        hvac.Pump, PipeStrand, hvac.Pipe, hvac.PipeFitting, hvac.Distributor,
        hvac.Boiler, ParallelPump, hvac.Valve, hvac.Storage,
        ConsumerHeatingDistributorModule, Consumer}
    wanted_elements = [hvac.Boiler, hvac.CHP]
    boarder_elements = [hvac.Distributor, ConsumerHeatingDistributorModule]
    multi = ('rated_power', 'has_bypass', 'rated_height', 'volume',
             'rated_volume_flow', 'rated_pump_power', 'has_pump')

    def __init__(self, element_graph, *args, **kwargs):
        self.non_relevant = kwargs.pop('non_relevant', set())  # todo workaround
        self.has_parallel = kwargs.pop('has_parallel', False)
        self.bypass_elements = kwargs.pop('bypass_elements', set())
        self.has_bypass = False
        if self.bypass_elements:
            self.has_bypass = True
        super().__init__(element_graph, *args, **kwargs)

    @classmethod
    def find_matches(cls, graph: {HvacGraph.element_graph}) -> \
            [HvacGraph.element_graph, list]:
        """
        Finds matches of generators with one fluid.

        Non relevant elements like bypasses are added to metas information to
        delete later.

        Args:
            graph: element_graph that should be checked for one fluid generators

        Returns:
            generator_cycles:
                List of element_graphs that hold a generator cycle including the
                distributor.
            metas:
                List of dict with metas information. One element for each
                element_graph. In this case it holds non_relevant nodes, which
                have to be deleted later but are not contained in the **resulting graph?** #todo
                element_graph. Because we are currently not able to distinguish
                to which graph these non_relevant nodes belong, we just output
                the complete list of non relevant nodes for every element_graph.

        Raises:
            None
        """
        element_graph = graph.element_graph
        wanted = set(cls.wanted_elements)
        boarders = set(cls.boarder_elements)
        inerts = set(cls.aggregatable_elements) - wanted
        _graph = HvacGraph.remove_not_wanted_nodes(element_graph, wanted,
                                                   inerts)
        dict_all_cycles_wanted = HvacGraph.get_all_cycles_with_wanted(_graph,
                                                                      wanted)
        list_all_cycles_wanted = [*dict_all_cycles_wanted.values()]

        # create flat lists to substract for non relevant
        generator_flat = set()
        wanted_flat = set()

        # check for generation cycles
        generator_cycles = []
        for cycles_list in list_all_cycles_wanted:
            generator_cycle = list(
                nx.subgraph(_graph, cycle) for cycle in cycles_list
                if any(type(node) == block for block in
                       boarders for node in cycle))
            if generator_cycle:
                generator_cycles.extend(generator_cycle)
                generator_flat.update(generator_cycle[0].nodes)
                wanted_flat.update(
                    [item for sublist in cycles_list for item in sublist])

        cleaned_generator_cycles = []
        metas = []
        if generator_flat:
            non_relevant = wanted_flat - generator_flat

            # Remove overlapping Elements in GeneratorCycles
            for gen_cycle in generator_cycles:
                pseudo_lst = gen_cycle.copy()
                for gen_cycle_two in generator_cycles:
                    if gen_cycle == gen_cycle_two:
                        continue
                    pseudo_lst.remove_nodes_from(gen_cycle_two)
                cleaned_generator_cycles.append(pseudo_lst)
            _graph = graph.copy()

            # get outer_connections
            for i, cycle in enumerate(cleaned_generator_cycles):
                metas.append(dict())
                metas[i]['outer_connections'] = []
                boarder_nodes = []
                for node in cycle:
                    for block in boarders:
                        if type(node) == block:
                            boarder_nodes.append(node)
                if len(boarder_nodes) > 1:
                    raise NotImplementedError(
                        "Generator cycles should only have one boarder")
                HvacGraph.remove_nodes_from(cycle, boarder_nodes)

                outer_elements = [v for v, d in cycle.degree() if d == 1]
                for outer_element in outer_elements:
                    for port in outer_element.ports:
                        if port in graph:
                            neighbor_ports = [neighbor_port for neighbor_port in
                                              graph.neighbors(port)]
                            for neighbor_port in neighbor_ports:
                                if neighbor_port.parent not in list(
                                        cycle.nodes):
                                    print(neighbor_port.parent)

                                    metas[i]['outer_connections'].append(port)

            # match bypass elements from non relevant elements
            for i in range(len(cleaned_generator_cycles)):
                metas[i]['bypass_elements'] = []
                for cycle in list_all_cycles_wanted[i]:
                    if len(cycle - cleaned_generator_cycles[
                        i].nodes - non_relevant) > 0:
                        continue
                    bypass_elements = cycle - cleaned_generator_cycles[i].nodes
                    cleaned_generator_cycles[i].add_nodes_from(bypass_elements)
                    non_relevant.difference_update(bypass_elements)
                    metas[i]['bypass_elements'].append(bypass_elements)

            if len(metas) > 0:
                metas[0]['non_relevant'] = non_relevant
        return cleaned_generator_cycles, metas

    @attribute.multi_calc
    def _calc_avg(self):
        """Calculates the parameters of all the below listed elements."""
        avg_diameter_strand = 0
        total_length = 0
        diameter_times_length = 0

        for element in self.not_whitelist_elements:
            if hasattr(element, "diameter") and hasattr(element, "length"):
                length = element.length
                diameter = element.diameter
                if not (length and diameter):
                    logger.info("Ignored '%s' in aggregation", item)
                    continue

                diameter_times_length += diameter * length
                total_length += length

            else:
                logger.info("Ignored '%s' in aggregation", item)

        if total_length != 0:
            avg_diameter_strand = diameter_times_length / total_length

        result = dict(
            length=total_length,
            diameter_strand=avg_diameter_strand
        )
        return result

    @attribute.multi_calc
    def _calc_has_bypass(self):
        decision = BoolDecision(
            "Does the generator %s has a bypass?" % self.name,
            global_key=self.guid + '.bypass',
            allow_save=True,
            allow_load=True,
            related=[element.guid for element in self.elements], )
        has_bypass = decision.decide()
        print(has_bypass)
        return dict(has_bypass=has_bypass)

    @classmethod
    def find_bypasses(cls, graph):
        """Finds bypasses based on the graphical network.
        Currently not used, might be removed in the future."""
        # todo remove if discussed
        wanted = set(cls.wanted_elements)
        boarders = set(cls.boarder_elements)
        inerts = set(cls.aggregatable_elements) - wanted
        bypass_nodes = HvacGraph.detect_bypasses_to_wanted(
            graph, wanted, inerts, boarders)
        return bypass_nodes

    def _calc_has_bypass_decision(self):
        """Checks if bypass exists based on decision. Currently not used as
        only possible with workaround. See todo documentation"""
        # todo remove if discussed, see #184
        # todo more elegant way? Problem is that cant yield from attributes
        #  or cached propertys @earnsdev. Maybe using
        #  get_pending_attribute_decisions() in combination with request?
        decisions = DecisionBunch()
        cur_decision = BoolDecision(
            "Does the generator %s has a bypass?" % self.guid,
            key=self,
            global_key=self.guid + '.bypass',
            related=[element.guid for element in self.elements], )
        decisions.append(cur_decision)
        yield decisions
        answers = decisions.to_answer_dict()
        has_bypass = list(answers.values())[0]
        self.has_bypass = has_bypass
        return has_bypass

    @cached_property
    def whitelist_elements(self) -> list:
        """list of whitelist elements present on the aggregation"""
        return [ele for ele in self.elements if type(ele)
                in self.wanted_elements]

    @cached_property
    def not_whitelist_elements(self) -> list:
        """list of not-whitelist elements present on the aggregation"""
        return [ele for ele in self.elements if type(ele) not
                in self.wanted_elements]

    def _calc_rated_power(self, name) -> ureg.Quantity:
        """Calculate the rated power adding the rated power of the whitelist
        elements"""
        return sum([ele.rated_power for ele in self.whitelist_elements])

    rated_power = attribute.Attribute(
        unit=ureg.kilowatt,
        description="rated power",
        functions=[_calc_rated_power],
        dependant_instances='whitelist_elements'
    )

    def _calc_min_power(self, name):
        """Calculates the min power, adding the min power of
        the whitelist_elements"""
        return sum([ele.min_power for ele in self.whitelist_elements])

    min_power = attribute.Attribute(
        unit=ureg.kilowatt,
        description="min power",
        functions=[_calc_min_power],
        dependant_instances='whitelist_elements'
    )

    def _calc_min_PLR(self, name):
        """Calculates the min PLR, using the min power and rated power"""
        return self.min_power/self.rated_power

    min_PLR = attribute.Attribute(
        description="Minimum part load ratio",
        unit=ureg.dimensionless,
        functions=[_calc_min_PLR],
        dependant_attributes=['min_power', 'rated_power']
    )

    def _calc_flow_temperature(self, name) -> ureg.Quantity:
        """Calculate the flow temperature, using the flow temperature of the
        whitelist elements"""
        return sum(ele.flow_temperature.to_base_units() for ele
                   in self.whitelist_elements)/len(self.whitelist_elements)

    flow_temperature = attribute.Attribute(
        description="Nominal inlet temperature",
        unit=ureg.kelvin,
        functions=[_calc_flow_temperature],
        dependant_instances='whitelist_elements'
    )

    def _calc_return_temperature(self, name) -> ureg.Quantity:
        """Calculate the return temperature, using the return temperature of the
        whitelist elements"""
        return sum(ele.return_temperature.to_base_units() for ele
                   in self.whitelist_elements)/len(self.whitelist_elements)

    return_temperature = attribute.Attribute(
        description="Nominal outlet temperature",
        unit=ureg.kelvin,
        functions=[_calc_return_temperature],
        dependant_instances='whitelist_elements'
    )

    def _calc_dT_water(self, name):
        """Rated power of boiler"""
        return self.return_temperature - self.flow_temperature

    dT_water = attribute.Attribute(
        description="Nominal temperature difference",
        unit=ureg.kelvin,
        functions=[_calc_dT_water],
        dependant_attributes=['return_temperature', 'flow_temperature']
    )

    def _calc_diameter(self, name) -> ureg.Quantity:
        """Calculate the diameter, using the whitelist elements diameter"""
        return sum(
            item.diameter ** 2 for item in self.whitelist_elements) ** 0.5

    diameter = attribute.Attribute(
        description='diameter',
        unit=ureg.millimeter,
        functions=[_calc_diameter],
        dependant_instances='whitelist_elements'
    )

    length = attribute.Attribute(
        description='length of aggregated pipe elements',
        functions=[_calc_avg],
        unit=ureg.meter,
    )

    diameter_strand = attribute.Attribute(
        description='average diameter of aggregated pipe elements',
        functions=[_calc_avg],
        unit=ureg.millimeter,
    )

    has_pump = attribute.Attribute(
        description="Cycle has a pumpsystem",
        functions=[HVACAggregationMixin._calc_has_pump]
    )

    @cached_property
    def pump_elements(self) -> list:
        """list of pump-like elements present on the aggregation"""
        return [ele for ele in self.elements if isinstance(ele, hvac.Pump)]

    def _calc_rated_pump_power(self, name) -> ureg.Quantity:
        """Calculate the rated pump power adding the rated power of the
        pump-like elements"""
        return sum([ele.rated_power for ele in self.pump_elements])

    rated_pump_power = attribute.Attribute(
        description="rated pump power",
        unit=ureg.kilowatt,
        functions=[_calc_rated_pump_power],
        dependant_instances='pump_elements'
    )

    def _calc_volume_flow(self, name) -> ureg.Quantity:
        """Calculate the volume flow, adding the volume flow of the pump-like
        elements"""
        return sum([ele.rated_volume_flow for ele in self.pump_elements])

    rated_volume_flow = attribute.Attribute(
        description="rated volume flow",
        unit=ureg.m ** 3 / ureg.s,
        functions=[_calc_volume_flow],
        dependant_instances='pump_elements'
    )

    def _calc_volume(self, name):
        """Calculates volume of GeneratorOneFluid."""
        return NotImplementedError

    volume = attribute.Attribute(
        description="Volume of Boiler",
        unit=ureg.m ** 3,
        functions=[_calc_volume]
    )

    def _calc_rated_height(self, name) -> ureg.Quantity:
        """Calculate the rated height power, using the maximal rated height of
        the pump-like elements"""
        return max([ele.rated_height for ele in self.pump_elements])

    rated_height = attribute.Attribute(
        description="rated volume flow",
        unit=ureg.m,
        functions=[_calc_rated_height],
        dependant_instances='pump_elements'
    )
