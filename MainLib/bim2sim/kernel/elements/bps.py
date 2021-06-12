"""Module contains the different classes for all HVAC elements"""
import inspect
import logging
import math
import re
import sys
from typing import Set, Tuple

import ifcopenshell
import ifcopenshell.geom
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.BRepBndLib import brepbndlib_Add
from OCC.Core.BRepLib import BRepLib_FuseEdges
from OCC.Core.BRepBuilderAPI import \
    BRepBuilderAPI_MakeFace, \
    BRepBuilderAPI_MakeEdge, \
    BRepBuilderAPI_MakeWire, BRepBuilderAPI_Transform, BRepBuilderAPI_MakeVertex
from OCC.Core.BRepGProp import brepgprop_SurfaceProperties, brepgprop_VolumeProperties
from OCC.Core.GProp import GProp_GProps
from OCC.Core.GeomAPI import GeomAPI_ProjectPointOnCurve
from OCC.Core.ShapeAnalysis import ShapeAnalysis_ShapeContents
from OCC.Core.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Core.gp import gp_Trsf, gp_Vec, gp_XYZ, gp_Dir, gp_Ax1, gp_Pnt
from OCC.Core.TopoDS import topods_Wire, topods_Face, TopoDS_Iterator
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_WIRE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.BRep import BRep_Tool
from OCC.Core.BRepTools import BRepTools_WireExplorer
from OCC.Core._Geom import Handle_Geom_Plane_DownCast
from OCC.Core.Extrema import Extrema_ExtFlag_MIN

from bim2sim.decorators import cached_property
from bim2sim.kernel import element, attribute
from bim2sim.decision import BoolDecision, RealDecision
from bim2sim.kernel.units import ureg
from bim2sim.kernel.ifc2python import get_layers_ifc
from bim2sim.utilities.common_functions import vector_angle, filter_instances
from bim2sim.task.common.inner_loop_remover import remove_inner_loops
from bim2sim.decision import StringDecision
from bim2sim.utilities.pyocc_tools import PyOCCTools

logger = logging.getLogger(__name__)


class BPSProduct(element.ProductBased):
    domain = 'BPS'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.thermal_zones = []
        self.space_boundaries = []
        self.storeys = []

    def get_bound_area(self, name):
        if type(self) != ThermalZone:
            bound_area = 0
            for sb in self.non_duplicated_sb:
                bound_area += sb.bound_area
            return bound_area
        else:
            return None

    def get_net_bound_area(self, name):
        if type(self) != ThermalZone:
            net_bound_area = 0
            for sb in self.non_duplicated_sb:
                net_bound_area += sb.net_bound_area
            return net_bound_area
        else:
            return None

    def get_non_duplicated_sb(self, name):
        if type(self) != ThermalZone:
            valid_sb = list(self.space_boundaries)
            for sb in self.space_boundaries:
                if sb in valid_sb:
                    if sb.related_bound and sb.related_bound in valid_sb:
                        valid_sb.remove(sb.related_bound)
            return valid_sb
        else:
            return None

    def get_top_bottom(self, name):
        if type(self) != ThermalZone:
            tbs = []
            for sb in self.non_duplicated_sb:
                tbs.append(sb.top_bottom)
            tbs_new = list(set(tbs))
            return tbs_new
        else:
            return None

    bound_area = attribute.Attribute(
        functions=[get_bound_area],
        unit=ureg.meter ** 2
    )
    net_bound_area = attribute.Attribute(
        functions=[get_net_bound_area],
        unit=ureg.meter ** 2
    )
    non_duplicated_sb = attribute.Attribute(
        functions=[get_non_duplicated_sb],
    )
    top_bottom = attribute.Attribute(
        functions=[get_top_bottom],
    )


class ThermalZone(BPSProduct):
    ifc_types = {
        "IfcSpace":
            ['*', 'SPACE', 'PARKING', 'GFA', 'INTERNAL', 'EXTERNAL']
    }

    pattern_ifc_type = [
        re.compile('Space', flags=re.IGNORECASE),
        re.compile('Zone', flags=re.IGNORECASE)
    ]

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
                tz = sb.related_bound.bound_thermal_zone
                # todo: check if computation of neighbors works as expected
                # what if boundary has no related bound but still has a neighbor?
                # hint: neighbors != related bounds
                if (tz is not self) and (tz not in neighbors):
                    neighbors.append(tz)
        return neighbors

    def _get_cooling(self, name):
        """get cooling parameters for thermal zone"""
        if self.t_set_cool is not None:
            return True
        else:
            cooling_decision = BoolDecision(
                question="Do you want for the thermal zone %s to be cooled? - with cooling" % self.name,
                collect=False, global_key="%s_%s.Cooling" % (type(self).__name__, self.guid),
                allow_skip=False, allow_load=True, allow_save=True, quick_decide=not True
            )
            cooling_decision.decide()
            if cooling_decision.value:
                return True
            else:
                return False

    def _get_heating(self, name):
        """get heating parameters for thermal zone"""
        if self.t_set_heat is not None:
            return True
        else:
            heating_decision = BoolDecision(
                question="Do you want for the thermal zone %s to be heated? - with heating" % self.name,
                collect=False,
                global_key="%s_%s.Heating" % (type(self).__name__, self.guid),
                allow_skip=False, allow_load=True, allow_save=True, quick_decide=not True
            )
            heating_decision.decide()
            if heating_decision.value:
                return True
            else:
                return False

    def get_space_shape(self, name):
        """returns topods shape of the IfcSpace"""
        settings = ifcopenshell.geom.main.settings()
        settings.set(settings.USE_PYTHON_OPENCASCADE, True)
        settings.set(settings.USE_WORLD_COORDS, True)
        settings.set(settings.EXCLUDE_SOLIDS_AND_SURFACES, False)
        settings.set(settings.INCLUDE_CURVES, True)
        return ifcopenshell.geom.create_shape(settings, self.ifc).geometry

    def get_center_of_space(self, name):
        """
        This function returns the center of the bounding box of an ifc space shape
        :return: center of space bounding box (gp_Pnt)
        """
        bbox = Bnd_Box()
        brepbndlib_Add(self.space_shape, bbox)
        bbox_center = ifcopenshell.geom.utils.get_bounding_box_center(bbox)
        return bbox_center

    def get_space_volume(self, name):
        props = GProp_GProps()
        brepgprop_VolumeProperties(self.space_shape, props)
        volume = props.Mass()
        return volume

    def _get_volume(self, name):
        return self.area * self.height

    def _get_usage(self, name):
        if self.zone_name is not None:
            usage = self.zone_name
        elif self.ifc.LongName is not None:
            usage = self.ifc.LongName
        else:
            usage = self.name
        return usage

    def _get_heating_profile(self, name):
        profile = None
        if self.t_set_heat is not None:
            profile = [self.t_set_heat.to(ureg.kelvin).m] * 25
        return profile

    def _get_cooling_profile(self, name):
        profile = None
        if self.t_set_cool is not None:
            profile = [self.t_set_cool.to(ureg.kelvin).m] * 25
        return profile

    def _get_persons(self, name):
        return 1 / self.AreaPerOccupant

    def _get_name(self, name):
        return self.ifc.Name

    name = attribute.Attribute(
        functions=[_get_name]
    )
    zone_name = attribute.Attribute(
    )
    usage = attribute.Attribute(
        default_ps=("Pset_SpaceOccupancyRequirements", "OccupancyType"),
        functions=[_get_usage]
    )
    t_set_heat = attribute.Attribute(
        default_ps=("Pset_SpaceThermalRequirements", "SpaceTemperatureMin"),
        unit=ureg.degC,
        default=21
    )
    t_set_cool = attribute.Attribute(
        default_ps=("Pset_SpaceThermalRequirements", "SpaceTemperatureMax"),
        unit=ureg.degC,
        default=25
    )
    t_ground = attribute.Attribute(
        unit=ureg.degC,
        default=13
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
        unit=ureg.meter ** 3,
        default=0
    )
    height = attribute.Attribute(
        default_ps=("Qto_SpaceBaseQuantities", "Height"),
        unit=ureg.meter,
        default=0
    )
    length = attribute.Attribute(
        default_ps=("Qto_SpaceBaseQuantities", "Length"),
        unit=ureg.meter,
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
    # use conditions
    with_cooling = attribute.Attribute(
        functions=[_get_cooling]
    )
    with_heating = attribute.Attribute(
        functions=[_get_heating]
    )
    with_ahu = attribute.Attribute(
        default_ps=("Pset_SpaceThermalRequirements", "AirConditioning"),
    )
    heating_profile = attribute.Attribute(
        functions=[_get_heating_profile]
    )
    cooling_profile = attribute.Attribute(
        functions=[_get_cooling_profile]
    )
    persons = attribute.Attribute(
        functions=[_get_persons]
    )
    typical_length = attribute.Attribute(
    )
    typical_width = attribute.Attribute(
    )
    T_threshold_heating = attribute.Attribute(
    )
    activity_degree_persons = attribute.Attribute(
    )
    fixed_heat_flow_rate_persons = attribute.Attribute(
    )
    internal_gains_moisture_no_people = attribute.Attribute(
    )
    T_threshold_cooling = attribute.Attribute(
    )
    ratio_conv_rad_persons = attribute.Attribute(
    )
    machines = attribute.Attribute(
    )
    ratio_conv_rad_machines = attribute.Attribute(
    )
    lighting_power = attribute.Attribute(
    )
    ratio_conv_rad_lighting = attribute.Attribute(
    )
    use_constant_infiltration = attribute.Attribute(
    )
    infiltration_rate = attribute.Attribute(
    )
    max_user_infiltration = attribute.Attribute(
    )
    max_overheating_infiltration = attribute.Attribute(
    )
    max_summer_infiltration = attribute.Attribute(
    )
    winter_reduction_infiltration = attribute.Attribute(
    )
    min_ahu = attribute.Attribute(
    )
    max_ahu = attribute.Attribute(
    )
    with_ideal_thresholds = attribute.Attribute(
    )
    persons_profile = attribute.Attribute(
    )
    machines_profile = attribute.Attribute(
    )
    lighting_profile = attribute.Attribute(
    )

    def __init__(self, *args, **kwargs):
        """thermalzone __init__ function"""
        super().__init__(*args, **kwargs)
        self.bound_elements = []

    def get__elements_by_type(self, type):
        raise NotImplementedError


class SpaceBoundary(element.RelationBased):
    ifc_types = {'IfcRelSpaceBoundary': ['*']}

    def __init__(self, *args, instances: dict, **kwargs):
        """spaceboundary __init__ function"""
        super().__init__(*args, **kwargs)
        self.disaggregation = []
        self.bound_instance = None
        self.bound_thermal_zone = None
        self._instances = instances

    def calc_orientation(self):

        # get relative position of resultant disaggregation
        if hasattr(self.ifc.ConnectionGeometry.SurfaceOnRelatingElement, 'BasisSurface'):
            axis = self.ifc.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface.Position.Axis.DirectionRatios
        else:
            axis = self.ifc.ConnectionGeometry.SurfaceOnRelatingElement.Position.Axis.DirectionRatios

        return vector_angle(axis)

    def calc_position(self):
        # get relative position of resultant disaggregation
        if hasattr(self.ifc.ConnectionGeometry.SurfaceOnRelatingElement, 'BasisSurface'):
            position = self.ifc.ConnectionGeometry.SurfaceOnRelatingElement.BasisSurface.Position.Location.Coordinates
        else:
            position = self.ifc.ConnectionGeometry.SurfaceOnRelatingElement.Position.Location.Coordinates

        return position

    @classmethod
    def pre_validate(cls, ifc) -> bool:
        return True

    def validate(self) -> bool:
        if self.bound_area and self.bound_area < 1e-2 * ureg.meter ** 2:
            return True
        return False

    def get_bound_neighbors(self, name):
        neighbors = []
        space_bounds = []
        if not hasattr(self.bound_thermal_zone, 'space_boundaries'):
            return None
        if len(self.bound_thermal_zone.space_boundaries) == 0:
            for obj in self.bound_thermal_zone.objects:
                this_obj = self.bound_thermal_zone.objects[obj]
                if this_obj.ifc_type != 'IfcRelSpaceBoundary':
                    continue
                if this_obj.bound_thermal_zone.ifc.GlobalId != self.bound_thermal_zone.ifc.GlobalId:
                    continue
                space_bounds.append(this_obj)
        else:
            space_bounds = self.bound_thermal_zone.space_boundaries
        for bound in space_bounds:
            if bound.ifc.GlobalId == self.ifc.GlobalId:
                continue
            distance = BRepExtrema_DistShapeShape(bound.bound_shape, self.bound_shape, Extrema_ExtFlag_MIN).Value()
            if distance == 0:
                neighbors.append(bound)
        return neighbors

    def get_bound_area(self, name):
        """compute area of a space boundary"""
        bound_prop = GProp_GProps()
        brepgprop_SurfaceProperties(self.bound_shape, bound_prop)
        area = bound_prop.Mass()
        return area * ureg.meter ** 2

    def get_floor_and_ceilings(self, name):
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
        if -1e-3 < self.bound_normal.Dot(vertical) < 1e-3:
            top_bottom = "VERTICAL"
        elif self.related_bound != None:
            if (self.bound_center.Z() - self.related_bound.bound_center.Z()) > 1e-2:
                top_bottom = "BOTTOM"
            elif (self.bound_center.Z() - self.related_bound.bound_center.Z()) < -1e-2:
                top_bottom = "TOP"
            else:
                if vertical.Dot(self.bound_normal) < -0.8:
                    top_bottom = "BOTTOM"
                elif vertical.Dot(self.bound_normal) > 0.8:
                    top_bottom = "TOP"
        elif self.related_adb_bound != None:
            if self.bound_center.Z() > self.related_adb_bound.bound_center.Z():
                top_bottom = "BOTTOM"
            else:
                top_bottom = "TOP"
        else:
            # direct = self.bound_center.Z() - self.thermal_zones[0].space_center.Z()
            # if direct < 0 and SpaceBoundary._compare_direction_of_normals(self.bound_normal, vertical):
            if vertical.Dot(self.bound_normal) < -0.8:
                top_bottom = "BOTTOM"
            elif vertical.Dot(self.bound_normal) > 0.8:
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

    def get_bound_center(self, name):
        """ compute center of the bounding box of a space boundary"""
        p = GProp_GProps()
        brepgprop_SurfaceProperties(self.bound_shape, p)
        return p.CentreOfMass().XYZ()

    def get_corresponding_bound(self, name):
        """
        Get corresponding space boundary in another space,
        ensuring that corresponding space boundaries have a matching number of vertices.
        """
        if hasattr(self.ifc, 'CorrespondingBoundary') and self.ifc.CorrespondingBoundary is not None:
            corr_bound = self._instances.get(self.ifc.CorrespondingBoundary.GlobalId)
            if corr_bound and corr_bound.ifc.RelatingSpace.is_a('IfcSpace'):
                if not corr_bound.ifc.RelatingSpace.is_a('IfcExternalSpatialStructure'):
                    nb_vert_this = PyOCCTools.get_number_of_vertices(self.bound_shape)
                    nb_vert_other = PyOCCTools.get_number_of_vertices(corr_bound.bound_shape)
                    # if not nb_vert_this == nb_vert_other:
                    #     print("NO VERT MATCH!:", nb_vert_this, nb_vert_other)
                    if nb_vert_this == nb_vert_other:
                        return corr_bound
        if self.bound_instance is None:
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
            #         nb_vert_this = bind.get_number_of_vertices(bind.bound_shape)
            #         nb_vert_other = bind.get_number_of_vertices(bound.bound_shape)
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
        elif len(self.bound_instance.space_boundaries) == 1:
            return None
        elif len(self.bound_instance.space_boundaries) >= 2:
            own_space_id = self.bound_thermal_zone.ifc.GlobalId
            min_dist = 1000
            corr_bound = None
            for bound in self.bound_instance.space_boundaries:
                if bound.level_description != "2a":
                    continue
                if bound is self:
                    continue
                # if bound.bound_normal.Dot(self.bound_normal) != -1:
                #     continue
                distance = BRepExtrema_DistShapeShape(
                    bound.bound_shape,
                    self.bound_shape,
                    Extrema_ExtFlag_MIN
                ).Value()
                center_dist = gp_Pnt(self.bound_center).Distance(gp_Pnt(bound.bound_center))**2
                if abs(center_dist) > 0.5:
                    continue
                if distance > min_dist:
                    continue
                min_dist = abs(center_dist)
                other_area = bound.bound_area
                if (other_area.m - self.bound_area.m)**2 < 1e-1:
                    # self.check_for_vertex_duplicates(bound)
                    nb_vert_this = PyOCCTools.get_number_of_vertices(self.bound_shape)
                    nb_vert_other = PyOCCTools.get_number_of_vertices(bound.bound_shape)
                    # if not nb_vert_this == nb_vert_other:
                    #     print("NO VERT MATCH!:", nb_vert_this, nb_vert_other)
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
        if self.related_bound:
            if self.bound_thermal_zone == self.related_bound.bound_thermal_zone:
                adb_bound = self.related_bound
        for bound in self.bound_instance.space_boundaries:
            if bound == self:
                continue
            if not bound.bound_thermal_zone == self.bound_thermal_zone:
                continue
            if (bound.bound_area.m - self.bound_area.m) ** 2 > 0.01:
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
        nb_vert_this = PyOCCTools.get_number_of_vertices(self.bound_shape)
        nb_vert_other = PyOCCTools.get_number_of_vertices(rel_bound.bound_shape)
        # if nb_vert_this != nb_vert_other:
        setattr(self, 'bound_shape_org', self.bound_shape)
        vert_list1 = PyOCCTools.get_vertex_list_from_face(self.bound_shape)
        vert_list1 = PyOCCTools.remove_vertex_duplicates(vert_list1)
        vert_list1.reverse()
        vert_list1 = PyOCCTools.remove_vertex_duplicates(vert_list1)

        setattr(rel_bound, 'bound_shape_org', rel_bound.bound_shape)
        vert_list2 = PyOCCTools.get_vertex_list_from_face(rel_bound.bound_shape)
        vert_list2 = PyOCCTools.remove_vertex_duplicates(vert_list2)
        vert_list2.reverse()
        vert_list2 = PyOCCTools.remove_vertex_duplicates(vert_list2)
        if len(vert_list1) == len(vert_list2):
            if len(vert_list1) < 5:
                return
            vert_list1.reverse()
            vert_list2.reverse()
            self.bound_shape = PyOCCTools.make_face_from_vertex_list(vert_list1)
            rel_bound.bound_shape = PyOCCTools.make_face_from_vertex_list(vert_list2)

    def calc_bound_shape(self, name):
        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_PYTHON_OPENCASCADE, True)
        settings.set(settings.USE_WORLD_COORDS, True)
        settings.set(settings.EXCLUDE_SOLIDS_AND_SURFACES, False)
        settings.set(settings.INCLUDE_CURVES, True)

        try:
            sore = self.ifc.ConnectionGeometry.SurfaceOnRelatingElement
            # if sore.get_info()["InnerBoundaries"] is None:
            shape = ifcopenshell.geom.create_shape(settings, sore)

            pnt_list = PyOCCTools.get_points_of_face(shape)
            pnt_list_new = PyOCCTools.remove_coincident_vertices(pnt_list)
            pnt_list_new = PyOCCTools.remove_collinear_vertices2(pnt_list_new)
            # pnt_list_new = self._remove_collinear_vertices2(pnt_list)
            if pnt_list_new != pnt_list:
                # print("vert new vs old", len(pnt_list_new), len(pnt_list))
                if len(pnt_list_new) < 3:
                    pnt_list_new = pnt_list
                shape = PyOCCTools.make_faces_from_pnts(pnt_list_new)

            if sore.InnerBoundaries:
                shape = remove_inner_loops(shape)  # todo: return None if not horizontal shape
                # if not shape:
                if self.bound_instance.ifc.is_a('IfcWall'): # todo: remove this hotfix (generalize)
                    ifc_new = ifcopenshell.file()
                    temp_sore = ifc_new.create_entity('IfcCurveBoundedPlane', OuterBoundary=sore.OuterBoundary,
                                                      BasisSurface=sore.BasisSurface)
                    temp_sore.InnerBoundaries = ()
                    shape = ifcopenshell.geom.create_shape(settings, temp_sore)
                    pnt_list = PyOCCTools.get_points_of_face(shape)
                    pnt_list_new = PyOCCTools.remove_coincident_vertices(pnt_list)
                    pnt_list_new = PyOCCTools.remove_collinear_vertices2(pnt_list_new)
                    # pnt_list_new = self._remove_collinear_vertices2(pnt_list)
                    if pnt_list_new != pnt_list:
                        # print("vert new vs old", len(pnt_list_new), len(pnt_list))
                        if len(pnt_list_new) < 3:
                            pnt_list_new = pnt_list
                        shape = PyOCCTools.make_faces_from_pnts(pnt_list_new)

        except:
            try:
                sore = self.ifc.ConnectionGeometry.SurfaceOnRelatingElement
                ifc_new = ifcopenshell.file()
                temp_sore = ifc_new.create_entity('IfcCurveBoundedPlane', OuterBoundary=sore.OuterBoundary,
                                                  BasisSurface=sore.BasisSurface)
                temp_sore.InnerBoundaries = ()
                shape = ifcopenshell.geom.create_shape(settings, temp_sore)
            except:
                poly = self.ifc.ConnectionGeometry.SurfaceOnRelatingElement.OuterBoundary.Points
                pnts = []
                for p in poly:
                    p.Coordinates = (p.Coordinates[0], p.Coordinates[1], 0.0)
                    pnts.append((p.Coordinates[:]))
                shape = PyOCCTools.make_faces_from_pnts(pnts)
        shape = BRepLib_FuseEdges(shape).Shape()

        shape_val = TopoDS_Iterator(self.bound_thermal_zone.space_shape).Value()
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
            #             vert_list1 = self.get_vertex_list_from_face(shape)
            #             vert_list1 = self.remove_collinear_vertices(vert_list1)
            #             vert_list1.reverse()
            #             vert_list1 = self.remove_collinear_vertices(vert_list1)
            #             vert_list1.reverse()
            #             shape = self.make_face_from_vertex_list(vert_list1)

        return shape

    def get_transformed_shape(self, shape):
        """transform TOPODS_Shape of each space boundary to correct position"""
        zone = self.bound_thermal_zone
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
        bbox_center = self.bound_thermal_zone.space_center
        an_exp = TopExp_Explorer(self.bound_shape, TopAbs_FACE)
        a_face = an_exp.Current()
        try:
            face = topods_Face(a_face)
        except:
            pnts = PyOCCTools.get_points_of_face(a_face)
            # pnts.append(pnts[0])
            face = PyOCCTools.make_faces_from_pnts(pnts)
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

    def get_space_boundary_storeys(self, name):
        storeys = self.bound_thermal_zone.storeys
        return storeys

    def get_level_description(self, name):
        return self.ifc.Description

    def get_is_external(self, name):
        return not self.ifc.InternalOrExternalBoundary.lower() == 'internal'

    def get_physical(self, name):
        return self.ifc.PhysicalOrVirtualBoundary.lower() == 'physical'

    def get_net_bound_area(self, name):
        opening_area = 0
        if self.opening_bounds:
            for opening_boundary in self.opening_bounds:
                opening_area += opening_boundary.bound_area.m
        area = self.bound_area.m - opening_area
        return area

    @cached_property
    def bound_shape(self):
        return self.calc_bound_shape('')

    @cached_property
    def bound_normal(self):
        return self.compute_surface_normals_in_space('')

    @cached_property
    def related_bound(self):
        return self.get_corresponding_bound('')

    @cached_property
    def related_adb_bound(self):
        return self.get_rel_adiab_bound('')

    @cached_property
    def bound_center(self):
        return self.get_bound_center('')

    @cached_property
    def top_bottom(self):
        return self.get_floor_and_ceilings('')

    bound_area = attribute.Attribute(
        functions=[get_bound_area],
        unit=ureg.meter ** 2
    )
    net_bound_area = attribute.Attribute(
        functions=[get_net_bound_area],
        unit=ureg.meter ** 2
    )
    bound_neighbors = attribute.Attribute(
        functions=[get_bound_neighbors]
    )
    storeys = attribute.Attribute(
        functions=[get_space_boundary_storeys]
    )
    level_description = attribute.Attribute(
        functions=[get_level_description]
    )
    is_external = attribute.Attribute(
        functions=[get_is_external]
    )
    physical = attribute.Attribute(
        functions=[get_physical]
    )
    opening_bounds = attribute.Attribute(
    )


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


class Wall(BPSProduct):
    ifc_types = {
        "IfcWall":
            ['*', 'MOVABLE', 'PARAPET', 'PARTITIONING', 'PLUMBINGWALL',
             'SHEAR', 'SOLIDWALL', 'POLYGONAL', 'DOOR', 'GATE', 'TRAPDOOR'],
        "IfcWallStandardCase":
            ['*', 'MOVABLE', 'PARAPET', 'PARTITIONING', 'PLUMBINGWALL',
             'SHEAR', 'SOLIDWALL', 'POLYGONAL', 'DOOR', 'GATE', 'TRAPDOOR'],
        # "IfcElementedCase": "?"  # TODO
    }

    pattern_ifc_type = [
        re.compile('Wall', flags=re.IGNORECASE),
        re.compile('Wand', flags=re.IGNORECASE)
    ]
    material_selected = {}
    is_external: bool = None

    def __init__(self, *args, **kwargs):
        """wall __init__ function"""
        super().__init__(*args, **kwargs)

    def _get_layers(self, name):
        """wall _get_layers function"""
        layers = []
        material_layers_dict = get_layers_ifc(self)
        for layer in material_layers_dict:
            new_layer = Layer.from_ifc(layer, finder=self.finder)
            new_layer.parent = self
            layers.append(new_layer)
        return layers

    def get_better_subclass(self):
        if self.is_external:
            return OuterWall
        else:
            return InnerWall

    def get_is_external(self, name):
        if len(self.ifc.ProvidesBoundaries) > 0:
            boundary = self.ifc.ProvidesBoundaries[0]
            if boundary.InternalOrExternalBoundary is not None:
                if boundary.InternalOrExternalBoundary.lower() == 'external':
                    return True
                elif boundary.InternalOrExternalBoundary.lower() == 'internal':
                    return False

    def get_bound_area(self, name):
        bound_area = 0
        for sb in self.non_duplicated_sb:
            bound_area += sb.bound_area
        return bound_area

    def get_net_bound_area(self, name):
        net_bound_area = 0
        for sb in self.non_duplicated_sb:
            net_bound_area += sb.net_bound_area
        return net_bound_area

    def get_non_duplicated_sb(self, name):
        valid_sb = list(self.space_boundaries)
        for sb in self.space_boundaries:
            if sb in valid_sb:
                if sb.related_bound and sb.related_bound in valid_sb:
                    valid_sb.remove(sb.related_bound)
        return valid_sb

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


class Layer(element.RelationBased):
    ifc_types = {'IfcMaterialLayer': ['*'], 'IfcMaterial': ['*']}
    material_selected = {}
    default_materials = {}

    def __init__(self, *args, material='', **kwargs):
        """layer __init__ function"""
        super().__init__(*args, **kwargs)
        self.material: str = material

    def __repr__(self):
        return "<%s (material: %s>" \
               % (self.__class__.__name__, self.material)

    @classmethod
    def ifc2args(cls, ifc) -> Tuple[tuple, dict]:
        args, kwargs = super().ifc2args(ifc)
        if hasattr(ifc, 'Material'):
            material = ifc.Material
        else:
            material = ifc
        if material is not None:
            kwargs['material'] = material.Name
        return args, kwargs

    @classmethod
    def pre_validate(cls, ifc) -> bool:
        return True

    def validate(self) -> bool:
        return True

    def get_ifc_thickness(self, name):
        if hasattr(self.ifc, 'LayerThickness'):
            return self.ifc.LayerThickness

    heat_capac = attribute.Attribute(
        default_ps=("Pset_MaterialThermal", "SpecificHeatCapacity"),
        default=0,
        unit=ureg.J / ureg.K
    )

    density = attribute.Attribute(
        default_ps=("Pset_MaterialThermal", "MassDensity"),
        default=0,
        unit=ureg.kg / ureg.m ** 3
    )

    thermal_conduc = attribute.Attribute(
        default_ps=("Pset_MaterialThermal", "ThermalConductivity"),
        default=0,
        unit=ureg.W / (ureg.m * ureg.K)
    )
    thickness = attribute.Attribute(
        functions=[get_ifc_thickness],
        default=0,
        unit=ureg.m
    )
    solar_absorp = attribute.Attribute(
        # default_ps=('Pset_MaterialOptical', 'SolarTransmittance'),
        default=0.7,
        unit=ureg.percent
    )


class OuterWall(Wall):
    pass
    # is_external = True


class InnerWall(Wall):
    pass
    # is_external = False


class Window(BPSProduct):
    ifc_types = {"IfcWindow": ['*', 'WINDOW', 'SKYLIGHT', 'LIGHTDOME']}

    pattern_ifc_type = [
        re.compile('Window', flags=re.IGNORECASE),
        re.compile('Fenster', flags=re.IGNORECASE)
    ]

    def _get_layers(self, name):
        """window _get_layers function"""
        layers = []
        material_layers_dict = get_layers_ifc(self)
        for layer in material_layers_dict:
            new_layer = Layer.from_ifc(layer, finder=self.finder)
            new_layer.parent = self
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
        default_ps=("Pset_WallCommon", "ThermalTransmittance"),
        unit=ureg.W / ureg.K / ureg.meter ** 2
    )
    g_value = attribute.Attribute(  # material
    )
    a_conv = attribute.Attribute(
    )
    shading_g_total = attribute.Attribute(
    )
    shading_max_irr = attribute.Attribute(
    )
    inner_convection = attribute.Attribute(
        unit=ureg.W / ureg.K / ureg.meter ** 2,
    )
    inner_radiation = attribute.Attribute(
        unit=ureg.W / ureg.K / ureg.meter ** 2,
    )
    outer_radiation = attribute.Attribute(
        unit=ureg.W / ureg.K / ureg.meter ** 2,
    )
    outer_convection = attribute.Attribute(
        unit=ureg.W / ureg.K / ureg.meter ** 2,
    )


class Door(BPSProduct):
    ifc_types = {"IfcDoor": ['*', 'DOOR', 'GATE', 'TRAPDOOR']}

    pattern_ifc_type = [
        re.compile('Door', flags=re.IGNORECASE),
        re.compile('Tuer', flags=re.IGNORECASE)
    ]

    def _get_layers(self, name):
        """door _get_layers function"""
        layers = []
        material_layers_dict = get_layers_ifc(self)
        for layer in material_layers_dict:
            new_layer = Layer.from_ifc(layer, finder=self.finder)
            new_layer.parent = self
            layers.append(new_layer)
        return layers

    def get_better_subclass(self):
        if self.is_external:
            return OuterDoor
        else:
            return InnerDoor

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
    # is_external = False
    pass


class OuterDoor(Door):
    # is_external = True
    pass


class Plate(BPSProduct):
    ifc_types = {"IfcPlate": ['*', 'CURTAIN_PANEL', 'SHEET']}


class Slab(BPSProduct):
    ifc_types = {
        "IfcSlab": ['*', 'LANDING', 'BASESLAB']
    }

    def __init__(self, *args, **kwargs):
        """slab __init__ function"""
        super().__init__(*args, **kwargs)

    def _get_layers(self, name):
        """slab _get_layers function"""
        layers = []
        material_layers_dict = get_layers_ifc(self)
        for layer in material_layers_dict:
            new_layer = Layer.from_ifc(layer, finder=self.finder)
            new_layer.parent = self
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
        unit=ureg.W / ureg.K / ureg.meter ** 2
    )

    is_external = attribute.Attribute(
        functions=[get_is_external],
        default=False
    )


class Roof(Slab):
    ifc_types = {
        "IfcRoof":
            ['*', 'FLAT_ROOF', 'SHED_ROOF', 'GABLE_ROOF', 'HIP_ROOF',
             'HIPPED_GABLE_ROOF', 'GAMBREL_ROOF', 'MANSARD_ROOF',
             'BARREL_ROOF', 'RAINBOW_ROOF', 'BUTTERFLY_ROOF', 'PAVILION_ROOF',
             'DOME_ROOF', 'FREEFORM'],
        "IfcSlab": ['ROOF']
    }


class Floor(Slab):
    ifc_types = {
        "IfcSlab": ['FLOOR']
    }


class GroundFloor(Slab):
    ifc_types = {
        "IfcSlab": ['BASESLAB']
    }
    # pattern_ifc_type = [
    #     re.compile('Bodenplatte', flags=re.IGNORECASE),
    #     re.compile('')
    # ]


class Site(BPSProduct):
    ifc_types = {"IfcSite": ['*']}


class Building(BPSProduct):
    ifc_types = {"IfcBuilding": ['*']}

    def _get_name(self, name):
        building_name = None
        if self.ifc is not None:
            if self.ifc.Name is not None:
                if len(self.ifc.Name) > 0:
                    building_name = self.ifc.Name
                else:
                    name_dec = StringDecision(question="Please enter name for the instance %s" % type(self).__name__,
                                              default="unnamed", global_key=f'IfcName-Decision-{self.guid}',
                                              allow_load=True, allow_save=True)
                    building_name = name_dec.decide()
        return building_name

    def check_building_year(self, name):
        year_decision = RealDecision("Enter value for the buildings year of construction",
                                     global_key="Building_%s.year_of_construction" % self.guid,
                                     allow_skip=False, allow_load=True, allow_save=True,
                                     collect=False, quick_decide=False, unit=ureg.year)
        year_decision.decide()
        return year_decision.value

    name = attribute.Attribute(
        functions=[_get_name]
    )
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


class Storey(BPSProduct):
    ifc_types = {'IfcBuildingStorey': ['*']}

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


# collect all domain classes
items: Set[BPSProduct] = set()
for name, cls in inspect.getmembers(
        sys.modules[__name__],
        lambda member: inspect.isclass(member)  # class at all
                       and issubclass(member, BPSProduct)  # domain subclass
                       and member is not BPSProduct  # but not base class
                       and member.__module__ == __name__):  # declared here
    items.add(cls)
