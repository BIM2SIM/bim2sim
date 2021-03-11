"""Module for defining workflows"""

import inspect

from enum import Enum
from bim2sim.project import get_config
from bim2sim.kernel import elements


class LOD(Enum):
    """Level of detail"""
    ignore = 0  # don't even read from ifc
    low = 1  # reduce to absolute minimum
    medium = 2  # aggregate
    full = 3  # keep full details


# TODO: config Aggregation can overwrite LODs
class Workflow:
    """Specification of Workflow"""

    def __init__(self,
                 ductwork: LOD,
                 hull: LOD,
                 consumer: LOD,
                 generator: LOD,
                 hvac: LOD,
                 spaces: LOD,
                 layers: LOD,
                 filters: list = None):

        self.ductwork = ductwork
        self.hull = hull
        self.consumer = consumer
        self.generator = generator
        self.hvac = hvac
        self.spaces = spaces
        self.layers = layers

        self.filters = filters if filters else []

        self.relevant_ifc_types = None

        # TODO: defaults should come from Workflow child classes
        config = get_config()
        self.pipes = LOD(config['Aggregation'].getint('Pipes', 2))
        self.underfloorheatings = LOD(config['Aggregation'].getint('UnderfloorHeating', 2))
        self.pumps = LOD(config['Aggregation'].getint('Pumps', 2))

    def get_relevant_ifc_types(self):
        relevant_ifc_types = []
        workflow_name = self.__str__()
        for name, obj in inspect.getmembers(elements):
            if inspect.isclass(obj) and hasattr(obj, 'workflow'):
                if workflow_name in obj.workflow:
                    extend_ifc_types = obj.ifc_type
                    if type(obj.ifc_type) is not list:
                        extend_ifc_types = [obj.ifc_type]
                    for ifc_type in extend_ifc_types:
                        if ifc_type not in relevant_ifc_types:
                            relevant_ifc_types.append(ifc_type)

        return relevant_ifc_types

    def __str__(self):
        return "%s" % self.__class__.__name__


class PlantSimulation(Workflow):

    def __init__(self):
        super().__init__(
            ductwork=LOD.low,
            hull=LOD.ignore,
            consumer=LOD.low,
            generator=LOD.full,
            hvac=LOD.low,
            spaces=LOD.ignore,
            layers=LOD.full,
        )
        self.relevant_ifc_types = self.get_relevant_ifc_types()


class BPSMultiZoneSeparated(Workflow):
    """Building performance simulation with every space as single zone
    separated from each other - no aggregation"""

    def __init__(self):
        super().__init__(
            ductwork=LOD.low,
            hull=LOD.medium,
            consumer=LOD.low,
            generator=LOD.ignore,
            hvac=LOD.low,
            spaces=LOD.low,
            # spaces=LOD.medium,
            layers=LOD.low,
            # layers=LOD.full,
        )
        self.relevant_ifc_types = self.get_relevant_ifc_types()
