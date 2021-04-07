"""Module for defining workflows"""

from enum import Enum
from bim2sim.project import get_config


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
        self.relevant_ifc_types = (
            'IfcAirTerminal',
            'IfcAirTerminalBox',
            'IfcAirToAirHeatRecovery',
            'IfcBoiler',
            'IfcBurner',
            'IfcChiller',
            'IfcCoil',
            'IfcCompressor',
            'IfcCondenser',
            'IfcCooledBeam',
            'IfcCoolingTower',
            'IfcDamper',
            'IfcDistributionChamberElement',
            'IfcDuctFitting',
            'IfcDuctSegment',
            'IfcDuctSilencer',
            'IfcEngine',
            'IfcEvaporativeCooler',
            'IfcEvaporator',
            'IfcFan',
            'IfcFilter',
            'IfcFlowMeter',
            'IfcHeatExchanger',
            'IfcHumidifier',
            'IfcMedicalDevice',
            'IfcPipeFitting',
            'IfcPipeSegment',
            'IfcPump',
            'IfcSpaceHeater',
            'IfcTank',
            'IfcTubeBundle',
            'IfcUnitaryEquipment',
            'IfcValve',
            'IfcVibrationIsolator',
            #'IfcHeatPump'
        )


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
            spaces=LOD.medium,
            layers=LOD.low,
            # layers=LOD.full,
        )
        self.relevant_ifc_types = (
            'IfcSite',
            'IfcBuilding',
            'IfcBuildingStorey',
            # 'IfcWallElementedCase',
            # 'IfcWallStandardCase',
            'IfcWall',
            'IfcWindow',
            'IfcDoor',
            'IfcSlab',
            'IfcRoof',
            'IfcSpaceHeater',
            'IfcAirTerminal',
            'IfcAirTerminalBox',
        )


class BPSMultiZoneAggregated(Workflow):
    """Building performance simulation with spaces aggregated - aggregations"""

    def __init__(self):
        super().__init__(
            ductwork=LOD.low,
            hull=LOD.medium,
            consumer=LOD.low,
            generator=LOD.ignore,
            hvac=LOD.low,
            spaces=LOD.medium,
            # layers=LOD.low,
            layers=LOD.full,
        )
        self.relevant_ifc_types = (
            'IfcSite',
            'IfcBuilding',
            'IfcBuildingStorey',
            # 'IfcWallElementedCase',
            # 'IfcWallStandardCase',
            'IfcWall',
            'IfcWindow',
            'IfcDoor',
            'IfcSlab',
            'IfcRoof',
            'IfcSpaceHeater',
            'IfcAirTerminal',
            'IfcAirTerminalBox',
        )


class BPSOneZoneAggregated(Workflow):
    """Building performance simulation with spaces aggregated - aggregations"""

    def __init__(self):
        super().__init__(
            ductwork=LOD.low,
            hull=LOD.medium,
            consumer=LOD.low,
            generator=LOD.ignore,
            hvac=LOD.low,
            spaces=LOD.low,
            # layers=LOD.low,
            layers=LOD.full,
        )
        self.relevant_ifc_types = (
            'IfcSite',
            'IfcBuilding',
            'IfcBuildingStorey',
            # 'IfcWallElementedCase',
            # 'IfcWallStandardCase',
            'IfcWall',
            'IfcWindow',
            'IfcDoor',
            'IfcSlab',
            'IfcRoof',
            'IfcSpaceHeater',
            'IfcAirTerminal',
            'IfcAirTerminalBox',
        )