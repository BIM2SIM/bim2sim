from OCC.Core.gp import gp_Pnt

from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements
from bim2sim.utilities.types import BoundaryOrientation
from bim2sim.utilities.pyocc_tools import PyOCCTools

class CorrectInternalExternal(ITask):
    reads = ('elements',)

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
        neighbor_spaces = {space: [] for space in spaces}
        max_space_dist = 0.8  # TODO #31 EDGE bldg
        global_bbox = PyOCCTools.simple_bounding_box_shape([s.space_shape for
                                                            s in spaces])
        global_faces = PyOCCTools.get_faces_from_shape(global_bbox)
        global_shell = PyOCCTools.make_shell_from_faces(global_faces)
        global_bbox_solid = PyOCCTools.make_solid_from_shell(global_shell)

        for space1 in spaces:
            for space2 in spaces:
                if space1 == space2:
                    continue
                if space1 in neighbor_spaces[space2]:
                    continue
                if (PyOCCTools.get_minimum_distance(
                        space1.space_shape, space2.space_shape) <
                        max_space_dist):
                    neighbor_spaces[space1].append(space2)
                    neighbor_spaces[space2].append(space1)

        vertical_bounds = [b for b in bounds
                           if b.top_bottom == BoundaryOrientation.vertical]
        vertical_internal_external = {b: None for b in vertical_bounds}
        for b in vertical_bounds:
            if b.related_bound:
                vertical_internal_external[b] = 'internal'
                continue
            moved_pnt1 = PyOCCTools.get_center_of_shape(
                PyOCCTools.move_bound_in_direction_of_normal(
                    b.bound_shape, 0.1))
            moved_pnt2 = PyOCCTools.get_center_of_shape(
                PyOCCTools.move_bound_in_direction_of_normal(b.bound_shape,
                                                             0.1,
                                                             reverse=True))
            if not all([PyOCCTools.check_pnt_in_solid(global_bbox_solid,
                                                      moved_pnt1),
                        PyOCCTools.check_pnt_in_solid(global_bbox_solid,
                                                      moved_pnt2)]):
                vertical_internal_external[b] = 'external'
                continue
            for ns in neighbor_spaces[b.bound_thermal_zone]:
                if (PyOCCTools.get_point_to_shape_distance(gp_Pnt(
                        b.bound_center), ns.space_shape) <
                        max_space_dist):
                    vertical_internal_external[b] = 'internal'
                    break
            if vertical_internal_external[b]:
                continue
            else:
                # check for column boundaries (bounds with large distance to
                # all other neighboring spaces, but included in boundingbox
                # of own thermal zone. This may fail for non-rectangular
                # space shapes, but most
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
                    vertical_internal_external[b] = 'external'

        # update is external for vertical bounds
        for b in bounds:
            if b in vertical_internal_external.keys():
                if vertical_internal_external[b] == 'external':
                    b.is_external = True
                    b.internal_external_type = 'EXTERNAL'
                else:
                    b.is_external = False
                    b.internal_external_type = 'INTERNAL'






