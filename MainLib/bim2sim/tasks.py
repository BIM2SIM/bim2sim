"""Module for defining tasks"""

from enum import Enum
from bim2sim.project import get_config


class LOD(Enum):
    """Level of detail"""
    ignore = 0  # don't even read from ifc
    low = 1  # reduce to absolute minimum
    medium = 2  # aggregate
    full = 3  # keep full details


# TODO: config Aggregation can overwrite LODs
class Task:
    """Specification of task"""

    def __init__(self,
                 ductwork: LOD,
                 hull: LOD,
                 consumer: LOD,
                 generator: LOD,
                 hvac: LOD,
                 filters: list = None):

        self.ductwork = ductwork
        self.hull = hull
        self.consumer = consumer
        self.generator = generator
        self.hvac = hvac

        self.filters = filters if filters else []

        # TODO: defaults should come from Task child classes
        config = get_config()
        # @diego: add [Aggregation] to config file
        self.pipes = LOD(config['Aggregation'].getint('Pipes', 2))
        self.underfloorheatings = LOD(config['Aggregation'].getint('UnderfloorHeating', 2))
        self.pumps = LOD(config['Aggregation'].getint('Pumps', 2))


class PlantSimulation(Task):

    def __init__(self):
        super().__init__(
            ductwork=LOD.low,
            hull=LOD.ignore,
            consumer=LOD.low,
            generator=LOD.full,
            hvac=LOD.low,
        )
