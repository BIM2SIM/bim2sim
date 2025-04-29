from OCC.Core.gp import gp_Pnt

from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements
from bim2sim.utilities.types import BoundaryOrientation
from bim2sim.utilities.pyocc_tools import PyOCCTools

class CorrectInternalExternal(ITask):
    reads = ('elements',)
    touches = ('elements',)

    def run(self, elements):
        if not self.playground.sim_settings.create_elements_from_sb:
            self.logger.warning(
                "Skipping task CorrectInternalExternal as sim_setting "
                "'create_elements_from_sb' is set to False and "
                "internal_external space boundary attributes are assumed to "
                "be correct."
            )
            return

        bounds = filter_elements(elements, 'SpaceBoundary')
        spaces = filter_elements(elements, 'ThermalZone')

        # define a global bounding box of all spaces included in the building.
        global_bbox = PyOCCTools.simple_bounding_box_shape([s.space_shape for
                                                            s in spaces])
        global_faces = PyOCCTools.get_faces_from_shape(global_bbox)
        global_shell = PyOCCTools.make_shell_from_faces(global_faces)
        global_bbox_solid = PyOCCTools.make_solid_from_shell(global_shell)
        max_space_dist = 0.8  # TODO #31 EDGE bldg

        # neighbor spaces are calculated in create_relations.py and assigned
        # to the ThermalZone element.

        # # calculate neighboring spaces of each space and store them in a
        # # dictionary. This pre-computation avoids computational overhead for
        # # further geometric calculations in this algorithm
        # neighbor_spaces = {space: [] for space in spaces}
        # # define the maximum distance to search for neighboring spaces. This
        # # should be the maximum occurring wall distance. If selected too
        # # large, more neighboring spaces are found, which may result in
        # # higher computational cost for further operations, and may lead to
        # # an increased number of false-internal surfaces.
        # for space1 in spaces:
        #     for space2 in spaces:
        #         if space1 == space2:
        #             continue
        #         if space1 in neighbor_spaces[space2]:
        #             continue
        #         if (PyOCCTools.get_minimum_distance(
        #                 space1.space_shape, space2.space_shape) <
        #                 max_space_dist):
        #             neighbor_spaces[space1].append(space2)
        #             neighbor_spaces[space2].append(space1)

        # Further calculations only address vertical boundaries. This
        # algorithm does not affect horizontal boundaries (floors / roofs /
        # slabs)
        vertical_bounds = [b for b in bounds
                           if b.top_bottom == BoundaryOrientation.vertical]
        vertical_internal_external = {b: None for b in vertical_bounds}
        for b in vertical_bounds:
            if vertical_internal_external[b] is not None:
                continue
            if b.related_bound:
                # boundaries with a related boundary (corresponding boundary)
                # are assigned to have a matching surface partner and are
                # thus assigned to be internal. This requires a correct
                # surface matching beforehand.
                vertical_internal_external[b] = 'internal'
                vertical_internal_external[b.related_bound] = 'internal'
                continue
            # First, it is checked if the space boundaries are close to the
            # edge surfaces of the global bounding box, which means
            # that they are external. This does only account for rectangular
            # building shapesy and if the global bounding box is aligned.
            moved_pnt1 = PyOCCTools.get_center_of_shape(
                PyOCCTools.move_bound_in_direction_of_normal(
                    b.bound_shape, 0.1))
            moved_pnt2 = PyOCCTools.get_center_of_shape(
                PyOCCTools.move_bound_in_direction_of_normal(b.bound_shape,
                                                             0.1,
                                                             reverse=True))
            # the bound shape is moved in direction and in reverse of its
            # surface normal, as we do not rely on the surface normal
            # orientation. If any of the moved center points of the moved
            # bounds is outside of the global box, it is an external
            # boundary. The moving distance is set to 0.1 here per default,
            # which may need modification if the space boundaries are not
            # aligned with the space surface.
            if not all([PyOCCTools.check_pnt_in_solid(global_bbox_solid,
                                                      moved_pnt1),
                        PyOCCTools.check_pnt_in_solid(global_bbox_solid,
                                                      moved_pnt2)]):
                vertical_internal_external[b] = 'external'
                continue
            # if the previous checks have not been successfull,
            # it is checked, if the space boundary has a distance below the
            # max_space_distance to any other neighboring space. This may
            # overshoot and result in false-internal assignments
            # if max_space_distance is too large.
            for ns in b.bound_thermal_zone.space_neighbors:
                if (PyOCCTools.get_point_to_shape_distance(gp_Pnt(
                        b.bound_center), ns.space_shape) <
                        max_space_dist):
                    vertical_internal_external[b] = 'internal'
                    break
            if vertical_internal_external[b]:
                continue
            else:
                # Finally, a check for column boundaries (bounds with large
                # distance to all other neighboring spaces) is applied,
                # as columns are included in boundingbox of the own thermal
                # zone. This may fail for non-rectangular space shapes,
                # or spaces with inner wholes (o-shapes) with inner bounds to
                # outdoors, but most columns should be detected correctly
                local_bbox = PyOCCTools.simple_bounding_box_shape(
                    b.bound_thermal_zone.space_shape)
                local_faces = PyOCCTools.get_faces_from_shape(local_bbox)
                local_shell = PyOCCTools.make_shell_from_faces(local_faces)
                local_bbox_solid = PyOCCTools.make_solid_from_shell(
                    local_shell)
                if all([PyOCCTools.check_pnt_in_solid(local_bbox_solid,
                                                      moved_pnt1),
                        PyOCCTools.check_pnt_in_solid(local_bbox_solid,
                                                      moved_pnt2)]):
                    vertical_internal_external[b] = 'internal'
                else:
                    # all leftover bounds are assigned to be external. This
                    # may also be set to internal per default, but needs
                    # further testing
                    vertical_internal_external[b] = 'external'

        # update is_external attributes for vertical bounds
        for b in bounds:
            if b in vertical_internal_external.keys():
                if vertical_internal_external[b] == 'external':
                    b.is_external = True
                    b.internal_external_type = 'EXTERNAL'
                else:
                    b.is_external = False
                    b.internal_external_type = 'INTERNAL'
        return elements,





