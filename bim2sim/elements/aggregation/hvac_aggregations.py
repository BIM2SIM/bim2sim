import math
from functools import partial
from typing import List, Iterable, Dict, Union, Tuple, Optional

import networkx as nx
import numpy as np

from bim2sim.elements import hvac_elements as hvac
from bim2sim.elements.aggregation import AggregationMixin, logger
from bim2sim.elements.base_elements import ProductBased
from bim2sim.elements.graphs.hvac_graph import HvacGraph
from bim2sim.elements.hvac_elements import HVACPort
from bim2sim.elements.mapping import attribute
from bim2sim.elements.mapping.units import ureg
from bim2sim.kernel.decision import BoolDecision, DecisionBunch


def verify_edge_ports(func):
    """Decorator to verify edge ports"""

    def wrapper(agg_instance, *args, **kwargs):
        ports = func(agg_instance, *args, **kwargs)
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
        self.flow_direction = self.flow_direction_from_original()

    def flow_direction_from_original(self):
        if len(self.originals) > 1:
            flow_directions = set(
                [original.flow_direction for original in self.originals])
            if len(flow_directions) > 1:
                raise NotImplementedError(
                    'Aggregation of HVACPorts with different flow directions'
                    'is not implemented.')
            else:
                return list(flow_directions)[0]
        else:
            originals = self.originals[0]
            while originals:
                if hasattr(originals, 'originals'):
                    if len(originals.originals) > 1:
                        raise NotImplementedError(
                            'Aggregation with more than one original is not '
                            'implemented.')
                    originals = originals.originals[0]
                else:
                    return originals.flow_direction

    def _calc_position(self, name):
        """Position of original port"""
        return self.originals.position


class HVACAggregationMixin(AggregationMixin):
    """ Mixin class for all HVACAggregations.

    Adds some HVAC specific functionality to the AggregationMixin.

    Args:
        base_graph: networkx graph that should be searched for aggregations
        match_graph: networkx graph that only holds matches
    """

    def __init__(self, base_graph: nx.Graph, match_graph: nx.Graph, *args,
                 **kwargs):
        # make get_ports signature match_graph ProductBased.get_ports
        self.get_ports = partial(self.get_ports, base_graph, match_graph)
        graph_elements = list(set([node.parent for node in match_graph.nodes]))
        super().__init__(graph_elements, *args, **kwargs)

    @verify_edge_ports
    def get_ports(self, base_graph: HvacGraph, match_graph: HvacGraph
                  ) -> List[HVACPort]:
        """ Get the edge ports based on the difference between base_graph and
            match_graph,

        Args:
            base_graph: The base graph.
            match_graph: The matching graph.

        Returns:
            A list of HVACPort objects representing the edge ports.
        """
        # edges of g excluding all relations to s
        e1 = base_graph.subgraph(base_graph.nodes - match_graph.nodes).edges

        # if graph and match_graph are identical
        if not e1:
            # ports with only one connection are edge ports in this case
            edge_ports = [v for v, d in match_graph.degree() if d == 1]
        else:
            # all edges related to s
            e2 = base_graph.edges - e1
            # related to s but not s exclusive
            e3 = e2 - match_graph.edges
            # get only edge_ports that belong to the match_graph graph
            edge_ports = list(
                set([port for port in [e for x in list(e3) for e in x]
                     if port in match_graph]))
        ports = [HVACAggregationPort(port, parent=self) for port in edge_ports]
        return ports

    @classmethod
    def get_empty_mapping(cls, elements: Iterable[ProductBased]):
        """ Get information to remove elements.

        Args:
            elements:

        Returns:
            mapping: tuple of mapping dict with original ports as values and
                None as keys.
            connections: connection list of outer connections.
        """
        ports = [port for element in elements for port in element.ports]
        mapping = {port: None for port in ports}
        # TODO: len > 1, optimize
        external_ports = []
        for port in ports:
            if port.connection and port.connection.parent not in elements:
                external_ports.append(port.connection)

        mapping[external_ports[0].connection] = external_ports[1]
        mapping[external_ports[1].connection] = external_ports[0]
        connections = []

        return mapping, connections

    def get_replacement_mapping(self) \
            -> Dict[HVACPort, Union[HVACAggregationPort, None]]:
        """ Get replacement dict for existing ports."""
        mapping = {port: None for element in self.elements
                   for port in element.ports}
        for port in self.ports:
            for original in port.originals:
                mapping[original] = port
        return mapping

    @classmethod
    def find_matches(cls, base_graph: HvacGraph
                     ) -> Tuple[List[nx.Graph], List[dict]]:
        """ Find all matches for aggregation in HVAC graph.

        Args:
            base_graph: The HVAC graph that is searched for potential
                matches.

        Returns:
            matches_graphs: List of HVAC graphs that matches the aggregation.
            metas: List of dict with metas information. One element for each
                matches_graphs.

        Raises:
            NotImplementedError: If method is not implemented.
        """
        raise NotImplementedError(
            "Method %s.find_matches not implemented" % cls.__name__)

    def _calc_has_pump(self, name) -> bool:
        """ Determines if aggregation contains pumps.

        Returns:
            True, if aggregation has pumps
        """
        has_pump = False
        for ele in self.elements:
            if hvac.Pump is ele.__class__:
                has_pump = True
                break
        return has_pump


class PipeStrand(HVACAggregationMixin, hvac.Pipe):
    """ Aggregates pipe strands, i.e. pipes, pipe fittings and valves.

    This aggregation reduces the number of elements by merging straight
    connected elements with just two ports into one PipeStrand. The length and
    a medium diameter are calculated based on the aggregated elements to
    maintain meaningful parameters for pressure loss calculations.
    """
    aggregatable_classes = {hvac.Pipe, hvac.PipeFitting, hvac.Valve}
    multi = ('length', 'diameter')

    @classmethod
    def find_matches(cls, base_graph: HvacGraph
                     ) -> Tuple[List[HvacGraph], List[dict]]:
        """ Find all matches for PipeStrand in HvacGraph.

        Args:
            base_graph: The Hvac graph to search for matches in.

        Returns:
            A tuple containing two lists:
                - matches_graphs: List of HvacGraphs that hold PipeStrands
                - metas: List of dict with meta information. One element for
                    each match.
        """
        pipe_strands = HvacGraph.get_type_chains(
            base_graph.element_graph, cls.aggregatable_classes,
            include_singles=True)
        matches_graphs = [base_graph.subgraph_from_elements(pipe_strand)
                          for pipe_strand in pipe_strands]

        metas = [{} for x in matches_graphs]  # no metadata calculated
        return matches_graphs, metas

    @attribute.multi_calc
    def _calc_avg(self) -> dict:
        """ Calculates the total length and average diameter of all pipe-like
            elements.
         """

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

    diameter = attribute.Attribute(
        description="Average diameter of aggregated pipe",
        functions=[_calc_avg],
        unit=ureg.millimeter,
        dependant_elements='elements'
    )

    length = attribute.Attribute(
        description="Length of aggregated pipe",
        functions=[_calc_avg],
        unit=ureg.meter,
        dependant_elements='elements'
    )


class UnderfloorHeating(PipeStrand):
    """ Class for aggregating underfloor heating systems.

    The normal pitch (spacing) between pipes is typically between 0.1m and 0.2m.
    """

    @classmethod
    def find_matches(cls, base_graph: HvacGraph
                     ) -> Tuple[List[HvacGraph], List[dict]]:
        """ Finds matches of underfloor heating systems in a given graph.

        Args:
            base_graph: An HvacGraph that should be checked for underfloor
                heating systems.

        Returns:
            A tuple containing two lists:
                - matches_graphs: A list of HvacGraphs that contain underfloor
                    heating systems.
                - metas: A list of dict with meta information for each
                    underfloor heating system. One element for each match.
        """
        chains = HvacGraph.get_type_chains(
            base_graph.element_graph, cls.aggregatable_classes,
            include_singles=True)
        matches_graphs = []
        metas = []
        for chain in chains:
            meta = cls.check_conditions(chain)
            if meta:
                metas.append(meta)
                matches_graphs.append(base_graph.subgraph_from_elements(chain))
        return matches_graphs, metas

    @staticmethod
    def check_number_of_elements(chain: nx.classes.reportviews.NodeView,
                                 tolerance: int = 20) -> bool:
        """ Check if the targeted chain has more than 20 elements.

        This method checks if a given chain has more than the specified number
        of elements.

        Args:
            chain: Possible chain of consecutive elements to be an underfloor
                heating.
            tolerance: Integer tolerance value to check the number of elements.
                Default is 20.

        Returns:
            True if the chain has more than the specified number of elements,
            False otherwise.
        """
        return len(chain) >= tolerance

    @staticmethod
    def check_pipe_strand_horizontality(ports_coors: np.ndarray,
                                        tolerance: float = 0.8) -> bool:
        """ Checks the horizontality of a pipe strand.

        This method checks if the pipe strand is located horizontally, meaning
        it is parallel to the floor and most elements are in the same z plane.

        Args:
            ports_coors: An array with pipe strand port coordinates.
            tolerance: Tolerance to check pipe strand horizontality.
                Default is 0.8.

        Returns:
            True, if check succeeds and False if check fails.
        """
        counts = np.unique(ports_coors[:, 2], return_counts=True)
        # TODO: cluster z coordinates
        idx_max = np.argmax(counts[1])
        return counts[1][idx_max] / ports_coors.shape[0] >= tolerance

    @staticmethod
    def get_pipe_strand_attributes(ports_coors: np.ndarray,
                                   chain: nx.classes.reportviews.NodeView
                                   ) -> [*(ureg.Quantity,) * 5]:
        """ Gets the attributes of a pipe strand.

        This method retrieves the attributes of a pipe strand in order to
        perform further checks and calculations.

        Args:
            ports_coors: An array with pipe strand port coordinates.
            chain: A possible chain of elements to be an Underfloor heating.

        Returns:
            heating_area: Underfloor heating area.
            total_length: Underfloor heating total pipe length.
            avg_diameter: Average underfloor heating diameter.
            dist_x: Underfloor heating dimension in x.
            dist_y: Underfloor heating dimension in y.
        """
        total_length = sum(segment.length for segment in chain if
                           segment.length is not None)
        avg_diameter = (sum(segment.diameter ** 2 * segment.length for segment
                            in chain if segment.length is not
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
        # TODO: function to obtain the underfloor heating form based on issue
        #  #211
        raise NotImplementedError

    @classmethod
    def get_pipe_strand_spacing(cls,
                                chain: nx.classes.reportviews.NodeView,
                                dist_x: ureg.Quantity,
                                dist_y: ureg.Quantity,
                                tolerance: int = 10
                                ) -> [*(ureg.Quantity,) * 2]:
        """ Sorts the pipe elements according to their angle in the horizontal
            plane. Necessary to calculate subsequently the underfloor heating
            spacing.

        Args:
            chain: possible chain of elements to be an Underfloor heating
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
        for element in chain:
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
        """ Check if the total area of the underfloor heating is greater than
            the tolerance value - just as safety factor.

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
                                          210 * ureg.millimeter)
                      ) -> Optional[bool]:
        """ Check if the spacing between adjacent elements with the same
            orientation is between the tolerance values.
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
                  tolerance: tuple = (0.09, 0.01)) -> Optional[bool]:
        """ Check if the quotient between the cross-sectional area of the pipe
            strand (x-y plane) and the total heating area is between the
            tolerance values - area density for underfloor heating.

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
    def check_conditions(cls, chain: nx.classes.reportviews.NodeView
                         ) -> Optional[dict]:
        """ Checks ps_elements and returns instance of UnderfloorHeating if all
            following criteria are fulfilled:
                0. minimum of 20 elements
                1. the pipe strand is located horizontally
                2. the pipe strand elements located in an specific z-coordinate
                3. the spacing tolerance
                4. underfloor heating area tolerance
                5. kpi criteria

        Args:
            chain: possible chain of elements to be an Underfloor heating

        Returns:
            None: if check fails
            meta: dict with calculated values if check succeeds
        """
        # TODO: use only floor heating pipes and not connecting pipes
        if not cls.check_number_of_elements(chain):
            return
        ports_coordinates = np.array(
            [p.position for e in chain for p in e.ports])
        if not cls.check_pipe_strand_horizontality(ports_coordinates):
            return

        heating_area, total_length, avg_diameter, dist_x, dist_y = \
            cls.get_pipe_strand_attributes(ports_coordinates, chain)
        x_spacing, y_spacing = cls.get_pipe_strand_spacing(
            chain, dist_x, dist_y)

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
    """ Aggregates pumps in parallel."""
    aggregatable_classes = {hvac.Pump, hvac.Pipe, hvac.PipeFitting, PipeStrand}
    whitelist_classe = {hvac.Pump}

    multi = ('rated_power', 'rated_height', 'rated_volume_flow', 'diameter',
             'diameter_strand', 'length')

    @classmethod
    def find_matches(cls, base_graph: HvacGraph
                     ) -> Tuple[List[HvacGraph], List[dict]]:
        """ Find matches of parallel pumps in the given graph.

        Args:
            base_graph: HVAC graph that should be checked for parallel pumps.

        Returns:
            A tuple containing two lists:
                matches_graph: List of HVAC graphs that hold the parallel pumps.
                metas: List of dict with meta information. One element for
                    each match.
        """
        element_graph = base_graph.element_graph
        inert_classes = cls.aggregatable_classes - cls.whitelist_classe
        parallel_pump_strands = HvacGraph.get_parallels(
            element_graph, cls.whitelist_classe, inert_classes,
            grouping={'rated_power': 'equal'},
            grp_threshold=1)
        matches_graph = [base_graph.subgraph_from_elements(parallel.nodes)
                         for parallel in parallel_pump_strands]
        metas = [{} for x in matches_graph]  # no metadata calculated
        return matches_graph, metas


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

    @property
    def pump_elements(self) -> list:
        """list of pump-like elements present on the aggregation"""
        return [ele for ele in self.elements if isinstance(ele, hvac.Pump)]

    def _calc_rated_power(self, name) -> ureg.Quantity:
        """Calculate the rated power adding the rated power of the pump-like
        elements"""
        value = sum(ele.rated_power for ele in self.pump_elements)
        if value:
            return value

    rated_power = attribute.Attribute(
        unit=ureg.kilowatt,
        description="rated power",
        functions=[_calc_rated_power],
        dependant_elements='pump_elements'
    )

    def _calc_rated_height(self, name) -> ureg.Quantity:
        """Calculate the rated height, using the maximal rated height of
        the pump-like elements"""
        return max([ele.rated_height for ele in self.pump_elements])

    rated_height = attribute.Attribute(
        description='rated height',
        functions=[_calc_rated_height],
        unit=ureg.meter,
        dependant_elements='pump_elements'
    )

    def _calc_volume_flow(self, name) -> ureg.Quantity:
        """Calculate the volume flow, adding the volume flow of the pump-like
        elements"""
        value = sum([ele.rated_volume_flow for ele in self.pump_elements])
        if value:
            return value

    rated_volume_flow = attribute.Attribute(
        description='rated volume flow',
        functions=[_calc_volume_flow],
        unit=ureg.meter ** 3 / ureg.hour,
        dependant_elements='pump_elements'
    )

    def _calc_diameter(self, name) -> ureg.Quantity:
        """Calculate the diameter, using the pump-like elements diameter"""
        value = sum(item.diameter ** 2 for item in self.pump_elements) ** 0.5
        if value:
            return value

    diameter = attribute.Attribute(
        description='diameter',
        functions=[_calc_diameter],
        unit=ureg.millimeter,
        dependant_elements='pump_elements'
    )

    @property
    def not_pump_elements(self) -> list:
        """list of not-pump-like elements present on the aggregation"""
        return [ele for ele in self.elements if not isinstance(ele, hvac.Pump)]

    length = attribute.Attribute(
        description='length of aggregated pipe elements',
        functions=[_calc_avg],
        unit=ureg.meter,
        dependant_elements='not_pump_elements'
    )

    diameter_strand = attribute.Attribute(
        description='average diameter of aggregated pipe elements',
        functions=[_calc_avg],
        unit=ureg.millimeter,
        dependant_elements='not_pump_elements'
    )


class Consumer(HVACAggregationMixin, hvac.HVACProduct):
    """ A class that aggregates a Consumer.

        This class represents a Consumer system in an HVAC graph, which can
        contain various elements such as space heaters, pipes, pumps, and
        valves. It aggregates these elements into a single entity, called
        Consumer.

    Attributes:
        multi: A tuple of attribute names that can have multiple
            values for a Consumer.
        aggregatable_classes: A dict of element classes that can be
            aggregated into a Consumer.
        whitelist_classes: A dict of element classes that should be included
            when searching for a Consumer in an HVAC graph.
        blacklist_classes: A dict of element classes that should be excluded
            when searching for a Consumer in an HVAC graph.
        boarder_classes: A dictionary of element classes that define the
            border of a Consumer system.
    """

    aggregatable_classes = {
        hvac.SpaceHeater, hvac.Pipe, hvac.PipeFitting, hvac.Junction,
        hvac.Pump, hvac.Valve, hvac.ThreeWayValve, PipeStrand,
        UnderfloorHeating}
    whitelist_classes = {hvac.SpaceHeater, UnderfloorHeating}
    blacklist_classes = {hvac.Chiller, hvac.Boiler, hvac.CoolingTower,
                         hvac.HeatPump, hvac.Storage, hvac.CHP}
    boarder_classes = {hvac.Distributor}
    multi = ('has_pump', 'rated_power', 'rated_pump_power', 'rated_height',
             'rated_volume_flow', 'temperature_inlet',
             'temperature_outlet', 'volume', 'description')

    @classmethod
    def find_matches(cls, base_graph: HvacGraph
                     ) -> Tuple[List[HvacGraph], List[dict]]:
        """ Find matches of consumer in the given base HVAC graph.

        Args:
            base_graph: The HVAC graph to search for consumers in.

        Returns:
            A tuple with two lists
                - matches_graph: A list of HVAC graphs that contain
                    consumers, and the second list contains
                - metas: A list of dict with meta information about each
                    consumer
        """
        # remove boarder_classes nodes from base_graph to separate cycles
        graph = HvacGraph.remove_classes_from(base_graph, cls.boarder_classes)
        cycles = nx.connected_components(graph)

        matches_graphs = []
        for cycle in cycles:
            cycle_graph = graph.subgraph(cycle)
            # check for blacklist_classes in cycle, i.e. generators
            generator = {ele for ele in cycle_graph.elements if
                         ele.__class__ in cls.blacklist_classes}
            if generator:
                # check for whitelist_classes in cycle, i.e. consumers
                gen_con = {ele for ele in cycle_graph.elements if
                           ele.__class__ in cls.whitelist_classes}
                if gen_con:
                    # TODO: Consumer separieren
                    pass
            else:
                consumer = {ele for ele in cycle_graph.elements if
                            ele.__class__ in cls.whitelist_classes}
                if consumer:
                    matches_graphs.append(cycle_graph)

        metas = [{} for x in matches_graphs]
        return matches_graphs, metas

    @property
    def pump_elements(self) -> list:
        """ List of pump-like elements present on the aggregation."""
        return [ele for ele in self.elements if isinstance(ele, hvac.Pump)]

    @property
    def not_pump_elements(self) -> list:
        """ List of not-pump-like elements present on the aggregation."""
        return [ele for ele in self.elements if not isinstance(ele, hvac.Pump)]

    def _calc_TControl(self, name):
        return any([isinstance(ele, hvac.ThreeWayValve) for ele in self.elements])

    @property
    def whitelist_elements(self) -> list:
        """ List of whitelist_classes elements present on the aggregation."""
        return [ele for ele in self.elements
                if type(ele) in self.whitelist_classes]

    def _calc_rated_power(self, name) -> ureg.Quantity:
        """ Calculate the rated power adding the rated power of the
            whitelist_classes elements.
        """
        value = sum([ele.rated_power for ele in self.whitelist_elements])
        if value:
            return value

    rated_power = attribute.Attribute(
        description="rated power",
        unit=ureg.kilowatt,
        functions=[_calc_rated_power],
        dependant_elements='whitelist_elements'
    )

    has_pump = attribute.Attribute(
        description="Cycle has a pump system",
        functions=[HVACAggregationMixin._calc_has_pump]
    )

    def _calc_rated_pump_power(self, name) -> ureg.Quantity:
        """ Calculate the rated pump power adding the rated power of the
            pump-like elements.
        """
        value = sum([ele.rated_power for ele in self.pump_elements])
        if value:
            return value

    rated_pump_power = attribute.Attribute(
        description="rated pump power",
        unit=ureg.kilowatt,
        functions=[_calc_rated_pump_power],
        dependant_elements='pump_elements'
    )

    def _calc_volume_flow(self, name) -> ureg.Quantity:
        """ Calculate the volume flow, adding the volume flow of the pump-like
            elements.
        """
        value = sum([ele.rated_volume_flow for ele in self.pump_elements])
        if value:
            return value

    rated_volume_flow = attribute.Attribute(
        description="rated volume flow",
        unit=ureg.meter ** 3 / ureg.hour,
        functions=[_calc_volume_flow],
        dependant_elements='pump_elements'
    )

    def _calc_flow_temperature(self, name) -> ureg.Quantity:
        """ Calculate the flow temperature, using the flow temperature of the
            whitelist_classes elements.
        """
        # TODO the following would work, but only if we want a medium
        #  temperature for the consumer. If we want a list, this needs to look
        #  different
        value = (sum(ele.flow_temperature.to_base_units() for ele
                     in self.whitelist_elements if
                     ele.flow_temperature is not None)
                 / len([ele for ele in self.whitelist_elements if
                        ele.flow_temperature is not None]))
        # value = (sum(ele.flow_temperature.to_base_units() for ele
        #            in self.whitelist_elements if ele.flow_temperature)
        #         / len(self.whitelist_elements))
        if value:
            return value

    flow_temperature = attribute.Attribute(
        description="temperature inlet",
        unit=ureg.kelvin,
        functions=[_calc_flow_temperature],
        dependant_elements='whitelist_elements'
    )

    def _calc_return_temperature(self, name) -> ureg.Quantity:
        """ Calculate the return temperature, using the return temperature of
            the whitelist_classes elements.
        """
        value = (sum(ele.return_temperature.to_base_units() for ele
                     in self.whitelist_elements if
                     ele.return_temperature is not None)
                 / len([ele for ele in self.whitelist_elements if
                        ele.return_temperature is not None]))
        if value:
            return value

    return_temperature = attribute.Attribute(
        description="temperature outlet",
        unit=ureg.kelvin,
        functions=[_calc_return_temperature],
        dependant_elements='whitelist_elements'
    )

    def _calc_dT_water(self, name):
        """ Water dt of consumer."""
        if self.flow_temperature and self.return_temperature:
            return self.flow_temperature - self.return_temperature

    dT_water = attribute.Attribute(
        description="Nominal temperature difference",
        unit=ureg.kelvin,
        functions=[_calc_dT_water],
    )

    def _calc_body_mass(self, name):
        """ Body mass of consumer."""
        value = sum(ele.body_mass for ele in self.whitelist_elements)
        if value:
            return value

    body_mass = attribute.Attribute(
        description="Body mass of Consumer",
        functions=[_calc_body_mass],
        unit=ureg.kg,
    )

    def _calc_heat_capacity(self, name):
        """ Heat capacity of consumer."""
        value = sum(ele.heat_capacity for ele in self.whitelist_elements)
        if value:
            return value

    heat_capacity = attribute.Attribute(
        description="Heat capacity of Consumer",
        functions=[_calc_heat_capacity],
        unit=ureg.joule / ureg.kelvin,
    )

    def _calc_demand_type(self, name):
        """ Demand type of consumer."""
        return 1 if self.dT_water > 0 else -1

    demand_type = attribute.Attribute(
        description="Type of demand if 1 - heating, if -1 - cooling",
        functions=[_calc_demand_type],
    )

    volume = attribute.Attribute(
        description="volume",
        unit=ureg.meter ** 3,
    )

    def _calc_rated_height(self, name) -> ureg.Quantity:
        """ Calculate the rated height power, using the maximal rated height of
            the pump-like elements.
        """
        return max([ele.rated_height for ele in self.pump_elements])

    rated_height = attribute.Attribute(
        description="rated volume flow",
        unit=ureg.meter,
        functions=[_calc_rated_height],
        dependant_elements='pump_elements'
    )

    def _calc_description(self, name) -> str:
        """ Obtains the aggregation description using the whitelist_classes
            elements.
        """
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
        dependant_elements='whitelist_elements'
    )

    t_control = attribute.Attribute(
        description="Bool for temperature control cycle.",
        functions=[_calc_TControl]
    )


class ConsumerHeatingDistributorModule(HVACAggregationMixin, hvac.HVACProduct):
    """ A class that aggregates (several) consumers including the distributor.

    Attributes:
        multi: A Tuple of attributes to consider in aggregation.
        aggregatable_classes: A dict of element classes that can be
            aggregated into a ConsumerDistributorModule.
        whitelist_classes: A dict of element classes that should be included
            when searching for a ConsumerDistributorModule in an HVAC graph.
        blacklist_classes: A dict of element classes that should be excluded
            when searching for a ConsumerDistributorModule in an HVAC graph.
        boarder_classes: Dictionary of classes that are used as boarders.
   """

    multi = (
        'medium', 'use_hydraulic_separator', 'hydraulic_separator_volume',
        'temperature_inlet', 'temperature_outlet')
    # TODO: Abused to not just sum attributes from elements
    aggregatable_classes = {
        hvac.SpaceHeater, hvac.Pipe, hvac.PipeFitting, hvac.Distributor,
        PipeStrand, Consumer, hvac.Junction, hvac.ThreeWayValve }
    whitelist_classes = {
        hvac.SpaceHeater, UnderfloorHeating, Consumer}
    blacklist_classes = {hvac.Chiller, hvac.Boiler, hvac.CoolingTower}
    boarder_classes = {hvac.Distributor}

    def __init__(self, base_graph, match_graph, *args, **kwargs):
        self.undefined_consumer_ports = kwargs.pop(
            'undefined_consumer_ports', None)
        self._consumer_cycles = kwargs.pop('consumer_cycles', None)
        self.consumers = {con for consumer in self._consumer_cycles for con in
                          consumer if con.__class__ in self.whitelist_classes}
        self.open_consumer_pairs = self._register_open_consumer_ports()
        super().__init__(base_graph, match_graph, *args, **kwargs)
        # add open consumer ports to found ports by get_ports()
        for con_ports in self.open_consumer_pairs:
            self.ports.append(HVACAggregationPort(con_ports, parent=self))

    def _register_open_consumer_ports(self):
        """ This function registers open consumer ports by pairing up loose
            ends at the distributor. If there is an odd number of loose ends,
            it raises a NotImplementedError.

        Returns:
            list: A list of pairs of open consumer ports.

        Raises:
            NotImplementedError: If there is an odd number of loose ends at
                the distributor.
        """
        if (len(self.undefined_consumer_ports) % 2) == 0:
            consumer_ports = self.undefined_consumer_ports
        else:
            raise NotImplementedError(
                "Odd Number of loose ends at the distributor.")
        return consumer_ports

    @classmethod
    def find_matches(cls, base_graph: HvacGraph
                     ) -> Tuple[List[HvacGraph], List[dict]]:
        """ Finds matches of consumer heating distributor modules in the given
            graph.

        Args:
            base_graph: The graph to be checked for consumer heating distributor
                modules.

        Returns:
            A tuple containing two lists:
                - matches_graphs: contains the HVAC graphs that hold the
                    consumer heating distributor module.
            The second list
                - metas: contains the meta information for each consumer
                    heating distributor modules as a dictionary.
        """
        distributors = {ele for ele in base_graph.elements
                        if type(ele) in cls.boarder_classes}
        matches_graphs = []
        metas = []
        for distributor in distributors:
            _graph = base_graph.copy()
            _graph.remove_nodes_from(distributor.ports)
            consumer_cycle_elements = []
            metas.append({'undefined_consumer_ports': [],
                          'consumer_cycles': []})
            cycles = nx.connected_components(_graph)
            for cycle in cycles:
                cycle_graph = base_graph.subgraph(cycle)
                # check for blacklist_classes in cycle, i.e. generators
                generator = {ele for ele in cycle_graph.elements if
                             ele.__class__ in cls.blacklist_classes}
                if generator:
                    # check for whitelist_classes in cycle that contains a
                    # generator
                    gen_con = {ele for ele in cycle_graph.elements if
                               ele.__class__ in cls.whitelist_classes}
                    if gen_con:
                        # TODO: separate consumer (maybe recursive function?)
                        pass
                else:
                    consumer_cycle = {ele for ele in cycle_graph.elements if
                                      ele.__class__ in cls.whitelist_classes}
                    if consumer_cycle:
                        consumer_cycle_elements.extend(cycle_graph.elements)
                        metas[-1]['consumer_cycles'].append(
                            consumer_cycle_elements)
                    else:
                        # cycle does not hold a consumer might be undefined
                        # consumer ports
                        metas[-1]['undefined_consumer_ports'].extend(
                            [neighbor for cycle_node in list(cycle_graph.nodes)
                             for neighbor in base_graph.neighbors(cycle_node)
                             if neighbor.parent == distributor])

            match_graph = base_graph.subgraph_from_elements(
                consumer_cycle_elements + [distributor])
            matches_graphs.append(match_graph)

        return matches_graphs, metas

    @attribute.multi_calc
    # TODO fix hardcoded values
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

    @property
    def whitelist_elements(self) -> list:
        """list of whitelist_classes elements present on the aggregation"""
        return [ele for ele in self.elements if type(ele) in self.whitelist_classes]

    def _calc_has_pump(self, name) -> list[bool]:
        """Returns a list with boolean for every consumer if it has a pump."""
        return [con.has_pump for con in self.whitelist_elements]

    flow_temperature = attribute.Attribute(
        description="temperature inlet",
        unit=ureg.kelvin,
        functions=[Consumer._calc_flow_temperature],
        dependant_elements='whitelist_elements'
    )

    has_pump = attribute.Attribute(
        description="List with bool for every consumer if it has a pump",
        functions=[_calc_has_pump]
    )

    return_temperature = attribute.Attribute(
        description="temperature outlet",
        unit=ureg.kelvin,
        functions=[Consumer._calc_return_temperature],
        dependant_elements='whitelist_elements'
    )

    def _calc_dT_water(self, name):
        """water dt of consumer"""
        return [ele.dT_water.to_base_units() for ele
                in self.whitelist_elements]

    dT_water = attribute.Attribute(
        description="Nominal temperature difference",
        unit=ureg.kelvin,
        functions=[_calc_dT_water],
        dependant_elements='whitelist_elements'
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
        dependant_elements='whitelist_elements'
    )

    def calc_mass_flow(self, name):
        """Returns the mass flow, in the form of a list with the mass flow of
        the whitelist_classes-like elements"""
        return [ele.rated_mass_flow for ele in self.whitelist_elements]

    rated_mass_flow = attribute.Attribute(
        description="rated mass flow",
        functions=[calc_mass_flow],
        unit=ureg.kg / ureg.s,
        dependant_elements='whitelist_elements'
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
        dependant_elements='whitelist_elements'
    )

    def _calc_TControl(self, name) -> list[bool]:
        return [con.t_control for con in self.whitelist_elements]

    t_control = attribute.Attribute(
        description="List with bool for every consumer if it has a feedback "
                    "cycle for temperature control.",
        functions=[_calc_TControl]
    )

    def _calc_temperature_array(self):
        return [self.flow_temperature, self.return_temperature]

    temperature_array = attribute.Attribute(
        description="Array of flow and return temperature",
        functions=[_calc_temperature_array]
    )


class GeneratorOneFluid(HVACAggregationMixin, hvac.HVACProduct):
    """ Aggregates generator modules with only one fluid cycle (CHPs, Boilers,
        ...)

        Not for Chillers or Heat-pumps!
    """
    aggregatable_classes = {
        hvac.Pump, PipeStrand, hvac.Pipe, hvac.PipeFitting, hvac.Distributor,
        hvac.Boiler, ParallelPump, hvac.Valve, hvac.Storage,
        hvac.ThreeWayValve, hvac.Junction, ConsumerHeatingDistributorModule,
        Consumer}
    whitelist_classes = {hvac.Boiler, hvac.CHP}
    boarder_classes = {hvac.Distributor, ConsumerHeatingDistributorModule}
    multi = ('rated_power', 'has_bypass', 'rated_height', 'volume',
             'rated_volume_flow', 'rated_pump_power', 'has_pump')

    def __init__(self, base_graph, match_graph, *args, **kwargs):
        self.non_relevant = kwargs.pop('non_relevant', set())
        self.has_parallel = kwargs.pop('has_parallel', False)
        self.bypass_elements = kwargs.pop('bypass_elements', set())
        self.has_bypass = True if self.bypass_elements else False
        super().__init__(base_graph, match_graph, *args, **kwargs)

    @classmethod
    def find_matches(cls, base_graph: HvacGraph
                     ) -> Tuple[List[HvacGraph], List[dict]]:
        """ Finds matches of generators with one fluid.

            Non-relevant elements like bypasses are added to metas
            information to delete later.

        Args:
            base_graph: HVAC graph that should be checked for one fluid
                generators

        Returns:
            A tuple containing two lists:
                - matches_graphs: List of HVAC graphs that hold a generator
                    cycle including the distributor.
                - metas: List of dict with meta information for each generator
                    as a dictionary. In this case it holds non_relevant
                    nodes, which have to be deleted later but are not
                    contained in the match_graph .Because we are currently not
                    able to distinguish to which graph these non_relevant
                    nodes belong, we just output the complete list of
                    non-relevant nodes for every element_graph.
        """
        element_graph = base_graph.element_graph
        inerts = cls.aggregatable_classes - cls.whitelist_classes
        _graph = HvacGraph.remove_not_wanted_nodes(
            element_graph, cls.whitelist_classes, inerts)
        dict_all_cycles_wanted = HvacGraph.get_all_cycles_with_wanted(
            _graph, cls.whitelist_classes)
        list_all_cycles_wanted = [*dict_all_cycles_wanted.values()]

        # create flat lists to subtract for non-relevant
        generator_flat = set()
        wanted_flat = set()

        # check for generation cycles
        generator_cycles = []
        for cycles_list in list_all_cycles_wanted:
            generator_cycle = list(
                nx.subgraph(_graph, cycle) for cycle in cycles_list
                if any(type(node) == block for block in
                       cls.boarder_classes for node in cycle))
            if generator_cycle:
                generator_cycles.extend(generator_cycle)
                generator_flat.update(generator_cycle[0].nodes)
                wanted_flat.update(
                    [item for sublist in cycles_list for item in sublist])

        cleaned_generator_cycles = []
        metas = []
        if generator_flat:
            non_relevant = wanted_flat - generator_flat

            # remove overlapping elements in GeneratorCycles
            for gen_cycle in generator_cycles:
                pseudo_lst = gen_cycle.copy()
                for gen_cycle_two in generator_cycles:
                    if gen_cycle == gen_cycle_two:
                        continue
                    pseudo_lst.remove_nodes_from(gen_cycle_two)
                cleaned_generator_cycles.append(pseudo_lst)
            _graph = base_graph.copy()

            # match_graph bypass elements from non relevant elements
            for i in range(len(cleaned_generator_cycles)):
                metas.append(dict())
                metas[i]['bypass_elements'] = []
                for cycle in list_all_cycles_wanted[i]:
                    if len(cycle - cleaned_generator_cycles[i].nodes
                           - non_relevant) > 0:
                        continue
                    bypass_elements = cycle - cleaned_generator_cycles[i].nodes
                    cleaned_generator_cycles[i].add_nodes_from(bypass_elements)
                    non_relevant.difference_update(bypass_elements)
                    metas[i]['bypass_elements'].append(bypass_elements)

            if len(metas) > 0:
                metas[0]['non_relevant'] = non_relevant

        matches_graphs = []
        for cycle in cleaned_generator_cycles:
            match_graph = base_graph.subgraph_from_elements(list(cycle.nodes))
            match_graph = HvacGraph.remove_classes_from(
                match_graph, cls.boarder_classes)
            matches_graphs.append(match_graph)
        return matches_graphs, metas

    @attribute.multi_calc
    def _calc_avg(self):
        """ Calculates the parameters of all the below listed elements."""
        avg_diameter_strand = 0
        total_length = 0
        diameter_times_length = 0

        for element in self.not_whitelist_elements:
            if hasattr(element, "diameter") and hasattr(element, "length"):
                length = element.length
                diameter = element.diameter
                if not (length and diameter):
                    logger.info("Ignored '%s' in aggregation", element)
                    continue

                diameter_times_length += diameter * length
                total_length += length

            else:
                logger.info("Ignored '%s' in aggregation", element)

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
        return dict(has_bypass=has_bypass)

    @classmethod
    def find_bypasses(cls, graph):
        """ Finds bypasses based on the graphical network.

        Currently not used, might be removed in the future.
        """
        # todo remove if discussed
        wanted = set(cls.whitelist_classes)
        boarders = set(cls.boarder_classes)
        inerts = set(cls.aggregatable_elements) - wanted
        bypass_nodes = HvacGraph.detect_bypasses_to_wanted(
            graph, wanted, inerts, boarders)
        return bypass_nodes

    def _calc_has_bypass_decision(self):
        """ Checks if bypass exists based on decision. Currently not used as
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

    @property
    def whitelist_elements(self) -> list:
        """ List of whitelist_classes elements present on the aggregation"""
        return [ele for ele in self.elements if type(ele)
                in self.whitelist_classes]

    @property
    def not_whitelist_elements(self) -> list:
        """ List of not-whitelist_classes elements present on the aggregation"""
        return [ele for ele in self.elements if type(ele) not
                in self.whitelist_classes]

    def _calc_rated_power(self, name) -> ureg.Quantity:
        """ Calculate the rated power adding the rated power of the
            whitelist_classes elements."""
        value = sum([ele.rated_power for ele in self.whitelist_elements
                    if ele.rated_power])
        if value:
            return value

    rated_power = attribute.Attribute(
        unit=ureg.kilowatt,
        description="rated power",
        functions=[_calc_rated_power],
        dependant_elements='whitelist_elements'
    )

    def _calc_min_power(self, name):
        """ Calculates the min power, adding the min power of the
            whitelist_elements."""
        min_powers =  [ele.min_power for ele in self.whitelist_elements
                       if ele.min_power]
        if min_powers:
            return min(min_powers)

    min_power = attribute.Attribute(
        unit=ureg.kilowatt,
        description="min power",
        functions=[_calc_min_power],
        dependant_elements='whitelist_elements'
    )

    def _calc_min_PLR(self, name):
        """ Calculates the min PLR, using the min power and rated power."""
        if self.min_power and self.rated_power:
            return self.min_power / self.rated_power

    min_PLR = attribute.Attribute(
        description="Minimum part load ratio",
        unit=ureg.dimensionless,
        functions=[_calc_min_PLR],
    )

    flow_temperature = attribute.Attribute(
        description="Nominal flow temperature",
        unit=ureg.celsius,
        functions=[Consumer._calc_flow_temperature],
        dependant_elements='whitelist_elements'
    )

    def _calc_return_temperature(self, name) -> ureg.Quantity:
        """ Calculate the return temperature, using the return temperature of
            the whitelist_classes elements."""
        value = (sum(ele.return_temperature.to_base_units() for ele
                    in self.whitelist_elements if ele.return_temperature)
                / len(self.whitelist_elements))
        if value:
            return value

    return_temperature = attribute.Attribute(
        description="Nominal return temperature",
        unit=ureg.celsius,
        functions=[_calc_return_temperature],
        dependant_elements='whitelist_elements'
    )

    def _calc_dT_water(self, name):
        """ Rated power of boiler."""
        if self.return_temperature and self.flow_temperature:
            return abs(self.return_temperature - self.flow_temperature)

    dT_water = attribute.Attribute(
        description="Nominal temperature difference",
        unit=ureg.kelvin,
        functions=[_calc_dT_water],
    )

    def _calc_diameter(self, name) -> ureg.Quantity:
        """ Calculate the diameter, using the whitelist_classes elements
            diameter."""
        value = sum(
            item.diameter ** 2 for item in self.whitelist_elements) ** 0.5
        if value:
            return value

    diameter = attribute.Attribute(
        description='diameter',
        unit=ureg.millimeter,
        functions=[_calc_diameter],
        dependant_elements='whitelist_elements'
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

    @property
    def pump_elements(self) -> list:
        """ List of pump-like elements present on the aggregation"""
        return [ele for ele in self.elements if isinstance(ele, hvac.Pump)]

    def _calc_rated_pump_power(self, name) -> ureg.Quantity:
        """ Calculate the rated pump power adding the rated power of the
            pump-like elements."""
        value = all(ele.rated_power for ele in self.pump_elements)
        if value:
            return value

    rated_pump_power = attribute.Attribute(
        description="rated pump power",
        unit=ureg.kilowatt,
        functions=[_calc_rated_pump_power],
        dependant_elements='pump_elements'
    )

    def _calc_volume_flow(self, name) -> ureg.Quantity:
        """ Calculate the volume flow, adding the volume flow of the pump-like
            elements."""
        value = sum([ele.rated_volume_flow for ele in self.pump_elements])
        if value:
            return value

    rated_volume_flow = attribute.Attribute(
        description="rated volume flow",
        unit=ureg.m ** 3 / ureg.s,
        functions=[_calc_volume_flow],
        dependant_elements='pump_elements'
    )

    def _calc_volume(self, name):
        """ Calculates volume of GeneratorOneFluid."""
        return NotImplementedError

    volume = attribute.Attribute(
        description="Volume of Boiler",
        unit=ureg.m ** 3,
        functions=[_calc_volume]
    )

    def _calc_rated_height(self, name) -> ureg.Quantity:
        """ Calculate the rated height power, using the maximal rated height of
            the pump-like elements."""
        return max([ele.rated_height for ele in self.pump_elements])

    rated_height = attribute.Attribute(
        description="rated volume flow",
        unit=ureg.m,
        functions=[_calc_rated_height],
        dependant_elements='pump_elements'
    )
