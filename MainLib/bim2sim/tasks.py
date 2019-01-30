
from enum import Enum

class LOD(Enum):
    """Level of detail"""
    ignore = 0
    low = 1
    medium = 2
    full = 3



class Task():

    def __init__(self, ductwork:LOD, hull:LOD, consumer:LOD, generator:LOD, hvac:LOD, filters:list=None):
        self.ductwork = ductwork
        self.hull = hull
        self.consumer = consumer
        self.generator = generator
        self.hvac = hvac

        self.filters = filters if filters else []
        

class PlantSimulation(Task):

    def __init__(self):
        return super().__init__(ductwork=LOD.medium, hull=LOD.ignore, consumer=LOD.low, generator=LOD.full, hvac=LOD.low)

