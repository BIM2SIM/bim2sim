import logging
import math

from OCC.Core.gp import gp_Pnt

from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.openfoam_elements.openfoam_base_boundary_conditions import \
    OpenFOAMBaseBoundaryFields
from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.openfoam_elements.openfoam_base_element import \
    OpenFOAMBaseElement
from bim2sim.utilities.pyocc_tools import PyOCCTools

logger = logging.getLogger(__name__)


class Furniture(OpenFOAMBaseBoundaryFields, OpenFOAMBaseElement):
    def __init__(self, shape, triSurface_path, furniture_type,
                 bbox_min_max=None, solid_name='furniture',
                 increase_small_refinement=0.10,
                 increase_large_refinement=0.20):
        super().__init__()
        self.solid_name = solid_name + '_' + furniture_type
        self.stl_name = self.solid_name + '.stl'
        self.stl_file_path_name = (triSurface_path.as_posix() + '/' +
                                   self.stl_name)
        self.bbox_min_max = bbox_min_max
        self.patch_info_type = 'wall'
        self.refinement_level = [2, 3]
        self.tri_geom = PyOCCTools.triangulate_bound_shape(shape)
        self.point_in_shape = PyOCCTools.get_center_of_volume(self.tri_geom)
        if not bbox_min_max:
            self.bbox_min_max = PyOCCTools.simple_bounding_box(shape)

        # self.refinement_zone_small = []
        # self.refinement_zone_small.append([c - increase_small_refinement for c
        #                                    in self.bbox_min_max[0]])
        # self.refinement_zone_small.append([c + increase_small_refinement for c
        #                                    in self.bbox_min_max[1]])
        # self.refinement_zone_level_small = [0,
        #                                     self.refinement_level[0]]
        # self.refinement_zone_large = []
        # self.refinement_zone_large.append(
        #     [c - increase_large_refinement for c in
        #      self.bbox_min_max[0]])
        # self.refinement_zone_large.append(
        #     [c + increase_large_refinement for c in
        #      self.bbox_min_max[1]])
        # self.refinement_zone_level_large = [0,
        #                                     self.refinement_level[0]-1]

    def set_boundary_conditions(self):
        pass


class Table(Furniture):
    def __init__(self, furniture_setting, shape, triSurface_path,
                 furniture_type,
                 bbox_min_max=None, solid_name='furniture',
                 chair_bbox_min_max=None,
                 increase_small_refinement=0.10,
                 increase_large_refinement=0.20):
        super().__init__(shape, triSurface_path, furniture_type,
                         bbox_min_max, solid_name,
                         increase_small_refinement,
                         increase_large_refinement)
        self.furniture_type = furniture_type
        self.chair_trsfs = []
        self.chair_locations = []
        self.furniture_setting = furniture_setting
        self.width = bbox_min_max[1][0] - bbox_min_max[0][0]
        self.depth = bbox_min_max[1][1] - bbox_min_max[0][1]
        self.height = bbox_min_max[1][2] - bbox_min_max[0][2]
        chair_width = chair_bbox_min_max[1][0] - chair_bbox_min_max[0][0]
        chair_depth = chair_bbox_min_max[1][1] - chair_bbox_min_max[0][1]
        self.chair_locations, self.chair_trsfs = self.get_local_chair_positions(
            self.furniture_setting, self.bbox_min_max, self.width,
            self.depth, chair_bbox_min_max, chair_width, chair_depth)

    def get_local_chair_positions(self, furniture_setting, table_bbox_min_max,
                                  table_width, table_depth,
                                  chair_bbox_min_max, chair_width, chair_depth):
        distance_y_chair_to_table = chair_depth

        org_chair_pos = gp_Pnt(*chair_bbox_min_max[0])
        z_pos = table_bbox_min_max[0][2]
        chair_pnts = []
        chair_trsfs = []

        if furniture_setting == 'Office':
            min_width = 1.20
            if table_width < min_width:
                logger.warning(
                    f"Width (={table_width}m of table is too small for "
                    f"furniture setting {furniture_setting}. "
                    f"Minimum width of {min_width}m is required. "
                    f"Resulting position does not comply with "
                    f"standards.")
            x_pos = table_bbox_min_max[0][0] + table_width / 2 - chair_width / 2
            y_pos = table_bbox_min_max[0][1] - distance_y_chair_to_table
            chair_pnts.append(gp_Pnt(x_pos, y_pos, z_pos))
            chair_trsfs += PyOCCTools.generate_obj_trsfs(chair_pnts,
                                                             org_chair_pos)

        elif furniture_setting in ['Classroom', 'TwoSideTable', 'GroupTable']:
            chair_pnts0 = []
            min_width = 0.6
            if table_width < min_width:
                logger.warning(
                    f"Width (={table_width}m of table is too small for "
                    f"furniture setting {furniture_setting}. "
                    f"Minimum width of {min_width}m is required. "
                    f"Resulting position does not comply with "
                    f"standards.")
            num_chairs_long = math.floor(table_width / min_width)
            width_per_chair_long = table_width / num_chairs_long
            x_pos = table_bbox_min_max[0][0]
            y_pos = table_bbox_min_max[0][1] - distance_y_chair_to_table
            for i in range(num_chairs_long):
                if i == 0:
                    x_pos += width_per_chair_long / 2 - \
                             chair_width / 2
                else:
                    x_pos += width_per_chair_long
                chair_pnts0.append(gp_Pnt(x_pos, y_pos, z_pos))
            chair_trsfs += PyOCCTools.generate_obj_trsfs(chair_pnts0,
                                                             org_chair_pos)
            chair_pnts += chair_pnts0
        if furniture_setting in ['TwoSideTable', 'GroupTable']:
            chair_pnts180 = []
            min_width = 0.6
            if table_depth < min_width:
                logger.warning(
                    f"Depth (={table_depth}m of table is too small for "
                    f"furniture setting {furniture_setting}. "
                    f"Minimum depth of {min_width}m is required. "
                    f"Resulting position does not comply with "
                    f"standards.")
            num_chairs_long = math.floor(table_width / min_width)
            width_per_chair_long = table_width / num_chairs_long
            x_pos_rot180 = table_bbox_min_max[1][0]
            y_pos_rot180 = table_bbox_min_max[1][1] + distance_y_chair_to_table
            for i in range(num_chairs_long):
                if i == 0:
                    x_pos_rot180 -= (width_per_chair_long / 2 - chair_width / 2)
                else:
                    x_pos_rot180 -= width_per_chair_long
                chair_pnts180.append(gp_Pnt(x_pos_rot180, y_pos_rot180,
                                            z_pos))
            chair_trsfs += PyOCCTools.generate_obj_trsfs(chair_pnts180,
                                                             org_chair_pos,
                                                             rot_angle=180)
            chair_pnts += chair_pnts180

        if furniture_setting in ['GroupTable']:
            min_width = 0.6
            chair_pnts90 = []
            chair_pnts270 = []

            num_chairs_long = math.floor(table_depth / min_width)
            width_per_chair_short = table_depth / num_chairs_long
            x_pos_rot90 = table_bbox_min_max[1][0] + distance_y_chair_to_table
            y_pos_rot90 = table_bbox_min_max[0][1]
            for i in range(num_chairs_long):
                if i == 0:
                    y_pos_rot90 += width_per_chair_short / 2 - \
                                   chair_width / 2
                else:
                    y_pos_rot90 += width_per_chair_short
                chair_pnts90.append(gp_Pnt(x_pos_rot90, y_pos_rot90,
                                           z_pos))
            chair_trsfs += PyOCCTools.generate_obj_trsfs(chair_pnts90,
                                                             org_chair_pos,
                                                             rot_angle=90)
            chair_pnts += chair_pnts90

            x_pos_rot270 = table_bbox_min_max[0][0] - distance_y_chair_to_table
            y_pos_rot270 = table_bbox_min_max[1][1]
            for i in range(num_chairs_long):
                if i == 0:
                    y_pos_rot270 -= (width_per_chair_short / 2 - \
                                    chair_width / 2)
                else:
                    y_pos_rot270 += width_per_chair_short
                chair_pnts270.append(gp_Pnt(x_pos_rot270, y_pos_rot270, z_pos))
            chair_trsfs += PyOCCTools.generate_obj_trsfs(chair_pnts270,
                                                             org_chair_pos,
                                                             rot_angle=270)
            chair_pnts += chair_pnts270

        return chair_pnts, chair_trsfs
