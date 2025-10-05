"""Module contains the different classes for all HVAC elements"""
import inspect
import logging
import math
import re
import sys
from datetime import date
from typing import Set, List, Union

import ifcopenshell
import ifcopenshell.geom
from OCC.Core.BRepBndLib import brepbndlib_Add
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Core.BRepGProp import brepgprop_SurfaceProperties
from OCC.Core.BRepLib import BRepLib_FuseEdges
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.Extrema import Extrema_ExtFlag_MIN
from OCC.Core.GProp import GProp_GProps
from OCC.Core.ShapeUpgrade import ShapeUpgrade_UnifySameDomain
from OCC.Core.gp import gp_Trsf, gp_Vec, gp_XYZ, gp_Pnt, \
    gp_Mat, gp_Quaternion
from ifcopenshell import guid

from bim2sim.elements.mapping import condition, attribute
from bim2sim.elements.base_elements import ProductBased, RelationBased
from bim2sim.elements.mapping.units import ureg
from bim2sim.tasks.common.inner_loop_remover import remove_inner_loops
from bim2sim.utilities.common_functions import vector_angle, angle_equivalent
from bim2sim.utilities.pyocc_tools import PyOCCTools
from bim2sim.utilities.types import IFCDomain, BoundaryOrientation

logger = logging.getLogger(__name__)


class BPSProduct(ProductBased):
    domain = 'BPS'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.thermal_zones = []
        self.space_boundaries = []
        self.storeys = []
        self.material = None
        self.disaggregations = []
        self.building = None
        self.site = None

    def __repr__(self):
        return "<%s (guid: %s)>" % (
            self.__class__.__name__, self.guid)

    def get_bound_area(self, name) -> ureg.Quantity:
        """ get gross bound area (including opening areas) of the element"""
        return sum(sb.bound_area for sb in self.sbs_without_corresponding)

    def get_net_bound_area(self, name) -> ureg.Quantity:
        """get net area (including opening areas) of the element"""
        return self.gross_area - self.opening_area

    @property
    def is_external(self) -> bool or None:
        """Checks if the corresponding element has contact with external
        environment (e.g. ground, roof, wall)"""
        if hasattr(self, 'parent'):
            return self.parent.is_external
        elif hasattr(self, 'ifc'):
            if hasattr(self.ifc, 'ProvidesBoundaries'):
                if len(self.ifc.ProvidesBoundaries) > 0:
                    ext_int = list(
                        set([boundary.InternalOrExternalBoundary for boundary
                             in self.ifc.ProvidesBoundaries]))
                    if len(ext_int) == 1:
                        if ext_int[0].lower() == 'external':
                            return True
                        if ext_int[0].lower() == 'internal':
                            return False
                    else:
                        return ext_int
        return None

    def calc_cost_group(self) -> int:
        """Default cost group for building elements is 300"""
        return 300

    def _calc_teaser_orientation(self, name) -> Union[int, None]:
        """Calculate the orientation of the bps product based on SB direction.

        For buildings elements we can use the more reliable space boundaries
        normal vector to calculate the orientation if the space boundaries
        exists. Otherwise the base calc_orientation of IFCBased will be used.

        Returns:
            Orientation angle between 0 and 360.
            (0 : north, 90: east, 180: south, 270: west)
        """
        true_north = self.get_true_north()
        if len(self.space_boundaries):
            new_orientation = self.group_orientation(
                [vector_angle(space_boundary.bound_normal.Coord())
                 for space_boundary in self.space_boundaries])
            if new_orientation is not None:
                return int(angle_equivalent(new_orientation + true_north))
        # return int(angle_equivalent(super().calc_orientation() + true_north))
        return None

    @staticmethod
    def group_orientation(orientations: list):
        dict_orientations = {}
        for orientation in orientations:
            rounded_orientation = round(orientation)
            if rounded_orientation not in dict_orientations:
                dict_orientations[rounded_orientation] = 0
            dict_orientations[rounded_orientation] += 1
        if len(dict_orientations):
            return max(dict_orientations, key=dict_orientations.get)
        return None

    def _get_sbs_without_corresponding(self, name) -> list:
        """get a list with only not duplicated space boundaries"""
        sbs_without_corresponding = list(self.space_boundaries)
        for sb in self.space_boundaries:
            if sb in sbs_without_corresponding:
                if sb.related_bound and sb.related_bound in \
                        sbs_without_corresponding:
                    sbs_without_corresponding.remove(sb.related_bound)
        return sbs_without_corresponding

    def _get_opening_area(self, name):
        """get sum of opening areas of the element"""
        return sum(sb.opening_area for sb in self.sbs_without_corresponding)

    teaser_orientation = attribute.Attribute(
        description="Orientation of element in TEASER conventions. 0-360 for "
                    "orientation of vertical elements and -1 for roofs and "
                    "ceiling, -2 for groundfloors and floors.",
        functions=[_calc_teaser_orientation],
    )

    gross_area = attribute.Attribute(
        functions=[get_bound_area],
        unit=ureg.meter ** 2
    )

    net_area = attribute.Attribute(
        functions=[get_net_bound_area],
        unit=ureg.meter ** 2
    )

    sbs_without_corresponding = attribute.Attribute(
        description="A list with only not duplicated space boundaries",
        functions=[_get_sbs_without_corresponding]
    )

    opening_area = attribute.Attribute(
        description="Sum of opening areas of the element",
        functions=[_get_opening_area]
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

    def __init__(self, *args, **kwargs):
        self.bound_elements = kwargs.pop('bound_elements', [])
        super().__init__(*args, **kwargs)

    @property
    def outer_walls(self) -> list:
        """List of all outer wall elements bounded to the thermal zone"""
        return [
            ele for ele in self.bound_elements if isinstance(ele, OuterWall)]

    @property
    def windows(self) -> list:
        """List of all window elements bounded to the thermal zone"""
        return [ele for ele in self.bound_elements if isinstance(ele, Window)]

    @property
    def is_external(self) -> bool:
        """determines if a thermal zone is external or internal based on the
        presence of outer walls"""
        return len(self.outer_walls) > 0

    def _get_external_orientation(self, name) -> str or float:
        """determines the orientation of the thermal zone based on its elements
        it can be a corner (list of 2 angles) or an edge (1 angle)"""
        if self.is_external is True:
            orientations = [ele.teaser_orientation for ele in self.outer_walls]
            calc_temp = list(set(orientations))
            sum_or = sum(calc_temp)
            if 0 in calc_temp:
                if sum_or > 180:
                    sum_or += 360
            return sum_or / len(calc_temp)
        return 'Internal'

    def _get_glass_percentage(self, name) -> float or ureg.Quantity:
        """determines the glass area/facade area ratio for all the windows in
        the space in one of the 4 following ranges
        0%-30%: 15
        30%-50%: 40
        50%-70%: 60
        70%-100%: 85"""
        glass_area = sum(wi.gross_area for wi in self.windows)
        facade_area = sum(wa.gross_area for wa in self.outer_walls)
        if facade_area > 0:
            return 100 * (glass_area / (facade_area + glass_area)).m
        else:
            return 'Internal'

    def _get_space_neighbors(self, name) -> list:
        """determines the neighbors of the thermal zone"""
        neighbors = []
        for sb in self.space_boundaries:
            if sb.related_bound is not None:
                tz = sb.related_bound.bound_thermal_zone
                # todo: check if computation of neighbors works as expected
                # what if boundary has no related bound but still has a
                # neighbor?
                # hint: neighbors != related bounds
                if (tz is not self) and (tz not in neighbors):
                    neighbors.append(tz)
        return neighbors

    def _get_space_shape(self, name):
        """returns topods shape of the IfcSpace"""
        settings = ifcopenshell.geom.main.settings()
        settings.set(settings.USE_PYTHON_OPENCASCADE, True)
        settings.set(settings.USE_WORLD_COORDS, True)
        settings.set(settings.EXCLUDE_SOLIDS_AND_SURFACES, False)
        settings.set(settings.INCLUDE_CURVES, True)
        return ifcopenshell.geom.create_shape(settings, self.ifc).geometry

    def _get_space_center(self, name) -> float:
        """
        This function returns the center of the bounding box of an ifc space
        shape
        :return: center of space bounding box (gp_Pnt)
        """
        bbox = Bnd_Box()
        brepbndlib_Add(self.space_shape, bbox)
        bbox_center = ifcopenshell.geom.utils.get_bounding_box_center(bbox)
        return bbox_center

    def _get_footprint_shape(self, name):
        """
        This function returns the footprint of a space shape. This can be
        used e.g., to visualize floor plans.
        """
        footprint = PyOCCTools.get_footprint_of_shape(self.space_shape)
        return footprint

    def _get_space_shape_volume(self, name):
        """
        This function returns the volume of a space shape
        """
        return PyOCCTools.get_shape_volume(self.space_shape)

    def _get_volume_geometric(self, name):
        """
        This function returns the volume of a space geometrically
        """
        return self.gross_area * self.height

    def _get_usage(self, name):
        """
        This function returns the usage of a space
        """
        if self.zone_name is not None:
            usage = self.zone_name
        elif self.ifc.LongName is not None and \
                "oldSpaceGuids_" not in self.ifc.LongName:
            # todo oldSpaceGuids_ is hardcode for erics tool
            usage = self.ifc.LongName
        else:
            usage = self.name
        return usage

    def _get_name(self, name):
        """
        This function returns the name of a space
        """
        if self.zone_name:
            space_name = self.zone_name
        else:
            space_name = self.ifc.Name
        return space_name

    def get_bound_floor_area(self, name):
        """Get bound floor area of zone. This is currently set by sum of all
        horizontal gross area and take half of it due to issues with
        TOP BOTTOM"""
        leveled_areas = {}
        for height, sbs in self.horizontal_sbs.items():
            if height not in leveled_areas:
                leveled_areas[height] = 0
            leveled_areas[height] += sum([sb.bound_area for sb in sbs])

        return sum(leveled_areas.values()) / 2

    def get_net_bound_floor_area(self, name):
        """Get net bound floor area of zone. This is currently set by sum of all
        horizontal net area and take half of it due to issues with TOP BOTTOM."""
        leveled_areas = {}
        for height, sbs in self.horizontal_sbs.items():
            if height not in leveled_areas:
                leveled_areas[height] = 0
            leveled_areas[height] += sum([sb.net_bound_area for sb in sbs])

        return sum(leveled_areas.values()) / 2

    def _get_horizontal_sbs(self, name):
        """get all horizonal SBs in a zone and convert them into a dict with
         key z-height in room and the SB as value."""
        # todo: use only bottom when TOP bottom is working correctly
        valid = [BoundaryOrientation.top, BoundaryOrientation.bottom]
        leveled_sbs = {}
        for sb in self.sbs_without_corresponding:
            if sb.top_bottom in valid:
                pos = round(sb.position[2], 1)
                if pos not in leveled_sbs:
                    leveled_sbs[pos] = []
                leveled_sbs[pos].append(sb)

        return leveled_sbs

    def _area_specific_post_processing(self, value):
        return value / self.net_area

    def _get_heating_profile(self, name) -> list:
        """returns a heating profile using the heat temperature in the IFC"""
        # todo make this "dynamic" with a night set back
        if self.t_set_heat is not None:
            return [self.t_set_heat.to(ureg.kelvin).m] * 24

    def _get_cooling_profile(self, name) -> list:
        """returns a cooling profile using the cool temperature in the IFC"""
        # todo make this "dynamic" with a night set back
        if self.t_set_cool is not None:
            return [self.t_set_cool.to(ureg.kelvin).m] * 24

    def _get_persons(self, name):
        if self.area_per_occupant:
            return 1 / self.area_per_occupant

    external_orientation = attribute.Attribute(
        description="Orientation of the thermal zone, either 'Internal' or a "
                    "list of 2 angles or a single angle as value between 0 and "
                    "360.",
        functions=[_get_external_orientation]
    )

    glass_percentage = attribute.Attribute(
        description="Determines the glass area/facade area ratio for all the "
                    "windows in the space in one of the 4 following ranges:"
                    " 0%-30%: 15, 30%-50%: 40, 50%-70%: 60, 70%-100%: 85.",
        functions=[_get_glass_percentage]
    )

    space_neighbors = attribute.Attribute(
        description="Determines the neighbors of the thermal zone.",
        functions=[_get_space_neighbors]
    )

    space_shape = attribute.Attribute(
        description="Returns topods shape of the IfcSpace.",
        functions=[_get_space_shape]
    )

    space_center = attribute.Attribute(
        description="Returns the center of the bounding box of an ifc space "
                    "shape.",
        functions=[_get_space_center]
    )

    footprint_shape = attribute.Attribute(
        description="Returns the footprint of a space shape, which can be "
                    "used e.g., to visualize floor plans.",
        functions=[_get_footprint_shape]
    )

    horizontal_sbs = attribute.Attribute(
        description="All horizontal space boundaries in a zone as dict. Key is" 
                    " the z-zeight in the room and value the SB.",
        functions=[_get_horizontal_sbs]
    )

    zone_name = attribute.Attribute(
        default_ps=("Pset_SpaceCommon", "Reference")
    )

    name = attribute.Attribute(
        functions=[_get_name]
    )

    usage = attribute.Attribute(
        default_ps=("Pset_SpaceOccupancyRequirements", "OccupancyType"),
        functions=[_get_usage]
    )

    t_set_heat = attribute.Attribute(
        default_ps=("Pset_SpaceThermalRequirements", "SpaceTemperatureMin"),
        unit=ureg.degC,
    )

    t_set_cool = attribute.Attribute(
        default_ps=("Pset_SpaceThermalRequirements", "SpaceTemperatureMax"),
        unit=ureg.degC,
    )

    t_ground = attribute.Attribute(
        unit=ureg.degC,
        default=13,
    )

    max_humidity = attribute.Attribute(
        default_ps=("Pset_SpaceThermalRequirements", "SpaceHumidityMax"),
        unit=ureg.dimensionless,
    )

    min_humidity = attribute.Attribute(
        default_ps=("Pset_SpaceThermalRequirements", "SpaceHumidityMin"),
        unit=ureg.dimensionless,
    )

    natural_ventilation = attribute.Attribute(
        default_ps=("Pset_SpaceThermalRequirements", "NaturalVentilation"),
    )

    natural_ventilation_rate = attribute.Attribute(
        default_ps=("Pset_SpaceThermalRequirements", "NaturalVentilationRate"),
        unit=1 / ureg.hour,
    )

    mechanical_ventilation_rate = attribute.Attribute(
        default_ps=("Pset_SpaceThermalRequirements",
                    "MechanicalVentilationRate"),
        unit=1 / ureg.hour,
    )

    with_ahu = attribute.Attribute(
        default_ps=("Pset_SpaceThermalRequirements", "AirConditioning"),
    )

    central_ahu = attribute.Attribute(
        default_ps=("Pset_SpaceThermalRequirements", "AirConditioningCentral"),
    )

    gross_area = attribute.Attribute(
        default_ps=("Qto_SpaceBaseQuantities", "GrossFloorArea"),
        functions=[get_bound_floor_area],
        unit=ureg.meter ** 2
    )

    net_area = attribute.Attribute(
        default_ps=("Qto_SpaceBaseQuantities", "NetFloorArea"),
        functions=[get_net_bound_floor_area],
        unit=ureg.meter ** 2
    )

    net_wall_area = attribute.Attribute(
        default_ps=("Qto_SpaceBaseQuantities", "NetWallArea"),
        unit=ureg.meter ** 2
    )

    net_ceiling_area = attribute.Attribute(
        default_ps=("Qto_SpaceBaseQuantities", "NetCeilingArea"),
        unit=ureg.meter ** 2
    )

    net_volume = attribute.Attribute(
        default_ps=("Qto_SpaceBaseQuantities", "NetVolume"),
        functions=[_get_space_shape_volume, _get_volume_geometric],
        unit=ureg.meter ** 3,
    )
    gross_volume = attribute.Attribute(
        default_ps=("Qto_SpaceBaseQuantities", "GrossVolume"),
        functions=[_get_volume_geometric],
        unit=ureg.meter ** 3,
    )

    height = attribute.Attribute(
        default_ps=("Qto_SpaceBaseQuantities", "Height"),
        unit=ureg.meter,
    )

    length = attribute.Attribute(
        default_ps=("Qto_SpaceBaseQuantities", "Length"),
        unit=ureg.meter,
    )

    width = attribute.Attribute(
        default_ps=("Qto_SpaceBaseQuantities", "Width"),
        unit=ureg.m
    )

    area_per_occupant = attribute.Attribute(
        default_ps=("Pset_SpaceOccupancyRequirements", "AreaPerOccupant"),
        unit=ureg.meter ** 2
    )

    space_shape_volume = attribute.Attribute(
        functions=[_get_space_shape_volume],
        unit=ureg.meter ** 3,
    )

    clothing_persons = attribute.Attribute(
        default_ps=("", "")
    )

    surround_clo_persons = attribute.Attribute(
        default_ps=("", "")
    )

    heating_profile = attribute.Attribute(
        functions=[_get_heating_profile],
    )

    cooling_profile = attribute.Attribute(
        functions=[_get_cooling_profile],
    )

    persons = attribute.Attribute(
        functions=[_get_persons],
    )

    # use conditions
    with_cooling = attribute.Attribute(
    )

    with_heating = attribute.Attribute(
    )

    T_threshold_heating = attribute.Attribute(
    )

    activity_degree_persons = attribute.Attribute(
    )

    fixed_heat_flow_rate_persons = attribute.Attribute(
        default_ps=("Pset_SpaceThermalLoad", "People"),
        unit=ureg.W,
    )

    internal_gains_moisture_no_people = attribute.Attribute(
    )

    T_threshold_cooling = attribute.Attribute(
    )

    ratio_conv_rad_persons = attribute.Attribute(
        default=0.5,
    )

    ratio_conv_rad_machines = attribute.Attribute(
        default=0.5,
    )

    ratio_conv_rad_lighting = attribute.Attribute(
        default=0.5,
    )

    machines = attribute.Attribute(
        description="Specific internal gains through machines, if taken from"
                    " IFC property set a division by thermal zone area is"
                    " needed.",
        default_ps=("Pset_SpaceThermalLoad", "EquipmentSensible"),
        ifc_postprocessing=_area_specific_post_processing,
        unit=ureg.W / (ureg.meter ** 2),
    )

    def _calc_lighting_power(self, name) -> float:
        if self.use_maintained_illuminance:
            return self.maintained_illuminance / self.lighting_efficiency_lumen
        else:
            return self.fixed_lighting_power

    lighting_power = attribute.Attribute(
        description="Specific lighting power in W/m2. If taken from IFC"
                    " property set a division by thermal zone area is needed.",
        default_ps=("Pset_SpaceThermalLoad", "Lighting"),
        ifc_postprocessing=_area_specific_post_processing,
        functions=[_calc_lighting_power],
        unit=ureg.W / (ureg.meter ** 2),
    )

    fixed_lighting_power = attribute.Attribute(
        description="Specific fixed electrical power for lighting in W/m2. "
                    "This value is taken from SIA 2024.",
        unit=ureg.W / (ureg.meter ** 2)
    )

    maintained_illuminance = attribute.Attribute(
        description="Maintained illuminance value for lighting. This value is"
                    " taken from SIA 2024.",
        unit=ureg.lumen / (ureg.meter ** 2)
    )

    use_maintained_illuminance = attribute.Attribute(
        description="Decision variable to determine if lighting_power will"
                    " be given by fixed_lighting_power or by calculation "
                    "using the variables maintained_illuminance and "
                    "lighting_efficiency_lumen. This is not available in IFC "
                    "and can be set through the sim_setting with equivalent "
                    "name. "
    )

    lighting_efficiency_lumen = attribute.Attribute(
        description="Lighting efficiency in lm/W_el, in german: Lichtausbeute.",
        unit=ureg.lumen / ureg.W
    )

    use_constant_infiltration = attribute.Attribute(
    )

    base_infiltration = attribute.Attribute(
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
        default_ps=("Pset_AirSideSystemInformation", "TotalAirflow"),
        unit=ureg.meter ** 3 / ureg.s
    )

    with_ideal_thresholds = attribute.Attribute(
    )

    persons_profile = attribute.Attribute(
    )

    machines_profile = attribute.Attribute(
    )

    lighting_profile = attribute.Attribute(
    )

    def get__elements_by_type(self, type):
        raise NotImplementedError

    def __repr__(self):
        return "<%s (usage: %s)>" \
               % (self.__class__.__name__, self.usage)

class ExternalSpatialElement(ThermalZone):
    ifc_types = {
        "IfcExternalSpatialElement":
            ['*']
    }


class SpaceBoundary(RelationBased):
    ifc_types = {'IfcRelSpaceBoundary': ['*']}

    def __init__(self, *args, elements: dict, **kwargs):
        """spaceboundary __init__ function"""
        super().__init__(*args, **kwargs)
        self.disaggregation = []
        self.bound_element = None
        self.disagg_parent = None
        self.bound_thermal_zone = None
        self._elements = elements
        self.parent_bound = None
        self.opening_bounds = []

    def _calc_position(self, name):
        """
        calculates the position of the spaceboundary, using the relative
        position of resultant disaggregation
        """
        if hasattr(self.ifc.ConnectionGeometry.SurfaceOnRelatingElement,
                   'BasisSurface'):
            position = self.ifc.ConnectionGeometry.SurfaceOnRelatingElement. \
                BasisSurface.Position.Location.Coordinates
        else:
            position = self.ifc.ConnectionGeometry.SurfaceOnRelatingElement. \
                Position.Location.Coordinates

        return position

    @classmethod
    def pre_validate(cls, ifc) -> bool:
        return True

    def validate_creation(self) -> bool:
        if self.bound_area and self.bound_area < 1e-2 * ureg.meter ** 2:
            return True
        return False

    def get_bound_area(self, name) -> ureg.Quantity:
        """compute area of a space boundary"""
        bound_prop = GProp_GProps()
        brepgprop_SurfaceProperties(self.bound_shape, bound_prop)
        area = bound_prop.Mass()
        return area * ureg.meter ** 2

    bound_area = attribute.Attribute(
        description="The area bound by the space boundary.",
        unit=ureg.meter ** 2,
        functions=[get_bound_area]
    )

    def _get_top_bottom(self, name) -> BoundaryOrientation:
        """
        Determines if a boundary is a top (ceiling/roof) or bottom (floor/slab)
         element based solely on its normal vector orientation.

        Classification is based on the dot product between the boundary's
        normal vector and the vertical vector (0, 0, 1):
        - TOP: when normal points upward (dot product > cos(89°))
        - BOTTOM: when normal points downward (dot product < cos(91°))
        - VERTICAL: when normal is perpendicular to vertical (dot product ≈ 0)

        Returns:
            BoundaryOrientation: Enumerated orientation classification
        """
        vertical_vector = gp_XYZ(0.0, 0.0, 1.0)
        cos_angle_top = math.cos(math.radians(89))
        cos_angle_bottom = math.cos(math.radians(91))

        normal_dot_vertical = vertical_vector.Dot(self.bound_normal)

        # Classify based on dot product
        if normal_dot_vertical > cos_angle_top:
            return BoundaryOrientation.top
        elif normal_dot_vertical < cos_angle_bottom:
            return BoundaryOrientation.bottom

        return BoundaryOrientation.vertical

    def _get_bound_center(self, name):
        """ compute center of the bounding box of a space boundary"""
        p = GProp_GProps()
        brepgprop_SurfaceProperties(self.bound_shape, p)
        return p.CentreOfMass().XYZ()

    def _get_related_bound(self, name):
        """
        Get corresponding space boundary in another space,
        ensuring that corresponding space boundaries have a matching number of
        vertices.
        """
        if hasattr(self.ifc, 'CorrespondingBoundary') and \
                self.ifc.CorrespondingBoundary is not None:
            corr_bound = self._elements.get(
                self.ifc.CorrespondingBoundary.GlobalId)
            if corr_bound:
                nb_vert_this = PyOCCTools.get_number_of_vertices(
                    self.bound_shape)
                nb_vert_other = PyOCCTools.get_number_of_vertices(
                    corr_bound.bound_shape)
                # if not nb_vert_this == nb_vert_other:
                #     print("NO VERT MATCH!:", nb_vert_this, nb_vert_other)
                if nb_vert_this == nb_vert_other:
                    return corr_bound
                else:
                    # deal with a mismatch of vertices, due to different
                    # triangulation or for other reasons. Only applicable for
                    # small differences in the bound area between the
                    # corresponding surfaces
                    if abs(self.bound_area.m - corr_bound.bound_area.m) < 0.01:
                        # get points of the current space boundary
                        p = PyOCCTools.get_points_of_face(self.bound_shape)
                        # reverse the points and create a new face. Points
                        # have to be reverted, otherwise it would result in an
                        # incorrectly oriented surface normal
                        p.reverse()
                        new_corr_shape = PyOCCTools.make_faces_from_pnts(p)
                        # move the new shape of the corresponding boundary to
                        # the original position of the corresponding boundary
                        new_moved_corr_shape = (
                            PyOCCTools.move_bounds_to_vertical_pos([
                            new_corr_shape], corr_bound.bound_shape))[0]
                        # assign the new shape to the original shape and
                        # return the new corresponding boundary
                        corr_bound.bound_shape = new_moved_corr_shape
                    return corr_bound
        if self.bound_element is None:
            # return None
            # check for virtual bounds
            if not self.physical:
                corr_bound = None
                # cover virtual space boundaries without related IfcVirtualElement
                if not self.ifc.RelatedBuildingElement:
                    vbs = [b for b in self._elements.values() if
                           isinstance(b, SpaceBoundary) and not
                           b.ifc.RelatedBuildingElement]
                    for b in vbs:
                        if b is self:
                            continue
                        if b.ifc.RelatingSpace == self.ifc.RelatingSpace:
                            continue
                        if not (b.bound_area.m - self.bound_area.m) ** 2 < 1e-2:
                            continue
                        center_dist = gp_Pnt(self.bound_center).Distance(
                            gp_Pnt(b.bound_center)) ** 2
                        if center_dist > 0.5:
                            continue
                        corr_bound = b
                        return corr_bound
                    return None
                # cover virtual space boundaries related to an IfcVirtualElement
                if self.ifc.RelatedBuildingElement.is_a('IfcVirtualElement'):
                    if len(self.ifc.RelatedBuildingElement.ProvidesBoundaries) == 2:
                        for bound in self.ifc.RelatedBuildingElement.ProvidesBoundaries:
                            if bound.GlobalId != self.ifc.GlobalId:
                                corr_bound = self._elements[bound.GlobalId]
                                return corr_bound
        elif len(self.bound_element.space_boundaries) == 1:
            return None
        elif len(self.bound_element.space_boundaries) >= 2:
            own_space_id = self.bound_thermal_zone.ifc.GlobalId
            min_dist = 1000
            corr_bound = None
            for bound in self.bound_element.space_boundaries:
                if bound.level_description != "2a":
                    continue
                if bound is self:
                    continue
                # if bound.bound_normal.Dot(self.bound_normal) != -1:
                #     continue
                other_area = bound.bound_area
                if (other_area.m - self.bound_area.m) ** 2 > 1e-1:
                    continue
                center_dist = gp_Pnt(self.bound_center).Distance(
                    gp_Pnt(bound.bound_center)) ** 2
                if abs(center_dist) > 0.5:
                    continue
                distance = BRepExtrema_DistShapeShape(
                    bound.bound_shape,
                    self.bound_shape,
                    Extrema_ExtFlag_MIN
                ).Value()
                if distance > min_dist:
                    continue
                min_dist = abs(center_dist)
                # self.check_for_vertex_duplicates(bound)
                nb_vert_this = PyOCCTools.get_number_of_vertices(
                    self.bound_shape)
                nb_vert_other = PyOCCTools.get_number_of_vertices(
                    bound.bound_shape)
                # if not nb_vert_this == nb_vert_other:
                #     print("NO VERT MATCH!:", nb_vert_this, nb_vert_other)
                if nb_vert_this == nb_vert_other:
                    corr_bound = bound
            return corr_bound
        else:
            return None

    def _get_related_adb_bound(self, name):
        adb_bound = None
        if self.bound_element is None:
            return None
            # check for visual bounds
        if not self.physical:
            return None
        if self.related_bound:
            if self.bound_thermal_zone == self.related_bound.bound_thermal_zone:
                adb_bound = self.related_bound
            return adb_bound
        for bound in self.bound_element.space_boundaries:
            if bound == self:
                continue
            if not bound.bound_thermal_zone == self.bound_thermal_zone:
                continue
            if abs(bound.bound_area.m - self.bound_area.m) > 1e-3:
                continue
            if all([abs(i) < 1e-3 for i in
                    ((self.bound_normal - bound.bound_normal).Coord())]):
                continue
            if gp_Pnt(bound.bound_center).Distance(
                    gp_Pnt(self.bound_center)) < 0.4:
                adb_bound = bound
        return adb_bound

    related_adb_bound = attribute.Attribute(
        description="Related adiabatic boundary.",
        functions=[_get_related_adb_bound]
    )

    def _get_is_physical(self, name) -> bool:
        """
        This function returns True if the spaceboundary is physical
        """
        return self.ifc.PhysicalOrVirtualBoundary.lower() == 'physical'

    def _get_bound_shape(self, name):
        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_PYTHON_OPENCASCADE, True)
        settings.set(settings.USE_WORLD_COORDS, True)
        settings.set(settings.EXCLUDE_SOLIDS_AND_SURFACES, False)
        settings.set(settings.INCLUDE_CURVES, True)

        # check if the space boundary shapes need a unit conversion (i.e.,
        # an additional transformation to the correct size and position)
        length_unit = self.ifc_units.get('IfcLengthMeasure'.lower())
        conv_required = length_unit != ureg.meter

        try:
            sore = self.ifc.ConnectionGeometry.SurfaceOnRelatingElement
            # if sore.get_info()["InnerBoundaries"] is None:
            shape = ifcopenshell.geom.create_shape(settings, sore)

            if sore.InnerBoundaries:
                # shape = remove_inner_loops(shape)  # todo: return None if not horizontal shape
                # if not shape:
                if self.bound_element.ifc.is_a(
                        'IfcWall'):  # todo: remove this hotfix (generalize)
                    ifc_new = ifcopenshell.file()
                    temp_sore = ifc_new.create_entity('IfcCurveBoundedPlane',
                                                      OuterBoundary=sore.OuterBoundary,
                                                      BasisSurface=sore.BasisSurface)
                    temp_sore.InnerBoundaries = ()
                    shape = ifcopenshell.geom.create_shape(settings, temp_sore)
                else:
                    shape = remove_inner_loops(shape)
            if not (sore.InnerBoundaries and not self.bound_element.ifc.is_a(
                    'IfcWall')):
                faces = PyOCCTools.get_faces_from_shape(shape)
                if len(faces) > 1:
                    unify = ShapeUpgrade_UnifySameDomain()
                    unify.Initialize(shape)
                    unify.Build()
                    shape = unify.Shape()
                    faces = PyOCCTools.get_faces_from_shape(shape)
                face = faces[0]
                face = PyOCCTools.remove_coincident_and_collinear_points_from_face(
                    face)
                shape = face
        except:
            try:
                sore = self.ifc.ConnectionGeometry.SurfaceOnRelatingElement
                ifc_new = ifcopenshell.file()
                temp_sore = ifc_new.create_entity('IfcCurveBoundedPlane',
                                                  OuterBoundary=sore.OuterBoundary,
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

        if conv_required:
            # scale newly created shape of space boundary to correct size
            conv_factor = (1 * length_unit).to(
                ureg.metre).m
            # shape scaling seems to be covered by ifcopenshell, obsolete
            # shape = PyOCCTools.scale_shape(shape, conv_factor, gp_Pnt(0, 0,
            # 0))

        if self.ifc.RelatingSpace.ObjectPlacement:
            lp = PyOCCTools.local_placement(
                self.ifc.RelatingSpace.ObjectPlacement).tolist()
            # transform newly created shape of space boundary to correct
            # position if a unit conversion is required.
            if conv_required:
                for i in range(len(lp)):
                    for j in range(len(lp[i])):
                        coord = lp[i][j] * length_unit
                        lp[i][j] = coord.to(ureg.meter).m
            mat = gp_Mat(lp[0][0], lp[0][1], lp[0][2], lp[1][0], lp[1][1],
                         lp[1][2], lp[2][0], lp[2][1], lp[2][2])
            vec = gp_Vec(lp[0][3], lp[1][3], lp[2][3])
            trsf = gp_Trsf()
            trsf.SetTransformation(gp_Quaternion(mat), vec)
            shape = BRepBuilderAPI_Transform(shape, trsf).Shape()

        # shape = shape.Reversed()
        unify = ShapeUpgrade_UnifySameDomain()
        unify.Initialize(shape)
        unify.Build()
        shape = unify.Shape()

        if self.bound_element is not None:
            bi = self.bound_element
            if not hasattr(bi, "related_openings"):
                return shape
            if len(bi.related_openings) == 0:
                return shape
        shape = PyOCCTools.get_face_from_shape(shape)
        return shape

    def get_level_description(self, name) -> str:
        """
        This function returns the level description of the spaceboundary
        """
        return self.ifc.Description

    def _get_is_external(self, name) -> Union[None, bool]:
        """
        This function returns True if the spaceboundary is external
        """
        if self.ifc.InternalOrExternalBoundary is not None:
            ifc_ext_internal = self.ifc.InternalOrExternalBoundary.lower()
            if ifc_ext_internal == 'internal':
                return False
            elif 'external' in ifc_ext_internal:
                return True
        else:
            return None
        # return not self.ifc.InternalOrExternalBoundary.lower() == 'internal'

    def _get_opening_area(self, name):
        """
        This function returns the opening area of the spaceboundary
        """
        if self.opening_bounds:
            return sum(opening_boundary.bound_area for opening_boundary
                       in self.opening_bounds)
        return 0

    def _get_net_bound_area(self, name):
        """
        This function returns the net bound area of the spaceboundary
        """
        return self.bound_area - self.opening_area

    is_external = attribute.Attribute(
        description="True if the Space Boundary is external",
        functions=[_get_is_external]
    )

    bound_shape = attribute.Attribute(
        description="Bound shape element of the SB.",
        functions=[_get_bound_shape]
    )

    top_bottom = attribute.Attribute(
        description="Info if the SB is top "
                    "(ceiling etc.) or bottom (floor etc.).",
        functions=[_get_top_bottom]
    )

    bound_center = attribute.Attribute(
        description="The center of the space boundary.",
        functions=[_get_bound_center]
    )

    related_bound = attribute.Attribute(
        description="Related space boundary.",
        functions=[_get_related_bound]
    )

    physical = attribute.Attribute(
        description="If the Space Boundary is physical or not.",
        functions=[_get_is_physical]
    )

    opening_area = attribute.Attribute(
        description="Opening area of the Space Boundary.",
        functions = [_get_opening_area]
    )

    net_bound_area = attribute.Attribute(
        description="Net bound area of the Space Boundary",
        functions=[_get_net_bound_area]
    )

    def _get_bound_normal(self, name):
        """
        This function returns the normal vector of the spaceboundary
        """
        return PyOCCTools.simple_face_normal(self.bound_shape)

    bound_normal = attribute.Attribute(
        description="Normal vector of the Space Boundary.",
        functions=[_get_bound_normal]
    )

    level_description = attribute.Attribute(
        functions=[get_level_description],
        # Todo this should be removed in near future. We should either 
        #  find # a way to distinguish the level of SB by something
        #  different or should check this during the creation of SBs
        #  and throw an error if the level is not defined.
        default='2a'
        # HACK: Rou's Model has 2a boundaries but, the description is None,
        #  default set to 2a to temporary solve this problem
    )

    internal_external_type = attribute.Attribute(
        description="Defines, whether the Space Boundary is internal"
                    " (Internal), or external, i.e. adjacent to open space "
                    "(that can be an partially enclosed space, such as terrace"
                    " (External",
        ifc_attr_name="InternalOrExternalBoundary"
    )


class ExtSpatialSpaceBoundary(SpaceBoundary):
    """describes all space boundaries related to an IfcExternalSpatialElement instead of an IfcSpace"""
    pass


class SpaceBoundary2B(SpaceBoundary):
    """describes all newly created space boundaries of type 2b to fill gaps within spaces"""

    def __init__(self, *args, elements=None, **kwargs):
        super(SpaceBoundary2B, self).__init__(*args, elements=None, **kwargs)
        self.ifc = ifcopenshell.create_entity('IfcRelSpaceBoundary')
        self.guid = None
        self.bound_shape = None
        self.thermal_zones = []
        self.bound_element = None
        self.physical = True
        self.is_external = False
        self.related_bound = None
        self.related_adb_bound = None
        self.level_description = '2b'


class BPSProductWithLayers(BPSProduct):
    ifc_types = {}

    def __init__(self, *args, **kwargs):
        """BPSProductWithLayers __init__ function.

        Convention in bim2sim for layerset is layer 0 is inside,
         layer n is outside.
        """
        super().__init__(*args, **kwargs)
        self.layerset = None

    def get_u_value(self, name):
        """wall get_u_value function"""
        layers_r = 0
        for layer in self.layerset.layers:
            if layer.thickness:
                if layer.material.thermal_conduc and \
                        layer.material.thermal_conduc > 0:
                    layers_r += layer.thickness / layer.material.thermal_conduc

        if layers_r > 0:
            return 1 / layers_r
        return None

    def get_thickness_by_layers(self, name):
        """calculate the total thickness of the product based on the thickness
        of each layer."""
        thickness = 0
        for layer in self.layerset.layers:
            if layer.thickness:
                thickness += layer.thickness
        return thickness


class Wall(BPSProductWithLayers):
    """Abstract wall class, only its subclasses Inner- and Outerwalls are used.

    Every element where self.is_external is not True, is an InnerWall.
    """
    ifc_types = {
        "IfcWall":
            ['*', 'MOVABLE', 'PARAPET', 'PARTITIONING', 'PLUMBINGWALL',
             'SHEAR', 'SOLIDWALL', 'POLYGONAL', 'DOOR', 'GATE', 'TRAPDOOR'],
        "IfcWallStandardCase":
            ['*', 'MOVABLE', 'PARAPET', 'PARTITIONING', 'PLUMBINGWALL',
             'SHEAR', 'SOLIDWALL', 'POLYGONAL', 'DOOR', 'GATE', 'TRAPDOOR'],
        "IfcColumn": ['*'],  # Hotfix. TODO: Implement appropriate classes
        "IfcCurtainWall": ['*'] # Hotfix. TODO: Implement appropriate classes
        # "IfcElementedCase": "?"  # TODO
    }

    conditions = [
        condition.RangeCondition('u_value',
                                 0 * ureg.W / ureg.K / ureg.meter ** 2,
                                 5 * ureg.W / ureg.K / ureg.meter ** 2,
                                 critical_for_creation=False),
        condition.UValueCondition('u_value',
                                  threshold=0.2,
                                  critical_for_creation=False),
    ]

    pattern_ifc_type = [
        re.compile('Wall', flags=re.IGNORECASE),
        re.compile('Wand', flags=re.IGNORECASE)
    ]

    def __init__(self, *args, **kwargs):
        """wall __init__ function"""
        super().__init__(*args, **kwargs)

    def get_better_subclass(self):
        return OuterWall if self.is_external else InnerWall

    net_area = attribute.Attribute(
        default_ps=("Qto_WallBaseQuantities", "NetSideArea"),
        functions=[BPSProduct.get_net_bound_area],
        unit=ureg.meter ** 2
    )

    gross_area = attribute.Attribute(
        default_ps=("Qto_WallBaseQuantities", "GrossSideArea"),
        functions=[BPSProduct.get_bound_area],
        unit=ureg.meter ** 2
    )

    tilt = attribute.Attribute(
        default=90
    )

    u_value = attribute.Attribute(
        default_ps=("Pset_WallCommon", "ThermalTransmittance"),
        unit=ureg.W / ureg.K / ureg.meter ** 2,
        functions=[BPSProductWithLayers.get_u_value],
    )

    width = attribute.Attribute(
        default_ps=("Qto_WallBaseQuantities", "Width"),
        functions=[BPSProductWithLayers.get_thickness_by_layers],
        unit=ureg.m
    )

    inner_convection = attribute.Attribute(
        unit=ureg.W / ureg.K / ureg.meter ** 2,
        default=0.6
    )

    is_load_bearing = attribute.Attribute(
        default_ps=("Pset_WallCommon", "LoadBearing"),
    )

    net_volume = attribute.Attribute(
        default_ps=("Qto_WallBaseQuantities", "NetVolume"),
        unit=ureg.meter ** 3
    )

    gross_volume = attribute.Attribute(
        default_ps=("Qto_WallBaseQuantities", "GrossVolume")
    )


class Layer(BPSProduct):
    """Represents the IfcMaterialLayer class."""
    ifc_types = {
        "IfcMaterialLayer": ["*"],
    }
    guid_prefix = "Layer_"

    conditions = [
        condition.RangeCondition('thickness',
                                 0 * ureg.m,
                                 10 * ureg.m,
                                 critical_for_creation=False, incl_edges=False)
    ]

    def __init__(self,  *args, **kwargs):
        """layer __init__ function"""
        super().__init__(*args, **kwargs)
        self.to_layerset: List[LayerSet] = []
        self.parent = None
        self.material = None

    @staticmethod
    def get_id(prefix=""):
        prefix_length = len(prefix)
        if prefix_length > 10:
            raise AttributeError("Max prefix length is 10!")
        ifcopenshell_guid = guid.new()[prefix_length + 1:]
        return f"{prefix}{ifcopenshell_guid}"

    @classmethod
    def pre_validate(cls, ifc) -> bool:
        return True

    def validate_creation(self) -> bool:
        return True

    def _get_thickness(self, name):
        """layer thickness function"""
        if hasattr(self.ifc, 'LayerThickness'):
            return self.ifc.LayerThickness * ureg.meter
        else:
            return float('nan') * ureg.meter

    thickness = attribute.Attribute(
        unit=ureg.m,
        functions=[_get_thickness]
    )

    is_ventilated = attribute.Attribute(
        description="Indication of whether the material layer represents an "
                    "air layer (or cavity).",
        ifc_attr_name="IsVentilated",
    )

    description = attribute.Attribute(
        description="Definition of the material layer in more descriptive "
                    "terms than given by attributes Name or Category.",
        ifc_attr_name="Description",
    )

    category = attribute.Attribute(
        description="Category of the material layer, e.g. the role it has in"
                    " the layer set it belongs to (such as 'load bearing', "
                    "'thermal insulation' etc.). The list of keywords might be"
                    " extended by model view definitions, however the "
                    "following keywords shall apply in general:",
        ifc_attr_name="Category",
    )

    def __repr__(self):
        return "<%s (material: %s>" \
               % (self.__class__.__name__, self.material)


class LayerSet(BPSProduct):
    """Represents a Layerset in bim2sim.

    Convention in bim2sim for layerset is layer 0 is inside,
     layer n is outside.

    # TODO: when not enriching we currently don't check layer orientation.
    """

    ifc_types = {
        "IfcMaterialLayerSet": ["*"],
    }

    guid_prefix = "LayerSet_"
    conditions = [
        condition.ListCondition('layers',
                                critical_for_creation=False),
        condition.ThicknessCondition('total_thickness',
                                     threshold=0.2,
                                     critical_for_creation=False),
    ]

    def __init__(self, *args, **kwargs):
        """layerset __init__ function"""
        super().__init__(*args, **kwargs)
        self.parents: List[BPSProductWithLayers] = []
        self.layers: List[Layer] = []

    @staticmethod
    def get_id(prefix=""):
        prefix_length = len(prefix)
        if prefix_length > 10:
            raise AttributeError("Max prefix length is 10!")
        ifcopenshell_guid = guid.new()[prefix_length + 1:]
        return f"{prefix}{ifcopenshell_guid}"

    def get_total_thickness(self, name):
        if hasattr(self.ifc, 'TotalThickness'):
            if self.ifc.TotalThickness:
                return self.ifc.TotalThickness * ureg.m
        return sum(layer.thickness for layer in self.layers)

    def _get_volume(self, name):
        if hasattr(self, "net_volume"):
            if self.net_volume:
                vol = self.net_volume
                return vol
            # TODO This is not working currently, because with multiple parents
            #  we dont know the area or width of the parent
            # elif self.parent.width:
            #     vol = self.parent.volume * self.parent.width / self.thickness
            else:
                vol = float('nan') * ureg.meter ** 3
        # TODO see above
        # elif self.parent.width:
        #     vol = self.parent.volume * self.parent.width / self.thickness
        else:
            vol = float('nan') * ureg.meter ** 3
        return vol

    thickness = attribute.Attribute(
        unit=ureg.m,
        functions=[get_total_thickness],
    )

    name = attribute.Attribute(
        description="The name by which the IfcMaterialLayerSet is known.",
        ifc_attr_name="LayerSetName",
    )

    volume = attribute.Attribute(
        description="Volume of layer set",
        functions=[_get_volume],
    )

    def __repr__(self):
        if self.name:
            return "<%s (name: %s, layers: %d)>" \
                   % (self.__class__.__name__, self.name, len(self.layers))
        else:
            return "<%s (layers: %d)>" % (self.__class__.__name__, len(self.layers))


class OuterWall(Wall):
    ifc_types = {}

    def calc_cost_group(self) -> int:
        """Calc cost group for OuterWall

        Load bearing outer walls: 331
        Not load bearing outer walls: 332
        Rest: 330
        """

        if self.is_load_bearing:
            return 331
        elif not self.is_load_bearing:
            return 332
        else:
            return 330


class InnerWall(Wall):
    """InnerWalls are assumed to be always symmetric."""
    ifc_types = {}

    def calc_cost_group(self) -> int:
        """Calc cost group for InnerWall

        Load bearing inner walls: 341
        Not load bearing inner walls: 342
        Rest: 340
        """

        if self.is_load_bearing:
            return 341
        elif not self.is_load_bearing:
            return 342
        else:
            return 340


class Window(BPSProductWithLayers):
    ifc_types = {"IfcWindow": ['*', 'WINDOW', 'SKYLIGHT', 'LIGHTDOME']}

    pattern_ifc_type = [
        re.compile('Window', flags=re.IGNORECASE),
        re.compile('Fenster', flags=re.IGNORECASE)
    ]

    def get_glazing_area(self, name):
        """returns only the glazing area of the windows"""
        if self.glazing_ratio:
            return self.gross_area * self.glazing_ratio
        return self.opening_area

    def calc_cost_group(self) -> int:
        """Calc cost group for Windows

        Outer door: 334
        """

        return 334

    net_area = attribute.Attribute(
        functions=[get_glazing_area],
        unit=ureg.meter ** 2,
    )

    gross_area = attribute.Attribute(
        default_ps=("Qto_WindowBaseQuantities", "Area"),
        functions=[BPSProduct.get_bound_area],
        unit=ureg.meter ** 2
    )

    glazing_ratio = attribute.Attribute(
        default_ps=("Pset_WindowCommon", "GlazingAreaFraction"),
    )

    width = attribute.Attribute(
        default_ps=("Qto_WindowBaseQuantities", "Depth"),
        functions=[BPSProductWithLayers.get_thickness_by_layers],
        unit=ureg.m
    )
    u_value = attribute.Attribute(
        default_ps=("Pset_WindowCommon", "ThermalTransmittance"),
        unit=ureg.W / ureg.K / ureg.meter ** 2,
        functions=[BPSProductWithLayers.get_u_value],
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


class Door(BPSProductWithLayers):
    ifc_types = {"IfcDoor": ['*', 'DOOR', 'GATE', 'TRAPDOOR']}

    pattern_ifc_type = [
        re.compile('Door', flags=re.IGNORECASE),
        re.compile('Tuer', flags=re.IGNORECASE)
    ]

    conditions = [
        condition.RangeCondition('glazing_ratio',
                                 0 * ureg.dimensionless,
                                 1 * ureg.dimensionless, True,
                                 critical_for_creation=False),
    ]

    def get_better_subclass(self):
        return OuterDoor if self.is_external else InnerDoor

    def get_net_area(self, name):
        if self.glazing_ratio:
            return self.gross_area * (1 - self.glazing_ratio)
        return self.gross_area - self.opening_area

    net_area = attribute.Attribute(
        functions=[get_net_area, ],
        unit=ureg.meter ** 2,
    )

    gross_area = attribute.Attribute(
        default_ps=("Qto_DoorBaseQuantities", "Area"),
        functions=[BPSProduct.get_bound_area],
        unit=ureg.meter ** 2
    )

    glazing_ratio = attribute.Attribute(
        default_ps=("Pset_DoorCommon", "GlazingAreaFraction"),
    )

    width = attribute.Attribute(
        default_ps=("Qto_DoorBaseQuantities", "Width"),
        functions=[BPSProductWithLayers.get_thickness_by_layers],
        unit=ureg.m
    )

    u_value = attribute.Attribute(
        unit=ureg.W / ureg.K / ureg.meter ** 2,
        functions=[BPSProductWithLayers.get_u_value],
    )

    inner_convection = attribute.Attribute(
        unit=ureg.W / ureg.K / ureg.meter ** 2,
        default=0.6
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


class InnerDoor(Door):
    ifc_types = {}

    def calc_cost_group(self) -> int:
        """Calc cost group for Innerdoors

        Inner door: 344
        """

        return 344


class OuterDoor(Door):
    ifc_types = {}

    def calc_cost_group(self) -> int:
        """Calc cost group for Outerdoors

        Outer door: 334
        """

        return 334


class Slab(BPSProductWithLayers):
    ifc_types = {
        "IfcSlab": ['*', 'LANDING']
    }

    def __init__(self, *args, **kwargs):
        """slab __init__ function"""
        super().__init__(*args, **kwargs)

    def _calc_teaser_orientation(self, name) -> int:
        """Returns the orientation of the slab in TEASER convention."""
        return -1

    net_area = attribute.Attribute(
        default_ps=("Qto_SlabBaseQuantities", "NetArea"),
        functions=[BPSProduct.get_net_bound_area],
        unit=ureg.meter ** 2
    )

    gross_area = attribute.Attribute(
        default_ps=("Qto_SlabBaseQuantities", "GrossArea"),
        functions=[BPSProduct.get_bound_area],
        unit=ureg.meter ** 2
    )

    width = attribute.Attribute(
        default_ps=("Qto_SlabBaseQuantities", "Width"),
        functions=[BPSProductWithLayers.get_thickness_by_layers],
        unit=ureg.m
    )

    u_value = attribute.Attribute(
        default_ps=("Pset_SlabCommon", "ThermalTransmittance"),
        unit=ureg.W / ureg.K / ureg.meter ** 2,
        functions=[BPSProductWithLayers.get_u_value],
    )

    net_volume = attribute.Attribute(
        default_ps=("Qto_SlabBaseQuantities", "NetVolume"),
        unit=ureg.meter ** 3
    )

    is_load_bearing = attribute.Attribute(
        default_ps=("Pset_SlabCommon", "LoadBearing"),
    )


class Roof(Slab):
    # todo decomposed roofs dont have materials, layers etc. because these
    #  information are stored in the slab itself and not the decomposition
    # is_external = True
    ifc_types = {
        "IfcRoof":
            ['*', 'FLAT_ROOF', 'SHED_ROOF', 'GABLE_ROOF', 'HIP_ROOF',
             'HIPPED_GABLE_ROOF', 'GAMBREL_ROOF', 'MANSARD_ROOF',
             'BARREL_ROOF', 'RAINBOW_ROOF', 'BUTTERFLY_ROOF', 'PAVILION_ROOF',
             'DOME_ROOF', 'FREEFORM'],
        "IfcSlab": ['ROOF']
    }

    def calc_cost_group(self) -> int:
        """Calc cost group for Roofs


        Load bearing: 361
        Not load bearing: 363
        """
        if self.is_load_bearing:
            return 361
        elif not self.is_load_bearing:
            return 363
        else:
            return 300


class InnerFloor(Slab):
    """In bim2sim we handle all inner slabs as floors/inner floors.

    Orientation of layerset is layer 0 is inside (floor surface of this room),
     layer n is outside (ceiling surface of room below).
    """
    ifc_types = {
        "IfcSlab": ['FLOOR']
    }

    def calc_cost_group(self) -> int:
        """Calc cost group for Floors

        Floor: 351
        """
        return 351


class GroundFloor(Slab):
    # is_external = True  # todo to be removed
    ifc_types = {
        "IfcSlab": ['BASESLAB']
    }

    def _calc_teaser_orientation(self, name) -> int:
        """Returns the orientation of the groundfloor in TEASER convention."""
        return -2

    def calc_cost_group(self) -> int:
        """Calc cost group for groundfloors

        groundfloors: 322
        """

        return 322


    # pattern_ifc_type = [
    #     re.compile('Bodenplatte', flags=re.IGNORECASE),
    #     re.compile('')
    # ]


class Site(BPSProduct):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        del self.building
        self.buildings = []

    # todo move this to base elements as this relevant for other domains as well
    ifc_types = {"IfcSite": ['*']}

    gross_area = attribute.Attribute(
        default_ps=("Qto_SiteBaseQuantities", "GrossArea"),
        unit=ureg.meter ** 2
    )

    location_latitude = attribute.Attribute(
        ifc_attr_name="RefLatitude",
    )

    location_longitude = attribute.Attribute(
        ifc_attr_name="RefLongitude"
    )


class Building(BPSProduct):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.thermal_zones = []
        self.storeys = []
        self.elements = []

    ifc_types = {"IfcBuilding": ['*']}
    from_ifc_domains = [IFCDomain.arch]

    conditions = [
        condition.RangeCondition('year_of_construction',
                                 1900 * ureg.year,
                                 date.today().year * ureg.year,
                                 critical_for_creation=False),
    ]

    def _get_building_name(self, name):
        """get building name"""
        bldg_name = self.get_ifc_attribute('Name')
        if bldg_name:
            return bldg_name
        else:
            # todo needs to be adjusted for multiple buildings #165
            bldg_name = 'Building'
        return bldg_name

    def _get_number_of_storeys(self, name):
        return len(self.storeys)

    def _get_avg_storey_height(self, name):
        """Calculates the average height of all storeys."""
        storey_height_sum = 0
        avg_height = None
        if hasattr(self, "storeys"):
            if len(self.storeys) > 0:
                for storey in self.storeys:
                    if storey.height:
                        height = storey.height
                    elif storey.gross_height:
                        height = storey.gross_height
                    elif storey.net_height:
                        height = storey.net_height
                    else:
                        height = None
                    if height:
                        storey_height_sum += height
                avg_height = storey_height_sum / len(self.storeys)
        return avg_height

    def _check_tz_ahu(self, name):
        """Check if any TZs have AHU, then the building has one as well."""
        with_ahu = False
        for tz in self.thermal_zones:
            if tz.with_ahu:
                with_ahu = True
                break
        return with_ahu

    bldg_name = attribute.Attribute(
        functions=[_get_building_name],
    )

    year_of_construction = attribute.Attribute(
        default_ps=("Pset_BuildingCommon", "YearOfConstruction"),
        unit=ureg.year
    )

    gross_area = attribute.Attribute(
        default_ps=("Qto_BuildingBaseQuantities", "GrossFloorArea"),
        unit=ureg.meter ** 2
    )

    net_area = attribute.Attribute(
        default_ps=("Qto_BuildingBaseQuantities", "NetFloorArea"),
        unit=ureg.meter ** 2
    )

    number_of_storeys = attribute.Attribute(
        unit=ureg.dimensionless,
        functions=[_get_number_of_storeys]
    )

    occupancy_type = attribute.Attribute(
        default_ps=("Pset_BuildingCommon", "OccupancyType"),
    )

    avg_storey_height = attribute.Attribute(
        unit=ureg.meter,
        functions=[_get_avg_storey_height]
    )

    with_ahu = attribute.Attribute(
        functions=[_check_tz_ahu]
    )

    ahu_heating = attribute.Attribute(
        attr_type=bool
    )

    ahu_cooling = attribute.Attribute(
        attr_type=bool
    )

    ahu_dehumidification = attribute.Attribute(
        attr_type=bool
    )

    ahu_humidification = attribute.Attribute(
        attr_type=bool
    )

    ahu_heat_recovery = attribute.Attribute(
        attr_type=bool
    )

    ahu_heat_recovery_efficiency = attribute.Attribute(
    )


class Storey(BPSProduct):
    ifc_types = {'IfcBuildingStorey': ['*']}
    from_ifc_domains = [IFCDomain.arch]

    def __init__(self, *args, **kwargs):
        """storey __init__ function"""
        super().__init__(*args, **kwargs)
        self.elements = []

    spec_machines_internal_load = attribute.Attribute(
        default_ps=("Pset_ThermalLoadDesignCriteria",
                    "ReceptacleLoadIntensity"),
        unit=ureg.kilowatt / (ureg.meter ** 2)
    )

    spec_lighting_internal_load = attribute.Attribute(
        default_ps=("Pset_ThermalLoadDesignCriteria", "LightingLoadIntensity"),
        unit=ureg.kilowatt / (ureg.meter ** 2)
    )

    cooling_load = attribute.Attribute(
        default_ps=("Pset_ThermalLoadAggregate", "TotalCoolingLoad"),
        unit=ureg.kilowatt
    )

    heating_load = attribute.Attribute(
        default_ps=("Pset_ThermalLoadAggregate", "TotalHeatingLoad"),
        unit=ureg.kilowatt
    )

    air_per_person = attribute.Attribute(
        default_ps=("Pset_ThermalLoadDesignCriteria", "OutsideAirPerPerson"),
        unit=ureg.meter ** 3 / ureg.hour
    )

    percent_load_to_radiant = attribute.Attribute(
        default_ps=("Pset_ThermalLoadDesignCriteria",
                    "AppliancePercentLoadToRadiant"),
        unit=ureg.percent
    )

    gross_floor_area = attribute.Attribute(
        default_ps=("Qto_BuildingStoreyBaseQuantities", "GrossFloorArea"),
        unit=ureg.meter ** 2
    )

    # todo make the lookup for height hierarchical
    net_height = attribute.Attribute(
        default_ps=("Qto_BuildingStoreyBaseQuantities", "NetHeight"),
        unit=ureg.meter
    )

    gross_height = attribute.Attribute(
        default_ps=("Qto_BuildingStoreyBaseQuantities", "GrossHeight"),
        unit=ureg.meter
    )

    height = attribute.Attribute(
        default_ps=("Qto_BuildingStoreyBaseQuantities", "Height"),
        unit=ureg.meter
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
