"""Module for aggregation and simplifying elements"""

import logging
import math
from collections import defaultdict

import numpy as np

from bim2sim.ifc2python.element import BaseElement, BasePort
from bim2sim.ifc2python import elements


class AggregationPort(BasePort):
    """Port for Aggregation"""

    def __init__(self, original, *args, **kwargs):
        if 'guid' not in kwargs:
            kwargs['guid'] = self.get_id("AggPort")
        super().__init__(*args, **kwargs)
        self.original = original

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

        self._total_length = None
        self._avg_diameter = None

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

    def _calc_avg(self):
        """Calculates the total length and average diameter of all pipe-like
         elements."""
        self._total_length = 0
        self._avg_diameter = 0
        diameter_times_length = 0

        for pipe in self.elements:
            length = getattr(pipe, "length")
            diameter = getattr(pipe, "diameter")
            if not (length and diameter):
                self.logger.warning("Ignored '%s' in aggregation", pipe)
                continue

            diameter_times_length += diameter*length
            self._total_length += length

        if self._total_length != 0:
            self._avg_diameter = diameter_times_length / self._total_length

    def get_replacement_mapping(self):
        """Returns dict with original ports as values and their aggregated replacement as keys."""
        mapping = {port: None for element in self.elements
                   for port in element.ports}
        for port in self.ports:
            mapping[port.original] = port
        return mapping

    @property
    def diameter(self):
        """Diameter of aggregated pipe"""
        if self._avg_diameter is None:
            self._calc_avg()
        return self._avg_diameter

    @property
    def length(self):
        """Length of aggregated pipe"""
        if self._total_length is None:
            self._calc_avg()
        return self._total_length


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

    def __init__(self, name, elements, cycle, *args, **kwargs):
        self.cycle = cycle
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

    def _get_start_and_end_ports(self):
        """
        Finds and sets the first and last port of the parallelpumps

        Assumes all elements in are ordered as connected
        :return ports:
        """

        agg_ports = []
        # first port
        port = self.elements[0].ports[1]
        port.aggregated_parent = self
        agg_ports.append(port)
        # last port
        port = self.elements[-1].ports[1]
        port.aggregated_parent = self
        agg_ports.append(port)
        return agg_ports

    def _calc_avg(self):
        """Calculates the parameters of all pump-like elements."""
        self._total_rated_power = 0
        self._avg_rated_height = 0
        self._total_rated_volume_flow = 0
        self._total_diameter = 0
        self._avg_diameter_strand = 0
        self._total_length = 0
        diameter_times_length = 0

        for pump in self.elements:
            if "Pump" in str(pump):
                rated_power = getattr(pump, "rated_power")
                rated_height = getattr(pump, "rated_height")
                rated_volume_flow = getattr(pump, "rated_volume_flow")
                diameter = getattr(pump, "diameter")
                if not (rated_power and rated_height and rated_volume_flow and diameter):
                    self.logger.warning("Ignored '%s' in aggregation", pump)
                    continue

                self._total_rated_volume_flow += rated_volume_flow
                if self._avg_rated_height != 0:
                    if rated_height < self._avg_rated_height:
                        self._avg_rated_height = rated_height
                else:
                    self._avg_rated_height = rated_height

                self._total_diameter = self._total_diameter + diameter ** 2
            else:
                if hasattr(pump, "diameter") and hasattr(pump, "length"):
                    length = pump.length
                    diameter = pump.diameter
                    if not (length and diameter):
                        self.logger.warning("Ignored '%s' in aggregation", pump)
                        continue

                    diameter_times_length += diameter * length
                    self._total_length += length

                else:
                    self.logger.warning("Ignored '%s' in aggregation", pump)

        if self._total_length != 0:
            self._avg_diameter_strand = diameter_times_length / self._total_length

        self._total_diameter = math.sqrt(self._total_diameter)
        g = 9.81
        rho = 1000
        self._total_rated_power = self.rated_volume_flow * self.rated_height * g * rho

    def get_replacement_mapping(self):
        """Returns dict with original ports as values and their aggregated replacement as keys."""
        mapping = {port: None for element in self.elements
                   for port in element.ports}
        for port in self.ports:
            mapping[port.original] = port
        return mapping

    @property
    def rated_power(self):
        """Length of aggregated pipe"""
        if self._total_rated_power is None:
            self._calc_avg()
        return self._total_rated_power

    @property
    def rated_height(self):
        """Length of aggregated pipe"""
        if self._avg_rated_height is None:
            self._calc_avg()
        return self._avg_rated_height

    @property
    def rated_volume_flow(self):
        """Length of aggregated pipe"""
        if self._total_rated_volume_flow is None:
            self._calc_avg()
        return self._total_rated_volume_flow

    @property
    def diameter(self):
        """Diameter of aggregated pipe"""
        if self._total_diameter is None:
            self._calc_avg()
        return self._total_diameter

    @property
    def length(self):
        """Diameter of aggregated pipe"""
        if self._total_length is None:
            self._calc_avg()
        return self._total_length

    @property
    def diameter_strand(self):
        """Diameter of aggregated pipe"""
        if self._avg_diameter_strand is None:
            self._calc_avg()
        return self._avg_diameter_strand


def cycles_reduction(cycles):
    """reduce the found cycles, to just the cycles that fulfill the next criteria:
    1. it's a parallel cycle (the two strands have the same flow direction)
    2. it has one or more pumps in each strand
    finally it creates a list with the founded cycles with the next lists:
    'elements', 'up_strand', 'low_strand', 'ports'
    """

    for cycle in cycles:
        length_cycle = len(cycle)
        cycle.append([])
        for port in cycle[:length_cycle]:
            if isinstance(port.parent, elements.PipeFitting):
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
        if len(cycles[i][length_a - 1]) != 4:
            cycles.remove(cycles[i])
            length = length - 1
            continue
        i = i + 1
    New_cycles = []
    n_cycle = 0
    for cycle in cycles:
        New_cycles.append([])
        len_aux = len(cycle) - 1
        cycle.append([])
        cycle[len(cycle) - 1].append([])
        cycle[len(cycle) - 1].append([])
        for port in cycle[:len_aux]:
            if cycle.index(cycle[len_aux][1]) < cycle.index(port) < cycle.index(cycle[len_aux][2]):
                cycle[len(cycle) - 1][1].append(port)
            elif (cycle.index(port) < cycle.index(cycle[len_aux][0])) and (port not in cycle[len_aux]):
                cycle[len(cycle) - 1][0].append(port)
            elif (cycle.index(port) > cycle.index(cycle[len_aux][3])) and (port not in cycle[len_aux]):
                cycle[len(cycle) - 1][0].append(port)

        n_item = 0
        for item in cycle[-1]:
            New_cycles[n_cycle].append([])
            if n_item == 0:
                New_cycles[n_cycle][n_item].append(cycle[len_aux][3].parent)
            else:
                New_cycles[n_cycle][n_item].append(cycle[len_aux][0].parent)
            for port in item[0::2]:
                New_cycles[n_cycle][n_item].append(port.parent)
            if n_item == 0:
                New_cycles[n_cycle][n_item].append(cycle[len_aux][0].parent)
            else:
                New_cycles[n_cycle][n_item].append(cycle[len_aux][2].parent)
            n_item += 1
        New_cycles[n_cycle].append(cycle[-2])
        n_cycle += 1

    for cycle in New_cycles:
        for strand in cycle[0:2]:
            n_element = 0
            for item in strand:
                if isinstance(item, elements.Pump):
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

    keys = ['elements', 'up_strand', 'low_strand', 'ports']
    for cycle in New_cycles:
        elements_aux = []
        for element in cycle[0][:len(cycle[0]) - 1]:
            elements_aux.append(element)
        for element in cycle[1][len(cycle[1]) - 2::-1]:
            elements_aux.append(element)
        cycle.insert(0, elements_aux)
    reduced_cycles = []
    for cycle in New_cycles:
        reduced_cycles.append(dict(zip(keys, cycle)))

    return reduced_cycles
