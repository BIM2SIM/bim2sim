"""Package for Python representations of HKESim models"""
from bim2sim_teaser import export
from teaser.logic.buildingobjects.building import Building as Building_Teaser
from teaser.logic.buildingobjects.buildingphysics.door \
    import Door as Door_Teaser
from teaser.logic.buildingobjects.buildingphysics.floor \
    import Floor as Floor_Teaser
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

import bim2sim.kernel.aggregation as aggregation
from bim2sim.metastructure import bps
from bim2sim.kernel.units import ureg


class TEASER(export.Instance):
    library = "TEASER"


class Building(TEASER, Building_Teaser):
    represents = [bps.Building]

    def __init__(self, bim2sim_element, parent):
        Building_Teaser.__init__(self, parent=parent)
        TEASER.__init__(self, bim2sim_element)
        self.used_library_calc = "AixLib"
        self.add_thermal_zones_to_building()

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


class ThermalZone(TEASER, ThermalZone_Teaser):
    represents = [bps.ThermalZone, aggregation.AggregatedThermalZone]

    def __init__(self, element, parent):
        ThermalZone_Teaser.__init__(self, parent=parent)
        TEASER.__init__(self, element)
        self.number_of_elements = 2
        self.use_conditions = UseConditions(element=element, parent=self)
        self.add_elements_to_thermal_zone()

    def add_elements_to_thermal_zone(self):
        for bound_instance in self.element.bound_elements:
            export.Instance.factory(bound_instance, parent=self)

    def request_params(self):
        self.request_param("name", None)
        self.request_param("net_area",
                           self.check_numeric(
                               min_value=0 * ureg.meter ** 2),
                           "area")
        self.request_param("t_ground", None)
        self.request_param("net_volume",
                           None,
                           "volume")


class UseConditions(TEASER, UseConditions_Teaser):
    represents = []

    def __init__(self, element, parent):
        UseConditions_Teaser.__init__(self, parent=parent)
        TEASER.__init__(self, element)

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
        self.request_param("ratio_conv_rad_lighting", None)
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
    represents = [bps.InnerDoor, bps.InnerWall]

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
                               min_value=0 * ureg.W / ureg.K / ureg.meter ** 2),
                           "inner_convection")


class OuterWall(ElementWithLayers, OuterWall_Teaser):
    represents = [bps.OuterWall]

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
    represents = [bps.Roof]

    def __init__(self, element, parent):
        Rooftop_Teaser.__init__(self, parent=parent)
        ElementWithLayers.__init__(self, element)

    def request_params(self):
        self.orientation = self.element.orientation
        self.request_param("net_area",
                           self.check_numeric(min_value=0 * ureg.m ** 2),
                           "area")


class Floor(ElementWithLayers, Floor_Teaser):
    represents = [bps.Floor]

    def __init__(self, element, parent):
        Floor_Teaser.__init__(self, parent=parent)
        ElementWithLayers.__init__(self, element)

    def request_params(self):
        self.orientation = self.element.orientation
        self.request_param("net_area",
                           self.check_numeric(min_value=0 * ureg.m ** 2),
                           "area")


class GroundFloor(ElementWithLayers, GroundFloor_Teaser):
    represents = [bps.GroundFloor]

    def __init__(self, element, parent):
        GroundFloor_Teaser.__init__(self, parent=parent)
        ElementWithLayers.__init__(self, element)

    def request_params(self):
        self.orientation = self.element.orientation
        self.request_param("net_area",
                           self.check_numeric(min_value=0 * ureg.m ** 2),
                           "area")


class Window(ElementWithLayers, Window_Teaser):
    represents = [bps.Window]

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
    represents = [bps.OuterDoor]

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
