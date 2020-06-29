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


def diameter_post_processing(value):
    if isinstance(value, list):
        return sum(value) / len(value)
    return value


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

    pattern_ifc_type = [
        #re.compile('Heat.?pump', flags=re.IGNORECASE),
        re.compile('Kessel', flags=re.IGNORECASE),
        re.compile('Boiler', flags=re.IGNORECASE),
    ]

    #def _add_ports(self):
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
        unit=ureg.meter**3,
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
    conditions = [
        condition.RangeCondition("diameter", 5.0*ureg.millimeter, 300.00*ureg.millimeter)   #ToDo: unit?!
    ]

    diameter = attribute.Attribute(
        default_ps=('Pset_PipeSegmentTypeCommon', 'NominalDiameter'),
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
        default_ps=('Qto_PipeSegmentBaseQuantities', 'Length'),
        unit=ureg.meter,
        patterns=[
            re.compile('.*Länge.*', flags=re.IGNORECASE),
            re.compile('.*Length.*', flags=re.IGNORECASE),
        ],
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

    conditions = [
        condition.RangeCondition("diameter", 5.0*ureg.millimeter, 300.00*ureg.millimeter)   #ToDo: unit?!
    ]

    diameter = attribute.Attribute(
        default_ps=('Pset_PipeFittingTypeCommon', 'NominalDiameter'),
        unit=ureg.millimeter,
        patterns=[
            re.compile('.*Durchmesser.*', flags=re.IGNORECASE),
            re.compile('.*Diameter.*', flags=re.IGNORECASE),
        ],
        ifc_postprocessing=diameter_post_processing,
    )

    length = attribute.Attribute(
        unit=ureg.meter,
        default=0,
    )

    pressure_class = attribute.Attribute(
        unit=ureg.pascal,
        default_ps=('Pset_PipeFittingTypeCommon', 'PressureClass')
    )

    @staticmethod
    def _diameter_post_processing(value):
        if isinstance(value, list):
            return np.average(value).item()
        return value


class SpaceHeater(element.Element):
    ifc_type = 'IfcSpaceHeater'
    pattern_ifc_type = [
        re.compile('Space.?heater', flags=re.IGNORECASE)
    ]

    def is_consumer(self):
        return True

    nominal_power = attribute.Attribute(
        description="Nominal power of SpaceHeater",
        unit=ureg.kilowatt,
        default=42,
    )


class ExpansionTank(element.Element):
    ifc_type = "IfcExpansionTank"   #ToDo: Richtig?!
    pattern_ifc_type = [
        re.compile('Expansion.?Tank', flags=re.IGNORECASE),
        re.compile('Ausdehnungs.?gef(ä|ae)(ss|ß)', flags=re.IGNORECASE),
    ]


class StorageDevice(element.Element):
    ifc_type = "IfcStorageDevice"
    pattern_ifc_type = [
        re.compile('Storage.?device', flags=re.IGNORECASE)
    ]


class Storage(element.Element):
    ifc_type = "IfcTank"
    pattern_ifc_type = [
        re.compile('Tank', flags=re.IGNORECASE),
        re.compile('Speicher', flags=re.IGNORECASE),
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
        unit=ureg.meter**3 / ureg.hour,
    )

    diameter = attribute.Attribute(
        unit=ureg.meter,
    )


class Valve(element.Element):
    ifc_type = "IfcValve"
    pattern_ifc_type = [
        re.compile('Valve', flags=re.IGNORECASE),
        re.compile('Drossel', flags=re.IGNORECASE),
        re.compile('Ventil', flags=re.IGNORECASE)
    ]

    conditions = [
        condition.RangeCondition("diameter", 5.0*ureg.millimeter, 500.00*ureg.millimeter)  # ToDo: unit?!
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
    pattern_ifc_type = [
        re.compile('Air.?terminal', flags=re.IGNORECASE)
    ]

    diameter = attribute.Attribute(
        description='Terminal diameter',
        unit=ureg.millimeter,
    )


class ThermalZone(element.Element):
    ifc_type = "IfcSpace"

    pattern_ifc_type = [
        re.compile('Space', flags=re.IGNORECASE),
        re.compile('Zone', flags=re.IGNORECASE)
    ]

    zone_name = attribute.Attribute(
        name='zone_name',
        default_ps=True
    )

    def _get_usage(bind, name):
        pattern_usage = {
            "Living": [
                re.compile('Living', flags=re.IGNORECASE),
                re.compile('Wohnen', flags=re.IGNORECASE)
            ],
            "Traffic area": [
                re.compile('Traffic', flags=re.IGNORECASE),
                re.compile('Flur', flags=re.IGNORECASE)
            ],
            "Bed room": [
                re.compile('Bed', flags=re.IGNORECASE),
                re.compile('Schlafzimmer', flags=re.IGNORECASE)
            ],
            "Kitchen - preparations, storage": [
                re.compile('Küche', flags=re.IGNORECASE),
                re.compile('Kitchen', flags=re.IGNORECASE)
            ]
        }
        for usage, pattern in pattern_usage.items():
            for i in pattern:
                if i.match(bind.zone_name):
                    return usage
        usage_decision = ListDecision("Which usage does the Space %s have?" %
                                      (str(bind.zone_name)),
                                      choices=["Living",
                                               "Traffic area",
                                               "Bed room",
                                               "Kitchen - preparations, storage"],
                                      allow_skip=False,
                                      allow_load=True,
                                      allow_save=True,
                                      quick_decide=not True)
        usage_decision.decide()
        return usage_decision.value



    usage = attribute.Attribute(
        name='usage',
        functions=[_get_usage]
    )

    t_set_heat = attribute.Attribute(
        name='t_set_heat',
        default_ps=True
    )
    t_set_cool = attribute.Attribute(
        name='t_set_cool',
        default_ps=True
    )
    # # todo remove default, when regular expression compare is implemented
    # usage = attribute.Attribute(
    #     name='usage',
    #     default='Living'
    # )
    area = attribute.Attribute(
        name='area',
        default_ps=True,
        default=0
    )
    net_volume = attribute.Attribute(
        name='net_volume',
        default_ps=True,
        default=0
    )
    height = attribute.Attribute(
        name='height',
        default_ps=True,
        default=0
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bound_elements = []

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
    ifc_type = "IfcDistributionSystems"
    pattern_ifc_type = [
        re.compile('Medium', flags=re.IGNORECASE)
    ]


class Wall(element.Element):
    ifc_type = ["IfcWall", "IfcWallStandardCase"]
    pattern_ifc_type = [
        re.compile('Wall', flags=re.IGNORECASE),
        re.compile('Wand', flags=re.IGNORECASE)
    ]
    material_selected = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ifc_type = self.ifc.is_a()
        if self.is_external:
            self.__class__ = OuterWall
            self.__init__()
        elif not self.is_external:
            self.__class__ = InnerWall
            self.__init__()

    def _get_layers(bind, name):
        layers = []
        material_layers_dict = get_layers_ifc(bind)
        for layer in material_layers_dict:
            new_layer = element.SubElement.factory(layer, 'IfcMaterialLayer')
            new_layer.parent = bind
            layers.append(new_layer)
        return layers

    layers = attribute.Attribute(
        name='layers',
        functions=[_get_layers]
    )

    def _get_wall_properties(bind, name):
        """get wall material properties based on teaser templates if properties not given"""
        material = bind.material
        material_ref = ''.join([i for i in material if not i.isdigit()])
        is_external = bind.is_external
        external = 'external'
        if not is_external:
            external = 'internal'

        try:
            bind.material_selected[material]['properties']
        except KeyError:
            first_decision = BoolDecision(
                question="Do you want for %s_%s_%s to use template" % (str(bind), bind.guid, external),
                collect=False)
            first_decision.decide()
            first_decision.stored_decisions.clear()
            if first_decision.value:

                Materials_DEU = bind.finder.templates[bind.source_tool][bind.__class__.__name__]['material']
                material_templates = dict(DataClass(used_param=2).element_bind)
                del material_templates['version']

                if material_ref not in str(Materials_DEU.keys()):
                    decision_ = input("Material not found, enter value for the material %s_%s_%s" % (str(bind), bind.guid, external))
                    material_ref = decision_

                for k in Materials_DEU:
                    if material_ref in k:
                        material_ref = Materials_DEU[k]

                options = {}
                for k in material_templates:
                    if material_ref in material_templates[k]['name']:
                        options[k] = material_templates[k]
                materials_options = [[material_templates[k]['name'], k] for k in options]
                if len(materials_options) > 0:
                    decision1 = ListDecision("Multiple possibilities found",
                                             choices=list(materials_options),
                                             allow_skip=True, allow_load=True, allow_save=True,
                                             collect=False, quick_decide=not True)
                    decision1.decide()
                    bind.material_selected[material] = {}
                    bind.material_selected[material]['properties'] = material_templates[decision1.value[1]]
                    bind.material_selected[material_templates[decision1.value[1]]['name']] = {}
                    bind.material_selected[material_templates[decision1.value[1]]['name']]['properties'] = material_templates[decision1.value[1]]
                else:
                    bind.logger.warning("No possibilities found")
                    bind.material_selected[material] = {}
                    bind.material_selected[material]['properties'] = {}
            else:
                bind.material_selected[material] = {}
                bind.material_selected[material]['properties'] = {}

        property_template = bind.finder.templates[bind.source_tool]['MaterialTemplates']
        name_template = name
        if name in property_template:
            name_template = property_template[name]

        try:
            value = bind.material_selected[material]['properties'][name_template]
        except KeyError:
            decision2 = RealDecision("Enter value for the parameter %s" % name,
                                     validate_func=lambda x: isinstance(x, float),  # TODO
                                     global_key="%s" % name,
                                     allow_skip=False, allow_load=True, allow_save=True,
                                     collect=False, quick_decide=False)
            decision2.decide()
            value = decision2.value
        try:
            bind.material = bind.material_selected[material]['properties']['name']
        except KeyError:
            bind.material = material
        return value

    area = attribute.Attribute(
        name='area',
        default_ps=True,
        default=1
    )

    is_external = attribute.Attribute(
        name='is_external',
        default_ps=True,
        default=False
    )

    thermal_transmittance = attribute.Attribute(
        name='thermal_transmittance',
        default_ps=True,
        default=0
    )

    material = attribute.Attribute(
        name='material',
        default_ps=True,
        default=0
    )

    thickness = attribute.Attribute(
        name='thickness',
        default_ps=True,
        # functions=[_get_wall_properties],
        default=0
    )

    heat_capacity = attribute.Attribute(
        name='heat_capacity',
        # functions=[_get_wall_properties],
        default=0
    )

    density = attribute.Attribute(
        name='density',
        # functions=[_get_wall_properties],
        default=0
    )

    tilt = attribute.Attribute(
        name='thermal_transmittance',
        default_ps=True,
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
        if hasattr(self.ifc, 'LayerThickness'):
            self.thickness = self.ifc.LayerThickness
        else:
            self.thickness = 0.1
            # self.thickness = float(input('Thickness not given, please provide a value:'))

    def __repr__(self):
        return "<%s (material: %s>" \
               % (self.__class__.__name__, self.material)

    heat_capacity = attribute.Attribute(
        name='heat_capacity',
        default_ps=True,
        default=0
    )

    density = attribute.Attribute(
        name='density',
        default_ps=True,
        default=0
    )

    thermal_conductivity = attribute.Attribute(
        name='thermal_conductivity',
        default_ps=True,
        default=0
    )


class OuterWall(Wall):
    def __init__(self, *args, **kwargs):
        pass


class InnerWall(Wall):
    def __init__(self, *args, **kwargs):
        pass


class Window(element.Element):
    ifc_type = "IfcWindow"
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
        name='layers',
        functions=[_get_layers]
    )

    is_external = attribute.Attribute(
        name='is_external',
        default_ps=True,
        default=True
    )

    area = attribute.Attribute(
        name='area',
        default_ps=True,
        default=0
    )

    thickness = attribute.Attribute(
        name='thickness',
        default_ps=True,
        default=0
    )

    material = attribute.Attribute(
        name='material',
        default_ps=True,
        default=0
    )


class Door(element.Element):
    ifc_type = "IfcDoor"

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
        name='layers',
        functions=[_get_layers]
    )

    is_external = attribute.Attribute(
        name='is_external',
        default_ps=True,
        default=True
    )

    area = attribute.Attribute(
        name='area',
        default_ps=True,
        default=0
    )

    thickness = attribute.Attribute(
        name='thickness',
        default_ps=True,
        default=0
    )

    material = attribute.Attribute(
        name='material',
        default_ps=True,
        default=0
    )

# class OuterWall(Wall):
#     pattern_ifc_type = [
#         re.compile('Outer.?wall', flags=re.IGNORECASE),
#         re.compile('Au(ß|ss)en.?wand', flags=re.IGNORECASE)
#     ]
#
#     @property
#     def area(self):
#         return 1
#
#     @property
#     def u_value(self):
#         return 1
#
#     @property
#     def g_value(self):
#         return 1


class Plate(element.Element):
    ifc_type = "IfcPlate"

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # todo more generic with general function and check of existing
        # subclasses
        # todo ask for decision if not type is inserted
        if self.predefined_type == "ROOF":
            self.__class__ = Roof
            self.__init__()
        if self.predefined_type == "FLOOR":
            self.__class__ = Floor
            self.__init__()
        if self.predefined_type == "BASESLAB":
            self.__class__ = GroundFloor
            self.__init__()

    def _get_layers(bind, name):
        layers = []
        material_layers_dict = get_layers_ifc(bind)
        for layer in material_layers_dict:
            new_layer = element.SubElement.factory(layer, 'IfcMaterialLayer')
            new_layer.parent = bind
            layers.append(new_layer)
        return layers

    layers = attribute.Attribute(
        name='layers',
        functions=[_get_layers]
    )
    area = attribute.Attribute(
        name='area',
        default_ps=True,
        default=0
    )

    thickness = attribute.Attribute(
        name='thickness',
        default_ps=True,
        default=0
    )

    thermal_transmittance = attribute.Attribute(
        name='thermal_transmittance',
        default_ps=True,
        default=0
    )

    is_external = attribute.Attribute(
        name='thermal_transmittance',
        default_ps=True,
        default=0
    )

    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #   self.parent = []
    #   self.sub_slabs = []


class Roof(Slab):
    ifc_type = "IfcRoof"
    # ifc_type = ["IfcRoof", "IfcSlab"]
    # if self.ifc:
    def __init__(self, *args, **kwargs):
        if hasattr(self, 'ifc'):
            self.ifc_type = self.ifc.is_a()
        else:
            super().__init__(*args, **kwargs)


    # predefined_type = {
    #         "IfcSlab": "ROOF",
    #     }


class Floor(Slab):

    def __init__(self, *args, **kwargs):
        pass
    # ifc_type = 'IfcSlab'
    # predefined_type = {
    #         "IfcSlab": "FLOOR",
    #     }


class GroundFloor(Slab):
    def __init__(self, *args, **kwargs):
        pass
    # ifc_type = 'IfcSlab'
    # predefined_type = {
    #         "IfcSlab": "BASESLAB",
    #     }


class Building(element.Element):
    ifc_type = "IFcBuilding"

    year_of_construction = attribute.Attribute(
        name='year_of_construction',
        default_ps=True
    )
    gross_area = attribute.Attribute(
        name='gross_area',
        default_ps=True
    )
    net_area = attribute.Attribute(
        name='net_area',
        default_ps=True
    )
    number_of_storeys = attribute.Attribute(
        name='number_of_storeys',
        default_ps=True
    )
    occupancy_type = attribute.Attribute(
        name='occupancy_type',
        default_ps=True
    )


class Storey(element.Element):
    ifc_type = 'IfcBuildingStorey'

    gross_floor_area = attribute.Attribute(
        name='gross_floor_area',
        default_ps=True
    )
    #todo make the lookup for height hierarchical
    net_height = attribute.Attribute(
        name='net_height',
        default_ps=True
    )
    gross_height = attribute.Attribute(
        name='gross_height',
        default_ps=True
    )
    height = attribute.Attribute(
        name='height',
        default_ps=True
    )


__all__ = [ele for ele in locals().values() if ele in element.Element.__subclasses__()]
