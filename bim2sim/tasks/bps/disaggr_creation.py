from bim2sim.elements.aggregation.bps_aggregations import \
    InnerWallDisaggregated, OuterWallDisaggregated, GroundFloorDisaggregated, \
    RoofDisaggregated, InnerFloorDisaggregated
from bim2sim.elements.bps_elements import Slab, Wall, InnerWall, OuterWall, \
    GroundFloor, Roof, InnerFloor, BPSProductWithLayers, ExtSpatialSpaceBoundary
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import all_subclasses


class DisaggregationCreation(ITask):
    """Disaggregates building elements based on their space boundaries.

    # TODO we also fix types based on SBs

    This task is needed to allow the later combination for thermal zones. If
    two
    thermal zones are combined to one, we might need to cut/disaggregate
    elements like walls into pieces that belong to the different zones.
    """

    reads = ('elements',)

    # def __init__(self, playground):
    #     super().__init__(playground)
    # self.disaggregations = {}
    # self.vertical_elements = ['Wall', 'InnerWall', 'OuterWall']
    # TODO aren't Slabs missing in horizontal_elements?
    # self.horizontal_elements = ['Roof', 'Floor', 'GroundFloor']
    # self.attributes_dict = {}

    def run(self, elements):
        # from bim2sim.elements.aggregation.bps_aggregations import
        # InnerSlabDisaggregated
        # slab_test = elements['2RGlQk4xH47RHK93zcTzUL']
        # disaggr_test = InnerSlabDisaggregated(slab_test, sbs)

        elements_overwrite = {}
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
            for sb in ele.space_boundaries:  # TODO: check if list or dict
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
                            disaggr= (
                                self.create_disaggregation_with_type_correction(
                                ele, [sb]))
                        else:
                            disaggr = self.create_disaggregation_with_type_correction(
                                ele, [sb, sb.related_bound])
                    else:
                        self.logger.info(f'No disggregation needed for {ele}')
                else:
                    disaggr = self.create_disaggregation_with_type_correction(ele, [sb])
                if disaggr:
                    disaggregations.append(disaggr)
            if disaggregations:
                elements_overwrite[ele] = disaggregations
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

    def type_correction_not_disaggregation(
            self, element, sbs: list['SpaceBoundary']):
        """Type correction for non disaggregation with SBs.

        Args:
            element:
            sbs:

        Returns:

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
        # TODO door type

    def create_disaggregation_with_type_correction(
            self, element, sbs: list['SpaceBoundary']):
        """Disaggregation creation including type correction with SBs.

        Args:
            element:
            sbs:

        Returns:

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
                # self.overwrite_attributes(inst, bound_element, sb, tz,
                #                           sub_class)
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
            if disaggr:
                if not isinstance(element, slab_type):
                    self.logger.info(f'Replacing {element.__class__.__name__} '
                                     f'with {slab_type.__name__} for'
                                     f' disaggregated element with parent IFC'
                                     f' GUID {element.guid} based on SB'
                                     f' information.')
                # self.overwrite_attributes(inst, bound_element, sb, tz,
                #                           sub_class)
                return disaggr
        # TODO handle plates and coverings

    def get_corrected_door_type(self, element):
        # TODO
        pass

    def get_corrected_wall_type(self, element, sbs):
        """Get corrected wall types based on SB information.

        Args:
            element:
            sbs:

        Returns:

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
        # TODO check plate and covering?

    def get_corrected_slab_type(self, element, sbs):
        """Get corrected slab type based on SB information.


        Args:
            element:
            sbs:

        Returns:

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
                    # EXTERNAL_EARTH
                    if sb.internal_external_type == 'EXTERNAL_EARTH':
                        return GroundFloor
                    elif sb.top_bottom == 'BOTTOM':
                        # TODO check if external floor is external_earth then
                        #  we use InnerSlab here
                        return GroundFloor
                    elif sb.top_bottom == 'TOP':
                        return Roof
                    # check top bottom
                    return OuterWall
                # 2B space Boundary
                else:
                    return InnerFloor
            else:
                return self.logger("Error in check of correct wall type")
        else:
            return None
        # TODO check plate and covering?


    # def overwrite_attributes(self, inst, parent, sb, tz, subclass,
    #                          threshold=0.1):
    #     """# todo write documentation"""
    #     type_parent = subclass.__name__
    #     inst.parent = parent
    #     if type_parent not in self.attributes_dict:
    #         attributes = inspect.getmembers(
    #             type(parent), lambda a: (type(a) in [attribute.Attribute,
    #                                                  cached_property]))
    #         self.attributes_dict[type_parent] = [attr[0] for attr in
    #         attributes]
    #
    #     inst.space_boundaries.append(sb)
    #     inst.thermal_zones.append(tz)
    #     inst.net_area = sb.net_bound_area
    #     inst.gross_area = sb.bound_area
    #     inst.orientation = parent.orientation
    #     inst.layerset = parent.layerset
    #     new_pos = np.array(sb.position)
    #     if type_parent in self.vertical_elements:
    #         inst.position = self.get_new_position_vertical_element(parent,
    #                                                                new_pos)
    #     if type_parent in self.horizontal_elements:
    #         inst.position = tz.position
    #         if tz.net_area and abs(1 - inst.net_area / tz.net_area) <
    #         threshold:
    #             inst.net_area = tz.net_area
    #     blacklist = ['position', 'net_area', 'gross_area', 'opening_area']
    #     for prop in self.attributes_dict[type_parent]:
    #         if prop not in blacklist:
    #             dis_value = getattr(inst, prop)
    #             if dis_value is None or dis_value == []:
    #                 parent_value = getattr(inst.parent, prop)
    #                 if parent_value:
    #                     setattr(inst, prop, parent_value)
    #
