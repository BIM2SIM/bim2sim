﻿"""Module contains the different classes for all HVAC elements"""

from functools import lru_cache

import math
import re

import numpy as np
import copy
import translators as ts
import ifcopenshell
import ifcopenshell.geom
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.BRepBndLib import brepbndlib_Add
from OCC.Core.BRepLib import BRepLib_FuseEdges
from OCC.Core.BRepBuilderAPI import \
    BRepBuilderAPI_MakeFace, \
    BRepBuilderAPI_MakeEdge, \
    BRepBuilderAPI_MakeWire, BRepBuilderAPI_Transform, BRepBuilderAPI_MakeVertex
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Fuse
from OCC.Core.BRepGProp import brepgprop_SurfaceProperties, brepgprop_VolumeProperties
from OCC.Core.GProp import GProp_GProps
from OCC.Core.GeomAPI import GeomAPI_ProjectPointOnCurve
from OCC.Core.ShapeAnalysis import ShapeAnalysis_ShapeContents
from OCC.Core.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Core.gp import gp_Trsf, gp_Vec, gp_XYZ,  gp_Dir, gp_Ax1, gp_Pnt
from OCC.Core.TopoDS import topods_Wire, topods_Face, TopoDS_Iterator
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_WIRE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.BRep import BRep_Tool
from OCC.Core.BRepTools import BRepTools_WireExplorer
from OCC.Core._Geom import Handle_Geom_Plane_DownCast
from OCC.Core.Extrema import Extrema_ExtFlag_MIN

from bim2sim.kernel import element, condition, attribute
from bim2sim.decision import BoolDecision, RealDecision, ListDecision
from bim2sim.kernel.units import ureg
from bim2sim.kernel.ifc2python import get_layers_ifc
from teaser.logic.buildingobjects.useconditions import UseConditions
from bim2sim.task.common.common_functions import vector_angle, filter_instances
from bim2sim.kernel.disaggregation import SubInnerWall, SubOuterWall, Disaggregation
from bim2sim.project import PROJECT


def diameter_post_processing(value):
    if isinstance(value, (list, set)):
        return sum(value) / len(value)
    return value


def length_post_processing(value):
    if isinstance(value, (list, set)):
        return max(value)
    return value


class HeatPump(element.Element):
    """"HeatPump"""

    ifc_type = 'IfcUnitaryEquipment'
    predefined_type = ['NOTDEFINED']

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
        """boiler is generator function"""
        return True

    @lru_cache()
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
        default_ps=('Pset_PipeFittingTypeCommon', 'NominalDiameter'),
        unit=ureg.millimeter,
        patterns=[
            re.compile('.*Durchmesser.*', flags=re.IGNORECASE),
            re.compile('.*Diameter.*', flags=re.IGNORECASE),
        ],
        ifc_postprocessing=diameter_post_processing,
    )

    length = attribute.Attribute(
        default_ps=("Qto_PipeSegmentBaseQuantities", "Length"),
        unit=ureg.meter,
        patterns=[
            re.compile('.*Länge.*', flags=re.IGNORECASE),
            re.compile('.*Length.*', flags=re.IGNORECASE),
        ],
        default=0,
        ifc_postprocessing=length_post_processing
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
        re.compile('Distributor', flags=re.IGNORECASE),
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
    )

    def get_is_external(self, name):
        """determines if a thermal zone is external or internal
        based on its elements (Walls and windows analysis)"""
        outer_walls = filter_instances(self.bound_elements, 'OuterWall')
        if len(outer_walls) > 0:
            return True
        else:
            return False

    def get_external_orientation(self, name):
        """determines the orientation of the thermal zone
        based on its elements
        it can be a corner (list of 2 angles) or an edge (1 angle)"""
        if self.is_external is True:
            orientations = []
            outer_walls = filter_instances(self.bound_elements, 'OuterWall')
            for ele in outer_walls:
                if hasattr(ele, 'orientation'):
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
        else:
            return 'Internal'

    def get_glass_area(self, name):
        """determines the glass area/facade area ratio for all the windows in the space in one of the 4 following ranges
        0%-30%: 15
        30%-50%: 40
        50%-70%: 60
        70%-100%: 85"""
        windows = filter_instances(self.bound_elements, 'Window')
        outer_walls = filter_instances(self.bound_elements, 'OuterWall')
        glass_area = sum(wi.area for wi in windows).m if len(windows) > 0 else 0
        facade_area = sum(wa.area for wa in outer_walls).m if len(outer_walls) > 0 else 0
        if facade_area > 0:
            return 100 * (glass_area / (facade_area + glass_area))
        else:
            return 'Internal'

    def get_neighbors(self, name):
        """determines the neighbors of the thermal zone"""
        neighbors = []
        for sb in self.space_boundaries:
            if sb.related_bound is not None:
                tz = sb.related_bound.thermal_zones[0]
                #todo: check if computation of neighbors works as expected
                #what if boundary has no related bound but still has a neighbor?
                #hint: neighbors != related bounds
                if (tz is not self) and (tz not in neighbors):
                    neighbors.append(tz)
        return neighbors

    def _get_cooling(bind, name):
        """get cooling parameters for thermal zone"""
        if bind.t_set_cool is not None:
            return True
        else:
            cooling_decision = BoolDecision(
                question="Do you want for the thermal zone %s to be cooled? - with cooling" % bind.name,
                collect=False, global_key="%s_%s.Cooling" % (type(bind).__name__, bind.guid),
                allow_skip=False, allow_load=True, allow_save=True, quick_decide=not True
            )
            cooling_decision.decide()
            if cooling_decision.value:
                return True
            else:
                return False

    def _get_heating(bind, name):
        """get heating parameters for thermal zone"""
        if bind.t_set_heat is not None:
            return True
        else:
            heating_decision = BoolDecision(
                question="Do you want for the thermal zone %s to be heated? - with heating" % bind.name,
                collect=False,
                global_key="%s_%s.Heating" % (type(bind).__name__, bind.guid),
                allow_skip=False, allow_load=True, allow_save=True, quick_decide=not True
            )
            heating_decision.decide()
            if heating_decision.value:
                return True
            else:
                return False

    def get_space_shape(bind, name):
        """returns topods shape of the IfcSpace"""
        settings = ifcopenshell.geom.main.settings()
        settings.set(settings.USE_PYTHON_OPENCASCADE, True)
        settings.set(settings.USE_WORLD_COORDS, True)
        settings.set(settings.EXCLUDE_SOLIDS_AND_SURFACES, False)
        settings.set(settings.INCLUDE_CURVES, True)
        return ifcopenshell.geom.create_shape(settings, bind.ifc).geometry

    def get_center_of_space(bind, name):
        """
        This function returns the center of the bounding box of an ifc space shape
        :return: center of space bounding box (gp_Pnt)
        """
        bbox = Bnd_Box()
        brepbndlib_Add(bind.space_shape, bbox)
        bbox_center = ifcopenshell.geom.utils.get_bounding_box_center(bbox)
        return bbox_center

    def get_space_volume(bind, name):
        props = GProp_GProps()
        brepgprop_VolumeProperties(bind.space_shape, props)
        volume = props.Mass()
        return volume

    def _get_volume(self, name):
        return self.area*self.height

    usage = attribute.Attribute(
    )
    t_set_heat = attribute.Attribute(
        default_ps=("Pset_SpaceThermalRequirements", "SpaceTemperatureMin"),
        unit=ureg.degC,
        default=15
    )
    t_set_cool = attribute.Attribute(
        default_ps=("Pset_SpaceThermalRequirements", "SpaceTemperatureMax"),
        unit=ureg.degC,
        default=22
    )
    area = attribute.Attribute(
        default_ps=("Qto_SpaceBaseQuantities", "GrossFloorArea"),
        default=0,
        unit=ureg.meter ** 2
    )
    net_volume = attribute.Attribute(
        default_ps=("Qto_SpaceBaseQuantities", "NetVolume"),
        default=0
    )
    volume = attribute.Attribute(
        functions=[_get_volume],
        unit=ureg.meter**3,
        default=0
    )
    height = attribute.Attribute(
        default_ps=("Qto_SpaceBaseQuantities", "Height"),
        unit=ureg.meter,
        default=0
    )
    length = attribute.Attribute(
        default_ps=("Qto_SpaceBaseQuantities", "Length"),
        default=0
    )
    width = attribute.Attribute(
        default_ps=("Qto_SpaceBaseQuantities", "Width"),
        default=0,
        unit=ureg.m
    )
    with_cooling = attribute.Attribute(
        functions=[_get_cooling]
    )
    with_heating = attribute.Attribute(
        functions=[_get_heating]
    )
    with_ahu = attribute.Attribute(
        default_ps=("Pset_SpaceThermalRequirements", "AirConditioning"),
    )
    AreaPerOccupant = attribute.Attribute(
        default_ps=("Pset_SpaceOccupancyRequirements", "AreaPerOccupant"),
        unit=ureg.meter ** 2
    )
    space_center = attribute.Attribute(
        functions=[get_center_of_space]
    )
    space_shape = attribute.Attribute(
        functions=[get_space_shape]
    )
    space_volume = attribute.Attribute(
        functions=[get_space_volume]
    )
    glass_percentage = attribute.Attribute(
        functions=[get_glass_area]
    )
    is_external = attribute.Attribute(
        functions=[get_is_external]
    )
    external_orientation = attribute.Attribute(
        functions=[get_external_orientation]
    )
    space_neighbors = attribute.Attribute(
        functions=[get_neighbors]
    )

    def __init__(self, *args, **kwargs):
        """thermalzone __init__ function"""
        super().__init__(*args, **kwargs)
        self.bound_elements = []

    def get__elements_by_type(self, type):
        raise NotImplementedError


class SpaceBoundary(element.SubElement):
    ifc_type = 'IfcRelSpaceBoundary'

    def __init__(self, *args, **kwargs):
        """spaceboundary __init__ function"""
        super().__init__(*args, **kwargs)
        self.guid = self.ifc.GlobalId  # check this
        self.level_description = self.ifc.Description
        relating_space = self.get_object(self.ifc.RelatingSpace.GlobalId)
        relating_space.space_boundaries.append(self)
        self.thermal_zones.append(relating_space)
        related_building_element = self.get_object(self.ifc.RelatedBuildingElement.GlobalId)
        related_building_element.space_boundaries.append(self)
        self.bound_instance = related_building_element
        self.disaggregation = []

        if self.ifc.InternalOrExternalBoundary.lower() == 'internal':
            self.is_external = False
        else:
            self.is_external = True
        if self.ifc.PhysicalOrVirtualBoundary.lower() == 'physical':
            self.physical = True
        else:
            self.physical = False
        self.storeys = self.get_space_boundary_storeys()
        self.orientation = self._get_orientation()
        self.position = self._get_position()

    def _get_orientation(self):

        # get relative position of resultant disaggregation
        if hasattr(self.ifc.ConnectionGeometry.SurfaceOnRelatingElement, 'BasisSurface'):
            axis = self.ifc.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface.Position.Axis.DirectionRatios
        else:
            axis = self.ifc.ConnectionGeometry.SurfaceOnRelatingElement.Position.Axis.DirectionRatios

        return vector_angle(axis)

    def _get_position(self):
        # get relative position of resultant disaggregation
        if hasattr(self.ifc.ConnectionGeometry.SurfaceOnRelatingElement, 'BasisSurface'):
            position = self.ifc.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface.Position.Location.Coordinates
        else:
            position = self.ifc.ConnectionGeometry.SurfaceOnRelatingElement.Position.Location.Coordinates

        return position

    def get_bound_neighbors(bind, name):
        neighbors = []
        space_bounds = []
        if not hasattr(bind.thermal_zones[0], 'space_boundaries'):
            return None
        if len(bind.thermal_zones[0].space_boundaries) == 0:
            for obj in bind.thermal_zones[0].objects:
                this_obj = bind.thermal_zones[0].objects[obj]
                if this_obj.ifc_type != 'IfcRelSpaceBoundary':
                    continue
                if this_obj.thermal_zones[0].ifc.GlobalId != bind.thermal_zones[0].ifc.GlobalId:
                    continue
                space_bounds.append(this_obj)
        else:
            space_bounds = bind.thermal_zones[0].space_boundaries
        for bound in space_bounds:
            if bound.ifc.GlobalId == bind.ifc.GlobalId:
                continue
            distance = BRepExtrema_DistShapeShape(bound.bound_shape, bind.bound_shape, Extrema_ExtFlag_MIN).Value()
            if distance == 0:
                neighbors.append(bound)
        return neighbors

    def get_bound_area(bind, name):
        """compute area of a space boundary"""
        bound_prop = GProp_GProps()
        brepgprop_SurfaceProperties(bind.bound_shape, bound_prop)
        area = bound_prop.Mass()
        return area

    def get_floor_and_ceilings(bind, name):
        """
        This function computes, if the center of a space boundary
        is below (bottom) or above (top) the center of a space.
        This function is used to distinguish floors and ceilings (IfcSlab)
        :return: top_bottom ("TOP", "BOTTOM")
        """
        top_bottom = None
        vertical = gp_XYZ(0.0, 0.0, 1.0)
        # only assign top and bottom for elements, whose
        # surface normals are not perpendicular to a vertical
        if -1e-3 < bind.bound_normal.Dot(vertical) <1e-3:
            top_bottom = "VERTICAL"
        elif bind.related_bound != None:
            if (bind.bound_center.Z() - bind.related_bound.bound_center.Z()) > 1e-2:
                top_bottom = "BOTTOM"
            elif (bind.bound_center.Z() - bind.related_bound.bound_center.Z()) < -1e-2:
                top_bottom = "TOP"
            else:
                if vertical.Dot(bind.bound_normal) < -0.8:
                    top_bottom = "BOTTOM"
                elif vertical.Dot(bind.bound_normal) > 0.8:
                    top_bottom = "TOP"
        elif bind.related_adb_bound != None:
                if bind.bound_center.Z() > bind.related_adb_bound.bound_center.Z():
                    top_bottom = "BOTTOM"
                else:
                    top_bottom = "TOP"
        else:
            # direct = self.bound_center.Z() - self.thermal_zones[0].space_center.Z()
            # if direct < 0 and SpaceBoundary._compare_direction_of_normals(self.bound_normal, vertical):
            if vertical.Dot(bind.bound_normal) < -0.8:
                top_bottom = "BOTTOM"
            elif vertical.Dot(bind.bound_normal) > 0.8:
                top_bottom = "TOP"
        return top_bottom

    # @staticmethod
    # def _compare_direction_of_normals(normal1, normal2):
    #     """
    #     Compare the direction of two surface normals (vectors).
    #     True, if direction is same or reversed
    #     :param normal1: first normal (gp_Pnt)
    #     :param normal2: second normal (gp_Pnt)
    #     :return: True/False
    #     """
    #     dotp = normal1.Dot(normal2)
    #     check = False
    #     if 1-1e-2 < dotp ** 2 < 1+1e-2:
    #         check = True
    #     return check

    def get_bound_center(bind, name):
        """ compute center of the bounding box of a space boundary"""
        p = GProp_GProps()
        brepgprop_SurfaceProperties(bind.bound_shape, p)
        return p.CentreOfMass().XYZ()

    def get_corresponding_bound(bind, name):
        """
        Get corresponding space boundary in another space,
        ensuring that corresponding space boundaries have a matching number of vertices.
        """
        if hasattr(bind.ifc, 'CorrespondingBoundary') and bind.ifc.CorrespondingBoundary is not None:
            corr_bound = bind.get_object(bind.ifc.CorrespondingBoundary.GlobalId)
            if corr_bound.ifc.RelatingSpace.is_a('IfcSpace'):
                if not corr_bound.ifc.RelatingSpace.is_a('IfcExternalSpatialStructure'):
                    return corr_bound
        if bind.bound_instance is None:
            return None
            # check for visual bounds
            # if bind.level_description != "2a":
            #     return None
            # if not bind.physical:
            #     corr_bound = None
            #     bounds = []
            #     min_dist = 1000
            #     for obj in bind.thermal_zones[0].objects:
            #         if bind.thermal_zones[0].objects[obj].ifc_type == 'IfcRelSpaceBoundary':
            #             bounds.append(bind.thermal_zones[0].objects[obj])
            #     for bound in bounds:
            #         if bound.physical:
            #             continue
            #         if bound.thermal_zones[0].ifc.GlobalId == bind.thermal_zones[0].ifc.GlobalId:
            #             continue
            #         if (bound.bound_area-bind.bound_area)**2 > 1:
            #             continue
            #         if bound.ifc.GlobalId == bind.ifc.GlobalId:
            #             continue
            #         if bound.bound_normal.Dot(bind.bound_normal) != -1:
            #             continue
            #         distance = BRepExtrema_DistShapeShape(
            #             bound.bound_shape,
            #             bind.bound_shape,
            #             Extrema_ExtFlag_MIN
            #         ).Value()
            #         if distance > min_dist or distance > 0.4:
            #             continue
            #         bind.check_for_vertex_duplicates(bound)
            #         nb_vert_this = bind._get_number_of_vertices(bind.bound_shape)
            #         nb_vert_other = bind._get_number_of_vertices(bound.bound_shape)
            #         center_dist = gp_Pnt(bind.bound_center).Distance(gp_Pnt(bound.bound_center)) ** 2
            #         if (center_dist) > 0.5:
            #             continue
            #         if nb_vert_other != nb_vert_this:
            #             # replace bound shape by corresponding bound shape
            #             rel_dist = BRepExtrema_DistShapeShape(bind.bound_shape, bound.bound_shape, Extrema_ExtFlag_MIN).Value()
            #             bind.bound_shape = copy.copy(bound.bound_shape.Reversed())
            #             bind.bound_shape = bind.move_bound_in_direction_of_normal(bind.bound_shape, bind.bound_normal,
            #                                                                       rel_dist, reversed=True)
            #         corr_bound = bound
            #     return corr_bound
            #     # for bound in self.objects.
            # return None
        elif len(bind.bound_instance.space_boundaries) == 1:
            return None
        # elif len(bind.bound_instance.space_boundaries) == 2:
        #     if bind.bound_instance.guid == '3QvvbxsHP1IRaR5M7CZy9i':
        #         print()
        #     for bound in bind.bound_instance.space_boundaries:
        #         if bound.ifc.GlobalId == bind.ifc.GlobalId:
        #             continue
        #         if bound.bound_normal.Dot(bind.bound_normal) != -1:
        #             continue
        #         bind.check_for_vertex_duplicates(bound)
        #         nb_vert_this = bind._get_number_of_vertices(bind.bound_shape)
        #         nb_vert_other = bind._get_number_of_vertices(bound.bound_shape)
        #         if nb_vert_this == nb_vert_other:
        #             return bound
        #         else:
        #             return None
        elif len(bind.bound_instance.space_boundaries) >= 2:
            own_space_id = bind.thermal_zones[0].ifc.GlobalId
            min_dist = 1000
            corr_bound = None
            for bound in bind.bound_instance.space_boundaries:
                if bound.level_description != "2a":
                    continue
                if bound.thermal_zones[0].ifc.GlobalId == own_space_id:
                    # skip boundaries within same space (cannot be corresponding bound)
                    continue
                # if bound.bound_normal.Dot(self.bound_normal) != -1:
                #     continue
                distance = BRepExtrema_DistShapeShape(
                    bound.bound_shape,
                    bind.bound_shape,
                    Extrema_ExtFlag_MIN
                ).Value()
                center_dist = gp_Pnt(bind.bound_center).Distance(gp_Pnt(bound.bound_center))**2
                if (center_dist)**0.5 > 0.5:
                    continue
                if distance > min_dist:
                    continue
                other_area = bound.bound_area
                if (other_area.m - bind.bound_area.m)**2 < 1e-1:
                    bind.check_for_vertex_duplicates(bound)
                    nb_vert_this = bind._get_number_of_vertices(bind.bound_shape)
                    nb_vert_other = bind._get_number_of_vertices(bound.bound_shape)
                    if nb_vert_this == nb_vert_other:
                        corr_bound = bound
            return corr_bound
        else:
            return None

    def get_rel_adiab_bound(self, name):
        adb_bound = None
        if self.bound_instance is None:
            return None
            # check for visual bounds
        if not self.physical:
            return None
        for bound in self.bound_instance.space_boundaries:
            if bound == self:
                continue
            if not bound.thermal_zones[0] == self.thermal_zones[0]:
                continue
            if (bound.bound_area.m - self.bound_area.m)**2 > 0.01:
                continue
            if gp_Pnt(bound.bound_center).Distance(gp_Pnt(self.bound_center)) < 0.4:
                adb_bound = bound
        return adb_bound

    @staticmethod
    def move_bound_in_direction_of_normal(shape, normal, move_dist, reversed=False):
        prod_vec = []
        move_dir = normal.Coord()
        if reversed:
            move_dir = normal.Reversed().Coord()
        for i in move_dir:
            prod_vec.append(move_dist * i)

        # move bound in direction of bound normal by move_dist
        trsf = gp_Trsf()
        coord = gp_XYZ(*prod_vec)
        vec = gp_Vec(coord)
        trsf.SetTranslation(vec)
        moved_shape = BRepBuilderAPI_Transform(shape, trsf).Shape()

        return moved_shape

    def check_for_vertex_duplicates(self, rel_bound):
        return  # todo: Bugfix, disabled for now
        nb_vert_this = self._get_number_of_vertices(self.bound_shape)
        nb_vert_other = self._get_number_of_vertices(rel_bound.bound_shape)
        # if nb_vert_this != nb_vert_other:
        setattr(self, 'bound_shape_org', self.bound_shape)
        vert_list1 = self._get_vertex_list_from_face(self.bound_shape)
        vert_list1 = self._remove_vertex_duplicates(vert_list1)
        vert_list1.reverse()
        vert_list1 = self._remove_vertex_duplicates(vert_list1)

        setattr(rel_bound, 'bound_shape_org', rel_bound.bound_shape)
        vert_list2 = self._get_vertex_list_from_face(rel_bound.bound_shape)
        vert_list2 = self._remove_vertex_duplicates(vert_list2)
        vert_list2.reverse()
        vert_list2 = self._remove_vertex_duplicates(vert_list2)
        if len(vert_list1) == len(vert_list2):
            if len(vert_list1) < 5:
                return
            vert_list1.reverse()
            vert_list2.reverse()
            self.bound_shape = self._make_face_from_vertex_list(vert_list1)
            rel_bound.bound_shape = self._make_face_from_vertex_list(vert_list2)

    @staticmethod
    def _remove_vertex_duplicates(vert_list):
        for i, vert in enumerate(vert_list):
            edge_pp_p = BRepBuilderAPI_MakeEdge(vert_list[(i) % (len(vert_list) - 1)],
                                                vert_list[(i + 1) % (len(vert_list) - 1)]).Shape()
            distance = BRepExtrema_DistShapeShape(vert_list[(i + 2) % (len(vert_list) - 1)], edge_pp_p,
                                                  Extrema_ExtFlag_MIN)
            if 0 < distance.Value() < 0.001:
                # first: project close vertex to edge
                edge = BRepBuilderAPI_MakeEdge(vert_list[(i) % (len(vert_list) - 1)],
                                               vert_list[(i + 1) % (len(vert_list) - 1)]).Edge()
                projector = GeomAPI_ProjectPointOnCurve(BRep_Tool.Pnt(vert_list[(i + 2) % (len(vert_list) - 1)]),
                                                        BRep_Tool.Curve(edge)[0])
                np = projector.NearestPoint()
                vert_list[(i + 2) % (len(vert_list) - 1)] = BRepBuilderAPI_MakeVertex(np).Vertex()
                # delete additional vertex
                vert_list.pop((i + 1) % (len(vert_list) - 1))
        return vert_list

    @staticmethod
    def _remove_collinear_vertices(vert_list):
        vert_list = vert_list[:-1]
        if len(vert_list) < 5:
            return vert_list
        for i, vert in enumerate(vert_list):
            vert_dist = BRepExtrema_DistShapeShape(vert_list[(i) % (len(vert_list))],
                                                   vert_list[(i + 2) % (len(vert_list))],
                                                   Extrema_ExtFlag_MIN).Value()
            if vert_dist < 1e-3:
                return vert_list
            edge_pp_p = BRepBuilderAPI_MakeEdge(vert_list[(i) % (len(vert_list))],
                                                vert_list[(i + 2) % (len(vert_list))]).Shape()
            distance = BRepExtrema_DistShapeShape(vert_list[(i + 1) % (len(vert_list))], edge_pp_p,
                                                  Extrema_ExtFlag_MIN).Value()
            if distance < 1e-3:
                vert_list.pop((i + 1) % (len(vert_list)))

        vert_list.append(vert_list[0])
        return vert_list

    @staticmethod
    def _make_faces_from_pnts(pnt_list):
        """
        This function returns a TopoDS_Face from list of gp_Pnt
        :param pnt_list: list of gp_Pnt or Coordinate-Tuples
        :return: TopoDS_Face
        """
        an_edge = []
        if isinstance(pnt_list[0], tuple):
            new_list = []
            for pnt in pnt_list:
                new_list.append(gp_Pnt(gp_XYZ(pnt[0], pnt[1], pnt[2])))
            pnt_list = new_list
        for i in range(len(pnt_list[:-1])):
            edge = BRepBuilderAPI_MakeEdge(pnt_list[i], pnt_list[i + 1]).Edge()
            an_edge.append(edge)
        a_wire = BRepBuilderAPI_MakeWire()
        for edge in an_edge:
            a_wire.Add(edge)
        a_wire = a_wire.Wire()
        a_face = BRepBuilderAPI_MakeFace(a_wire).Face()
        return a_face

    @staticmethod
    def _make_face_from_vertex_list(vert_list):
        an_edge = []
        for i in range(len(vert_list[:-1])):
            edge = BRepBuilderAPI_MakeEdge(vert_list[i], vert_list[i + 1]).Edge()
            an_edge.append(edge)
        a_wire = BRepBuilderAPI_MakeWire()
        for edge in an_edge:
            a_wire.Add(edge)
        a_wire = a_wire.Wire()
        a_face = BRepBuilderAPI_MakeFace(a_wire).Face()

        return a_face  # .Reversed()

    @staticmethod
    def _get_vertex_list_from_face(face):
        # fc_exp = TopExp_Explorer(face, TopAbs_FACE)
        # fc = topods_Face(fc_exp.Current())
        # fc = bps.ExportEP.fix_face(fc)
        # an_exp = TopExp_Explorer(fc, TopAbs_WIRE)
        an_exp = TopExp_Explorer(face, TopAbs_WIRE)
        vert_list = []
        while an_exp.More():
            wire = topods_Wire(an_exp.Current())
            w_exp = BRepTools_WireExplorer(wire)
            while w_exp.More():
                vert1 = w_exp.CurrentVertex()
                vert_list.append(vert1)
                w_exp.Next()
            an_exp.Next()
        vert_list.append(vert_list[0])

        return vert_list

    @staticmethod
    def _get_number_of_vertices(shape):
        shape_analysis = ShapeAnalysis_ShapeContents()
        shape_analysis.Perform(shape)
        nb_vertex = shape_analysis.NbVertices()

        return nb_vertex

    def calc_bound_shape(self, name):
        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_PYTHON_OPENCASCADE, True)
        settings.set(settings.USE_WORLD_COORDS, True)
        settings.set(settings.EXCLUDE_SOLIDS_AND_SURFACES, False)
        settings.set(settings.INCLUDE_CURVES, True)

        try:
            sore = self.ifc.ConnectionGeometry.SurfaceOnRelatingElement
            # if sore.get_info()["InnerBoundaries"] is None:
            sore.InnerBoundaries = ()
            shape = ifcopenshell.geom.create_shape(settings, sore)
        except:
            try:
                shape = ifcopenshell.geom.create_shape(settings,
                                                       self.ifc.ConnectionGeometry.SurfaceOnRelatingElement.OuterBoundary)
            except:
                poly = self.ifc.ConnectionGeometry.SurfaceOnRelatingElement.OuterBoundary.Points
                pnts = []
                for p in poly:
                    p.Coordinates = (p.Coordinates[0], p.Coordinates[1], 0.0)
                    pnts.append((p.Coordinates[:]))
                shape = self._make_faces_from_pnts(pnts)
        shape = BRepLib_FuseEdges(shape).Shape()

        shape_val = TopoDS_Iterator(self.thermal_zones[0].space_shape).Value()
        loc = shape_val.Location()
        shape.Move(loc)
        # shape = shape.Reversed()
        unify = ShapeUpgrade_UnifySameDomain()
        unify.Initialize(shape)
        unify.Build()
        shape = unify.Shape()

        if self.bound_instance is not None:
            bi = self.bound_instance
            if not hasattr(bi, "related_openings"):
                return shape
            if len(bi.related_openings) == 0:
                return shape
            # for op in bi.related_openings:
            #     if op.ifc_type != "IfcDoor":
            #         continue
            #     # bbox = Bnd_Box()
            #     # brepbndlib_Add(shape, bbox)
            #     # shape = BRepPrimAPI_MakeBox(bbox.CornerMin(), bbox.CornerMax()).Shape()
            #     # shape = bps.ExportEP.fix_shape(shape)
            #     opd_shp = None
            #     for opb in op.space_boundaries:
            #         distance = BRepExtrema_DistShapeShape(opb.bound_shape, shape, Extrema_ExtFlag_MIN).Value()
            #         if distance < 1e-3:
            #             opd_shp = opb.bound_shape
            #             fused_shp = BRepAlgoAPI_Fuse(shape, opd_shp).Shape()
            #             unify = ShapeUpgrade_UnifySameDomain()
            #             unify.Initialize(fused_shp)
            #             unify.Build()
            #             shape = unify.Shape()
            #             shape = bps.ExportEP.fix_shape(shape)
            #             vert_list1 = self._get_vertex_list_from_face(shape)
            #             vert_list1 = self._remove_collinear_vertices(vert_list1)
            #             vert_list1.reverse()
            #             vert_list1 = self._remove_collinear_vertices(vert_list1)
            #             vert_list1.reverse()
            #             shape = self._make_face_from_vertex_list(vert_list1)

        return shape

    def get_transformed_shape(self, shape):
        """transform TOPODS_Shape of each space boundary to correct position"""
        zone = self.thermal_zones[0]
        zone_position = gp_XYZ(zone.position[0], zone.position[1], zone.position[2])
        trsf1 = gp_Trsf()
        trsf2 = gp_Trsf()
        if zone.orientation == None:
            zone.orientation = 0
        trsf2.SetRotation(gp_Ax1(gp_Pnt(zone_position), gp_Dir(0, 0, 1)), -zone.orientation * math.pi / 180)
        trsf1.SetTranslation(gp_Vec(gp_XYZ(zone.position[0], zone.position[1], zone.position[2])))
        try:
            shape = BRepBuilderAPI_Transform(shape, trsf1).Shape()
            shape = BRepBuilderAPI_Transform(shape, trsf2).Shape()
        except:
            pass
        return shape.Reversed()

    def compute_surface_normals_in_space(self, name):
        """
        This function returns the face normal of the boundary
        pointing outwarts the center of the space.
        Additionally, the area of the boundary is computed
        :return: face normal (gp_XYZ)
        """
        bbox_center = self.thermal_zones[0].space_center
        an_exp = TopExp_Explorer(self.bound_shape, TopAbs_FACE)
        a_face = an_exp.Current()
        try:
            face = topods_Face(a_face)
        except:
            pnts = bps.IdfObject._get_points_of_face(a_face)
            pnts.append(pnts[0])
            face = self._make_faces_from_pnts(pnts)
        surf = BRep_Tool.Surface(face)
        obj = surf
        assert obj.DynamicType().Name() == "Geom_Plane"
        plane = Handle_Geom_Plane_DownCast(surf)
        # face_bbox = Bnd_Box()
        # brepbndlib_Add(face, face_bbox)
        # face_center = ifcopenshell.geom.utils.get_bounding_box_center(face_bbox).XYZ()
        face_prop = GProp_GProps()
        brepgprop_SurfaceProperties(self.bound_shape, face_prop)
        area = face_prop.Mass()
        face_normal = plane.Axis().Direction().XYZ()
        if face.Orientation() == 1:
            face_normal = face_normal.Reversed()
        face_towards_center = bbox_center.XYZ() - self.bound_center
        face_towards_center.Normalize()

        dot = face_towards_center.Dot(face_normal)

        # check if surface normal points into direction of space center
        # Transform surface normals to be pointing outwards
        # For faces without reversed surface normal, reverse the orientation of the face itself
        # if dot > 0:
        #    face_normal = face_normal.Reversed()
        #     self.bound_shape = self.bound_shape.Reversed()
        # else:
        #     self.bound_shape = self.bound_shape.Reversed()

        return face_normal

    bound_shape = attribute.Attribute(
        functions=[calc_bound_shape]
    )
    bound_normal = attribute.Attribute(
        functions=[compute_surface_normals_in_space]
    )
    related_bound = attribute.Attribute(
        functions=[get_corresponding_bound]
    )
    related_adb_bound = attribute.Attribute(
        functions=[get_rel_adiab_bound]
    )
    bound_center = attribute.Attribute(
        functions=[get_bound_center]
    )
    top_bottom = attribute.Attribute(
        functions=[get_floor_and_ceilings]
    )
    bound_area = attribute.Attribute(
        functions=[get_bound_area],
        unit=ureg.meter ** 2
    )
    # area = attribute.Attribute(
    #     functions=[get_bound_area]
    # )
    bound_neighbors = attribute.Attribute(
        functions=[get_bound_neighbors]
    )

    def get_space_boundary_storeys(self):
        storeys = self.thermal_zones[0].storeys

        return storeys

# class SpaceBoundary2B:
#     """Generated 2nd Level Space boundaries of type 2b
#     (generated if not included in IFC)
#     """
#     def __init__(self):
#         self.ifc_type = None
#         self.guid = None
#         self.bound_shape = None
#         self.bound_neighbors = []
#         self.thermal_zones = []
#         self.bound_instance = None
#         self.physical = True
#         self.is_external = False
#         self.related_bound = None
#         self.related_adb_bound = None
#         self.level_description = '2b'
#
#     def __str__(self):
#         return "%s" % self.__class__.__name__
#
#     @cached_property
#     def bound_center(self):
#         return SpaceBoundary.get_bound_center(self)
#
#     @cached_property
#     def bound_normal(self):
#         return SpaceBoundary.compute_surface_normals_in_space(self)
#
#     @cached_property
#     def bound_area(self):
#         return SpaceBoundary.get_bound_area(self.bound_shape)
#
#     @cached_property
#     def top_bottom(self):
#         return SpaceBoundary.get_floor_and_ceilings(self)
#
#
# class ExtSpatialSpaceBoundary(element.SubElement):
#     # ifc_type = 'IfcRelSpaceBoundary'
#     # def __init__(self):
#     #     """External Spatial Element spaceboundary __init__ function"""
#         # super().__init__(*args, **kwargs)
#     pass

class Medium(element.Element):
    # is deprecated?
    ifc_type = "IfcDistributionSystems"
    pattern_ifc_type = [
        re.compile('Medium', flags=re.IGNORECASE)
    ]


class CHP(element.Element):
    ifc_type = 'IfcElectricGenerator'
    predefined_type = ['CHP']

    rated_power = attribute.Attribute(
        default_ps=('Pset_ElectricGeneratorTypeCommon', 'MaximumPowerOutput'),
        description="Rated power of CHP",
        patterns=[
          re.compile('.*Nennleistung', flags=re.IGNORECASE),
          re.compile('.*capacity', flags=re.IGNORECASE),
        ],
        unit=ureg.kilowatt,
    )

    efficiency = attribute.Attribute(
        default_ps=('Pset_ElectricGeneratorTypeCommon', 'ElectricGeneratorEfficiency'),
        description="Electric efficiency of CHP",
        patterns=[
            re.compile('.*electric.*efficiency', flags=re.IGNORECASE),
            re.compile('.*el.*efficiency', flags=re.IGNORECASE),
        ],
        unit=ureg.dimensionless,
    )

    water_volume = attribute.Attribute(
        description="Water volume CHP chp",
        unit=ureg.meter ** 3,
    )


class Wall(element.Element):
    ifc_type = ["IfcWall", "IfcWallStandardCase"]
    predefined_types = ['MOVABLE', 'PARAPET', 'PARTITIONING', 'PLUMBINGWALL', 'SHEAR', 'SOLIDWALL', 'POLYGONAL',
                        'DOOR', 'GATE', 'TRAPDOOR']
    pattern_ifc_type = [
        re.compile('Wall', flags=re.IGNORECASE),
        re.compile('Wand', flags=re.IGNORECASE)
    ]
    material_selected = {}

    def __init__(self, *args, **kwargs):
        """wall __init__ function"""
        super().__init__(*args, **kwargs)
        self.ifc_type = self.ifc.is_a()

    def _get_layers(bind, name):
        """wall _get_layers function"""
        layers = []
        material_layers_dict = get_layers_ifc(bind)
        for layer in material_layers_dict:
            new_layer = element.SubElement.factory(layer, 'IfcMaterialLayer')
            new_layer.parent = bind
            layers.append(new_layer)
        return layers

    def get_is_external(self, name):
        if len(self.ifc.ProvidesBoundaries) > 0:
            boundary = self.ifc.ProvidesBoundaries[0]
            if boundary.InternalOrExternalBoundary is not None:
                if boundary.InternalOrExternalBoundary.lower() == 'external':
                    return True
                elif boundary.InternalOrExternalBoundary.lower() == 'internal':
                    return False

    layers = attribute.Attribute(
        functions=[_get_layers]
    )
    area = attribute.Attribute(
        default_ps=("QTo_WallBaseQuantities", "NetSideArea"),
        default=0,
        unit=ureg.meter ** 2
    )
    gross_area = attribute.Attribute(
        default_ps=("QTo_WallBaseQuantities", "GrossSideArea"),
        default=1,
        unit=ureg.meter ** 2
    )
    is_external = attribute.Attribute(
        functions=[get_is_external],
        default=False
    )
    tilt = attribute.Attribute(
        default=90
    )
    u_value = attribute.Attribute(
        default_ps=("Pset_WallCommon", "ThermalTransmittance"),
        unit=ureg.W / ureg.K / ureg.meter ** 2
    )
    width = attribute.Attribute(
        default_ps=("QTo_WallBaseQuantities", "Width"),
        unit=ureg.m
    )


class Layer(element.SubElement):
    ifc_type = ['IfcMaterialLayer', 'IfcMaterial']
    material_selected = {}

    def __init__(self, *args, **kwargs):
        """layer __init__ function"""
        super().__init__(*args, **kwargs)
        self.material = None
        if hasattr(self.ifc, 'Material'):
            material = self.ifc.Material
        else:
            material = self.ifc
        if material is not None:
            self.material = material.Name

    def __repr__(self):
        return "<%s (material: %s>" \
               % (self.__class__.__name__, self.material)

    @classmethod
    def create_additional_layer(cls, thickness, parent, material=None, material_properties=None):
        new_layer = cls(ifc=None)
        new_layer.material = material
        new_layer.parent = parent
        new_layer.thickness = thickness
        if material_properties is not None:
            for attr in new_layer.attributes:
                if getattr(new_layer, attr) == 0:
                    setattr(new_layer, attr, material_properties[attr])
        return new_layer

    def get_ifc_thickness(bind, name):
        if hasattr(bind.ifc, 'LayerThickness'):
            return bind.ifc.LayerThickness

    heat_capac = attribute.Attribute(
        default_ps=("Pset_MaterialThermal", "SpecificHeatCapacity"),
        default=0,
        unit=ureg.J/ureg.K
    )

    density = attribute.Attribute(
        default_ps=("Pset_MaterialThermal", "MassDensity"),
        default=0,
        unit=ureg.kg/ureg.m**3
    )

    thermal_conduc = attribute.Attribute(
        default_ps=("Pset_MaterialThermal", "ThermalConductivity"),
        default=0,
        unit=ureg.W/(ureg.m*ureg.K)
    )
    thickness = attribute.Attribute(
        functions=[get_ifc_thickness],
        default=0,
        unit=ureg.m
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
        """window _get_layers function"""
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
        default_ps=("Pset_WindowCommon", "IsExternal"),
        default=True
    )
    area = attribute.Attribute(
        default_ps=("QTo_WindowBaseQuantities", "Area"),
        default=0,
        unit=ureg.meter ** 2
    )
    width = attribute.Attribute(
        default_ps=("QTo_WindowBaseQuantities", "Depth"),
        default=0,
        unit=ureg.m
    )
    u_value = attribute.Attribute(
        unit=ureg.W / ureg.K / ureg.meter ** 2
    )


class Door(element.Element):
    ifc_type = "IfcDoor"
    predefined_types = ['DOOR', 'GATE', 'TRAPDOOR']

    pattern_ifc_type = [
        re.compile('Door', flags=re.IGNORECASE),
        re.compile('Tuer', flags=re.IGNORECASE)
    ]

    def _get_layers(bind, name):
        """door _get_layers function"""
        layers = []
        material_layers_dict = get_layers_ifc(bind)
        for layer in material_layers_dict:
            new_layer = element.SubElement.factory(layer, layer.is_a())
            new_layer.parent = bind
            layers.append(new_layer)
        return layers

    def get_is_external(self, name):
        if len(self.ifc.ProvidesBoundaries) > 0:
            boundary = self.ifc.ProvidesBoundaries[0]
            if boundary.InternalOrExternalBoundary is not None:
                if boundary.InternalOrExternalBoundary.lower() == 'external':
                    return True
                elif boundary.InternalOrExternalBoundary.lower() == 'internal':
                    return False

    layers = attribute.Attribute(
        functions=[_get_layers]
    )

    is_external = attribute.Attribute(
        functions=[get_is_external],
        default=False
    )

    area = attribute.Attribute(
        default_ps=("QTo_DoorBaseQuantities", "Area"),
        default=0,
        unit=ureg.meter ** 2
    )

    width = attribute.Attribute(
        default_ps=("QTo_DoorBaseQuantities", "Depth"),
        default=0,
        unit=ureg.m
    )
    u_value = attribute.Attribute(
        unit=ureg.W / ureg.K / ureg.meter ** 2
    )


class InnerDoor(Door):
    special_argument = {'is_external': False}


class OuterDoor(Door):
    special_argument = {'is_external': True}


class Plate(element.Element):
    ifc_type = "IfcPlate"
    predefined_types = ['CURTAIN_PANEL', 'SHEET']


class Slab(element.Element):
    ifc_type = "IfcSlab"
    predefined_types = ['FLOOR', 'ROOF', 'LANDING', 'BASESLAB']

    def __init__(self, *args, **kwargs):
        """slab __init__ function"""
        super().__init__(*args, **kwargs)

    def _get_layers(bind, name):
        """slab _get_layers function"""
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
        default_ps=("QTo_SlabBaseQuantities", "NetArea"),
        default=0,
        unit=ureg.meter ** 2
    )
    gross_area = attribute.Attribute(
        default_ps=("QTo_SlabBaseQuantities", "GrossArea"),
        default=1,
        unit=ureg.meter ** 2
    )

    width = attribute.Attribute(
        default_ps=("QTo_SlabBaseQuantities", "Width"),
        default=0,
        unit=ureg.m
    )

    u_value = attribute.Attribute(
        default_ps=("Pset_SlabCommon", "ThermalTransmittance"),
        default=0,
        unit = ureg.W / ureg.K / ureg.meter ** 2
    )

    is_external = attribute.Attribute(
        default_ps=("Pset_SlabCommon", "IsExternal"),
        default=False
    )


class Roof(Slab):
    ifc_type = "IfcRoof"
    predefined_types = ['FLAT_ROOF', 'SHED_ROOF', 'GABLE_ROOF', 'HIP_ROOF', 'HIPPED_GABLE_ROOF', 'GAMBREL_ROOF',
                        'MANSARD_ROOF', 'BARREL_ROOF', 'RAINBOW_ROOF', 'BUTTERFLY_ROOF', 'PAVILION_ROOF', 'DOME_ROOF',
                        'FREEFORM']
    predefined_type = "ROOF"

    def __init__(self, *args, **kwargs):
        """roof __init__ function"""
        super().__init__(*args, **kwargs)
        if hasattr(self, 'ifc'):
            self.ifc_type = self.ifc.is_a()


class Floor(Slab):
    predefined_type = "FLOOR"


class GroundFloor(Slab):
    predefined_type = "BASESLAB"


class Site(element.Element):
    ifc_type = "IfcSite"


class Building(element.Element):
    ifc_type = "IfcBuilding"

    def check_building_year(bind, name):
        year_decision = RealDecision("Enter value for the buildings year of construction",
                                     global_key="Building_%s.year_of_construction" % bind.guid,
                                     allow_skip=False, allow_load=True, allow_save=True,
                                     collect=False, quick_decide=False, unit=ureg.year)
        year_decision.decide()
        return year_decision.value

    year_of_construction = attribute.Attribute(
        default_ps=("Pset_BuildingCommon", "YearOfConstruction"),
        functions=[check_building_year],
        unit=ureg.year
    )
    gross_area = attribute.Attribute(
        default_ps=("Pset_BuildingCommon", "GrossPlannedArea"),
        unit=ureg.meter ** 2
    )
    net_area = attribute.Attribute(
        default_ps=("Pset_BuildingCommon", "NetAreaPlanned"),
        unit=ureg.meter ** 2
    )
    number_of_storeys = attribute.Attribute(
        default_ps=("Pset_BuildingCommon", "NumberOfStoreys"),
    )
    occupancy_type = attribute.Attribute(
        default_ps=("Pset_BuildingCommon", "OccupancyType"),
    )


class Storey(element.Element):
    ifc_type = 'IfcBuildingStorey'

    def __init__(self, *args, **kwargs):
        """storey __init__ function"""
        super().__init__(*args, **kwargs)
        self.storey_instances = []

    gross_floor_area = attribute.Attribute(
        default_ps=("Qto_BuildingStoreyBaseQuantities", "GrossFloorArea"),
        unit=ureg.meter ** 2
    )
    # todo make the lookup for height hierarchical
    net_height = attribute.Attribute(
        default_ps=("Qto_BuildingStoreyBaseQuantities", "NetHeight"),
    )
    gross_height = attribute.Attribute(
        default_ps=("Qto_BuildingStoreyBaseQuantities", "GrossHeight"),
    )
    height = attribute.Attribute(
        default_ps=("Qto_BuildingStoreyBaseQuantities", "Height"),
    )

    def get_storey_instances(self):
        storey_instances = []
        # instances
        if not hasattr(self.ifc, 'ContainsElements'):
            print()
        for ifc_structure in self.ifc.ContainsElements:
            for ifc_element in ifc_structure.RelatedElements:
                instance = self.get_object(ifc_element.GlobalId)
                if instance is not None:
                    storey_instances.append(instance)
                    if self not in instance.storeys:
                        instance.storeys.append(self)
        # spaces
        storey_spaces = []
        for ifc_aggregates in self.ifc.IsDecomposedBy:
            for ifc_element in ifc_aggregates.RelatedObjects:
                instance = self.get_object(ifc_element.GlobalId)
                if instance is not None:
                    storey_spaces.append(instance)
                    if self not in instance.storeys:
                        instance.storeys.append(self)
        return storey_instances, storey_spaces

    def set_storey_instances(self):
        self.storey_instances, self.thermal_zones = self.get_storey_instances()


__all__ = [ele for ele in locals().values() if ele in element.Element.__subclasses__()]
schema = 'IFC4'
