import logging
import math
from typing import List, Union

from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Core.Extrema import Extrema_ExtFlag_MIN
from OCC.Core.gp import gp_Pnt, gp_Dir

from bim2sim.filter import TypeFilter
from bim2sim.kernel.element import RelationBased, Element, IFCBased
from bim2sim.kernel.elements.bps import SpaceBoundary, ExtSpatialSpaceBoundary, \
    ThermalZone, Window, Door
from bim2sim.kernel.finder import TemplateFinder
from bim2sim.kernel.units import ureg
from bim2sim.task.base import ITask
from bim2sim.simulation_settings import BaseSimSettings

logger = logging.getLogger(__name__)


class CreateSpaceBoundaries(ITask):
    """Create space boundary elements from ifc."""

    reads = ('ifc_files', 'instances')
    touches = ('space_boundaries',)

    def run(self, ifc_files, instances):
        logger.info("Creates elements for IfcRelSpaceBoundarys")
        type_filter = TypeFilter(('IfcRelSpaceBoundary',))
        space_boundaries = {}
        for ifc_cls in ifc_files:
            entity_type_dict, unknown_entities = type_filter.run(ifc_cls.file)
            instance_lst = self.instantiate_space_boundaries(
                entity_type_dict, instances, ifc_cls.finder,
                self.playground.sim_settings.create_external_elements,
                ifc_cls.ifc_units)
            bound_instances = self.get_parents_and_children(
                self.playground.sim_settings, instance_lst, instances)
            instance_lst = list(bound_instances.values())
            logger.info(f"Created {len(bound_instances)} bim2sim SpaceBoundary "
                        f"instances based on IFC file: {ifc_cls.ifc_file_name}")
            space_boundaries.update({inst.guid: inst for inst in instance_lst})
        logger.info(f"Created {len(space_boundaries)} bim2sim SpaceBoundary "
                    f"instances in total for all IFC files.")
        return space_boundaries,

    def get_parents_and_children(self, sim_settings: BaseSimSettings,
                                 boundaries: list[SpaceBoundary],
                                 instances: dict, opening_area_tolerance=0.01) \
            -> dict[str, SpaceBoundary]:
        """Get parent-children relationships between space boundaries.

        This function computes the parent-children relationships between
        IfcElements (e.g. Windows, Walls) to obtain the corresponding
        relationships of their space boundaries.

        Args:
            sim_settings: BIM2SIM EnergyPlus simulation settings
            boundaries: list of SpaceBoundary instances
            instances: dict[guid: element]
            opening_area_tolerance: Tolerance for comparison of opening areas.
        Returns:
            bound_dict: dict[guid: element]
        """
        logger.info("Compute relationships between space boundaries")
        logger.info("Compute relationships between openings and their "
                    "base surfaces")
        drop_list = {}  # HACK: dictionary for bounds which have to be removed
        bound_dict = {bound.guid: bound for bound in boundaries}
        temp_instances = instances.copy()
        temp_instances.update(bound_dict)
        # from instances (due to duplications)
        for inst_obj in boundaries:
            if inst_obj.level_description == "2b":
                continue
            inst_obj_space = inst_obj.ifc.RelatingSpace
            b_inst = inst_obj.bound_instance
            if b_inst is None:
                continue
            # assign opening elems (Windows, Doors) to parents and vice versa
            related_opening_elems = \
                self.get_related_opening_elems(b_inst, temp_instances)
            if not related_opening_elems:
                continue
            # assign space boundaries of opening elems (Windows, Doors)
            # to parents and vice versa
            for opening in related_opening_elems:
                op_bound = self.get_opening_boundary(
                    inst_obj, inst_obj_space, opening,
                    sim_settings.max_wall_thickness)
                if not op_bound:
                    continue
                # HACK:
                # find cases where opening area matches area of corresponding
                # wall (within inner loop) and reassign the current opening
                # boundary to the surrounding boundary (which is the true
                # parent boundary)
                if (inst_obj.bound_area - op_bound.bound_area).m \
                        < opening_area_tolerance:
                    rel_bound, drop_list = self.reassign_opening_bounds(
                        inst_obj, op_bound, b_inst, drop_list,
                        sim_settings.max_wall_thickness)
                    if not rel_bound:
                        continue
                    rel_bound.opening_bounds.append(op_bound)
                    op_bound.parent_bound = rel_bound
                else:
                    inst_obj.opening_bounds.append(op_bound)
                    op_bound.parent_bound = inst_obj
        # remove boundaries from dictionary if they are false duplicates of
        # windows in shape of walls
        bound_dict = {k: v for k, v in bound_dict.items() if k not in drop_list}
        return bound_dict

    @staticmethod
    def get_related_opening_elems(bound_instance: Element, instances: dict) \
            -> list[Union[Window, Door]]:
        """Get related opening elements of current building element.

        This function returns all opening elements of the current related
        building element which is related to the current space boundary.

        Args:
            bound_instance: BIM2SIM building element (e.g., Wall, Floor, ...)
            instances: dict[guid: element]
        Returns:
            related_opening_elems: list of Window and Door instances
        """
        related_opening_elems = []
        if not hasattr(bound_instance.ifc, 'HasOpenings'):
            return related_opening_elems
        if len(bound_instance.ifc.HasOpenings) == 0:
            return related_opening_elems

        for opening in bound_instance.ifc.HasOpenings:
            if hasattr(opening.RelatedOpeningElement, 'HasFillings'):
                for fill in opening.RelatedOpeningElement.HasFillings:
                    opening_obj = instances[
                        fill.RelatedBuildingElement.GlobalId]
                    related_opening_elems.append(opening_obj)
        return related_opening_elems

    @staticmethod
    def get_opening_boundary(this_boundary: SpaceBoundary,
                             this_space: ThermalZone,
                             opening_elem: Union[Window, Door],
                             max_wall_thickness=0.3) \
            -> Union[SpaceBoundary, None]:
        """Get related opening boundary of another space boundary.

        This function returns the related opening boundary of another
        space boundary.

        Args:
            this_boundary: current instance of SpaceBoundary
            this_space: ThermalZone instance
            opening_elem: BIM2SIM instance of Window or Door.
            max_wall_thickness: maximum expected wall thickness in the building.
                Space boundaries of openings may be displaced by this distance.
        Returns:
            opening_boundary: Union[SpaceBoundary, None]
        """
        opening_boundary = None
        distances = {}
        for op_bound in opening_elem.space_boundaries:
            if not op_bound.ifc.RelatingSpace == this_space:
                continue
            if op_bound in this_boundary.opening_bounds:
                continue
            center_shape = BRepBuilderAPI_MakeVertex(
                gp_Pnt(op_bound.bound_center)).Shape()
            center_dist = BRepExtrema_DistShapeShape(
                this_boundary.bound_shape,
                center_shape,
                Extrema_ExtFlag_MIN
            ).Value()
            if center_dist > max_wall_thickness:
                continue
            distances[center_dist] = op_bound
        sorted_distances = dict(sorted(distances.items()))
        if sorted_distances:
            opening_boundary = next(iter(sorted_distances.values()))
        return opening_boundary

    @staticmethod
    def reassign_opening_bounds(this_boundary: SpaceBoundary,
                                opening_boundary: SpaceBoundary,
                                bound_instance: Element,
                                drop_list: dict[str, SpaceBoundary],
                                max_wall_thickness=0.3,
                                angle_tolerance=0.1) -> \
            tuple[SpaceBoundary, dict[str, SpaceBoundary]]:
        """Fix assignment of parent and child space boundaries.

        This function reassigns the current opening bound as an opening
        boundary of its surrounding boundary. This function only applies if
        the opening boundary has the same surface area as the assigned parent
        surface.
        HACK:
        Some space boundaries have inner loops which are removed for vertical
        bounds in calc_bound_shape (elements.py). Those inner loops contain
        an additional vertical bound (wall) which is "parent" of an
        opening. EnergyPlus does not accept openings having a parent
        surface of same size as the opening. Thus, since inner loops are
        removed from shapes beforehand, those boundaries are removed from
        "instances" and the openings are assigned to have the larger
        boundary as a parent.

        Args:
            this_boundary: current instance of SpaceBoundary
            opening_boundary: current instance of opening SpaceBoundary (
                related to BIM2SIM Window or Door)
            bound_instance: BIM2SIM building element (e.g., Wall, Floor, ...)
            drop_list: dict[str, SpaceBoundary] with SpaceBoundary instances
                that have same size as opening space boundaries and therefore
                should be dropped
            max_wall_thickness: maximum expected wall thickness in the building.
                Space boundaries of openings may be displaced by this distance.
            angle_tolerance: tolerance for comparison of surface normal angles.
        Returns:
            rel_bound: New parent boundary for the opening that had the same
                geometry as its previous parent boundary
            drop_list: Updated dict[str, SpaceBoundary] with SpaceBoundary
                instances that have same size as opening space boundaries and
                therefore should be dropped
        """
        rel_bound = None
        drop_list[this_boundary.guid] = this_boundary
        ib = [b for b in bound_instance.space_boundaries if
              b.ifc.ConnectionGeometry.SurfaceOnRelatingElement.InnerBoundaries
              if
              b.bound_thermal_zone == opening_boundary.bound_thermal_zone]
        if len(ib) == 1:
            rel_bound = ib[0]
        elif len(ib) > 1:
            for b in ib:
                # check if orientation of possibly related bound is the same
                # as opening
                angle = math.degrees(
                    gp_Dir(b.bound_normal).Angle(gp_Dir(
                        opening_boundary.bound_normal)))
                if not (angle < 0 + angle_tolerance
                        or angle > 180 - angle_tolerance):
                    continue
                distance = BRepExtrema_DistShapeShape(
                    b.bound_shape,
                    opening_boundary.bound_shape,
                    Extrema_ExtFlag_MIN
                ).Value()
                if distance > max_wall_thickness:
                    continue
                else:
                    rel_bound = b
        else:
            tzb = \
                [b for b in
                 opening_boundary.bound_thermal_zone.space_boundaries if
                 b.ifc.ConnectionGeometry.SurfaceOnRelatingElement.InnerBoundaries]
            for b in tzb:
                # check if orientation of possibly related bound is the same
                # as opening
                angle = None
                try:
                    angle = math.degrees(
                        gp_Dir(b.bound_normal).Angle(
                            gp_Dir(opening_boundary.bound_normal)))
                except Exception as ex:
                    logger.warning(f"Unexpected {ex=}. Comparison of bound "
                                   f"normals failed for  "
                                   f"{b.guid} and {opening_boundary.guid}. "
                                   f"{type(ex)=}")
                if not (angle < 0 + angle_tolerance
                        or angle > 180 - angle_tolerance):
                    continue
                distance = BRepExtrema_DistShapeShape(
                    b.bound_shape,
                    opening_boundary.bound_shape,
                    Extrema_ExtFlag_MIN
                ).Value()
                if distance > max_wall_thickness:
                    continue
                else:
                    rel_bound = b
        return rel_bound, drop_list

    def instantiate_space_boundaries(
            self, entities_dict: dict[str], instances: dict, finder:
            TemplateFinder,
            create_external_elements: bool, ifc_units: dict[str, ureg]) \
            -> List[RelationBased]:
        """Instantiate space boundary ifc_entities.

        This function instantiates space boundaries using given element class.
        Result is a list with the resulting valid elements.

        Args:
            entities_dict: dict of Ifc Entities (as str)
            instances: dict[guid: element]
            finder: BIM2SIM TemplateFinder
            create_external_elements: bool, True if external spatial elements 
                should be considered for space boundary setup
            ifc_units: dict of IfcMeasures and Unit (ureg)
        Returns:
            list of dict[guid: SpaceBoundary]
        """
        instance_lst = {}
        for entity in entities_dict:
            if entity.is_a() == 'IfcRelSpaceBoundary1stLevel' or \
                    entity.Name == '1stLevel':
                continue
            if entity.RelatingSpace.is_a('IfcSpace'):
                element = SpaceBoundary.from_ifc(
                    entity, instances=instance_lst, finder=finder,
                    ifc_units=ifc_units)
            elif create_external_elements and entity.RelatingSpace.is_a(
                    'IfcExternalSpatialElement'):
                element = ExtSpatialSpaceBoundary.from_ifc(
                    entity, instances=instance_lst, finder=finder,
                    ifc_units=ifc_units)
            else:
                continue
            # for RelatingSpaces both IfcSpace and IfcExternalSpatialElement are
            # considered
            relating_space = instances.get(
                element.ifc.RelatingSpace.GlobalId, None)
            if relating_space is not None:
                self.connect_space_boundaries(element, relating_space,
                                              instances)
                instance_lst[element.guid] = element

        return list(instance_lst.values())

    def connect_space_boundaries(
            self, space_boundary: SpaceBoundary, relating_space: ThermalZone,
            instances: dict[str, IFCBased]):
        """Connect space boundary with relating space.

        Connects resulting space boundary with the corresponding relating
        space (i.e., ThermalZone) and related building element (if given).

        Args:
            space_boundary: SpaceBoundary
            relating_space: ThermalZone (relating space)
            instances: dict[guid: element]
            """
        relating_space.space_boundaries.append(space_boundary)
        space_boundary.bound_thermal_zone = relating_space

        if space_boundary.ifc.RelatedBuildingElement:
            related_building_element = instances.get(
                space_boundary.ifc.RelatedBuildingElement.GlobalId, None)
            if related_building_element:
                related_building_element.space_boundaries.append(space_boundary)
                space_boundary.bound_instance = related_building_element
                self.connect_instance_to_zone(relating_space,
                                              related_building_element)

    @staticmethod
    def connect_instance_to_zone(thermal_zone: ThermalZone,
                                 bound_instance: IFCBased):
        """Connects related building element and corresponding thermal zone.

        This function connects a thermal zone and its IFCBased related
        building elements.

        Args:
            thermal_zone: ThermalZone
            bound_instance: BIM2SIM IFCBased instance
        """
        if bound_instance not in thermal_zone.bound_elements:
            thermal_zone.bound_elements.append(bound_instance)
        if thermal_zone not in bound_instance.thermal_zones:
            bound_instance.thermal_zones.append(thermal_zone)
