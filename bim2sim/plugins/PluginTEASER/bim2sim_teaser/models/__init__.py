"""Package for Python representations of TEASER models"""
from teaser.logic.buildingobjects.building import Building as Building_Teaser
from teaser.logic.buildingobjects.buildingphysics.door \
    import Door as Door_Teaser
from teaser.logic.buildingobjects.buildingphysics.floor \
    import Floor as Floor_Teaser
from teaser.logic.buildingobjects.buildingphysics.ceiling \
    import Ceiling as Ceiling_Teaser
from teaser.logic.buildingobjects.buildingphysics.groundfloor \
    import GroundFloor as GroundFloor_Teaser
from teaser.logic.buildingobjects.buildingphysics.innerwall \
    import InnerWall as InnerWall_Teaser
from teaser.logic.buildingobjects.buildingphysics.layer \
    import Layer as Layer_Teaser
from teaser.logic.buildingobjects.buildingphysics.material \
    import Material as Material_Teaser
from teaser.logic.buildingobjects.buildingphysics.outerwall \
    import OuterWall as OuterWall_Teaser
from teaser.logic.buildingobjects.buildingphysics.rooftop \
    import Rooftop as Rooftop_Teaser
from teaser.logic.buildingobjects.buildingphysics.window \
    import Window as Window_Teaser
from teaser.logic.buildingobjects.thermalzone import \
    ThermalZone as ThermalZone_Teaser
from teaser.logic.buildingobjects.useconditions import \
    UseConditions as UseConditions_Teaser
from teaser.logic.buildingobjects.buildingsystems.buildingahu import \
    BuildingAHU as BuildingAHU_Teaser

from bim2sim.elements.aggregation.bps_aggregations import AggregatedThermalZone
from bim2sim.elements import bps_elements as bps
from bim2sim.elements.aggregation import bps_aggregations as bps_aggr
from bim2sim.elements.mapping.units import ureg
from bim2sim.plugins.PluginTEASER.bim2sim_teaser import export


class TEASER(export.TEASERExportInstance):
    library = "TEASER"


class Building(TEASER, Building_Teaser):
    represents = [bps.Building]

    def __init__(self, bim2sim_element, parent):
        Building_Teaser.__init__(self, parent=parent)
        TEASER.__init__(self, bim2sim_element)
        self.used_library_calc = "AixLib"
        self.add_thermal_zones_to_building()
        if bim2sim_element.with_ahu:
            self.central_ahu = BuildingAHU(
                element=bim2sim_element, parent=self)

    def add_thermal_zones_to_building(self):
        for tz in self.element.thermal_zones:
            ThermalZone(tz, parent=self)

    def request_params(self):
        self.request_param("bldg_name", None, "name")
        self.request_param("year_of_construction",
                           self.check_numeric(
                               min_value=0 * ureg.year), export_unit=ureg.year)
        self.request_param("number_of_storeys",
                           self.check_numeric(
                               min_value=1 * ureg.dimensionless),
                           "number_of_floors")
        self.request_param("avg_storey_height",
                           self.check_numeric(
                               min_value=1 * ureg.meter),
                           "height_of_floors")
        # todo workaround until setter method is changed in TEASER, see TEASER
        #  issue #772
        self.request_param("with_ahu", export_name="_with_ahu")


class ThermalZone(TEASER, ThermalZone_Teaser):
    represents = [bps.ThermalZone, AggregatedThermalZone]

    def __init__(self, element, parent):
        ThermalZone_Teaser.__init__(self, parent=parent)
        TEASER.__init__(self, element)
        self.number_of_elements = 2
        self.use_conditions = UseConditions(element=element, parent=self)
        self.add_elements_to_thermal_zone()

    def add_elements_to_thermal_zone(self):
        for bound_element in self.element.bound_elements:
            export.TEASERExportInstance.factory(bound_element, parent=self)

    def request_params(self):
        if self.element.guid:
            self.name = self.element.guid
        else:
            self.request_param("name", None)
        self.request_param("net_area",
                           self.check_numeric(
                               min_value=0 * ureg.meter ** 2),
                           "area")
        self.request_param("t_ground", None)
        self.request_param("net_volume",
                           None,
                           "volume")


class BuildingAHU(TEASER, BuildingAHU_Teaser):
    represents = []

    def __init__(self, element, parent):
        BuildingAHU_Teaser.__init__(self, parent=parent)
        self.overwrite_teaser_defaults()
        TEASER.__init__(self, element)

    def overwrite_teaser_defaults(self):
        """Overwrites default BuildingAHU values from TEASER

        This is required as TEASER sets defaults for e.g. the AHU setup and in
        enrichment we only enrich not-existing values. Without setting the
        defaults back to None would lead to errors.
        """
        self.heating = None
        self.cooling = None
        self.dehumidification = None
        self.humidification = None
        self.heat_recovery = None
        self.efficiency_recovery = None

    def request_params(self):
        self.request_param("ahu_heating", export_name="heating")
        self.request_param("ahu_cooling", export_name="cooling")
        self.request_param("ahu_dehumidification",
                           export_name="dehumidification")
        self.request_param("ahu_humidification", export_name="humidification")
        self.request_param("ahu_heat_recovery", export_name="heat_recovery")
        self.request_param("ahu_heat_recovery_efficiency",
                           export_name="efficiency_recovery")


class UseConditions(TEASER, UseConditions_Teaser):
    represents = []

    def __init__(self, element, parent):
        UseConditions_Teaser.__init__(self, parent=parent)
        self.overwrite_teaser_defaults()
        TEASER.__init__(self, element)

    def overwrite_teaser_defaults(self):
        """Overwrites default use conditions values from TEASER

        This is required as TEASER sets defaults for e.g. the usage and in
        enrichment we only enrich not-existing values. Without setting the
        defaults back to None would lead to errors.
        """
        self.usage = None

        self.typical_length = None
        self.typical_width = None

        self.with_heating = True
        self.with_cooling = False
        self.T_threshold_heating = None
        self.T_threshold_cooling = None

        self.fixed_heat_flow_rate_persons = None
        self.activity_degree_persons = None
        self._persons = None
        self.internal_gains_moisture_no_people = None
        self.ratio_conv_rad_persons = None

        self.machines = None
        self.ratio_conv_rad_machines = None

        self.use_maintained_illuminance = None
        self.lighting_power = None
        self.fixed_lighting_power = None
        self.ratio_conv_rad_lighting = None
        self.maintained_illuminance = None
        self.lighting_efficiency_lumen = None

        self.use_constant_infiltration = None
        self.infiltration_rate = None
        self.max_user_infiltration = None
        self.max_overheating_infiltration = []
        self.max_summer_infiltration = []
        self.winter_reduction_infiltration = []

        self.min_ahu = None
        self.max_ahu = None
        self.with_ahu = None

        self._first_saturday_of_year = 1
        self.profiles_weekend_factor = None

        self._set_back_times = None
        self.heating_set_back = -2
        self.cooling_set_back = 2

        self._adjusted_opening_times = None

        self._with_ideal_thresholds = False

        self._heating_profile = []
        self._cooling_profile = []
        self._persons_profile = []
        self._machines_profile = []
        self._lighting_profile = []

        self._schedules = None

    def request_params(self):
        self.request_param("name", None)
        self.request_param("with_cooling", None)
        self.request_param("with_heating", None)
        self.request_param("with_ahu", None)
        self.request_param("heating_profile", None)
        self.request_param("cooling_profile", None)
        self.request_param("persons", None)
        self.request_param("typical_length", None)
        self.request_param("typical_width", None)
        self.request_param("T_threshold_heating", None)
        self.request_param("activity_degree_persons", None)
        self.request_param("fixed_heat_flow_rate_persons", None,
                           export_unit=ureg.W)
        self.request_param("internal_gains_moisture_no_people", None)
        self.request_param("T_threshold_cooling", None)
        self.request_param("ratio_conv_rad_persons", None)
        self.request_param("machines", None, export_unit=ureg.W)
        self.request_param("ratio_conv_rad_machines", None)
        self.request_param("lighting_power", None, export_unit=ureg.W)
        self.request_param("fixed_lighting_power", None, export_unit=ureg.W)
        self.request_param("ratio_conv_rad_lighting", None)
        self.request_param("maintained_illuminance", None)
        self.request_param("lighting_efficiency_lumen", None)
        self.request_param("use_maintained_illuminance", None)
        self.request_param("use_constant_infiltration", None)
        self.request_param("infiltration_rate", None)
        self.request_param("max_user_infiltration", None)
        self.request_param("max_overheating_infiltration", None)
        self.request_param("max_summer_infiltration", None)
        self.request_param("winter_reduction_infiltration", None)
        self.request_param("min_ahu", None)
        self.request_param("max_ahu", None)
        self.request_param("with_ideal_thresholds", None)
        self.request_param("persons_profile", None)
        self.request_param("machines_profile", None)
        self.request_param("lighting_profile", None)
        self.request_param("usage", None)


class ElementWithLayers(TEASER):

    def __init__(self, element):
        self.add_layers_to_element(element)
        super().__init__(element)

    def add_layers_to_element(self, element):
        if element.layerset:
            if element.layerset.layers:
                for layer in element.layerset.layers:
                    Layer(layer, parent=self)

    def __repr__(self):
        return "<%s>" % type(self).__name__


class InnerWall(ElementWithLayers, InnerWall_Teaser):
    represents = [
        bps.InnerDoor,
        bps.InnerWall,
        bps_aggr.InnerWallDisaggregated
    ]

    def __init__(self, element, parent):
        InnerWall_Teaser.__init__(self, parent=parent)
        ElementWithLayers.__init__(self, element)

    def request_params(self):
        self.orientation = self.element.orientation
        self.request_param("net_area",
                           self.check_numeric(min_value=0 * ureg.m ** 2),
                           "area")
        self.request_param("inner_convection",
                           self.check_numeric(
                               min_value=0 * ureg.W / ureg.K / ureg.meter **
                                         2),
                           "inner_convection")


class OuterWall(ElementWithLayers, OuterWall_Teaser):
    represents = [bps.OuterWall, bps_aggr.OuterWallDisaggregated]

    def __init__(self, element, parent):
        OuterWall_Teaser.__init__(self, parent=parent)
        ElementWithLayers.__init__(self, element)

    def request_params(self):
        self.orientation = self.element.orientation
        self.request_param("net_area",
                           self.check_numeric(min_value=0 * ureg.m ** 2),
                           "area")
        self.request_param("tilt", None, "tilt")


class Rooftop(ElementWithLayers, Rooftop_Teaser):
    represents = [bps.Roof, bps_aggr.RoofDisaggregated]

    def __init__(self, element, parent):
        Rooftop_Teaser.__init__(self, parent=parent)
        ElementWithLayers.__init__(self, element)

    def request_params(self):
        self.request_param("net_area",
                           self.check_numeric(min_value=0 * ureg.m ** 2),
                           "area")


class Floor(ElementWithLayers, Floor_Teaser):
    represents = [bps.InnerFloor, bps_aggr.InnerFloorDisaggregated]

    def __init__(self, element, parent):
        Floor_Teaser.__init__(self, parent=parent)
        ElementWithLayers.__init__(self, element)

    def request_params(self):
        self.request_param("net_area",
                           self.check_numeric(min_value=0 * ureg.m ** 2),
                           "area")


class Ceiling(ElementWithLayers, Ceiling_Teaser):
    represents = [bps.InnerFloor, bps_aggr.InnerFloorDisaggregated]

    def __init__(self, element, parent):
        Ceiling_Teaser.__init__(self, parent=parent)
        ElementWithLayers.__init__(self, element)

    def request_params(self):
        self.request_param("net_area",
                           self.check_numeric(min_value=0 * ureg.m ** 2),
                           "area")


class GroundFloor(ElementWithLayers, GroundFloor_Teaser):
    represents = [bps.GroundFloor, bps_aggr.GroundFloorDisaggregated]

    def __init__(self, element, parent):
        GroundFloor_Teaser.__init__(self, parent=parent)
        ElementWithLayers.__init__(self, element)

    def request_params(self):
        self.request_param("net_area",
                           self.check_numeric(min_value=0 * ureg.m ** 2),
                           "area")


class Window(ElementWithLayers, Window_Teaser):
    represents = [bps.Window, bps_aggr.WindowDisaggregated]

    def __init__(self, element, parent):
        Window_Teaser.__init__(self, parent=parent)
        ElementWithLayers.__init__(self, element)

    def request_params(self):
        self.orientation = self.element.orientation
        self.request_param("gross_area",
                           self.check_numeric(min_value=0 * ureg.m ** 2),
                           "area")
        self.request_param("a_conv", None)
        self.request_param("g_value", None)
        self.request_param("inner_convection", None)
        self.request_param("inner_radiation", None)
        self.request_param("outer_radiation", None)
        self.request_param("outer_convection", None)
        self.request_param("shading_g_total", None)
        self.request_param("shading_max_irr", None)


class Door(ElementWithLayers, Door_Teaser):
    represents = [
        bps.OuterDoor,
        bps.Door,
        bps_aggr.OuterDoorDisaggregated
    ]

    def __init__(self, element, parent):
        Door_Teaser.__init__(self, parent=parent)
        ElementWithLayers.__init__(self, element)

    def request_params(self):
        self.orientation = self.element.orientation
        self.request_param("gross_area",
                           self.check_numeric(min_value=0 * ureg.m ** 2),
                           "area")
        self.request_param("inner_convection", None)


class Layer(TEASER, Layer_Teaser):
    represents = [bps.Layer]

    def __init__(self, element: bps.Layer, parent):
        Layer_Teaser.__init__(self, parent=parent)
        TEASER.__init__(self, element)
        Material(element.material, parent=self)

    def request_params(self):
        self.request_param("thickness", None)

    def __repr__(self):
        return "<%s>" % type(self).__name__


class Material(TEASER, Material_Teaser):
    # represents = [element.Material]

    def __init__(self, element, parent):
        Material_Teaser.__init__(self, parent=parent)
        TEASER.__init__(self, element)

    def request_params(self):
        self.name = self.element.material
        self.request_param("density", None)
        self.request_param(
            "spec_heat_capacity", None, "heat_capac",
            export_unit=ureg.kilojoule / (ureg.kg * ureg.K))
        self.request_param("thermal_conduc", None)
