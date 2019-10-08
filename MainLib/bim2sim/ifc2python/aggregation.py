"""Module for aggregation and simplifying elements"""

import logging

from bim2sim.ifc2python.element import BaseElement, BasePort


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
            #TODO: make guid reproducable unique for same aggregation elements
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
        mapping = {port:None for element in self.elements
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


class ThermalZone(Aggregation):
    ifc_type = "IfcZone"

    @property
    def area(self):
        return 1

    @property
    def u_value(self):
        return 1

    @property
    def max_temperature(self):
        return 1

    @property
    def min_temperature(self):
        return 1

    @property
    def zone_spaces(self):
        return 1


def group_by_range(elements, range_group, parameter):

    groups = {}
    for element in elements:
        if hasattr(element, parameter):
            attribute = int(getattr(element, parameter))

            # if str(attribute) in groups:
            #     groups[str(attribute)].append(element)
            # else:
            #     groups[str(attribute)] = []
            #     groups[str(attribute)].append(element)

            if str(attribute) in groups:
                groups[str(attribute)].append(element)
            elif str(attribute + range_group) in groups:
                groups[str(attribute + range_group)].append(element)
            elif str(attribute - range_group) in groups:
                groups[str(attribute - range_group)].append(element)
            else:
                groups[str(attribute)] = []
                groups[str(attribute)].append(element)

    x = dict(groups)
    for group in x:
        if len(groups[str(group)]) < 2:
            del groups[str(group)]

    return groups
