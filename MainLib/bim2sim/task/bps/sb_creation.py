from typing import List
from bim2sim.filter import TypeFilter
from bim2sim.kernel.element import RelationBased
from bim2sim.task.base import ITask, Task
from bim2sim.kernel.elements.bps import SpaceBoundary, InnerWall
from OCC.Core.GProp import GProp_GProps
from OCC.Core.BRepGProp import brepgprop_SurfaceProperties
import ifcopenshell.geom
from OCC.Core.gp import gp_Trsf, gp_Vec, gp_XYZ, gp_Dir, gp_Ax1, gp_Pnt
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Core.Extrema import Extrema_ExtFlag_MIN


class CreateSpaceBoundaries(ITask):
    """Create internal elements from ifc."""

    reads = ('ifc', 'instances', 'finder')
    touches = ('space_boundaries', )

    def __init__(self):
        super().__init__()
        self.non_sb_elements = []

    def run(self, workflow, ifc, instances, finder):
        self.logger.info("Creates elements of relevant ifc types")
        type_filter = TypeFilter(('IfcRelSpaceBoundary',))
        entity_type_dict, unknown_entities = type_filter.run(ifc)
        instance_lst = self.instantiate_space_boundaries(
            entity_type_dict, instances, finder)
        self.set_instances_openings(instances, instance_lst)
        self.logger.info("Created %d elements", len(instance_lst))

        space_boundaries = {inst.guid: inst for inst in instance_lst}
        return space_boundaries,

    @Task.log
    def instantiate_space_boundaries(self, entities_dict, instances,
                                     finder) -> List[RelationBased]:
        """Instantiate ifc_entities using given element class.
        Resulting instances are validated (if not force).
        Results are two lists, one with valid elements and one with
        remaining entities."""

        instance_lst = []
        for entity in entities_dict:
            element = SpaceBoundary.from_ifc(entity, finder=finder)
            if element.ifc.RelatingSpace.is_a('IfcSpace'):
                self.connect_space_boundaries(element, instances)
                instance_lst.append(element)

        return instance_lst

    def connect_space_boundaries(self, space_boundary, instances):
        relating_space = instances.get(space_boundary.ifc.RelatingSpace.GlobalId, None)
        relating_space.space_boundaries.append(space_boundary)
        space_boundary.bound_thermal_zone = relating_space
        # space_boundary.thermal_zones.append(relating_space)  # ToDo: Delete?

        if space_boundary.ifc.RelatedBuildingElement:
            related_building_element = instances.get(space_boundary.ifc.RelatedBuildingElement.GlobalId, None)
            if related_building_element:
                related_building_element.space_boundaries.append(space_boundary)
                space_boundary.bound_instance = related_building_element
                self.connect_instance_to_zone(relating_space, related_building_element)

    @staticmethod
    def connect_instance_to_zone(thermal_zone, bound_instance):
        if bound_instance not in thermal_zone.bound_elements:
            thermal_zone.bound_elements.append(bound_instance)
        if thermal_zone not in bound_instance.thermal_zones:
            bound_instance.thermal_zones.append(thermal_zone)

    def set_instances_openings(self, instances, space_boundaries):
        selected_sb = self.get_no_element_space_boundaries(space_boundaries)
        corresponding = self.get_corresponding_opening(space_boundaries, selected_sb)
        for inst in instances.values():
            self.get_instance_openings(inst, instances, selected_sb, corresponding)

    @staticmethod
    def get_corresponding_opening(space_boundaries, selected_sb, threshold=1e-2):
        corresponding = {}
        for sb_opening in selected_sb.values():
            for sb in space_boundaries:
                if sb != sb_opening:
                    if (sb.bound_thermal_zone == sb_opening.bound_thermal_zone) and \
                            (sb.top_bottom == sb_opening.top_bottom):
                        shape_dist = BRepExtrema_DistShapeShape(
                            sb_opening.bound_shape,
                            sb.bound_shape,
                            Extrema_ExtFlag_MIN
                        ).Value()
                        if shape_dist < threshold:
                            corresponding[sb_opening.guid] = sb
        return corresponding

    def get_instance_openings(self, instance, instances, selected_sb, corresponding):
        if hasattr(instance.ifc, 'HasOpenings'):
            for opening in instance.ifc.HasOpenings:
                related_building_element = opening.RelatedOpeningElement.HasFillings[0].RelatedBuildingElement if \
                    len(opening.RelatedOpeningElement.HasFillings) > 0 else None
                if related_building_element:
                    # opening with element (windows for example)
                    opening_instance = instances.get(related_building_element.GlobalId, None)
                    matched_sb = self.find_opening_bound(instance, opening_instance)
                    if matched_sb:
                        normal_sb = matched_sb[0]
                        opening_sb = matched_sb[1]
                        if not normal_sb.opening_bounds:
                            normal_sb.opening_bounds = []
                        normal_sb.opening_bounds.append(opening_sb)
                        if normal_sb.related_bound:
                            if not normal_sb.related_bound.opening_bounds:
                                normal_sb.related_bound.opening_bounds = []
                            normal_sb.related_bound.opening_bounds.append(opening_sb)
                    else:
                        self.non_sb_elements.append(opening_instance)
                else:
                    # opening with no element (stairs for example)
                    matched_sb = self.filter_matching_sbs(corresponding, instance)
                    self.set_sb_openings(matched_sb, selected_sb)

    @staticmethod
    def get_no_element_space_boundaries(space_boundaries):
        selected_sb = {}
        for sb in space_boundaries:
            if not sb.bound_instance:
                selected_sb[sb.guid] = sb
        return selected_sb

    @staticmethod
    def filter_matching_sbs(corresponding, instance):
        matched = {}
        for guid, sb in corresponding.items():
            if sb.bound_instance == instance:
                matched[guid] = sb
        return matched

    @staticmethod
    def set_sb_openings(matched_sb, selected_sb):
        for guid, sb in matched_sb.items():
            sb_opening = selected_sb[guid]
            if not sb.opening_bounds:
                sb.opening_bounds = []
            sb.opening_bounds.append(sb_opening)

    @staticmethod
    def find_opening_bound(instance, opening_instance):
        distances = {}
        for sb in instance.space_boundaries:
            for sb_opening in opening_instance.space_boundaries:
                if (sb.bound_thermal_zone == sb_opening.bound_thermal_zone) and \
                        (sb.top_bottom == sb_opening.top_bottom):
                    shape_dist = BRepExtrema_DistShapeShape(
                        sb_opening.bound_shape,
                        sb.bound_shape,
                        Extrema_ExtFlag_MIN
                    ).Value()
                    distances[shape_dist] = (sb, sb_opening)
        sorted_distances = dict(sorted(distances.items()))
        if len(sorted_distances) > 0:
            return next(iter(sorted_distances.values()))
        else:
            return None
