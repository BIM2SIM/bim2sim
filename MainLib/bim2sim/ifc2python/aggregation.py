"""Module for aggregation and simplifying elements"""

import logging


#class AggregationPort():
#    def __init__(self, parent):
#        self.parent = parent
#        self.connections = []


class Aggregation():
    """Base aggregation of models"""
    def __init__(self, name, elements):
        self.logger = logging.getLogger(__name__)
        self.name = name
        self.elements = elements
        for model in self.elements:
            model.aggregation = self

    def __repr__(self):
        return "<%s '%s' (aggregation of %d elements)>" % (
            self.__class__.__name__, self.name, len(self.elements))


class PipeStrand(Aggregation):
    """Aggregates pipe strands"""
    aggregatable_elements = ['IfcPipeSegment', 'IfcPipeFitting']

    def __init__(self, name, elements):
        super().__init__(name, elements)
        self.ports = self._get_start_and_end_ports()
        self._total_length = None
        self._avg_diameter = None


    def _get_start_and_end_ports(self):
        """
        Finds and sets the first and last port of the pipestrand.

        Assumes all elements in cycle are ordered as connected
        :return ports:
        """
        agg_ports = []
        # first port
        found_in = False
        found_out = False
        for port in self.elements[0].ports:
            if not port.connection:
                continue #end node
            if not port.connection.parent in self.elements:
                found_out = True
                port.aggregated_parent = self
                agg_ports.append(port)
            else:
                found_in = True
        if not (found_in and found_out):
            raise AssertionError("Assumtion of ordered elements violated")

        # last port
        found_in = False
        found_out = False
        for port in self.elements[-1].ports:
            if not port.connection.parent in self.elements:
                found_out = True
                port.aggregated_parent = self
                agg_ports.append(port)
            else:
                found_in = True
        if not (found_in and found_out):
            raise AssertionError("Assumtion of ordered elements violated")

        return agg_ports

    def _calc_avg(self):
        """Calculates the total length and average diameter of all pipe-like
         elements."""
        self._total_length = 0
        self._avg_diameter = 0
        diameter_times_length = 0

        for pipe in self.elements:
            if hasattr(pipe, "diameter") and hasattr(pipe, "length"):
                length = pipe.length
                diameter = pipe.diameter
                if not (length and diameter):
                    self.logger.warning("Ignored '%s' in aggregation", pipe)
                    continue

                diameter_times_length += diameter*length
                self._total_length += length

            else:
                self.logger.warning("Ignored '%s' in aggregation", pipe)
        if self._total_length == 0:
            self._avg_diameter = diameter_times_length / self._total_length

    @property
    def diameter(self):
        """Diameter of aggregated pipe"""
        if not self._avg_diameter:
            self._calc_avg()
        return self._avg_diameter

    @property
    def length(self):
        """Length of aggregated pipe"""
        if not self._total_length:
            self._calc_avg()
        return self._total_length
