"""Module for defining workflows"""

from enum import Enum

from bim2sim.kernel import elements


class LOD(Enum):
    """Level of detail"""
    ignore = 0  # don't even read from ifc
    low = 1  # reduce to absolute minimum
    medium = 2  # aggregate
    full = 3  # keep full details


class Workflow:
    """Specification of Workflow

    Args:
        ductwork: LOD for ductwork
            low: ...
            medium: ...
            full: ...
        ...
        spaces:
            low: All IfcSpaces of the building will be merged into one
                thermalzone.
            medium: IfcSpaces of the building will be merged together based
                on different criteria. See documentation of
                group_thermal_zones_by_all_criteria() in
                bim2sim.task.bps.bind_tz for more details.
            full: Every IfcSpace will be a separate thermalzone.

        layers_and_materials: LOD for layers and materials
            low: Layer structure and materials will be overwritten by templates.
            full: layer structure and materials will be taken from ifc. If
                material data is missing or not complete, decisions will be
                triggered to fill in the missing data.
    """

    def __init__(self,
                 # hull: LOD,
                 # consumer: LOD,
                 # generator: LOD,
                 # hvac: LOD,
                 # spaces: LOD,
                 layers_and_materials=None,
                 construction_class=None,
                 create_external_elements=False,
                 cfd_export=False,
                 dymola_simulation=False,
                 filters: list = None):

        # self.hull = hull
        # self.consumer = consumer
        # self.generator = generator
        # self.hvac = hvac
        # self.spaces = spaces
        self.layers_and_materials = layers_and_materials
        self.construction_class = construction_class
        self.create_external_elements = create_external_elements
        self.cfd_export = cfd_export
        self.dymola_simulation = dymola_simulation

        #
        # self.infiltration_rate = 0.5
        # self.building_heated = True
        # self.building_cooled = False
        #
        # self.input_params = {
        #     'boolean': [, ],
        #     'floats': [self.infiltration_rate ],
        # }
        # for type, value in self.input_params:
        #     type('boolean')
        # self.boolean_input_params = []

        self.filters = filters if filters else []
        self.ifc_units = {}  # dict to store project related units

        self.relevant_elements = []

        # default values
        self.pipes = LOD.medium
        self.underfloorheatings = LOD.medium
        self.pumps = LOD.medium

        self.simulated = False

    def update_from_config(self, config):
        """Updates the workflow specification from the config file"""
        self.pipes = LOD(config['Aggregation'].getint('Pipes', 2))
        self.underfloorheatings = LOD(config['Aggregation'].getint(
            'UnderfloorHeating', 2))
        self.pumps = LOD(config['Aggregation'].getint('Pumps', 2))
        if not self.layers_and_materials:
            self.layers_and_materials = LOD(config['LayersAndMaterials'].getint(
                'LayersAndMaterials', 2))
        if not self.construction_class:
            self.construction_class = LOD(config['ConstructionClass'].getint(
                'ConstructionClass', 2))


class PlantSimulation(Workflow):
    # todo split parameters into building and plant simulation
    # todo make parameters selectable and settable from backend
    # todo add new parameters for heating, cooling, zone aggregation, hvac aggregation
    # todo: do we still need lods?
    def __init__(self,
                 ductwork=LOD.low):
        super().__init__(
            # hull=LOD.ignore,
            # consumer=LOD.low,
            # generator=LOD.full,
            # hvac=LOD.low,
            # spaces=LOD.ignore,
            layers_and_materials=LOD.full,
        )
        self.ductwork=ductwork

class BuildingSimulation(Workflow):

    def __init__(self, building_parameters):
        super().__init__()

class BPSMultiZoneSeparatedLayersFull(Workflow):
    """Building performance simulation with every space as single zone
    separated from each other - no aggregation.
    Detailed layer information required."""

    def __init__(self):
        super().__init__(
            # hull=LOD.medium,
            # consumer=LOD.low,
            # generator=LOD.ignore,
            # hvac=LOD.low,
            # spaces=LOD.full,
            # layers=LOD.low,
            layers_and_materials=LOD.full,
        )



class BPSMultiZoneSeparatedLayersLow(Workflow):
    """Building performance simulation with every space as single zone
    separated from each other - no aggregation.
    Not existing layer information is enriched by templates."""

    def __init__(self):
        super().__init__(
            # hull=LOD.medium,
            # consumer=LOD.low,
            # generator=LOD.ignore,
            # hvac=LOD.low,
            # spaces=LOD.full,
            layers_and_materials=LOD.low,
        )


class BPSMultiZoneCombinedLayersFull(Workflow):
    """Building performance simulation with aggregation based on zone
    aggregation algorithms.
    Detailed layer information required."""

    def __init__(self):
        super().__init__(
            # hull=LOD.medium,
            # consumer=LOD.low,
            # generator=LOD.ignore,
            # hvac=LOD.low,
            # spaces=LOD.medium,
            layers_and_materials=LOD.full,
        )
        self.materials = None


class BPSMultiZoneCombinedLayersLow(Workflow):
    """Building performance simulation with aggregation based on zone
    aggregation algorithms.
    Not existing layer information is enriched by templates."""

    def __init__(self):
        super().__init__(
            # hull=LOD.medium,
            # consumer=LOD.low,
            # generator=LOD.ignore,
            # hvac=LOD.low,
            # spaces=LOD.medium,
            layers_and_materials=LOD.low,
        )


class BPSMultiZoneAggregatedLayersLow(Workflow):
    """Building performance simulation with spaces aggregated.
     Not existing layer information is enriched by templates."""

    def __init__(self):
        super().__init__(
            # hull=LOD.medium,
            # consumer=LOD.low,
            # generator=LOD.ignore,
            # hvac=LOD.low,
            # spaces=LOD.medium,
            layers_and_materials=LOD.low,
        )

class BPSMultiZoneAggregatedLayersLowSimulation(Workflow):
    """Building performance simulation with spaces aggregated.
     Not existing layer information is enriched by templates."""

    def __init__(self):
        super().__init__(
            # hull=LOD.medium,
            # consumer=LOD.low,
            # generator=LOD.ignore,
            # hvac=LOD.low,
            # spaces=LOD.medium,
            layers_and_materials=LOD.low,
            dymola_simulation=True
        )


class BPSMultiZoneAggregatedLayersFull(Workflow):
    """Building performance simulation with spaces aggregated.
    Detailed layer information required."""

    def __init__(self):
        super().__init__(
            # hull=LOD.medium,
            # consumer=LOD.low,
            # generator=LOD.ignore,
            # hvac=LOD.low,
            # spaces=LOD.medium,
            layers_and_materials=LOD.full,
        )


class BPSOneZoneAggregatedLayersLow(Workflow):
    """Building performance simulation with all rooms aggregated to one thermal
    zone. Not existing layer information is enriched by templates."""

    def __init__(self):
        super().__init__(
            # hull=LOD.medium,
            # consumer=LOD.low,
            # generator=LOD.ignore,
            # hvac=LOD.low,
            # spaces=LOD.low,
            layers_and_materials=LOD.low,
            # layers=LOD.full,
        )


class BPSOneZoneAggregatedLayersFull(Workflow):
    """Building performance simulation with all rooms aggregated to one thermal
    zone. Detailed layer information required."""

    def __init__(self):
        super().__init__(
            # hull=LOD.medium,
            # consumer=LOD.low,
            # generator=LOD.ignore,
            # hvac=LOD.low,
            # spaces=LOD.low,
            layers_and_materials=LOD.full,
        )


class BPSMultiZoneSeparatedEP(Workflow):
    """Building performance simulation with every space as single zone
    separated from each other - no aggregation,
    used within the EnergyPlus Workflow"""

    def __init__(self):
        super().__init__(
            # hull=LOD.medium,
            # consumer=LOD.low,
            # generator=LOD.ignore,
            # hvac=LOD.low,
            # spaces=LOD.full,
            layers_and_materials=LOD.low,
            create_external_elements=True,  # consider IfcExternalSpatialElements
            cfd_export=False,
        )


class BPSMultiZoneSeparatedEPfull(Workflow):
    """Building performance simulation with every space as single zone
    separated from each other - no aggregation,
    used within the EnergyPlus Workflow"""

    def __init__(self):
        super().__init__(
            # hull=LOD.medium,
            # consumer=LOD.low,
            # generator=LOD.ignore,
            # hvac=LOD.low,
            # spaces=LOD.full,
            layers_and_materials=LOD.full,
            create_external_elements=True,  # consider IfcExternalSpatialElements
            cfd_export=False,
        )


class BPSMultiZoneSeparatedEPforCFD(Workflow):
    """Building performance simulation with every space as single zone
    separated from each other - no aggregation,
    used within the EnergyPlus Workflow for CFD export (exports STL and
    surface inside face temperatures)"""

    def __init__(self):
        super().__init__(
            # hull=LOD.medium,
            # consumer=LOD.low,
            # generator=LOD.ignore,
            # hvac=LOD.low,
            # spaces=LOD.full,
            layers_and_materials=LOD.low,
            create_external_elements=True,  # consider IfcExternalSpatialElements
            cfd_export=True,
        )


class CFDWorkflowDummy(Workflow):
    # todo make something useful
    def __init__(self):
        super().__init__(
            # hull=LOD.medium,
            # consumer=LOD.low,
            # generator=LOD.ignore,
            # hvac=LOD.low,
            # spaces=LOD.full,
            layers_and_materials=LOD.full,
            create_external_elements=True,  # consider IfcExternalSpatialElements
        )
