"""Module for aggregation and simplifying elements"""

import logging
import math
from collections import defaultdict

import numpy as np

from bim2sim.ifc2python.element import BaseElement, BasePort
from bim2sim.ifc2python import elements, attribute


class AggregationPort(BasePort):
    """Port for Aggregation"""

    def __init__(self, original, *args, **kwargs):
        if 'guid' not in kwargs:
            kwargs['guid'] = self.get_id("AggPort")
        super().__init__(*args, **kwargs)
        self.original = original

    # def determine_flow_side(self):
        # return self.original.determine_flow_side()

    def calc_position(self):
        """Position of original port"""
        return self.original.position


class Aggregation(BaseElement):
    """Base aggregation of models"""

    def __init__(self, name, elements, *args, **kwargs):
        if 'guid' not in kwargs:
            # TODO: make guid reproducable unique for same aggregation elements
            # e.g. hash of all (ordered?) element guids?
            # Needed for save/load decisions on aggregations
            kwargs['guid'] = self.get_id("Agg")
        super().__init__(*args, **kwargs)
        self.name = name
        self.elements = elements
        for model in self.elements:
            model.aggregation = self

    def calc_position(self):
        """Position based on first and last element"""
        try:
            return (self.elements[0].position + self.elements[-1].position) / 2
        except:
            return None

    @classmethod
    def get_empty_mapping(cls, elements: list):
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

    def __repr__(self):
        return "<%s '%s' (aggregation of %d elements)>" % (
            self.__class__.__name__, self.name, len(self.elements))


class PipeStrand(Aggregation):
    """Aggregates pipe strands"""
    aggregatable_elements = ['IfcPipeSegment', 'IfcPipeFitting']

    def __init__(self, name, elements, *args, **kwargs):
        super().__init__(name, elements, *args, **kwargs)
        edge_ports = self._get_start_and_end_ports()
        self.ports.append(AggregationPort(edge_ports[0], parent=self))
        self.ports.append(AggregationPort(edge_ports[1], parent=self))

        for ele in self.elements:
            ele.request('diameter')
            ele.request('length')

        # self._total_length = None
        # self._avg_diameter = None

    def _get_start_and_end_ports(self):
        """
        Finds and sets the first and last port of the pipestrand.

        Assumes all elements in are ordered as connected
        :return ports:
        """
        agg_ports = []
        # first port
        found_in = False
        found_out = False
        for port in self.elements[0].ports:
            if not port.connection:
                continue  # end node
            if port.connection.parent not in self.elements:
                found_out = True
                port.aggregated_parent = self
                agg_ports.append(port)
            else:
                found_in = True
        if not (found_in and found_out):
            raise AssertionError("Assumption of ordered elements violated")

        # last port
        found_in = False
        found_out = False
        for port in self.elements[-1].ports:
            if port.connection.parent not in self.elements:
                found_out = True
                port.aggregated_parent = self
                agg_ports.append(port)
            else:
                found_in = True
        if not (found_in and found_out):
            raise AssertionError("Assumption of ordered elements violated")

        return agg_ports

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
                self.logger.warning("Ignored '%s' in aggregation", pipe)
                continue

            diameter_times_length += diameter*length
            total_length += length

        if total_length != 0:
            avg_diameter = diameter_times_length / total_length

        result = dict(
            length=total_length,
            diameter=avg_diameter
        )
        return result

    def get_replacement_mapping(self):
        """Returns dict with original ports as values and their aggregated replacement as keys."""
        mapping = {port: None for element in self.elements
                   for port in element.ports}
        for port in self.ports:
            mapping[port.original] = port
        return mapping

    diameter = attribute.Attribute(
        name='diameter',
        description="Average diameter of aggregated pipe",
        functions=[_calc_avg],
    )

    length = attribute.Attribute(
        name='length',
        description="Length of aggregated pipe",
        functions=[_calc_avg]
    )
    # @property
    # def diameter(self):
    #     """Diameter of aggregated pipe"""
    #     if self._avg_diameter is None:
    #         self._calc_avg()
    #     return self._avg_diameter
    #
    # @property
    # def length(self):
    #     """Length of aggregated pipe"""
    #     if self._total_length is None:
    #         self._calc_avg()
    #     return self._total_length


class UnderfloorHeating(PipeStrand):
    """Aggregates UnderfloorHeating, normal pitch (spacing) between
    pipes is between 0.1m and 0.2m"""

    def __init__(self, name, elements, *args, **kwargs):
        super().__init__(name, elements, *args, **kwargs)
        self._x_spacing = None
        self._y_spacing = None
        self._heating_area = None

    def is_consumer(self):
        return True

    @property
    def heating_area(self):
        """Heating area"""
        if self._heating_area is None:
            raise NotImplementedError("Adapt _calc_avg if needed")
        return self._heating_area

    @property
    def x_spacing(self):
        """Spacing in x"""
        if self._x_spacing is None:
            raise NotImplementedError("Adapt _calc_avg if needed")
        return self._x_spacing

    @property
    def y_spacing(self):
        """Spacing in y """
        if self._y_spacing is None:
            raise NotImplementedError("Adapt _calc_avg if needed")
        return self._y_spacing

    @classmethod
    def create_on_match(cls, name, uh_elements):
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
        heating_area = (max_x - min_x) * (max_y - min_y)
        if heating_area < 1e6:
            return  # heating area criteria failed

        # TODO: this is not correct for some layouts
        if len(y_orientation) - 1 != 0:
            x_spacing = (max_x - min_x) / (len(y_orientation) - 1)
        if len(x_orientation) - 1 != 0:
            y_spacing = (max_y - min_y) / (len(x_orientation) - 1)
        if not ((90 < x_spacing < 210) or (90 < y_spacing < 210)):
            return  # spacing criteria failed

        # create instance to check final kpi criteria
        underfloor_heating = cls(name, uh_elements)
        # pre set _calc_avg results
        underfloor_heating._heating_area = heating_area
        underfloor_heating._x_spacing = x_spacing
        underfloor_heating._y_spacing = y_spacing

        kpi_criteria = (underfloor_heating.length * underfloor_heating.diameter) / heating_area

        if 0.09 > kpi_criteria > 0.01:
            return underfloor_heating
        # else kpi criteria failed


class ParallelPump(Aggregation):
    """Aggregates pumps in parallel"""
    aggregatable_elements = ['IfcPump', 'PipeStand', 'IfcPipeSegment', 'IfcPipeFitting']

    def __init__(self, name, elements, *args, **kwargs):
        super().__init__(name, elements, *args, **kwargs)
        edge_ports = self._get_start_and_end_ports()
        self.ports.append(AggregationPort(edge_ports[0], parent=self))
        self.ports.append(AggregationPort(edge_ports[1], parent=self))

    def _get_start_and_end_ports(self):
        """
        Finds and sets the first and last port of the parallelpumps

        Assumes all elements in are ordered as connected
        :return ports:
        """
        total_ports = {}
        # all possible beginning and end of the cycle (always pipe fittings), pumps counting
        for port in self.elements:
            if isinstance(port.parent, elements.PipeFitting):
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

    @attribute.multi_calc
    def _calc_avg(self):
        """Calculates the parameters of all pump-like elements."""
        avg_rated_height = 0
        total_rated_volume_flow = 0
        total_diameter = 0
        avg_diameter_strand = 0
        total_length = 0
        diameter_times_length = 0

        cycle_elements = list(dict.fromkeys([v.parent for v in self.elements]))
        for pump in cycle_elements:
            if "Pump" in str(pump):
                rated_power = getattr(pump, "rated_power")
                rated_height = getattr(pump, "rated_height")
                rated_volume_flow = getattr(pump, "rated_volume_flow")
                diameter = getattr(pump, "diameter")
                if not (rated_power and rated_height and rated_volume_flow and diameter):
                    self.logger.warning("Ignored '%s' in aggregation", pump)
                    continue

                total_rated_volume_flow += rated_volume_flow
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
                        self.logger.warning("Ignored '%s' in aggregation", pump)
                        continue

                    diameter_times_length += diameter * length
                    total_length += length

                else:
                    self.logger.warning("Ignored '%s' in aggregation", pump)

        if total_length != 0:
            avg_diameter_strand = diameter_times_length / total_length

        total_diameter = math.sqrt(total_diameter)
        g = 9.81
        rho = 1000
        total_rated_power = total_rated_volume_flow * avg_rated_height * g * rho

        result = dict(
            rated_power=total_rated_power,
            rated_height=avg_rated_height,
            rated_volume_flow=total_rated_volume_flow,
            diameter=total_diameter,
            length=total_length,
            diameter_strand=avg_diameter_strand
        )
        return result

    def get_replacement_mapping(self):
        """Returns dict with original ports as values and their aggregated replacement as keys."""
        mapping = {port: None for element in self._elements
                   for port in element.ports}
        for port in self.ports:
            mapping[port.original] = port
        return mapping

    rated_power = attribute.Attribute(
        name='rated_power',
        description="a",
        functions=[_calc_avg]
    )

    rated_height = attribute.Attribute(
        name='rated_height',
        description='',
        functions=[_calc_avg]
    )

    rated_volume_flow = attribute.Attribute(
        name='rated_volume_flow',
        description='',
        functions=[_calc_avg]
    )

    diameter = attribute.Attribute(
        name='diameter',
        description='',
        functions=[_calc_avg]
    )

    length = attribute.Attribute(
        name='length',
        description='',
        functions=[_calc_avg]
    )

    diameter_strand = attribute.Attribute(
        name='diameter_strand',
        description='',
        functions=[_calc_avg]
    )

    @classmethod
    def create_on_match(cls, name, cycle):
        """reduce the found cycles, to just the cycles that fulfill the next criteria:
            1. it's a parallel cycle (the two strands have the same flow direction)
            2. it has one or more pumps in each strand
            finally it creates a list with the founded cycles with the next lists:
            'elements', 'up_strand', 'low_strand', 'ports'
            """
        p_instance = "Pump"
        n_pumps = 0
        total_ports = {}
        cycle_elements = []
        # all possible beginning and end of the cycle (always pipe fittings), pumps counting
        for port in cycle:
            if isinstance(port.parent, getattr(elements, p_instance)):
                n_pumps += 1
            if isinstance(port.parent, elements.PipeFitting):
                if port.parent.guid in total_ports:
                    total_ports[port.parent.guid].append(port)
                else:
                    total_ports[port.parent.guid] = []
                    total_ports[port.parent.guid].append(port)
        # 1st filter, cycle has more than 2 pump-ports, 1 pump
        if n_pumps >= 4:
            cycle_elements = list(dict.fromkeys([v.parent for v in cycle]))
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
        for elem in cycle_elements:
            if cycle_elements.index(final_ports[1].parent) \
                    < cycle_elements.index(elem) < cycle_elements.index(final_ports[2].parent):
                upper.append(elem)
            else:
                lower.append(elem)
        # 3rd Filter, each strand has one or more pumps
        check_up = str(dict.fromkeys(upper))
        check_low = str(dict.fromkeys(lower))

        parallel_pump = cls(name, cycle)
        parallel_pump._elements = cycle_elements
        parallel_pump._up_strand = upper
        parallel_pump._low_strand = lower

        if (p_instance in check_up) and (p_instance in check_low):
            return parallel_pump


class ParallelSpaceHeater(Aggregation):
    """Aggregates Space heater in parallel"""
    aggregatable_elements = ['IfcSpaceHeater', 'PipeStand', 'IfcPipeSegment', 'IfcPipeFitting']

    def __init__(self, name, elements, *args, **kwargs):
        super().__init__(name, elements, *args, **kwargs)
        edge_ports = self._get_start_and_end_ports()
        self.ports.append(AggregationPort(edge_ports[0], parent=self))
        self.ports.append(AggregationPort(edge_ports[1], parent=self))
        self._total_rated_power = None
        self._avg_rated_height = None
        self._total_rated_volume_flow = None
        self._total_diameter = None
        self._total_length = None
        self._avg_diameter_strand = None
        self._elements = None

    def _get_start_and_end_ports(self):
        """
        Finds and sets the first and last port of the parallelpumps

        Assumes all elements in are ordered as connected
        :return ports:
        """
        total_ports = {}
        # all possible beginning and end of the cycle (always pipe fittings), pumps counting
        for port in self.elements:
            if isinstance(port.parent, elements.PipeFitting):
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

    def get_replacement_mapping(self):
        """Returns dict with original ports as values and their aggregated replacement as keys."""
        mapping = {port: None for element in self._elements
                   for port in element.ports}
        for port in self.ports:
            mapping[port.original] = port
        return mapping

    @property
    def rated_power(self):
        """Length of aggregated pipe"""
        if self._total_rated_power is None:
            raise NotImplementedError("Adapt _calc_avg if needed")
        return self._total_rated_power

    @property
    def rated_height(self):
        """Length of aggregated pipe"""
        if self._avg_rated_height is None:
            raise NotImplementedError("Adapt _calc_avg if needed")
        return self._avg_rated_height

    @property
    def rated_volume_flow(self):
        """Length of aggregated pipe"""
        if self._total_rated_volume_flow is None:
            raise NotImplementedError("Adapt _calc_avg if needed")
        return self._total_rated_volume_flow

    @property
    def diameter(self):
        """Diameter of aggregated pipe"""
        if self._total_diameter is None:
            raise NotImplementedError("Adapt _calc_avg if needed")
        return self._total_diameter

    @property
    def length(self):
        """Diameter of aggregated pipe"""
        if self._total_length is None:
            raise NotImplementedError("Adapt _calc_avg if needed")
        return self._total_length

    @property
    def diameter_strand(self):
        """Diameter of aggregated pipe"""
        if self._avg_diameter_strand is None:
            raise NotImplementedError("Adapt _calc_avg if needed")
        return self._avg_diameter_strand

    @classmethod
    def create_on_match(cls, name, cycle):
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
            if isinstance(port.parent, elements.PipeFitting):
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

        instance = cls(name, cycle)
        instance._elements = new_cycle["elements"]
        instance._up_strand = upper
        instance._low_strand = lower

        if (p_instance in check_up) and (p_instance in check_low):
            return instance

# def cycles_reduction(cycles, p_instance):
#     """reduce the found cycles, to just the cycles that fulfill the next criteria:
#     1. it's a parallel cycle (the two strands have the same flow direction)
#     2. it has one or more pumps in each strand
#     finally it creates a list with the founded cycles with the next lists:
#     'elements', 'up_strand', 'low_strand', 'ports'
#     """
#     new_cycles = []
#     for cycle in cycles:
#         n_pumps = 0
#         total_ports = {}
#         new_cycle = {}
#         # all possible beginning and end of the cycle (always pipe fittings), pumps counting
#         for port in cycle:
#             if isinstance(port.parent, getattr(elements, p_instance)):
#                 n_pumps += 1
#             if isinstance(port.parent, elements.PipeFitting):
#                 if port.parent.guid in total_ports:
#                     total_ports[port.parent.guid].append(port)
#                 else:
#                     total_ports[port.parent.guid] = []
#                     total_ports[port.parent.guid].append(port)
#         # 1st filter, cycle has more than 2 pump-ports, 1 pump
#         if n_pumps >= 4:
#             new_cycle["elements"] = list(dict.fromkeys([v.parent for v in cycle]))
#         else:
#             continue
#         # 2nd filter, beginning and end of the cycle (parallel check)
#         final_ports = []
#         for k, ele in total_ports.items():
#             if ele[0].flow_direction == ele[1].flow_direction:
#                 final_ports.append(ele[0])
#                 final_ports.append(ele[1])
#         if len(final_ports) < 4:
#             continue
#         # Strand separation - upper & lower
#         upper = []
#         lower = []
#         for elem in new_cycle["elements"]:
#             if new_cycle["elements"].index(final_ports[1].parent) \
#                     < new_cycle["elements"].index(elem) < new_cycle["elements"].index(final_ports[2].parent):
#                 upper.append(elem)
#             else:
#                 lower.append(elem)
#         new_cycle['up_strand'] = upper
#         new_cycle['low_strand'] = lower
#         new_cycle["ports"] = final_ports
#         # 3rd Filter, each strand has one or more pumps
#         check_up = str(dict.fromkeys(new_cycle['up_strand']))
#         check_low = str(dict.fromkeys(new_cycle['low_strand']))
#         if (p_instance in check_up) and (p_instance in check_low):
#             new_cycles.append(new_cycle)
#     return new_cycles

