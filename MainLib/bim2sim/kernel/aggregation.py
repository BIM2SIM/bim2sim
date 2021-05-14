"""Module for aggregation and simplifying elements"""
import logging
import math
from functools import partial
from typing import Sequence, List, Union, Iterable, Tuple, Set, Dict
import inspect
import operator

import ast
import numpy as np
import networkx as nx

from bim2sim.kernel.element import ProductBased, Port
from bim2sim.kernel.elements.hvac import HVACPort
from bim2sim.kernel.elements import hvac, bps
from bim2sim.kernel import elements, attribute
from bim2sim.kernel.hvac.hvac_graph import HvacGraph
from bim2sim.kernel.units import ureg, ifcunits
from bim2sim.utilities.common_functions import filter_instances
from bim2sim.kernel.finder import TemplateFinder


logger = logging.getLogger(__name__)


def verify_edge_ports(func):
    """Decorator to verify edge ports"""

    def wrapper(agg_instance, *args, **kwargs):
        ports = func(agg_instance, *args, **kwargs)
        # inner_ports = [port for ele in agg_instance.elements for port in ele.ports]
        for port in ports:
            if not port.connection:
                continue
            if port.connection.parent in agg_instance.elements:
                raise AssertionError("%s (%s) is not an edge port of %s" % (port, port.guid, agg_instance))
        return ports

    return wrapper


class HVACAggregationPort(HVACPort):
    """Port for Aggregation"""
    guid_prefix = 'AggPort'

    def __init__(self, originals, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # TODO / TBD: DJA: can one Port replace multiple? what about position?
        if not type(originals) == list:
            self.originals = [originals]
        else:
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
                raise AssertionError("Can't aggregate %s form elements: %s" %
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

    def request(self, name):
        # broadcast request to all nested elements
        # if one attribute included in multi_calc is requested, all multi_calc attributes are needed

        if name in self.multi:
            names = self.multi
        else:
            names = (name,)

        # for ele in self.elements:
        #     for n in names:
        #         ele.request(n)

        for n in names:
            super().request(n)

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
    def get_ports(self, graph):
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

        edge_ports = []
        for port in (p for e in edge_elements for p in e.ports):
            if not port.connection:
                edge_ports.append(port)
                continue
            #     continue  # end node
            if port.connection.parent not in graph.nodes:
                edge_ports.append(port)

        if len(edge_ports) > 2:
            raise AttributeError("Graph elements are not only (2 port) pipes")

        return edge_ports

    @classmethod
    def find_matches(cls, graph: HvacGraph)\
            -> Tuple[List[nx.Graph], List[dict]]:
        """Find all matches for Aggregation in element graph
        :returns: matches, metas"""
        raise NotImplementedError(
            "Method %s.find_matches not implemented" % cls.__name__)


class PipeStrand(HVACAggregationMixin, hvac.Pipe):
    """Aggregates pipe strands"""
    aggregatable_elements = {hvac.Pipe, hvac.PipeFitting,
                             hvac.Valve}
    multi = ('length', 'diameter')

    def __init__(self, element_graph, *args, **kwargs):
        super().__init__(element_graph, *args, **kwargs)
        # edge_ports = self.get_edge_ports(element_graph)
        # for port in edge_ports:
        #     self.ports.append(HVACAggregationPort(port, parent=self))

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

    # def get_replacement_mapping(self):
    #     """Returns dict with original ports as values and their aggregated replacement as keys."""
    #     mapping = {port: None for element in self.elements
    #                for port in element.ports}
    #     for port in self.ports:
    #         for original in port.originals:
    #             mapping[original] = port
    #     return mapping

    @classmethod
    def find_matches(cls, graph):
        element_graph = graph.element_graph
        chains = HvacGraph.get_type_chains(element_graph, cls.aggregatable_elements, include_singles=True)
        element_graphs = [element_graph.subgraph(chain) for chain in chains if len(chain) > 1]
        metas = [{} for x in element_graphs]  # no metadata calculated
        return element_graphs, metas

    diameter = attribute.Attribute(
        description="Average diameter of aggregated pipe",
        functions=[_calc_avg],
        unit=ureg.millimeter,
    )

    length = attribute.Attribute(
        description="Length of aggregated pipe",
        functions=[_calc_avg],
        unit=ureg.meter,
    )


class UnderfloorHeating(PipeStrand):
    """Aggregates UnderfloorHeating, normal pitch (spacing) between
    pipes is between 0.1m and 0.2m"""

    def __init__(self, element_graph, *args, **kwargs):
        super().__init__(element_graph, *args, **kwargs)
        # edge_ports = self.get_edge_ports(element_graph)
        # for port in edge_ports:
        #     self.ports.append(AggregationPort(port, parent=self))

    @classmethod
    def find_matches(cls, graph):
        element_graph = graph.element_graph
        chains = HvacGraph.get_type_chains(element_graph, cls.aggregatable_elements, include_singles=True)
        element_graphs = [element_graph.subgraph(chain) for chain in chains]
        metas = []
        for g in element_graphs.copy():
            meta = cls.check_conditions(g.nodes)
            if meta:
                metas.append(meta)
            else:
                # remove failed checks
                element_graphs.remove(g)
        return element_graphs, metas

    @classmethod
    def check_conditions(cls, uh_elements):
        """checks ps_elements and returns instance of UnderfloorHeating if all following criteria are fulfilled:
            0. minimum of 20 elements
            1. the pipe strand is located horizontally -- parallel to the floor
            2. the pipe strand has most of the elements located in an specific z-coordinate (> 80%)
            3. the spacing between adjacent elements with the same orientation is between 90mm and 210 mm
            4. the total area of the underfloor heating is more than 1m² - just as safety factor
            5. the quotient between the cross sectional area of the pipe strand (x-y plane) and the total heating area
                is between 0.09 and 0.01 - area density for underfloor heating

            :returns None if check failed else
            :returns meta dict with calculated values"""
        # TODO: use only floor heating pipes and not connecting pipes

        if len(uh_elements) < 20:
            return  # number criteria failed

        # z_coordinates = defaultdict(list)
        # for element in uh_elements:
        #     z_coordinates[element.position[2]].append(element)
        # z_coordinate = []
        # for coordinate in z_coordinates:
        #     n_pipe = 0
        #     for element in z_coordinates[coordinate]:
        #         if isinstance(element, elements.PipeFitting):
        #             n_pipe += 1
        #     if n_pipe == 0 and (len(z_coordinates[coordinate]) > len(z_coordinate)):
        #         z_coordinate = z_coordinates[coordinate]
        # z_coordinate = z_coordinate[0].position[2]

        ports_coors = np.array([p.position for e in uh_elements for p in e.ports])
        counts = np.unique(ports_coors[:, 2], return_counts=True)
        # TODO: cluster z coordinates
        idx_max = np.argmax(counts[1])
        if counts[1][idx_max] / ports_coors.shape[0] < 0.8:
            return  # most elements in same z plane criteria failed

        z_coordinate2 = counts[0][idx_max]

        min_x = float("inf")
        max_x = -float("inf")
        min_y = float("inf")
        max_y = -float("inf")
        x_orientation = []
        y_orientation = []
        for element in uh_elements:
            if np.abs(element.ports[0].position[2] - z_coordinate2) < 1 \
                    and np.abs(element.ports[1].position[2] - z_coordinate2) < 1:
                if element.position[0] < min_x:
                    min_x = element.position[0]
                if element.position[0] > max_x:
                    max_x = element.position[0]
                if element.position[1] < min_y:
                    min_y = element.position[1]
                if element.position[1] > max_y:
                    max_y = element.position[1]

                # TODO: what if e.g. 45° orientation??
                if abs(element.ports[0].position[0] - element.ports[1].position[0]) < 1:
                    y_orientation.append(element)
                if abs(element.ports[0].position[1] - element.ports[1].position[1]) < 1:
                    x_orientation.append(element)

        length_unit = ifcunits.get('IfcLengthMeasure')
        heating_area = (max_x - min_x) * (max_y - min_y) * length_unit ** 2
        if heating_area < 1e6 * ifcunits.get('IfcLengthMeasure') ** 2:
            return  # heating area criteria failed

        # TODO: this is not correct for some layouts
        if len(y_orientation) - 1 != 0:
            x_spacing = (max_x - min_x) / (len(y_orientation) - 1) * length_unit
        if len(x_orientation) - 1 != 0:
            y_spacing = (max_y - min_y) / (len(x_orientation) - 1) * length_unit
        if not ((90 * length_unit < x_spacing < 210 * length_unit) or
                (90 * length_unit < y_spacing < 210 * length_unit)):
            return  # spacing criteria failed

        # check final kpi criteria
        total_length = sum(segment.length for segment in uh_elements if segment.length is not None)
        avg_diameter = (sum(segment.diameter ** 2 * segment.length for segment in uh_elements if segment.length is not
                            None) / total_length) ** 0.5

        kpi_criteria = (total_length * avg_diameter) / heating_area

        if 0.09 > kpi_criteria > 0.01:
            # check passed
            meta = dict(
                length=total_length,
                diameter=avg_diameter,
                heating_area=heating_area,
                x_spacing=x_spacing,
                y_spacing=y_spacing
            )
            return meta
        else:
            # else kpi criteria failed
            return None

    def is_consumer(self):
        return True

    @attribute.multi_calc
    def _calc_avg(self):
        pass

    heating_area = attribute.Attribute(
        unit=ureg.meter ** 2,
        description='Heating area',
        functions=[_calc_avg]
    )
    x_spacing = attribute.Attribute(
        unit=ureg.meter,
        description='Spacing in x',
        functions=[_calc_avg]
    )
    y_spacing = attribute.Attribute(
        unit=ureg.meter,
        description='Spacing in y',
        functions=[_calc_avg]
    )

    @classmethod
    def create_on_match(cls, name, uh_elements):  # TODO: obsolete and equal? to check_conditions
        """checks ps_elements and returns instance of UnderfloorHeating if all following criteria are fulfilled:
            0. minimum of 20 elements
            1. the pipe strand is located horizontally -- parallel to the floor
            2. the pipe strand has most of the elements located in an specific z-coordinate (> 80%)
            3. the spacing between adjacent elements with the same orientation is between 90mm and 210 mm
            4. the total area of the underfloor heating is more than 1m² - just as safety factor
            5. the quotient between the cross sectional area of the pipe strand (x-y plane) and the total heating area
                is between 0.09 and 0.01 - area density for underfloor heating"""
        # TODO: use only floor heating pipes and not connecting pipes

        if len(uh_elements) < 20:
            return  # number criteria failed

        # z_coordinates = defaultdict(list)
        # for element in uh_elements:
        #     z_coordinates[element.position[2]].append(element)
        # z_coordinate = []
        # for coordinate in z_coordinates:
        #     n_pipe = 0
        #     for element in z_coordinates[coordinate]:
        #         if isinstance(element, elements.PipeFitting):
        #             n_pipe += 1
        #     if n_pipe == 0 and (len(z_coordinates[coordinate]) > len(z_coordinate)):
        #         z_coordinate = z_coordinates[coordinate]
        # z_coordinate = z_coordinate[0].position[2]

        ports_coors = np.array([p.position for e in uh_elements for p in e.ports])
        counts = np.unique(ports_coors[:, 2], return_counts=True)
        # TODO: cluster z coordinates
        idx_max = np.argmax(counts[1])
        if counts[1][idx_max] / ports_coors.shape[0] < 0.8:
            return  # most elements in same z plane criteria failed

        z_coordinate2 = counts[0][idx_max]

        min_x = float("inf")
        max_x = -float("inf")
        min_y = float("inf")
        max_y = -float("inf")
        x_orientation = []
        y_orientation = []
        for element in uh_elements:
            if np.abs(element.ports[0].position[2] - z_coordinate2) < 1 \
                    and np.abs(element.ports[1].position[2] - z_coordinate2) < 1:
                if element.position[0] < min_x:
                    min_x = element.position[0]
                if element.position[0] > max_x:
                    max_x = element.position[0]
                if element.position[1] < min_y:
                    min_y = element.position[1]
                if element.position[1] > max_y:
                    max_y = element.position[1]

                # TODO: what if e.g. 45° orientation??
                if abs(element.ports[0].position[0] - element.ports[1].position[0]) < 1:
                    y_orientation.append(element)
                if abs(element.ports[0].position[1] - element.ports[1].position[1]) < 1:
                    x_orientation.append(element)
        heating_area = (max_x - min_x) * (max_y - min_y) * ureg.meter ** 2
        if heating_area < 1e6 * ureg.meter ** 2:
            return  # heating area criteria failed

        # TODO: this is not correct for some layouts
        if len(y_orientation) - 1 != 0:
            x_spacing = (max_x - min_x) / (len(y_orientation) - 1)
        if len(x_orientation) - 1 != 0:
            y_spacing = (max_y - min_y) / (len(x_orientation) - 1)
        if not ((90 < x_spacing < 210) or (90 < y_spacing < 210)):
            return  # spacing criteria failed

        # create instance to check final kpi criteria
        underfloor_heating = cls(uh_elements)
        # pre set _calc_avg results
        underfloor_heating._heating_area = heating_area
        underfloor_heating._x_spacing = x_spacing
        underfloor_heating._y_spacing = y_spacing

        kpi_criteria = (underfloor_heating.length * underfloor_heating.diameter) / heating_area

        if 0.09 * ureg.dimensionless > kpi_criteria > 0.01 * ureg.dimensionless:
            return underfloor_heating
        # else kpi criteria failed


class ParallelPump(HVACAggregationMixin, hvac.Pump):
    """Aggregates pumps in parallel"""
    # aggregatable_elements = ['IfcPump', 'PipeStrand', 'IfcPipeSegment',
    #                          'IfcPipeFitting']
    aggregatable_elements = {
        hvac.Pump, hvac.Pipe, hvac.PipeFitting, PipeStrand}
    multi = ('rated_power', 'rated_height', 'rated_volume_flow', 'diameter', 'diameter_strand', 'length')

    def __init__(self, element_graph, *args, **kwargs):
        super().__init__(element_graph, *args, **kwargs)

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
        """Calculates the parameters of all pump-like elements."""
        max_rated_height = 0
        total_rated_volume_flow = 0
        total_diameter = 0
        avg_diameter_strand = 0
        total_length = 0
        diameter_times_length = 0
        total_rated_power = 0

        for item in self.elements:
            if isinstance(item, hvac.Pump):

                total_rated_volume_flow += item.rated_volume_flow
                total_rated_power += item.rated_power

                if max_rated_height != 0:
                    if item.rated_height < max_rated_height:
                        max_rated_height = item.rated_height
                else:
                    max_rated_height = item.rated_height

                total_diameter += item.diameter ** 2
            else:
                if hasattr(item, "diameter") and hasattr(item, "length"):
                    length = item.length
                    diameter = item.diameter
                    if not (length and diameter):
                        logger.info("Ignored '%s' in aggregation", item)
                        continue

                    diameter_times_length += diameter * length
                    total_length += length

                else:
                    logger.info("Ignored '%s' in aggregation", item)

        if total_length != 0:
            avg_diameter_strand = diameter_times_length / total_length

        total_diameter = total_diameter ** .5

        result = dict(
            rated_power=total_rated_power,
            rated_height=max_rated_height,
            rated_volume_flow=total_rated_volume_flow,
            diameter=total_diameter,
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

    rated_power = attribute.Attribute(
        unit=ureg.kilowatt, description="rated power",
        functions=[_calc_avg],
    )

    rated_height = attribute.Attribute(
        description='rated height',
        functions=[_calc_avg],
        unit=ureg.meter,
    )

    rated_volume_flow = attribute.Attribute(
        description='rated volume flow',
        functions=[_calc_avg],
        unit=ureg.meter ** 3 / ureg.hour,
    )

    diameter = attribute.Attribute(
        description='diameter',
        functions=[_calc_avg],
        unit=ureg.millimeter,
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

    @classmethod
    def find_matches(cls, graph):
        """Find all matches for Aggregation in element graph
        :returns: matches, meta"""
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
    # aggregatable_elements = ['PipeStand', 'IfcPipeSegment', 'IfcPipeFitting']
    aggregatable_elements = {hvac.Pipe, hvac.PipeFitting, PipeStrand}
    threshold = None

    def __init__(self, element_graph, aggr_ports=None, *args, **kwargs):
        self.get_ports = partial(self.get_ports, aggr_ports)
        super().__init__(element_graph, *args, **kwargs)
        # self.get_ports(aggr_ports, element_graph)

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
    def find_matches(cls, graph):
        """Find all matches for Aggregation in element graph
        :returns: matches, meta"""
        wanted = {elements.hvac.PipeFitting}
        innerts = cls.aggregatable_elements - wanted
        connected_fittings = HvacGraph.get_connections_between(
            graph, wanted, innerts)
        metas = [{} for x in connected_fittings]  # no metadata calculated
        return connected_fittings, metas

    # def get_replacement_mapping(self):
    #     """Returns dict with original ports as values and their aggregated
    #     replacement as keys."""
    #     mapping = {port: None for element in self.elements
    #                for port in element.ports}
    #     for port in self.ports:
    #         for original in port.originals:
    #             mapping[original] = port
    #     return mapping


class ParallelSpaceHeater(HVACAggregationMixin, hvac.SpaceHeater):
    """Aggregates Space heater in parallel"""

    aggregatable_elements = {hvac.SpaceHeater, hvac.Pipe,
                             hvac.PipeFitting, PipeStrand}
    # aggregatable_elements = ['IfcSpaceHeater', 'PipeStand', 'IfcPipeSegment', 'IfcPipeFitting']

    def __init__(self, element_graph, *args, **kwargs):
        super().__init__(element_graph, *args, **kwargs)
        # edge_ports = self._get_start_and_end_ports()
        # self.ports.append(HVACAggregationPort(edge_ports[0], parent=self))
        # self.ports.append(HVACAggregationPort(edge_ports[1], parent=self))
        # self._total_rated_power = None
        # self._avg_rated_height = None
        # self._total_rated_volume_flow = None
        # self._total_diameter = None
        # self._total_length = None
        # self._avg_diameter_strand = None
        # self._elements = None

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
        """Calculates the parameters of all pump-like elements."""
        avg_rated_height = 0
        total_rated_volume_flow = 0
        total_diameter = 0
        avg_diameter_strand = 0
        total_length = 0
        diameter_times_length = 0

        for pump in self.elements:
            if "Pump" in pump.ifc_type:
                rated_power = getattr(pump, "rated_power")
                rated_height = getattr(pump, "rated_height")
                rated_volume_flow = getattr(pump, "rated_volume_flow")
                diameter = getattr(pump, "diameter")
                if not (rated_power and rated_height and rated_volume_flow and diameter):
                    logger.warning("Ignored '%s' in aggregation", pump)
                    continue

                total_rated_volume_flow += rated_volume_flow
                # this is not avg but max
                if avg_rated_height != 0:
                    if rated_height < avg_rated_height:
                        avg_rated_height = rated_height
                else:
                    avg_rated_height = rated_height

                total_diameter += diameter ** 2
            else:
                if hasattr(pump, "diameter") and hasattr(pump, "length"):
                    length = pump.length
                    diameter = pump.diameter
                    if not (length and diameter):
                        logger.warning("Ignored '%s' in aggregation", pump)
                        continue

                    diameter_times_length += diameter * length
                    total_length += length

                else:
                    logger.warning("Ignored '%s' in aggregation", pump)

        if total_length != 0:
            avg_diameter_strand = diameter_times_length / total_length

        total_diameter = math.sqrt(total_diameter)
        g = 9.81
        rho = 1000
        # TODO: two pumps with rated power of 3 each give a total rated power of 674928
        total_rated_power = total_rated_volume_flow * avg_rated_height * g * rho

        result = dict(
            rated_power=total_rated_power,
            rated_height=avg_rated_height,
            rated_volume_flow=total_rated_volume_flow,
            diameter=total_diameter,
            diameter_strand=avg_diameter_strand,
            length=total_length,
        )
        return result

    # def get_replacement_mapping(self):
    #     """Returns dict with original ports as values and their aggregated replacement as keys."""
    #     mapping = {port: None for element in self.elements
    #                for port in element.ports}
    #     for port in self.ports:
    #         for original in port.originals:
    #             mapping[original] = port
    #     return mapping

    rated_power = attribute.Attribute(
        description="rated power",
        functions=[_calc_avg]
    )
    rated_height = attribute.Attribute(
        description="rated height",
        functions=[_calc_avg]
    )
    rated_volume_flow = attribute.Attribute(
        description="rated volume flow",
        unit=ureg.meter ** 3 / ureg.hour,
        functions=[_calc_avg]
    )
    diameter = attribute.Attribute(
        description="diameter",
        functions=[_calc_avg]
    )
    length = attribute.Attribute(
        description="length of aggregated pipe elements",
        functions=[_calc_avg]
    )
    diameter_strand = attribute.Attribute(
        description="average diameter of aggregated pipe elements",
        functions=[_calc_avg]
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
            new_cycle["elements"] = list(dict.fromkeys([v.parent for v in cycle]))
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
                    < new_cycle["elements"].index(elem) < new_cycle["elements"].index(final_ports[2].parent):
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
    multi = ('has_pump', 'rated_power', 'rated_pump_power', 'rated_height', 'rated_volume_flow', 'temperature_inlet',
             'temperature_outlet', 'volume', 'description')

    aggregatable_elements = {
        hvac.SpaceHeater, hvac.Pipe,
        hvac.PipeFitting,
        hvac.Pump, hvac.Valve,
        PipeStrand, ParallelSpaceHeater, UnderfloorHeating}
    whitelist = [hvac.SpaceHeater, ParallelSpaceHeater, UnderfloorHeating]
    blacklist = [hvac.Chiller, hvac.Boiler,
                 hvac.CoolingTower]

    def __init__(self, element_graph, *args, **kwargs):
        super().__init__(element_graph, *args, **kwargs)
        # edge_ports = self._get_start_and_end_ports()
        # self.ports.append(HVACAggregationPort(edge_ports[0], parent=self))
        # self.ports.append(HVACAggregationPort(edge_ports[1], parent=self))
        # self._total_rated_power = None
        # self._avg_rated_height = None
        # self._total_rated_volume_flow = None
        # self._total_diameter = None
        # self._total_length = None
        # self._avg_diameter_strand = None
        # self._elements = None

    def get_ports(self, graph):
        return [HVACAggregationPort(port, parent=self)
                for port in self._get_start_and_end_ports()]

    @verify_edge_ports
    def _get_start_and_end_ports(self):
        """
        Finds external ports of aggregated group
        :return ports:
        """
        agg_ports = []

        for ports in self.outer_connections:
            agg_ports.append(ports[1])  # TBD: only one port?

        return agg_ports

    @classmethod
    def get_edge_ports(cls, graph) -> List[HVACPort]:
        pass  # TODO

    @classmethod
    def find_matches(cls, graph: HvacGraph) \
            -> Tuple[List[nx.Graph], List[dict]]:
        """Find all matches for Aggregation in element graph
        :returns: matches, meta"""
        boarder_class = {hvac.Distributor}
        # innerts = set(cls.aggregatable_elements) - wanted

        boarder_class = set(boarder_class)

        element_graph = graph.element_graph
        _element_graph = element_graph.copy()

        # remove blocking nodes
        remove = {node for node in _element_graph.nodes if node.__class__ in boarder_class}
        _element_graph.remove_nodes_from(remove)

        # identify outer connections
        remove_ports = [port for ele in remove for port in ele.ports]
        outer_connections = {}
        for port in remove_ports:
            outer_connections.update({neighbor.parent: (port, neighbor) for neighbor in graph.neighbors(port) if
                                      neighbor not in remove_ports})

        sub_graphs = nx.connected_components(_element_graph)  # get_parallels(graph, wanted, innerts)

        consumer_cycles = []
        metas = []
        generator_cycles = []

        for sub in sub_graphs:
            # check for generator in sub_graphs
            generator = {node for node in sub if node.__class__ in cls.blacklist}
            if generator:
                # check for consumer in generator subgraph
                gen_con = {node for node in sub if node.__class__ in cls.whitelist}
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
                consumer_cycle = {node for node in sub if node.__class__ in cls.whitelist}
                if consumer_cycle:
                    subgraph = _element_graph.subgraph(sub)
                    outer_con = [outer_connections[ele] for ele in sub if ele in outer_connections]
                    consumer_cycles.append(subgraph)
                    metas.append({'outer_connections': outer_con})

        return consumer_cycles, metas

    def request(self, name):
        super().__doc__

        # broadcast request to all nested elements
        # if one attribute included in multi_calc is requested, all multi_calc attributes are needed

        # 'temperature_inlet'
        # 'temperature_outlet'

        lst_pump = ['rated_pump_power', 'rated_height', 'rated_volume_flow']

        if name == 'rated_power':
            for ele in self.elements:
                if ele.ifc_type in Consumer.whitelist:
                    ele.request(name)
        if name in lst_pump:
            for ele in self.elements:
                if ele.ifc_type == hvac.Pump.ifc_type:
                    for n in lst_pump:
                        ele.request(n)
        if name == 'volume':
            for ele in self.elements:
                ele.request(name)

    @attribute.multi_calc
    def _calc_avg_pump(self):
        """Calculates the parameters of all pump-like elements."""
        avg_rated_height = 0
        total_rated_volume_flow = 0
        total_length = 0

        total_rated_pump_power = None

        volume = None

        # Spaceheater und andere Consumer
        # Leistung zusammenzählen - Unnötig da zb. für fußbodenheizung da nichts gegeben
        # Aus Medium das Temperaturniveau ziehen! Wo steht das Medium? IFCDestributionSystems!?!?!?!

        for ele in self.elements:
            # Pumps
            if hvac.Pump is ele.__class__:
                # Pumpenleistung herausziehen
                total_rated_pump_power = getattr(ele, "rated_power")
                # Pumpenhöhe herausziehen
                rated_height = getattr(ele, "rated_height")
                # Volumenstrom
                rated_volume_flow = getattr(ele, "rated_volume_flow")

                # Volumen
                # volume_ = getattr(ele, "volume")
                # if volume_:
                #    volume += volume_ #ToDo: Sobald ein Volumen nicht vorhanden, Angabe: Nicht vorhanden???

                # this is not avg but max
                if avg_rated_height != 0:
                    if rated_height < avg_rated_height:
                        avg_rated_height = rated_height
                else:
                    avg_rated_height = rated_height

                if not rated_volume_flow:  # Falls eine Pumpe kein volumenstrom hat unvollständig
                    total_rated_volume_flow = None
                    continue
                else:
                    total_rated_volume_flow += rated_volume_flow
            else:
                if hasattr(ele, "length"):  # ToDO: Parallel?
                    length = ele.length
                    if not (length):
                        logger.warning("Ignored '%s' in aggregation", ele)
                        continue

                    total_length += length

                else:
                    logger.warning("Ignored '%s' in aggregation", ele)

        if not total_rated_pump_power and total_rated_volume_flow and avg_rated_height:
            g = 9.81 * ureg.meter / (ureg.second ** 2)
            rho = 1000 * ureg.kilogram / (ureg.meter ** 3)
            total_rated_pump_power = total_rated_volume_flow * avg_rated_height * g * rho

        #  Volumen zusammenrechnen
        volume = 1

        result = dict(
            rated_pump_power=total_rated_pump_power,
            rated_height=avg_rated_height,
            rated_volume_flow=total_rated_volume_flow,
            volume=volume
        )
        return result

    @attribute.multi_calc
    def _calc_avg_consumer(self):
        total_rated_consumer_power = 0
        con_types = {}
        for ele in self.elements:
            if ele.__class__ in Consumer.whitelist:
                # Dict for description consumer
                con_types[ele.__class__] = con_types.get(ele.__class__, 0) + 1
            elif ele.__class__ is hvac.SpaceHeater:
                rated_consumer_power = getattr(ele, "rated_power")
                total_rated_consumer_power += rated_consumer_power

        # ToDO: Aus Medium ziehen
        temperaure_inlet = None
        temperature_outlet = None

        result = dict(
            rated_power=total_rated_consumer_power,
            temperature_inlet=temperaure_inlet,
            temperature_outlet=temperature_outlet,
            description=', '.join(['{1} x {0}'.format(k.__name__, v) for k, v in con_types.items()])
        )
        return result

    def _calc_TControl(self, name):
        return True  # ToDo: Look at Boiler Aggregation - David

    @attribute.multi_calc
    def _calc_has_pump(self):
        has_pump = False
        for ele in self.elements:
            if hvac.Pump is ele.__class__:
                has_pump = True
                break;

        result = dict(
            has_pump=has_pump)
        return result

    # def get_replacement_mapping(self):
    #     """Returns dict with original ports as values and their aggregated replacement as keys."""
    #     mapping = {port: None for element in self.elements
    #                for port in element.ports}
    #     for port in self.ports:
    #         for original in port.originals:
    #             mapping[original] = port
    #     return mapping

    rated_power = attribute.Attribute(
        description="rated power",
        unit=ureg.kilowatt,
        functions=[_calc_avg_consumer]
    )

    has_pump = attribute.Attribute(
        description="Cycle has a pumpsystem",
        functions=[_calc_has_pump]
    )

    rated_pump_power = attribute.Attribute(
        description="rated pump power",
        unit=ureg.kilowatt,
        functions=[_calc_avg_pump]
    )

    rated_volume_flow = attribute.Attribute(
        description="rated volume flow",
        unit=ureg.meter ** 3 / ureg.hour,
        functions=[_calc_avg_pump]
    )

    temperature_inlet = attribute.Attribute(
        description="temperature inlet",
        functions=[_calc_avg_consumer]
    )

    temperature_outlet = attribute.Attribute(
        description="temperature outlet",
        functions=[_calc_avg_consumer]
    )

    volume = attribute.Attribute(
        description="volume",
        unit=ureg.meter ** 3,
        functions=[_calc_avg_pump]
    )

    rated_height = attribute.Attribute(
        description="rated volume flow",
        functions=[_calc_avg_pump]
    )

    description = attribute.Attribute(
        description="String with number of Consumers",
        functions=[_calc_avg_consumer]
    )

    t_controll = attribute.Attribute(
        description="Bool for temperature controll cycle.",
        functions=[_calc_TControl]
    )


class ConsumerHeatingDistributorModule(HVACAggregationMixin, hvac.HVACProduct): #ToDo: Export Aggregation HKESim
    """Aggregates Consumer system boarder"""
    multi = (
        'medium', 'use_hydraulic_separator', 'hydraulic_separator_volume', 'temperature_inlet', 'temperature_outlet')
    # ToDo: Abused to not just sum attributes from elements

    # aggregatable_elements = ['IfcSpaceHeater', 'PipeStand', 'IfcPipeSegment', 'IfcPipeFitting', 'ParallelSpaceHeater']
    aggregatable_elements = {
        hvac.SpaceHeater, hvac.Pipe,
        hvac.PipeFitting,
        PipeStrand, ParallelSpaceHeater}
    whitelist = [hvac.SpaceHeater, ParallelSpaceHeater, UnderfloorHeating,
                 Consumer]
    blacklist = [hvac.Chiller, hvac.Boiler,
                 hvac.CoolingTower]

    def __init__(self, element_graph, *args, **kwargs):
        self.undefined_consumer_ports = kwargs.pop('undefined_consumer_ports', None)  # TODO: Richtig sO? WORKAROUND
        self._consumer_cycles = kwargs.pop('consumer_cycles', None)
        super().__init__(element_graph, *args, **kwargs)
        edge_ports = self._get_start_and_end_ports()
        for port in edge_ports:
            self.ports.append(HVACAggregationPort(port, parent=self))

        self.consumers = []

        for consumer in self._consumer_cycles:
            for con in consumer:  # ToDo: darf nur ein Consumer sein
                self.consumers.append(con)

        self.open_consumer_pairs = self._register_open_consumerports()
        for ports in self.open_consumer_pairs:
            a = HVACAggregationPort(ports[0], parent=self)
            b = HVACAggregationPort(ports[1], parent=self)
            self.ports.append(a)
            self.ports.append(b)

        self._total_rated_power = None
        self._avg_rated_height = None
        self._total_rated_volume_flow = None
        self._total_diameter = None
        self._total_length = None
        self._avg_diameter_strand = None
        self._elements = None

    @verify_edge_ports
    def _get_start_and_end_ports(self):
        """
        Finds external ports of aggregated group
        :return ports:
        """
        agg_ports = []

        #  ToDo: outer_connection immer die anschlussports für erzeugerkreis?
        for ports in self.outer_connections:
            agg_ports.append(ports[0])

        return agg_ports

    @classmethod
    def get_edge_ports(cls, graph) -> List[HVACPort]:
        pass  # TODO

    def _register_open_consumerports(self):

        consumer_ports = []
        if (len(self.undefined_consumer_ports) % 2) == 0:
            for i in range(0, int(len(self.undefined_consumer_ports) / 2)):
                consumer_ports.append(
                    (self.undefined_consumer_ports[2 * i][0], self.undefined_consumer_ports[2 * i + 1][0]))
        else:
            raise NotImplementedError("Odd Number of loose ends at the distributor.")
        return consumer_ports

    @classmethod
    def find_matches(cls, graph):
        """Find all matches for Aggregation in element graph
        :returns: matches, meta"""
        boarder_class = {hvac.Distributor.ifc_type}
        boarder_class = set(boarder_class)
        element_graph = graph.element_graph
        results = []
        remove = {node for node in element_graph.nodes if node.ifc_type in boarder_class}
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
                outer_connections.update({neighbor.parent: (port, neighbor) for neighbor in graph.neighbors(port) if
                                          neighbor not in remove_ports})

            sub_graphs = nx.connected_components(_element_graph)  # get_parallels(graph, wanted, innerts)

            for sub in sub_graphs:
                # check for generator in sub_graphs
                generator = {node for node in sub if node.__class__ in cls.blacklist}
                if generator:
                    # check for consumer in generator subgraph
                    gen_con = {node for node in sub if node.__class__ in cls.whitelist}
                    if gen_con:
                        # ToDO: Consumer separieren
                        pass
                    else:
                        outer_con = [outer_connections[ele] for ele in sub if ele in outer_connections]
                        if outer_con:
                            metas[-1]['outer_connections'].extend(outer_con)
                        # pure generator subgraph
                        # subgraph = graph.subgraph(sub)
                        # generator_cycles.append(subgraph)
                else:
                    consumer_cycle = {node for node in sub if node.__class__ in cls.whitelist}
                    if consumer_cycle:
                        subgraph = _element_graph.subgraph(sub)
                        consumer_cycles.extend(subgraph.nodes)
                        metas[-1]['consumer_cycles'].append(subgraph.nodes)
                    else:
                        outer_con = [outer_connections[ele] for ele in sub if ele in outer_connections]
                        if outer_con:
                            metas[-1]['undefined_consumer_ports'].extend(outer_con)

            subnodes = [dist, *consumer_cycles]

            result = element_graph.subgraph(subnodes)
            results.append(result)

        return results, metas

    # def get_replacement_mapping(self):
    #     """Returns dict with original ports as values and their aggregated replacement as keys."""
    #     mapping = {port: None for element in self.elements
    #                for port in element.ports}
    #     for port in self.ports:
    #         for original in port.originals:
    #             mapping[original] = port
    #     return mapping

    @attribute.multi_calc
    def _calc_avg(self):

        result = dict(
            medium=None,
            temperature_inlet=None,
            temperature_outlet=None,
            use_hydraulic_separator=False,
            hydraulic_separator_volume=1,
        )
        return result

    medium = attribute.Attribute(
        description="Medium of the DestributerCycle",
        functions=[_calc_avg]
    )

    temperature_inlet = attribute.Attribute(
        description="temperature inlet",
        functions=[_calc_avg]
    )

    temperature_outlet = attribute.Attribute(
        description="temperature outlet",
        functions=[_calc_avg]
    )

    use_hydraulic_separator = attribute.Attribute(
        description="boolean if there is a hdydraulic seperator",
        functions=[_calc_avg]
    )

    hydraulic_separator_volume = attribute.Attribute(
        description="Volume of the hdydraulic seperator",
        functions=[_calc_avg]
    )


class AggregatedThermalZone(AggregationMixin, bps.ThermalZone):
    """Aggregates thermal zones"""
    aggregatable_elements = {bps.ThermalZone}

    def __init__(self, elements, *args, **kwargs):
        super().__init__(elements, *args, **kwargs)
        # self.get_disaggregation_properties()
        self.bound_elements = self.bind_elements()
        self.description = ''
        # todo lump usage conditions of existing zones

    def bind_elements(self):
        """elements binder for the resultant thermal zone"""
        bound_elements = []
        aux_bound_elements = []
        for e in self.elements:
            for i in e.bound_elements:
                aux_bound_elements.append(i)
                if i not in bound_elements:
                    bound_elements.append(i)
        return bound_elements

    @classmethod
    def based_on_groups(cls, groups, instances):
        """creates a new thermal zone aggregation instance
         based on a previous filtering"""
        new_aggregations = []
        thermal_zones = filter_instances(instances, 'ThermalZone')
        total_area = sum(i.area for i in thermal_zones)
        for group in groups:
            if group == 'one_zone_building':
                name = "Aggregated_%s" % group
                # ToDO: Check Name property
                instance = cls(groups[group], finder=TemplateFinder())
                instance.name = name
                # instance = cls(groups[group], name=name)
                instance.description = group
                new_aggregations.append(instance)
                for tz in instance.elements:
                    if tz.guid in instances:
                        del instances[tz.guid]
                instances[instance.guid] = instance
            elif group == 'not_bind':
                # last criterion no similarities
                area = sum(i.area for i in groups[group])
                if area / total_area <= 0.05:
                    # Todo: usage and conditions criterion
                    name = "Aggregated_%s" % '_'.join([i.name for i in groups[group]])
                    # ToDO: Check Name property
                    instance = cls(groups[group], finder=TemplateFinder())
                    instance.name = name
                    # instance = cls(groups[group], name=name)
                    instance.description = group
                    new_aggregations.append(instance)
                    for tz in instance.elements:
                        if tz.guid in instances:
                            del instances[tz.guid]
                    instances[instance.guid] = instance
            else:
                # first criterion based on similarities
                name = "Aggregated_%s" % '_'.join([i.name for i in groups[group]])
                # ToDO: Check Name property
                instance = cls(groups[group], finder=TemplateFinder())
                instance.name = name
                # instance = cls(groups[group], name=name)
                instance.description = ', '.join(ast.literal_eval(group))
                new_aggregations.append(instance)
                for tz in instance.elements:
                    if tz.guid in instances:
                        del instances[tz.guid]
                instances[instance.guid] = instance
        return new_aggregations

    def _intensive_calc(self, name):
        """intensive properties getter - volumetric mean
        intensive_attributes = ['t_set_heat', 't_set_cool', 'height',  'AreaPerOccupant', 'typical_length',
        'typical_width', 'T_threshold_heating', 'activity_degree_persons', 'fixed_heat_flow_rate_persons',
        'internal_gains_moisture_no_people', 'T_threshold_cooling', 'ratio_conv_rad_persons', 'machines',
        'ratio_conv_rad_machines', 'lighting_power', 'ratio_conv_rad_lighting', 'infiltration_rate',
        'max_user_infiltration', 'min_ahu', 'max_ahu', 'persons']"""
        prop_sum = sum(getattr(tz, name) * tz.volume for tz in self.elements if getattr(tz, name) is not None
                       and tz.volume is not None)
        vol_total = sum(tz.volume for tz in self.elements if tz.volume is not None)
        return prop_sum / vol_total

    def _intensive_list_calc(self, name):
        """intensive list properties getter - volumetric mean
        intensive_list_attributes = ['heating_profile', 'cooling_profile', 'persons_profile', 'machines_profile',
         'lighting_profile', 'max_overheating_infiltration', 'max_summer_infiltration',
         'winter_reduction_infiltration']"""
        list_attrs = {'heating_profile': 25, 'cooling_profile': 25, 'persons_profile': 24,
                      'machines_profile': 24, 'lighting_profile': 24, 'max_overheating_infiltration': 2,
                      'max_summer_infiltration': 3,
                      'winter_reduction_infiltration': 3}
        length = list_attrs[name]
        vol_total = sum(tz.volume for tz in self.elements if tz.volume is not None).m
        aux = []
        for x in range(0, length):
            aux.append(sum(getattr(tz, name)[x] * tz.volume.m for tz in self.elements if getattr(tz, name) is not None
                           and tz.volume is not None) / vol_total)
        return aux

    def _extensive_calc(self, name):
        """extensive properties getter
        intensive_attributes = ['area', 'volume']"""
        prop_sum = sum(getattr(tz, name) for tz in self.elements if getattr(tz, name) is not None)
        return prop_sum

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
        functions=[_get_tz_usage]
    )
    t_set_heat = attribute.Attribute(
        functions=[_intensive_calc],
        unit=ureg.degC
    )
    t_set_cool = attribute.Attribute(
        functions=[_intensive_calc],
        unit=ureg.degC
    )
    t_ground = attribute.Attribute(
        functions=[_intensive_calc],
        unit=ureg.degC,
    )
    area = attribute.Attribute(
        functions=[_extensive_calc],
        unit=ureg.meter ** 2
    )
    net_volume = attribute.Attribute(
        functions=[_extensive_calc],
        unit=ureg.meter ** 3
    )
    volume = attribute.Attribute(
        functions=[_extensive_calc],
        unit=ureg.meter ** 3
    )
    height = attribute.Attribute(
        functions=[_intensive_calc],
        unit=ureg.meter
    )
    AreaPerOccupant = attribute.Attribute(
        functions=[_intensive_calc],
        unit=ureg.meter ** 2
    )
    # use conditions
    with_cooling = attribute.Attribute(
        functions=[_bool_calc]
    )
    with_heating = attribute.Attribute(
        functions=[_bool_calc]
    )
    with_ahu = attribute.Attribute(
        functions=[_bool_calc]
    )
    heating_profile = attribute.Attribute(
        functions=[_intensive_list_calc]
    )
    cooling_profile = attribute.Attribute(
        functions=[_intensive_list_calc]
    )
    persons = attribute.Attribute(
        functions=[_intensive_calc]
    )
    typical_length = attribute.Attribute(
        functions=[_intensive_calc]
    )
    typical_width = attribute.Attribute(
        functions=[_intensive_calc]
    )
    T_threshold_heating = attribute.Attribute(
        functions=[_intensive_calc]
    )
    activity_degree_persons = attribute.Attribute(
        functions=[_intensive_calc]
    )
    fixed_heat_flow_rate_persons = attribute.Attribute(
        functions=[_intensive_calc]
    )
    internal_gains_moisture_no_people = attribute.Attribute(
        functions=[_intensive_calc]
    )
    T_threshold_cooling = attribute.Attribute(
        functions=[_intensive_calc]
    )
    ratio_conv_rad_persons = attribute.Attribute(
        functions=[_intensive_calc]
    )
    machines = attribute.Attribute(
        functions=[_intensive_calc]
    )
    ratio_conv_rad_machines = attribute.Attribute(
        functions=[_intensive_calc]
    )
    lighting_power = attribute.Attribute(
        functions=[_intensive_calc]
    )
    ratio_conv_rad_lighting = attribute.Attribute(
        functions=[_intensive_calc]
    )
    use_constant_infiltration = attribute.Attribute(
        functions=[_bool_calc]
    )
    infiltration_rate = attribute.Attribute(
        functions=[_intensive_calc]
    )
    max_user_infiltration = attribute.Attribute(
        functions=[_intensive_calc]
    )
    max_overheating_infiltration = attribute.Attribute(
        functions=[_intensive_list_calc]
    )
    max_summer_infiltration = attribute.Attribute(
        functions=[_intensive_list_calc]
    )
    winter_reduction_infiltration = attribute.Attribute(
        functions=[_intensive_list_calc]
    )
    min_ahu = attribute.Attribute(
        functions=[_intensive_calc]
    )
    max_ahu = attribute.Attribute(
        functions=[_intensive_calc]
    )
    with_ideal_thresholds = attribute.Attribute(
        functions=[_bool_calc]
    )
    persons_profile = attribute.Attribute(
        functions=[_intensive_list_calc]
    )
    machines_profile = attribute.Attribute(
        functions=[_intensive_list_calc]
    )
    lighting_profile = attribute.Attribute(
        functions=[_intensive_list_calc]
    )
