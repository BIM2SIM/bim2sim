"""Module contains the different classes for all HVAC elements"""

import math
import re

import numpy as np
import ifcopenshell
import ifcopenshell.geom
from OCC.Bnd import Bnd_Box
from OCC.BRepBndLib import brepbndlib_Add
from OCC.BRepBuilderAPI import \
    BRepBuilderAPI_MakeFace, \
    BRepBuilderAPI_MakeEdge, \
    BRepBuilderAPI_MakeWire, BRepBuilderAPI_Transform, BRepBuilderAPI_MakeVertex
from OCC.BRepGProp import brepgprop_SurfaceProperties, brepgprop_VolumeProperties
from OCC.GProp import GProp_GProps
from OCC.GeomAPI import GeomAPI_ProjectPointOnCurve
from OCC.ShapeAnalysis import ShapeAnalysis_ShapeContents
from OCC.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.gp import gp_Trsf, gp_Vec, gp_XYZ,  gp_Dir, gp_Ax1, gp_Pnt
from OCC.TopoDS import topods_Wire, topods_Face
from OCC.TopAbs import TopAbs_FACE, TopAbs_WIRE
from OCC.TopExp import TopExp_Explorer
from OCC.BRep import BRep_Tool
from OCC.BRepTools import BRepTools_WireExplorer
from OCC.Geom import Handle_Geom_Plane
from OCC.Extrema import Extrema_ExtFlag_MIN

from math import pi

from bim2sim.decorators import cached_property
from bim2sim.kernel import element, condition, attribute
from bim2sim.decision import BoolDecision
from bim2sim.kernel.units import ureg
from bim2sim.decision import ListDecision, RealDecision
from bim2sim.kernel.ifc2python import get_layers_ifc
from bim2sim.enrichment_data.data_class import DataClass


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
        condition.RangeCondition("diameter", 5.0*ureg.millimeter, 300.00*ureg.millimeter)
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

    rated_power = attribute.Attribute(
        description="Rated power of SpaceHeater",
        unit=ureg.kilowatt,
        default=42,
    )


# class ExpansionTank(element.Element):
#     ifc_type = "IfcTank"   #ToDo: IfcTank, IfcTankType=Expansion
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
    ifc_type = "IfcTank"    #ToDo: IfcTank, IfcTankType=Storage
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
        functions=[_get_usage]
    )

    t_set_heat = attribute.Attribute(
        default_ps=True
    )
    t_set_cool = attribute.Attribute(
        default_ps=True
    )
    area = attribute.Attribute(
        default_ps=True,
        default=0
    )
    net_volume = attribute.Attribute(
        default_ps=True,
        default=0
    )
    height = attribute.Attribute(
        default_ps=True,
        default=0
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bound_elements = []

    def get__elements_by_type(self, type):
        raise NotImplementedError

    @cached_property
    def space_center(self):
        """returns geometric center of the space (of the bounding box of the space shape)"""
        return self.get_center_of_space()

    @cached_property
    def space_shape(self):
        """returns topods shape of the IfcSpace"""
        settings = ifcopenshell.geom.main.settings()
        settings.set(settings.USE_PYTHON_OPENCASCADE, True)
        settings.set(settings.USE_WORLD_COORDS, True)
        settings.set(settings.EXCLUDE_SOLIDS_AND_SURFACES, False)
        settings.set(settings.INCLUDE_CURVES, True)
        return ifcopenshell.geom.create_shape(settings, self.ifc).geometry

    @cached_property
    def space_volume(self):
        props = GProp_GProps()
        brepgprop_VolumeProperties(self.space_shape, props)
        volume = props.Mass()
        return volume

    def get_center_of_space(self):
        """
        This function returns the center of the bounding box of an ifc space shape
        :return: center of space bounding box (gp_Pnt)
        """
        bbox = Bnd_Box()
        brepbndlib_Add(self.space_shape, bbox)
        bbox_center = ifcopenshell.geom.utils.get_bounding_box_center(bbox)
        return bbox_center


class SpaceBoundary(element.SubElement):
    ifc_type = 'IfcRelSpaceBoundary'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.guid = self.ifc.GlobalId
        self.level_description = self.ifc.Description
        self.thermal_zones.append(self.get_object(self.ifc.RelatingSpace.GlobalId))
        if self.ifc.RelatedBuildingElement is not None:
            self.bound_instance = self.get_object(self.ifc.RelatedBuildingElement.GlobalId)
        else:
            self.bound_instance = None
        if self.ifc.InternalOrExternalBoundary.lower() == 'internal':
            self.is_external = False
        else:
            self.is_external = True
        if self.ifc.PhysicalOrVirtualBoundary.lower() == 'physical':
            self.physical = True
        else:
            self.physical = False
        if hasattr(self.ifc.ConnectionGeometry.SurfaceOnRelatingElement, 'BasisSurface'):
            self.position = self.ifc.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface.Position.Location.Coordinates
        else:
            self.position = self.ifc.ConnectionGeometry.SurfaceOnRelatingElement.Position.Location.Coordinates

    @cached_property
    def bound_shape(self):
        return self.calc_bound_shape()

    @cached_property
    def bound_normal(self):
        return self.compute_surface_normals_in_space()

    @cached_property
    def related_bound(self):
        return self.get_corresponding_bound()

    @cached_property
    def bound_center(self):
        return self.get_bound_center()

    @cached_property
    def top_bottom(self):
        return self.get_floor_and_ceilings()

    @cached_property
    def bound_area(self):
        return self.get_bound_area()

    def get_bound_area(self):
        """compute area of a space boundary"""
        bound_prop = GProp_GProps()
        brepgprop_SurfaceProperties(self.bound_shape, bound_prop)
        area = bound_prop.Mass()
        return area

    def get_floor_and_ceilings(self):
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
        if self.bound_normal.Dot(vertical) != 0:
            direct = self.bound_center.Z() - self.thermal_zones[0].space_center.Z()
            if direct < 0 and self._compare_direction_of_normals(self.bound_normal, vertical):
                top_bottom = "BOTTOM"
            else:
                top_bottom = "TOP"
        return top_bottom

    @staticmethod
    def _compare_direction_of_normals(normal1, normal2):
        """
        Compare the direction of two surface normals (vectors).
        True, if direction is same or reversed
        :param normal1: first normal (gp_Pnt)
        :param normal2: second normal (gp_Pnt)
        :return: True/False
        """
        dotp = normal1.Dot(normal2)
        check = False
        if 1-1e-2 < dotp ** 2 < 1+1e-2:
            check = True
        return check

    def get_bound_center(self):
        """ compute center of the bounding box of a space boundary"""
        face_bbox = Bnd_Box()
        brepbndlib_Add(self.bound_shape, face_bbox)
        face_center = ifcopenshell.geom.utils.get_bounding_box_center(face_bbox).XYZ()
        return face_center

    def get_corresponding_bound(self):
        """
        Get corresponding space boundary in another space,
        ensuring that corresponding space boundaries have a matching number of vertices.
        """
        if self.bound_instance is None:
            # check for visual bounds
            if not self.physical:
                corr_bound = None
                bounds = []
                min_dist = 1000
                for obj in self.thermal_zones[0].objects:
                    if self.thermal_zones[0].objects[obj].ifc_type == 'IfcRelSpaceBoundary':
                        bounds.append(self.thermal_zones[0].objects[obj])
                for bound in bounds:
                    if bound.physical:
                        continue
                    if bound.thermal_zones[0].ifc.GlobalId == self.thermal_zones[0].ifc.GlobalId:
                        continue
                    if (bound.bound_area-self.bound_area)**2 > 1:
                        continue
                    distance = BRepExtrema_DistShapeShape(
                        bound.bound_shape,
                        self.bound_shape,
                        Extrema_ExtFlag_MIN
                    ).Value()
                    if distance > min_dist or distance > 0.4 :
                        continue
                    self.check_for_vertex_duplicates(bound)
                    nb_vert_this = self._get_number_of_vertices(self.bound_shape)
                    nb_vert_other = self._get_number_of_vertices(bound.bound_shape)
                    center_dist = gp_Pnt(self.bound_center).Distance(gp_Pnt(bound.bound_center)) ** 2
                    if (center_dist) > 0.5:
                        continue
                    if nb_vert_other != nb_vert_this:
                        continue
                    corr_bound = bound
                return corr_bound
                # for bound in self.objects.
            return None
        elif len(self.bound_instance.space_boundaries) == 1:
            return None
        elif len(self.bound_instance.space_boundaries) == 2:
            for bound in self.bound_instance.space_boundaries:
                if bound.ifc.GlobalId == self.ifc.GlobalId:
                    continue
                self.check_for_vertex_duplicates(bound)
                nb_vert_this = self._get_number_of_vertices(self.bound_shape)
                nb_vert_other = self._get_number_of_vertices(bound.bound_shape)
                if nb_vert_this == nb_vert_other:
                    return bound
                else:
                    return None
        elif len(self.bound_instance.space_boundaries) > 2:
            own_space_id = self.thermal_zones[0].ifc.GlobalId
            min_dist = 1000
            corr_bound = None
            for bound in self.bound_instance.space_boundaries:
                if bound.thermal_zones[0].ifc.GlobalId == own_space_id:
                    # skip boundaries within same space (cannot be corresponding bound)
                    continue
                distance = BRepExtrema_DistShapeShape(
                    bound.bound_shape,
                    self.bound_shape,
                    Extrema_ExtFlag_MIN
                ).Value()
                center_dist = gp_Pnt(self.bound_center).Distance(gp_Pnt(bound.bound_center))**2
                if (center_dist)**0.5 > 0.5:
                    continue
                if distance > min_dist:
                    continue
                other_area = bound.bound_area
                if (other_area - self.bound_area)**2 < 1e-1:
                    self.check_for_vertex_duplicates(bound)
                    nb_vert_this = self._get_number_of_vertices(self.bound_shape)
                    nb_vert_other = self._get_number_of_vertices(bound.bound_shape)
                    if nb_vert_this == nb_vert_other:
                        corr_bound = bound
            return corr_bound
        else:
            return None

    def check_for_vertex_duplicates(self, rel_bound):
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

        return a_face#.Reversed()

    @staticmethod
    def _get_vertex_list_from_face(face):
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


    def calc_bound_shape(self):
        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_PYTHON_OPENCASCADE, True)
        settings.set(settings.USE_WORLD_COORDS, True)
        shape = ifcopenshell.geom.create_shape(settings, self.ifc.ConnectionGeometry.SurfaceOnRelatingElement)
        shape = self.get_transformed_shape(shape)
        return shape

    def get_transformed_shape(self, shape):
        """transform TOPODS_Shape of each space boundary to correct position"""
        zone = self.thermal_zones[0]
        zone_position = gp_XYZ(zone.position[0], zone.position[1], zone.position[2])
        trsf1 = gp_Trsf()
        trsf2 = gp_Trsf()
        trsf2.SetRotation(gp_Ax1(gp_Pnt(zone_position), gp_Dir(0, 0, 1)), -zone.orientation * pi / 180)
        trsf1.SetTranslation(gp_Vec(gp_XYZ(zone.position[0], zone.position[1], zone.position[2])))
        try:
            shape = BRepBuilderAPI_Transform(shape, trsf1).Shape()
            shape = BRepBuilderAPI_Transform(shape, trsf2).Shape()
        except:
            pass
        return shape.Reversed()

    def compute_surface_normals_in_space(self):
        """
        This function returns the face normal of the boundary
        pointing outwarts the center of the space.
        Additionally, the area of the boundary is computed
        :return: face normal (gp_XYZ)
        """
        bbox_center = self.thermal_zones[0].space_center
        an_exp = TopExp_Explorer(self.bound_shape, TopAbs_FACE)
        a_face = an_exp.Current()
        face = topods_Face(a_face)
        surf = BRep_Tool.Surface(face)
        obj = surf.GetObject()
        assert obj.DynamicType().GetObject().Name() == "Geom_Plane"
        plane = Handle_Geom_Plane.DownCast(surf).GetObject()
        # face_bbox = Bnd_Box()
        # brepbndlib_Add(face, face_bbox)
        # face_center = ifcopenshell.geom.utils.get_bounding_box_center(face_bbox).XYZ()
        face_prop = GProp_GProps()
        brepgprop_SurfaceProperties(self.bound_shape, face_prop)
        area = face_prop.Mass()
        face_normal = plane.Axis().Direction().XYZ()

        face_towards_center = bbox_center.XYZ() - self.bound_center
        face_towards_center.Normalize()

        dot = face_towards_center.Dot(face_normal)

        # check if surface normal points into direction of space center
        # Transform surface normals to be pointing outwards
        # For faces without reversed surface normal, reverse the orientation of the face itself
        if dot > 0:
            face_normal = face_normal.Reversed()
        # else:
        #     self.bound_shape = self.bound_shape.Reversed()

        return face_normal

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
        default_ps=True,
        default=1
    )

    is_external = attribute.Attribute(
        default_ps=True,
        default=False
    )

    thermal_transmittance = attribute.Attribute(
        default_ps=True,
        default=0
    )

    material = attribute.Attribute(
        default_ps=True,
        default=0
    )

    thickness = attribute.Attribute(
        default_ps=True,
        # functions=[_get_wall_properties],
        default=0
    )

    heat_capacity = attribute.Attribute(
        # functions=[_get_wall_properties],
        default=0
    )

    density = attribute.Attribute(
        # functions=[_get_wall_properties],
        default=0
    )

    tilt = attribute.Attribute(
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
        default_ps=True,
        default=0
    )

    density = attribute.Attribute(
        default_ps=True,
        default=0
    )

    thermal_conductivity = attribute.Attribute(
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
        functions=[_get_layers]
    )

    is_external = attribute.Attribute(
        default_ps=True,
        default=True
    )

    area = attribute.Attribute(
        default_ps=True,
        default=0
    )

    thickness = attribute.Attribute(
        default_ps=True,
        default=0
    )

    material = attribute.Attribute(
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
        functions=[_get_layers]
    )

    is_external = attribute.Attribute(
        default_ps=True,
        default=True
    )

    area = attribute.Attribute(
        default_ps=True,
        default=0
    )

    thickness = attribute.Attribute(
        default_ps=True,
        default=0
    )

    material = attribute.Attribute(
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
        functions=[_get_layers]
    )
    area = attribute.Attribute(
        default_ps=True,
        default=0
    )

    thickness = attribute.Attribute(
        default_ps=True,
        default=0
    )

    thermal_transmittance = attribute.Attribute(
        default_ps=True,
        default=0
    )

    is_external = attribute.Attribute(
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
        default_ps=True
    )
    gross_area = attribute.Attribute(
        default_ps=True
    )
    net_area = attribute.Attribute(
        default_ps=True
    )
    number_of_storeys = attribute.Attribute(
        default_ps=True
    )
    occupancy_type = attribute.Attribute(
        default_ps=True
    )


class Storey(element.Element):
    ifc_type = 'IfcBuildingStorey'

    gross_floor_area = attribute.Attribute(
        default_ps=True
    )
    #todo make the lookup for height hierarchical
    net_height = attribute.Attribute(
        default_ps=True
    )
    gross_height = attribute.Attribute(
        default_ps=True
    )
    height = attribute.Attribute(
        default_ps=True
    )


__all__ = [ele for ele in locals().values() if ele in element.Element.__subclasses__()]
