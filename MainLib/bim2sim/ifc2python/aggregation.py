"""Module for aggregation and simplifying elements"""

import logging


class AggregationPort():
    def __init__(self, parent):
        self.parent = parent
        self.connections = []


class Aggregation():
    """Base aggregation of models"""
    def __init__(self, name, models):
        self.logger = logging.getLogger(__name__)
        self.name = name
        self.models = models

    def __repr__(self):
        return "<%s (aggregation of %d elements)>" % (self.__class__.__name__,
                                                      len(self.models))


class PipeStrand(Aggregation):
    """Aggregates pipe strands"""
    aggregatable_elements = ['IfcPipeSegment', 'IfcPipeFitting']
# Todo first and last port of pipestrand
    def __init__(self, name, models):
        super().__init__(name, models)
        self.ports = []
        # self.find_outer_connections()
        self._total_length = None
        self._avg_diameter = None

    def add_port(self, port):
        self.ports.append(port)

    # def convert_pipes_to_pipestrand(self):

    # def find_outer_connections(self):
    #     for pipe in self.models:
    #         print(pipe)

    def _calc_avg(self):
        """Calculates the total length and average diameter of all pipe-like
         elements."""
        self._total_length = 0
        self._avg_diameter = 0
        diameter_times_length = 0

        for pipe in self.models:
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
        self._avg_diameter = diameter_times_length / self._total_length


    @property
    def diameter(self):
        if not self._avg_diameter:
            self._calc_avg()
        return self._avg_diameter

    @property
    def length(self):
        if not self._total_length:
            self._calc_avg()
        return self._total_length
