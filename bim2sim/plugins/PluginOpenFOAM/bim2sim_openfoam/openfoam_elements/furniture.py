from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.openfoam_elements.openfoam_base_boundary_conditions import \
    OpenFOAMBaseBoundaryFields
from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.openfoam_elements.openfoam_base_element import \
    OpenFOAMBaseElement
from bim2sim.utilities.pyocc_tools import PyOCCTools


class Furniture(OpenFOAMBaseBoundaryFields, OpenFOAMBaseElement):
    def __init__(self, shape, triSurface_path, furniture_type,
                 bbox_min_max=None, solid_name='furniture',
                 increase_small_refinement=0.10,
                 increase_large_refinement=0.20):
        super().__init__()
        self.bbox_min_max = bbox_min_max
        self.solid_name = solid_name + '_' + furniture_type
        self.stl_name = self.solid_name + '.stl'
        self.stl_file_path_name = (triSurface_path.as_posix() + '/' +
                                   self.stl_name)
        self.bbox_min_max = bbox_min_max
        self.patch_info_type = 'wall'
        self.refinement_level = [2, 7]
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

