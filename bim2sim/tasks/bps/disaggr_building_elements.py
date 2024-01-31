import inspect
import math
import numpy as np

from bim2sim.kernel.decorators import cached_property
from bim2sim.elements.mapping import attribute
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements
from bim2sim.utilities.types import LOD


class DisaggregateBuildingElements(ITask):
    """Disaggregate elements, run() method holds detailed information."""

    reads = ('elements',)

    def run(self, elements):
        """Disaggregation of building elements based on their space boundaries.

       This task is needed to allow the later combination of thermal zones in
       CombineThermalZones task.
       As walls, slabs and other elements are often not modeled separately for
       every room/space, we need to split those walls that are stretching along
       multiple spaces into separate pieces. This we call disaggregation.
       The basis to split the elements are the space boundaries that hold the
       relevant information.
       If the zoning_setup sim_setting is set to LOD.low no disaggregations are
       performed as this not required for a 1 zone building model.
       The split elements are added the bound_elements of each ThermalZone
       which will be used later in export.

        Args:
            elements: dict[guid: element] with `bim2sim` elements created based
             on ifc data
        """
        thermal_zones = filter_elements(elements, 'ThermalZone')
        # Disaggregations not necessary for buildings with one zone
        if self.playground.sim_settings.zoning_setup is not LOD.low:
            # Disaggregate elements and add them to bound_elements of the
            # corresponding ThermalZone element.
            n_disaggregations = 0
            for tz in thermal_zones:
                new_bound_elements, n_disaggregations = (
                    self.find_disaggregations(tz))
                # overwrite previous bound_elements with disaggregations
                tz.bound_elements = new_bound_elements
            self.logger.info(f"disaggregated {n_disaggregations} elements")

    def find_disaggregations(self, tz):
        """Retrieves disaggregations of elements for a given thermal zone.

        Args:
            tz (ThermalZone): The thermal zone for which disaggregations are to
             be obtained.

        Returns:
            List[BoundElement or None]: A list of BoundElement
                instances representing the disaggregated elements within the
                specified thermal zone. If an element does not have
                disaggregation information, it is represented as None.
        """
        disaggr_eles = []
        # Dict to maintain which space boundary area is covered by which
        # disaggregation or normal instance
        sb_disaggr_mapping = {}

        for sb in tz.space_boundaries:
            bound_element = sb.bound_element
            if bound_element is not None:
                # Check if disaggregation information is already available
                if sb.guid in sb_disaggr_mapping:
                    disaggr_ele = sb_disaggr_mapping[sb.guid]
                else:
                    # If bound_element belongs only to one ThermalZone, no
                    # disaggregation is needed
                    # TODO move this below
                    if len(bound_element.thermal_zones) == 1:
                        disaggr_ele = bound_element
                        # Store the disaggregation information for each space
                        # boundary in the element
                        for sb_ele in bound_element.space_boundaries:
                            sb_disaggr_mapping[sb_ele.guid] = disaggr_ele
                    else:
                        # Exclude space boundaries with no area
                        if not sb.net_bound_area:
                            disaggr_ele = None
                            sb_disaggr_mapping[sb.guid] = disaggr_ele
                        else:
                            # Create a new disaggregation instance
                            disaggr_ele = self.create_disaggregation(
                                bound_element, sb, tz)
                            sb_disaggr_mapping[sb.guid] = disaggr_ele
                            # Store disaggregation information for related
                            # boundaries
                            if sb.related_bound is not None:
                                sb_disaggr_mapping[sb.related_bound.guid] = \
                                    disaggr_ele
                # Update lists and associations based on the determined
                # instance
                if disaggr_ele:
                    # add disaggregation to list
                    if disaggr_ele not in disaggr_eles:
                        disaggr_eles.append(disaggr_ele)
                    # add sb to disaggregation
                    if sb not in disaggr_ele.space_boundaries:
                        disaggr_ele.space_boundaries.append(sb)
                    # add tz to disaggregation
                    if tz not in disaggr_ele.thermal_zones:
                        disaggr_ele.thermal_zones.append(tz)

        return disaggr_eles, len(sb_disaggr_mapping)

    def create_disaggregation(self, bound_element, sb, tz):
        """Creates disaggregation instance based on the provided bound element.

        This method checks if disaggregation is required for the given bound
        element. If disaggregation is needed, it creates a new instance of the
        same type as the bound element, overwrites attributes based on the
        provided disaggregation information, and returns the new instance. If
        disaggregation is not needed, it returns the original bound element.

        Args:
            bound_element (Type): The bound element to be disaggregated.
            sb (Type): The disaggregation information.
            tz (Type): The timezone information.

        Returns:
            Type: The disaggregated instance.
        """
        sub_class = type(bound_element)
        if self.check_disaggr_requirements(bound_element, sb):
            inst = sub_class(finder=bound_element.finder)
            self.overwrite_attributes(inst, bound_element, sb, tz, sub_class)
        else:
            inst = bound_element
        return inst

    @staticmethod
    def check_disaggr_requirements(element, sb, threshold=0.1):
        """Check if a disaggregation is needed for the given element.

        For elements which only have one space boundary or where the size
        of the space boundary is nearly the same of the element, no
        disaggregation is needed. These requirements are checked through this
        method.

        Args:
            element: `bim2sim` element that is bound to the SpaceBoundary
            sb: SpaceBoundary of the corresponding ThermalZone
            threshold: threshold to ignore elements that have nearly only one
                space boundary.

        Returns:
            True if requirements are fulfilled, False if not
        """
        # Elements with only one space boundary don't need a disaggregation
        if len(element.space_boundaries) == 1:
            return False
        # Negative areas are ignored
        elif sb.bound_area <= 0 or sb.net_bound_area <= 0:
            return False
        # If space boundary area is nearly the same size as total element area,
        # the element needs no disaggregation
        elif (abs(element.gross_area - sb.bound_area) /
              sb.bound_area < threshold):
            return False
        else:
            return True

    def overwrite_attributes(self, inst, parent, sb, tz, subclass,
                             threshold=0.1):
        """# todo write documentation"""
        vertical_elements = ['Wall', 'InnerWall', 'OuterWall']
        horizontal_elements = ['Roof', 'Floor', 'GroundFloor']
        attributes_dict = {}
        type_parent = subclass.__name__
        inst.parent = parent
        if type_parent not in attributes_dict:
            attributes = inspect.getmembers(
                type(parent), lambda a: (type(a) in [attribute.Attribute,
                                                     cached_property]))
            attributes_dict[type_parent] = [attr[0] for attr in attributes]

        inst.space_boundaries.append(sb)
        inst.thermal_zones.append(tz)
        inst.net_area = sb.net_bound_area
        inst.gross_area = sb.bound_area
        inst.orientation = parent.orientation
        inst.layerset = parent.layerset
        new_pos = np.array(sb.position)
        if type_parent in vertical_elements:
            inst.position = self.get_new_position_vertical_element(parent,
                                                                   new_pos)
        if type_parent in horizontal_elements:
            inst.position = tz.position
            if tz.net_area and abs(
                    1 - inst.net_area / tz.net_area) < threshold:
                inst.net_area = tz.net_area
        blacklist = ['position', 'net_area', 'gross_area', 'opening_area']
        for prop in attributes_dict[type_parent]:
            if prop not in blacklist:
                dis_value = getattr(inst, prop)
                if dis_value is None or dis_value == []:
                    parent_value = getattr(inst.parent, prop)
                    if parent_value:
                        setattr(inst, prop, parent_value)

    @staticmethod
    def get_new_position_vertical_element(parent, sub_position):
        """get new position based on parent position, orientation and relative
        disaggregation position"""
        rel_orientation_wall = math.floor(parent.orientation)
        x1, y1, z1 = sub_position
        x, y, z = parent.position
        if 45 <= rel_orientation_wall < 135 or 225 <= rel_orientation_wall \
                < 315:
            y1, z1, z1 = sub_position

        x = x - x1 * math.cos(math.radians(rel_orientation_wall))
        y = y - y1 * math.sin(math.radians(rel_orientation_wall))

        position = np.array([x, y, z])

        return position

# TODO check if this is all correct
# outer_walls = [ele for ele in elements.values() if isinstance(ele,
# OuterWall)]
# outer_walls_wt_parent = [wall for wall in outer_walls if not hasattr(wall,
# "parent")]
# disaggr_outer_walls = [ele for ele in self.disaggregations.values() if
# isinstance(ele, OuterWall)]
# disaggr_outer_walls_wt_parent = [wall for wall in disaggr_outer_walls if
# not hasattr(wall, "parent")]
#
# all_outer_walls = disaggr_outer_walls_wt_parent + outer_walls_wt_parent
# unique_outer_walls = set(all_outer_walls)
#
# real_disaggre_outer_walls = [wall for wall in disaggr_outer_walls if wall
# not in disaggr_outer_walls_wt_parent]
#
# area_all_real_disaggr_outer_walls = sum(wall.gross_area for wall in
# real_disaggre_outer_walls)
# area_all_normal_outer_walls = sum(wall.gross_area for wall in outer_walls)
# area_all_disaggr_outer_walls = sum(wall.gross_area for wall in
# disaggr_outer_walls)
# ToDo: why are there 4 normal outer walls that are part of the
#  disaggregations dict?
#  these are the walls that need no disaggregation (in case of FZK-Haus
#  these are the 4 walls of the upper storey)
