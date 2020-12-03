"""Module contains the different classes for all HVAC elements"""

import math
import re
import numpy as np

from bim2sim.decorators import cached_property
from bim2sim.kernel import element, condition, attribute
from bim2sim.decision import BoolDecision
from bim2sim.kernel.units import ureg
from bim2sim.decision import ListDecision, RealDecision
from bim2sim.kernel.ifc2python import get_layers_ifc
from bim2sim.enrichment_data.data_class import DataClass
from teaser.logic.buildingobjects.useconditions import UseConditions
from bim2sim.task.bps_f.bps_functions import get_matches_list, get_material_templates_resumed, \
    real_decision_user_input, filter_instances, get_pattern_usage
import translators as ts


def diameter_post_processing(value):
    if isinstance(value, list):
        return sum(value) / len(value)
    return value


def length_post_processing(value):
    if isinstance(value, list):
        return max(value)
    return value


pattern_usage = get_pattern_usage()


class HeatPump(element.Element):
    """"HeatPump"""

    ifc_type = 'IfcHeatPump'

    pattern_ifc_type = [
        re.compile('Heat.?pump', flags=re.IGNORECASE),
        re.compile('W(ä|ae)rme.?pumpe', flags=re.IGNORECASE),
    ]

    min_power = attribute.Attribute(
        description='Minimum power that HeatPump operates at.',
        unit=ureg.kilowatt,
    )
    rated_power = attribute.Attribute(
        description='Rated power of HeatPump.',
        unit=ureg.kilowatt,
    )
    efficiency = attribute.Attribute(
        description='Efficiency of HeatPump provided as list with pairs of [percentage_of_rated_power,efficiency]',
        unit=ureg.dimensionless,
    )


class Chiller(element.Element):
    """"Chiller"""

    ifc_type = 'IfcChiller'
    predefined_types = ['AIRCOOLED', 'WATERCOOLED', 'HEATRECOVERY']

    pattern_ifc_type = [
        re.compile('Chiller', flags=re.IGNORECASE),
        re.compile('K(ä|ae)lte.?maschine', flags=re.IGNORECASE),
    ]

    min_power = attribute.Attribute(
        description='Minimum power that Chiller operates at.',
        unit=ureg.kilowatt,
    )
    rated_power = attribute.Attribute(
        description='Rated power of Chiller.',
        unit=ureg.kilowatt,
    )
    efficiency = attribute.Attribute(
        description='Efficiency of Chiller provided as list with pairs of [percentage_of_rated_power,efficiency]',
        unit=ureg.dimensionless,
    )


class CoolingTower(element.Element):
    """"CoolingTower"""

    ifc_type = 'IfcCoolingTower'
    predefined_types = ['NATURALDRAFT', 'MECHANICALINDUCEDDRAFT', 'MECHANICALFORCEDDRAFT']

    pattern_ifc_type = [
        re.compile('Cooling.?Tower', flags=re.IGNORECASE),
        re.compile('Recooling.?Plant', flags=re.IGNORECASE),
        re.compile('K(ü|ue)hl.?turm', flags=re.IGNORECASE),
        re.compile('R(ü|ue)ck.?K(ü|ue)hl.?(werk|turm|er)', flags=re.IGNORECASE),
        re.compile('RKA', flags=re.IGNORECASE),
    ]

    min_power = attribute.Attribute(
        description='Minimum power that CoolingTower operates at.',
        unit=ureg.kilowatt,
    )
    rated_power = attribute.Attribute(
        description='Rated power of CoolingTower.',
        unit=ureg.kilowatt,
    )
    efficiency = attribute.Attribute(
        description='Efficiency of CoolingTower provided as list with pairs of [percentage_of_rated_power,efficiency]',
        unit=ureg.dimensionless,
    )


class HeatExchanger(element.Element):
    """"Heatexchanger"""

    ifc_type = 'IfcHeatExchanger'
    predefined_types = ['PLATE', 'SHELLANDTUBE']

    pattern_ifc_type = [
        re.compile('Heat.?Exchanger', flags=re.IGNORECASE),
        re.compile('W(ä|ae)rme.?(ü|e)bertrager', flags=re.IGNORECASE),
        re.compile('W(ä|ae)rme.?tauscher', flags=re.IGNORECASE),
    ]

    min_power = attribute.Attribute(
        description='Minimum power that HeatExchange operates at.',
        unit=ureg.kilowatt,
    )
    rated_power = attribute.Attribute(
        description='Rated power of HeatExchange.',
        unit=ureg.kilowatt,
    )
    efficiency = attribute.Attribute(
        description='Efficiency of HeatExchange provided as list with pairs of [percentage_of_rated_power,efficiency]',
        unit=ureg.dimensionless,
    )


class Boiler(element.Element):
    """Boiler"""
    ifc_type = 'IfcBoiler'
    predefined_types = ['WATER', 'STEAM']

    pattern_ifc_type = [
        # re.compile('Heat.?pump', flags=re.IGNORECASE),
        re.compile('Kessel', flags=re.IGNORECASE),
        re.compile('Boiler', flags=re.IGNORECASE),
    ]

    # def _add_ports(self):
    #    super()._add_ports()
    #    for port in self.ports:
    #        if port.flow_direction == 1:
    #            port.flow_master = True
    #        elif port.flow_direction == -1:
    #            port.flow_master = True

    def is_generator(self):
        return True

    def get_inner_connections(self):
        connections = []
        vl_pattern = re.compile('.*vorlauf.*', re.IGNORECASE)  # TODO: extend pattern
        rl_pattern = re.compile('.*rücklauf.*', re.IGNORECASE)
        VL = []
        RL = []
        for port in self.ports:
            if any(filter(vl_pattern.match, port.groups)):
                if port.flow_direction == 1:
                    VL.append(port)
                else:
                    self.logger.warning("Flow direction (%s) of %s does not match %s",
                                        port.verbose_flow_direction, port, port.groups)
                    decision = BoolDecision(
                        "Use %s as VL?" % (port),
                        global_key=port.guid,
                        allow_save=True,
                        allow_load=True)
                    use = decision.decide()
                    if use:
                        VL.append(port)
            elif any(filter(rl_pattern.match, port.groups)):
                if port.flow_direction == -1:
                    RL.append(port)
                else:
                    self.logger.warning("Flow direction (%s) of %s does not match %s",
                                        port.verbose_flow_direction, port, port.groups)
                    decision = BoolDecision(
                        "Use %s as RL?" % (port),
                        global_key=port.guid,
                        allow_save=True,
                        allow_load=True)
                    use = decision.decide()
                    if use:
                        RL.append(port)
        if len(VL) == 1 and len(RL) == 1:
            VL[0].flow_side = 1
            RL[0].flow_side = -1
            connections.append((RL[0], VL[0]))
        else:
            self.logger.warning("Unable to solve inner connections for %s", self)
        return connections

    water_volume = attribute.Attribute(
        description="Water volume of boiler",
        unit=ureg.meter ** 3,
    )

    min_power = attribute.Attribute(
        description="Minimum power that boiler operates at",
        unit=ureg.kilowatt,
    )

    rated_power = attribute.Attribute(
        description="Rated power of boiler",
        unit=ureg.kilowatt,
    )

    efficiency = attribute.Attribute(
        description="Efficiency of boiler provided as list with pairs of [percentage_of_rated_power,efficiency]",
        unit=ureg.dimensionless,
    )


class Pipe(element.Element):
    ifc_type = "IfcPipeSegment"
    predefined_types = ['CULVERT', 'FLEXIBLESEGMENT', 'RIGIDSEGMENT', 'GUTTER', 'SPOOL']

    conditions = [
        condition.RangeCondition("diameter", 5.0 * ureg.millimeter, 300.00 * ureg.millimeter)  # ToDo: unit?!
    ]

    diameter = attribute.Attribute(
        default_ps='diameter',
        unit=ureg.millimeter,
        patterns=[
            re.compile('.*Durchmesser.*', flags=re.IGNORECASE),
            re.compile('.*Diameter.*', flags=re.IGNORECASE),
        ],
        ifc_postprocessing=diameter_post_processing,
    )

    @staticmethod
    def _length_from_geometry(bind, name):
        try:
            return Pipe.get_lenght_from_shape(bind.ifc.Representation)
        except AttributeError:
            return None

    length = attribute.Attribute(
        default_ps='length',
        unit=ureg.meter,
        patterns=[
            re.compile('.*Länge.*', flags=re.IGNORECASE),
            re.compile('.*Length.*', flags=re.IGNORECASE),
        ],
        ifc_postprocessing=length_post_processing,
        functions=[_length_from_geometry],
    )

    @staticmethod
    def get_lenght_from_shape(ifc_representation):
        """Serach for extruded depth in representations

        Warning: Found extrusion may net be the required length!
        :raises: AttributeError if not exactly one extrusion is found"""
        candidates = []
        try:
            for representation in ifc_representation.Representations:
                for item in representation.Items:
                    if item.is_a() == 'IfcExtrudedAreaSolid':
                        candidates.append(item.Depth)
        except:
            raise AttributeError("Failed to determine length.")
        if not candidates:
            raise AttributeError("No representation to determine length.")
        if len(candidates) > 1:
            raise AttributeError("Too many representations to dertermine length %s." % candidates)

        return candidates[0]


class PipeFitting(element.Element):
    ifc_type = "IfcPipeFitting"
    predefined_types = ['BEND', 'CONNECTOR', 'ENTRY', 'EXIT', 'JUNCTION', 'OBSTRUCTION', 'TRANSITION']

    conditions = [
        condition.RangeCondition("diameter", 5.0 * ureg.millimeter, 300.00 * ureg.millimeter)
    ]

    diameter = attribute.Attribute(
        default_ps='diameter',
        unit=ureg.millimeter,
        patterns=[
            re.compile('.*Durchmesser.*', flags=re.IGNORECASE),
            re.compile('.*Diameter.*', flags=re.IGNORECASE),
        ],
        ifc_postprocessing=diameter_post_processing,
    )

    length = attribute.Attribute(
        default_ps='length',
        unit=ureg.meter,
        patterns=[
            re.compile('.*Länge.*', flags=re.IGNORECASE),
            re.compile('.*Length.*', flags=re.IGNORECASE),
        ],
        default=0,
        ifc_postprocessing=length_post_processing
    )

    pressure_class = attribute.Attribute(
        default_ps='pressure_class',
        unit=ureg.pascal
    )

    @staticmethod
    def _diameter_post_processing(value):
        if isinstance(value, list):
            return np.average(value).item()
        return value


class SpaceHeater(element.Element):
    ifc_type = 'IfcSpaceHeater'
    predefined_types = ['CONVECTOR', 'RADIATOR']

    pattern_ifc_type = [
        re.compile('Space.?heater', flags=re.IGNORECASE)
    ]

    def is_consumer(self):
        return True

    rated_power = attribute.Attribute(
        description="Rated power of SpaceHeater",
        unit=ureg.kilowatt,
        default=42,
    )


# class ExpansionTank(element.Element):
#     ifc_type = "IfcTank"   #ToDo: IfcTank, IfcTankType=Expansion
#     predefined_types = ['BASIN', 'BREAKPRESSURE', 'EXPANSION', 'FEEDANDEXPANSION', 'STORAGE', 'VESSEL']
#     pattern_ifc_type = [
#         re.compile('Expansion.?Tank', flags=re.IGNORECASE),
#         re.compile('Ausdehnungs.?gef(ä|ae)(ss|ß)', flags=re.IGNORECASE),
#     ]


# class StorageDevice(element.Element):
#     """IFC4 CHANGE  This entity has been deprecated for instantiation and will become ABSTRACT in a future release;
#     new subtypes should now be used instead."""
#     ifc_type = "IfcStorageDevice"
#     pattern_ifc_type = [
#         re.compile('Storage.?device', flags=re.IGNORECASE)
#     ]


class Storage(element.Element):
    ifc_type = "IfcTank"
    predefined_type = 'STORAGE'
    predefined_types = ['BASIN', 'BREAKPRESSURE', 'EXPANSION', 'FEEDANDEXPANSION', 'STORAGE', 'VESSEL']

    pattern_ifc_type = [
        re.compile('Tank', flags=re.IGNORECASE),
        re.compile('Speicher', flags=re.IGNORECASE),
        # re.compile('Expansion.?Tank', flags=re.IGNORECASE),
        re.compile('Ausdehnungs.?gef(ä|ae)(ss|ß)', flags=re.IGNORECASE),
    ]

    @property
    def storage_type(self):
        return None

    height = attribute.Attribute(
        unit=ureg.meter,
    )

    diameter = attribute.Attribute(
        unit=ureg.millimeter,
    )

    @property
    def port_positions(self):
        return (0, 0.5, 1)

    def _calc_volume(self):
        return self.height * self.diameter ** 2 / 4 * math.pi

    volume = attribute.Attribute(
        unit=ureg.meter ** 3,
    )


class Distributor(element.Element):
    ifc_type = "IfcDistributionChamberElement"
    predefined_types = ['FORMEDDUCT', 'INSPECTIONCHAMBER', 'INSPECTIONPIT', 'MANHOLE', 'METERCHAMBER',
                        'SUMP', 'TRENCH', 'VALVECHAMBER']

    pattern_ifc_type = [
        re.compile('Distribution.?chamber', flags=re.IGNORECASE),
        re.compile('Distributior', flags=re.IGNORECASE),
        re.compile('Verteiler', flags=re.IGNORECASE)
    ]

    volume = attribute.Attribute(
        description="Volume of the Distributor",
        unit=ureg.meter ** 3
    )

    nominal_power = attribute.Attribute(
        description="Nominal power of Distributor",
        unit=ureg.kilowatt
    )


class Pump(element.Element):
    ifc_type = "IfcPump"
    predefined_types = ['CIRCULATOR', 'ENDSUCTION', 'SPLITCASE', 'SUBMERSIBLEPUMP', 'SUMPPUMP', 'VERTICALINLINE',
                        'VERTICALTURBINE']

    pattern_ifc_type = [
        re.compile('Pumpe', flags=re.IGNORECASE),
        re.compile('Pump', flags=re.IGNORECASE)
    ]

    rated_power = attribute.Attribute(
        unit=ureg.kilowatt,
    )

    rated_height = attribute.Attribute(
        unit=ureg.meter,
    )

    rated_volume_flow = attribute.Attribute(
        unit=ureg.meter ** 3 / ureg.hour,
    )

    diameter = attribute.Attribute(
        unit=ureg.meter,
    )


class Valve(element.Element):
    ifc_type = "IfcValve"
    predefined_types = ['AIRRELEASE', 'ANTIVACUUM', 'CHANGEOVER', 'CHECK', 'COMMISSIONING', 'DIVERTING', 'DRAWOFFCOCK',
                        'DOUBLECHECK', 'DOUBLEREGULATING', 'FAUCET', 'FLUSHING', 'GASCOCK', 'GASTAP', 'ISOLATING',
                        'MIXING', 'PRESSUREREDUCING', 'PRESSURERELIEF', 'REGULATING', 'SAFETYCUTOFF', 'STEAMTRAP',
                        'STOPCOCK']

    pattern_ifc_type = [
        re.compile('Valve', flags=re.IGNORECASE),
        re.compile('Drossel', flags=re.IGNORECASE),
        re.compile('Ventil', flags=re.IGNORECASE)
    ]

    conditions = [
        condition.RangeCondition("diameter", 5.0 * ureg.millimeter, 500.00 * ureg.millimeter)  # ToDo: unit?!
    ]

    diameter = attribute.Attribute(
        description='Valve diameter',
        unit=ureg.millimeter,
        patterns=[
            re.compile('.*Durchmesser.*', flags=re.IGNORECASE),
            re.compile('.*Diameter.*', flags=re.IGNORECASE),
            re.compile('.*DN.*', flags=re.IGNORECASE),
        ],
    )
    # @cached_property
    # def diameter(self):
    #     result = self.find('diameter')
    #
    #     if isinstance(result, list):
    #         return np.average(result).item()
    #     return result

    length = attribute.Attribute(
        description='Length of Valve',
        unit=ureg.meter,
    )


class Duct(element.Element):
    ifc_type = "IfcDuctSegment"
    predefined_types = ['RIGIDSEGMENT', 'FLEXIBLESEGMENT']

    pattern_ifc_type = [
        re.compile('Duct.?segment', flags=re.IGNORECASE)
    ]

    diameter = attribute.Attribute(
        description='Duct diameter',
        unit=ureg.millimeter,
    )
    length = attribute.Attribute(
        description='Length of Duct',
        unit=ureg.meter,
    )


class DuctFitting(element.Element):
    ifc_type = "IfcDuctFitting"
    predefined_types = ['BEND', 'CONNECTOR', 'ENTRY', 'EXIT', 'JUNCTION', 'OBSTRUCTION', 'TRANSITION']

    pattern_ifc_type = [
        re.compile('Duct.?fitting', flags=re.IGNORECASE)
    ]

    diameter = attribute.Attribute(
        description='Duct diameter',
        unit=ureg.millimeter,
    )
    length = attribute.Attribute(
        description='Length of Duct',
        unit=ureg.meter,
    )


class AirTerminal(element.Element):
    ifc_type = "IfcAirTerminal"
    predefined_types = ['DIFFUSER', 'GRILLE', 'LOUVRE', 'REGISTER']

    pattern_ifc_type = [
        re.compile('Air.?terminal', flags=re.IGNORECASE)
    ]

    diameter = attribute.Attribute(
        description='Terminal diameter',
        unit=ureg.millimeter,
    )


class ThermalZone(element.Element):
    ifc_type = "IfcSpace"
    predefined_types = ['SPACE', 'PARKING', 'GFA', 'INTERNAL', 'EXTERNAL']

    pattern_ifc_type = [
        re.compile('Space', flags=re.IGNORECASE),
        re.compile('Zone', flags=re.IGNORECASE)
    ]

    zone_name = attribute.Attribute(
        default_ps='zone_name'
    )

    def _get_usage(bind, name):
        zone_pattern = []
        list_org = bind.zone_name.replace(' (', ' ').replace(')', ' ').replace(' -', ' ').replace(', ', ' ').split()
        for i_org in list_org:
            trans_aux = ts.bing(i_org, from_language='de')
            # trans_aux = ts.google(i_org, from_language='de')
            zone_pattern.append(trans_aux)

        matches = []
        # check if a string matches the zone name
        for usage, pattern in pattern_usage.items():
            for i in pattern:
                for i_name in zone_pattern:
                    if i.match(i_name):
                        if usage not in matches:
                            matches.append(usage)
        # if just a match given
        if len(matches) == 1:
            return matches[0]
        # if no matches given
        elif len(matches) == 0:
            matches = list(pattern_usage.keys())
        usage_decision = ListDecision("Which usage does the Space %s have?" %
                                      (str(bind.zone_name)),
                                      choices=matches,
                                      allow_skip=False,
                                      allow_load=True,
                                      allow_save=True,
                                      quick_decide=not True)
        usage_decision.decide()
        return usage_decision.value

    def get_is_external(self):
        """determines if a thermal zone is external or internal
        based on its elements (Walls and windows analysis)"""
        tz_elements = filter_instances(self.bound_elements, 'Wall') + filter_instances(self.bound_elements, 'Window')
        for ele in tz_elements:
            if hasattr(ele, 'is_external'):
                if ele.is_external is True:
                    return True

    def set_is_external(self):
        """set the property is_external -> Bool"""
        self.is_external = self.get_is_external()

    def get_external_orientation(self):
        """determines the orientation of the thermal zone
        based on its elements
        it can be a corner (list of 2 angles) or an edge (1 angle)"""
        if self.is_external is True:
            orientations = []
            for ele in self.bound_elements:
                if hasattr(ele, 'is_external') and hasattr(ele, 'orientation'):
                    if ele.is_external is True and ele.orientation not in [-1, -2]:
                        orientations.append(ele.orientation)
            if len(list(set(orientations))) == 1:
                return list(set(orientations))[0]
            else:
                # corner case
                calc_temp = list(set(orientations))
                sum_or = sum(calc_temp)
                if 0 in calc_temp:
                    if sum_or > 180:
                        sum_or += 360
                return sum_or / len(calc_temp)

    def set_external_orientation(self):
        """set the property external_orientation
        value can be an angle (edge) or a list of two angles (edge)"""
        self.external_orientation = self.get_external_orientation()

    def get_glass_area(self):
        """determines the glass area/facade area ratio for all the windows in the space in one of the 4 following ranges
        0%-30%: 15
        30%-50%: 40
        50%-70%: 60
        70%-100%: 85"""

        glass_area = 0
        facade_area = 0
        if self.is_external is True:
            for ele in self.bound_elements:
                if hasattr(ele.area, "m"):
                    e_area = ele.area.magnitude
                else:
                    e_area = ele.area
                if type(ele) is Window:
                    if ele.area is not None:
                        glass_area += e_area
                if 'Wall' in type(ele).__name__ and ele.is_external is True:
                    facade_area += e_area
            real_gp = 0
            try:
                real_gp = 100 * (glass_area / (facade_area + glass_area))
            except ZeroDivisionError:
                pass
            return real_gp

    def set_glass_area(self):
        """set the property external_orientation"""
        self.glass_percentage = self.get_glass_area()

    def get_neighbors(self):
        """determines the neighbors of the thermal zone"""
        neighbors = []
        for ele in self.bound_elements:
            for tz in ele.thermal_zones:
                if (tz is not self) and (tz not in neighbors):
                    neighbors.append(tz)
        return neighbors

    def set_neighbors(self):
        """set the neighbors of the thermal zone as a list"""
        self.space_neighbors = self.get_neighbors()

    usage = attribute.Attribute(
        functions=[_get_usage]
    )

    t_set_heat = attribute.Attribute(
        default_ps='t_set_heat'
    )
    t_set_cool = attribute.Attribute(
        default_ps='t_set_cool'
    )
    area = attribute.Attribute(
        default_ps='area',
        default=0
    )
    net_volume = attribute.Attribute(
        default_ps='net_volume',
        default=0
    )
    height = attribute.Attribute(
        default_ps='height',
        default=0
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bound_elements = []
        self.is_external = False
        self.external_orientation = 'Internal'
        self.glass_percentage = 'Internal'
        self.space_neighbors = []

    def get__elements_by_type(self, type):
        raise NotImplementedError


class SpaceBoundary(element.SubElement):
    ifc_type = 'IfcRelSpaceBoundary'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.level_description = self.ifc.Description
        self.thermal_zones.append(self.get_object(self.ifc.RelatingSpace.GlobalId))
        if self.ifc.RelatedBuildingElement is not None:
            self.bound_instance = self.get_object(self.ifc.RelatedBuildingElement.GlobalId)
        else:
            self.bound_instance = None
        if self.ifc.InternalOrExternalBoundary.lower() == 'internal':
            self.is_external = True
        else:
            self.is_external = False
        if self.ifc.PhysicalOrVirtualBoundary.lower() == 'physical':
            self.physical = True
        else:
            self.physical = False


class Medium(element.Element):
    # is deprecated?
    ifc_type = "IfcDistributionSystems"
    pattern_ifc_type = [
        re.compile('Medium', flags=re.IGNORECASE)
    ]


class Wall(element.Element):
    ifc_type = ["IfcWall", "IfcWallStandardCase"]
    predefined_types = ['MOVABLE', 'PARAPET', 'PARTITIONING', 'PLUMBINGWALL', 'SHEAR', 'SOLIDWALL', 'POLYGONAL']
    pattern_ifc_type = [
        re.compile('Wall', flags=re.IGNORECASE),
        re.compile('Wand', flags=re.IGNORECASE)
    ]
    material_selected = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ifc_type = self.ifc.is_a()
        # if self.is_external:
        #     self.__class__ = OuterWall
        #     self.__init__()
        # elif not self.is_external:
        #     self.__class__ = InnerWall
        #     self.__init__()

    def _get_layers(bind, name):
        layers = []
        material_layers_dict = get_layers_ifc(bind)
        for layer in material_layers_dict:
            new_layer = element.SubElement.factory(layer, 'IfcMaterialLayer')
            new_layer.parent = bind
            layers.append(new_layer)
        return layers

    layers = attribute.Attribute(
        functions=[_get_layers]
    )

    area = attribute.Attribute(
        default_ps='area',
        default=1
    )

    is_external = attribute.Attribute(
        default_ps='is_external',
        default=False
    )

    tilt = attribute.Attribute(
        default_ps='tilt',
        default=0
    )


class Layer(element.SubElement):
    ifc_type = ['IfcMaterialLayer', 'IfcMaterial']
    material_selected = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self.ifc, 'Material'):
            material = self.ifc.Material
        else:
            material = self.ifc
        self.material = material.Name
        # ToDO: what if doesn't have thickness
        self.thickness = None
        if hasattr(self.ifc, 'LayerThickness'):
            self.thickness = self.ifc.LayerThickness

    def __repr__(self):
        return "<%s (material: %s>" \
               % (self.__class__.__name__, self.material)

    def _get_material_properties(bind, name):
        if name == 'thickness':
            name = 'thickness_default'

        material = bind.material
        if material in bind.material_selected:
            if name in bind.material_selected[material]:
                return bind.material_selected[material][name]
            else:
                return real_decision_user_input(bind, name)
        else:
            first_decision = BoolDecision(question="Do you want for %s with the material %s to use avaiable templates, "
                                                   "enter 'n' for manual input"
                                                   % (bind.guid, bind.material),
                                          collect=False)
            first_decision.decide()
            first_decision.stored_decisions.clear()

            if first_decision.value:
                material_templates, resumed = get_material_templates_resumed()
                material_options = get_matches_list(bind.material, list(resumed.keys()))

                while len(material_options) == 0:
                    decision_ = input(
                        "Material not found, enter value for the material:")
                    material_options = get_matches_list(decision_, list(resumed.keys()))

                decision1 = ListDecision("Multiple possibilities found for material %s" % material,
                                         choices=list(material_options),
                                         allow_skip=True, allow_load=True, allow_save=True,
                                         collect=False, quick_decide=not True)
                decision1.decide()

                bind.material_selected[material] = material_templates[resumed[decision1.value]]
                return bind.material_selected[material][name]
            else:
                return real_decision_user_input(bind, name)

    heat_capac = attribute.Attribute(
        default_ps='heat_capac',
        functions=[_get_material_properties],
        default=0
    )

    density = attribute.Attribute(
        functions=[_get_material_properties],
        default_ps='density',
        default=0
    )

    thermal_conduc = attribute.Attribute(
        functions=[_get_material_properties],
        default_ps='thermal_conduc',
        default=0
    )


class OuterWall(Wall):
    special_argument = {'is_external': True}


class InnerWall(Wall):
    special_argument = {'is_external': False}


class Window(element.Element):
    ifc_type = "IfcWindow"
    predefined_types = ['WINDOW', 'SKYLIGHT', 'LIGHTDOME']
    # predefined_type = {
    #     "IfcWindow": ["WINDOW",
    #                   "SKYLIGHT",
    #                   "LIGHTDOME"
    #                   ]
    # }

    pattern_ifc_type = [
        re.compile('Window', flags=re.IGNORECASE),
        re.compile('Fenster', flags=re.IGNORECASE)
    ]

    def _get_layers(bind, name):
        layers = []
        material_layers_dict = get_layers_ifc(bind)
        for layer in material_layers_dict:
            new_layer = element.SubElement.factory(layer, layer.is_a())
            new_layer.parent = bind
            layers.append(new_layer)
        return layers

    layers = attribute.Attribute(
        functions=[_get_layers]
    )

    is_external = attribute.Attribute(
        default_ps='is_external',
        default=True
    )

    area = attribute.Attribute(
        default_ps='area',
        default=0
    )

    thickness = attribute.Attribute(
        default_ps='thickness',
        default=0
    )

    # material = attribute.Attribute(
    #     default_ps=True,
    #     default=0
    # )


class Door(element.Element):
    ifc_type = "IfcDoor"
    predefined_types = ['DOOR', 'GATE', 'TRAPDOOR']

    pattern_ifc_type = [
        re.compile('Door', flags=re.IGNORECASE),
        re.compile('Tuer', flags=re.IGNORECASE)
    ]

    def _get_layers(bind, name):
        layers = []
        material_layers_dict = get_layers_ifc(bind)
        for layer in material_layers_dict:
            new_layer = element.SubElement.factory(layer, layer.is_a())
            new_layer.parent = bind
            layers.append(new_layer)
        return layers

    layers = attribute.Attribute(
        functions=[_get_layers]
    )

    is_external = attribute.Attribute(
        default_ps='is_external',
        default=False
    )

    area = attribute.Attribute(
        default_ps='area',
        default=0
    )

    thickness = attribute.Attribute(
        default_ps='thickness',
        default=0
    )

    # material = attribute.Attribute(
    #     default_ps=True,
    #     default=0
    # )


class Plate(element.Element):
    ifc_type = "IfcPlate"
    predefined_types = ['CURTAIN_PANEL', 'SHEET']

    # @property
    # def area(self):
    #     return 1
    #
    # @property
    # def u_value(self):
    #     return 1
    #
    # @property
    # def g_value(self):
    #     return 1


class Slab(element.Element):
    ifc_type = "IfcSlab"
    predefined_types = ['FLOOR', 'ROOF', 'LANDING', 'BASESLAB']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # if self.predefined_type == "ROOF":
        #     self.__class__ = Roof
        #     self.__init__()
        # if self.predefined_type == "FLOOR":
        #     self.__class__ = Floor
        #     self.__init__()
        # if self.predefined_type == "BASESLAB":
        #     self.__class__ = GroundFloor
        #     self.__init__()

    def _get_layers(bind, name):
        layers = []
        material_layers_dict = get_layers_ifc(bind)
        for layer in material_layers_dict:
            new_layer = element.SubElement.factory(layer, 'IfcMaterialLayer')
            new_layer.parent = bind
            layers.append(new_layer)
        return layers

    layers = attribute.Attribute(
        functions=[_get_layers]
    )
    area = attribute.Attribute(
        default_ps='area',
        default=0
    )

    thickness = attribute.Attribute(
        default_ps='thickness',
        default=0
    )

    thermal_transmittance = attribute.Attribute(
        default_ps='thermal_transmittance',
        default=0
    )

    is_external = attribute.Attribute(
        default_ps='is_external',
        default=0
    )

    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #   self.parent = []
    #   self.sub_slabs = []


class Roof(Slab):
    ifc_type = "IfcRoof"
    predefined_types = ['FLAT_ROOF', 'SHED_ROOF', 'GABLE_ROOF', 'HIP_ROOF', 'HIPPED_GABLE_ROOF', 'GAMBREL_ROOF',
                        'MANSARD_ROOF', 'BARREL_ROOF', 'RAINBOW_ROOF', 'BUTTERFLY_ROOF', 'PAVILION_ROOF', 'DOME_ROOF',
                        'FREEFORM']
    predefined_type = "ROOF"

    def __init__(self, *args, **kwargs):
        if hasattr(self, 'ifc'):
            self.ifc_type = self.ifc.is_a()
        else:
            super().__init__(*args, **kwargs)


class Floor(Slab):
    predefined_type = "FLOOR"


class GroundFloor(Slab):
    predefined_type = "BASESLAB"


class Site(element.Element):
    ifc_type = "IfcSite"

    # year_of_construction = attribute.Attribute(
    #     name='year_of_construction',
    #     default_ps=True
    # )


class Building(element.Element):
    ifc_type = "IfcBuilding"

    year_of_construction = attribute.Attribute(
        default_ps='year_of_construction'
    )
    gross_area = attribute.Attribute(
        default_ps='gross_area'
    )
    net_area = attribute.Attribute(
        default_ps='net_area'
    )
    number_of_storeys = attribute.Attribute(
        default_ps='number_of_storeys'
    )
    occupancy_type = attribute.Attribute(
        default_ps='occupancy_type'
    )


class Storey(element.Element):
    ifc_type = 'IfcBuildingStorey'

    gross_floor_area = attribute.Attribute(
        default_ps='gross_floor_area'
    )
    # todo make the lookup for height hierarchical
    net_height = attribute.Attribute(
        default_ps='net_height'
    )
    gross_height = attribute.Attribute(
        default_ps='gross_height'
    )
    height = attribute.Attribute(
        default_ps='height'
    )


__all__ = [ele for ele in locals().values() if ele in element.Element.__subclasses__()]
