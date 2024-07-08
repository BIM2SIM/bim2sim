from __future__ import annotations

from typing import TYPE_CHECKING, Union, Type, Any

from bim2sim.elements.aggregation.bps_aggregations import \
    InnerWallDisaggregated, OuterWallDisaggregated, GroundFloorDisaggregated, \
    RoofDisaggregated, InnerFloorDisaggregated, InnerDoorDisaggregated, \
    OuterDoorDisaggregated
from bim2sim.elements.bps_elements import (
    Slab, Wall, InnerWall, OuterWall, GroundFloor, Roof, InnerFloor,
    BPSProductWithLayers, InnerDoor, OuterDoor,  Door, ExtSpatialSpaceBoundary)
from bim2sim.elements.mapping.units import ureg
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import all_subclasses

if TYPE_CHECKING:
    from bim2sim.elements.bps_elements import SpaceBoundary


class DisaggregationCreationAndTypeCheck(ITask):
    """Disaggregation of elements, run() method holds detailed information."""

    reads = ('elements',)

    def run(self, elements):
        """Disaggregates building elements based on their space boundaries.

        This task disaggregates the building elements like walls, slabs etc.
        based on their SpaceBoundaries. This is needed for two reasons:
        1. If e.g. a BaseSlab in IFC is modeled as one element for whole
         building but only parts of this BaseSlab have contact to ground,
         we can
         split the BaseSlab based on the space boundary information into
         single parts that hold the correct boundary conditions and material
         layer information in the later simulation.
        2. In TEASER we use CombineThermalZones Task to combine multiple
         ThermalZone elements into AggregatedThermalZones to improve simulation
         speed and accuracy. For this we need to split all elements into the
         parts that belong to each ThermalZone.

        This Task also checks and corrects the type of the non disaggregated
        elements based on their SpaceBoundary information, because sometimes
        the predefined types in IFC might not be correct.

        Args:
            elements (dict): Dictionary of building elements to process.
         """
        elements_overwrite = {}
        elements_to_aggregate = {}  # dict(new_element, old_element)
        for ele in elements.values():
            # only handle BPSProductWithLayers
            if not any([isinstance(ele, bps_product_layer_ele) for
                        bps_product_layer_ele in
                        all_subclasses(BPSProductWithLayers)]):
                continue
            # no disaggregation needed
            if len(ele.space_boundaries) < 2:
                self.logger.info(f'No disggregation needed for {ele}')
                continue
            disaggregations = []
            for sb in ele.space_boundaries:
                disaggr = None
                # the space_boundaries may contain those space boundaries,
                # which do not have an IfcSpace as RelatingSpace, but an
                # ExternalSpatialElement. These are handeled in bim2sim as
                # ExternalSpatialSpaceBoundaries and should be excluded for
                # disaggregation.
                if isinstance(sb, ExtSpatialSpaceBoundary):
                    continue
                # skip if disaggregation already exists for this SB
                if sb.disagg_parent:
                    continue
                if sb.related_bound:
                    # todo
                    # related_bounds may have different bound_elements if,
                    # e.g., floor and ceiling are modeled as individual slabs
                    # that are directly bounded without air gap. These should
                    # be aggregated in further development, but for now,
                    # these are aggregated in this disaggregation process
                    if ele != sb.related_bound.bound_element:
                        elements_to_aggregate.update({
                            ele: sb.related_bound.bound_element})
                    # sb with related bound and only 2 sbs needs no
                    # disaggregation
                    if len(ele.space_boundaries) == 2:
                        self.logger.info(f'No disggregation needed for {ele}')
                        continue
                    if len(ele.space_boundaries) > 2:
                        # as above: if the related_bound of a space boundary
                        # is an ExternalSpatialSpaceBoundary,
                        # this related_bound should not be considered for
                        # disaggregation, and the space boundary should be
                        # treated as it had no partner in an adjacent space.
                        if isinstance(sb.related_bound,
                                      ExtSpatialSpaceBoundary):
                            disaggr = (
                                self.
                                create_disaggregation_with_type_correction(
                                    ele, [sb]))
                        else:
                            disaggr = (
                                self.
                                create_disaggregation_with_type_correction(
                                    ele, [sb, sb.related_bound]))
                    else:
                        self.logger.info(f'No disggregation needed for {ele}')
                else:
                    disaggr = self.create_disaggregation_with_type_correction(
                        ele, [sb])
                if disaggr:
                    disaggregations.append(disaggr)
            if disaggregations:
                elements_overwrite[ele] = disaggregations
                # check if disaggregations are complete
                area_disaggr = 0
                for disaggr in disaggregations:
                    area_disaggr += disaggr.gross_area
                diff = (abs(ele.gross_area - area_disaggr) /
                        ele.gross_area * 100) * ureg.percent
                if diff > 5 * ureg.percent:
                    self.logger.warning(
                        f"Found a difference of {round(diff,2)} area of created"
                        f" Disaggregations and original element "
                        f"{ele}, with GUID {ele.guid}. Please check this.")
            else:
                # this type check should only be performed for elements that
                # hold common SpaceBoundary entities, but not for those,
                # which only have ExternalSpatialSpaceBoundaries.
                type_check_sbs = \
                    [s for s in ele.space_boundaries if not
                    isinstance(s, ExtSpatialSpaceBoundary)]
                if len(type_check_sbs) > 0:
                    self.type_correction_not_disaggregation(
                        ele, type_check_sbs)

        # add disaggregations and remove their parent from elements
        for ele, replacements in elements_overwrite.items():
            del elements[ele.guid]
            for replace in replacements:
                elements[replace.guid] = replace

        # remove elements to aggregate (values only, these are deprecated)
        # from elements dictionary.
        for key, value in elements_to_aggregate.items():
            if value in elements:
                del elements[value.guid]

    def type_correction_not_disaggregation(
            self, element, sbs: list['SpaceBoundary']):
        """Performs type correction for non disaggregated elements.

        Args:
            element (BPSProductWithLayers): The element to correct.
            sbs (list[SpaceBoundary]): List of space boundaries associated with
             the element.
        """
        wall_type = self.get_corrected_wall_type(element, sbs)
        if wall_type:
            if not isinstance(element, wall_type):
                self.logger.info(f'Replacing {element.__class__.__name__} '
                                 f'with {wall_type.__name__} for '
                                 f'element with IFC GUID {element.guid} based '
                                 f'on SB information.')
                element.__class__ = wall_type
                return
        slab_type = self.get_corrected_slab_type(element, sbs)
        if slab_type:
            if not isinstance(element, slab_type):
                self.logger.info(f'Replacing {element.__class__.__name__} '
                                 f'with {slab_type.__name__} for '
                                 f'element with IFC GUID {element.guid} based '
                                 f'on SB information.')
                element.__class__ = slab_type
                return
        door_type = self.get_corrected_door_type(element, sbs)
        if door_type:
            if not isinstance(element, door_type):
                self.logger.info(f'Replacing {element.__class__.__name__} '
                                 f'with {door_type.__name__} for '
                                 f'element with IFC GUID {element.guid} based '
                                 f'on SB information.')
                element.__class__ = door_type
                return

    def create_disaggregation_with_type_correction(
            self, element, sbs: list['SpaceBoundary']) -> BPSProductWithLayers:
        """Creates a disaggregation for an element including type correction.

        Args:
            element (BPSProductWithLayers): The element to disaggregate.
            sbs (list[SpaceBoundary]): List of space boundaries associated with
             the element.

        Returns:
            BPSProductWithLayers: The disaggregated element with the correct
             type.
        """
        disaggr = None
        # if Wall
        wall_type = self.get_corrected_wall_type(element, sbs)
        if wall_type:
            if wall_type == InnerWall:
                disaggr = InnerWallDisaggregated(
                    element, sbs)
            elif wall_type == OuterWall:
                disaggr = OuterWallDisaggregated(
                    element, sbs)
            if disaggr:
                if not isinstance(element, wall_type):
                    self.logger.info(f'Replacing {element.__class__.__name__} '
                                     f'with {wall_type.__name__} for'
                                     f' disaggregated element with parent IFC'
                                     f' GUID {element.guid} based on SB'
                                     f' information.')
                return disaggr
        # if Slab
        slab_type = self.get_corrected_slab_type(element, sbs)
        if slab_type:
            if slab_type == GroundFloor:
                disaggr = GroundFloorDisaggregated(
                    element, sbs
                )
            elif slab_type == Roof:
                disaggr = RoofDisaggregated(
                    element, sbs
                )
            elif slab_type == InnerFloor:
                disaggr = InnerFloorDisaggregated(
                    element, sbs
                )
            elif slab_type == OuterWall:
                disaggr = OuterWallDisaggregated(
                    element, sbs
                )
            if disaggr:
                if not isinstance(element, slab_type):
                    self.logger.info(f'Replacing {element.__class__.__name__} '
                                     f'with {slab_type.__name__} for'
                                     f' disaggregated element with parent IFC'
                                     f' GUID {element.guid} based on SB'
                                     f' information.')
                return disaggr
        door_type = self.get_corrected_door_type(element, sbs)
        if door_type:
            if door_type == InnerDoor:
                disaggr = InnerDoorDisaggregated(
                    element, sbs)
            elif door_type == OuterDoor:
                disaggr = OuterDoorDisaggregated(
                    element, sbs)
            if disaggr:
                if not isinstance(element, door_type):
                    self.logger.info(f'Replacing {element.__class__.__name__} '
                                     f'with {door_type.__name__} for'
                                     f' disaggregated element with parent IFC'
                                     f' GUID {element.guid} based on SB'
                                     f' information.')
                return disaggr

    def get_corrected_door_type(self, element, sbs) -> (
            Type[InnerDoor] | Type[OuterDoor] | None):
        """Gets the correct door type based on space boundary information.

        Args:
            element (BPSProductWithLayers): The element to check.
            sbs (list[SpaceBoundary]): List of space boundaries associated with
             the element.

        Returns:
            type: The correct door type or None if not applicable.
        """
        if any([isinstance(element, door_class) for door_class in
                all_subclasses(Door)]):
            # Corresponding Boundaries
            if len(sbs) == 2:
                return InnerDoor
            elif len(sbs) == 1:
                # external Boundary
                if sbs[0].is_external:
                    return OuterDoor
                # 2B space Boundary
                else:
                    return InnerDoor
            else:
                return self.logger("Error in check of correct door type")
        else:
            return None

    def get_corrected_wall_type(
            self, element, sbs) -> (
            Type[InnerWall] | Type[OuterWall] | None):
        """Gets the correct wall type based on space boundary information.

        Args:
            element (BPSProductWithLayers): The element to check.
            sbs (list[SpaceBoundary]): List of space boundaries associated with
             the element.

        Returns:
            type: The correct wall type or None if not applicable.
        """
        if any([isinstance(element, wall_class) for wall_class in
                all_subclasses(Wall)]):
            # Corresponding Boundaries
            if len(sbs) == 2:
                return InnerWall
            elif len(sbs) == 1:
                # external Boundary
                if sbs[0].is_external:
                    return OuterWall
                # 2B space Boundary
                else:
                    return InnerWall
            else:
                return self.logger("Error in check of correct wall type")
        else:
            return None

    def get_corrected_slab_type(
            self, element, sbs) -> (
            Type[InnerFloor] | Type[GroundFloor] | None | Type[Roof],
            Type[OuterWall]):
        """Gets the correct slab type based on space boundary information.

        Args:
            element (BPSProductWithLayers): The element to check.
            sbs (list[SpaceBoundary]): List of space boundaries associated with
             the element
        Returns:
            type: The correct wall type or None if not applicable.
        """
        if any([isinstance(element, slab_class) for slab_class in
                all_subclasses(Slab)]):
            # Corresponding Boundaries
            if len(sbs) == 2:
                return InnerFloor
            elif len(sbs) == 1:
                # external Boundary
                sb = sbs[0]
                if sb.is_external:
                    if sb.internal_external_type == 'EXTERNAL_EARTH':
                        return GroundFloor
                    elif sb.top_bottom == 'BOTTOM':
                        # Possible failure for overhangs that are external but
                        # have contact to air, because IFC provides
                        # information about "EXTERNAL_EARTH" only in rare cases
                        return GroundFloor
                    elif sb.top_bottom == 'TOP':
                        return Roof
                    # vertical slabs might occur in IFC but will be mapped to
                    # bim2sim OuterWall
                    elif sb.top_bottom == "VERTICAL":
                        return OuterWall
                    else:
                        self.logger.error(f"Error in type correction of "
                                          f"{element}")
                # 2B space Boundary
                else:
                    return InnerFloor
            else:
                return self.logger.error("Error in check of correct wall type")
        else:
            return None
