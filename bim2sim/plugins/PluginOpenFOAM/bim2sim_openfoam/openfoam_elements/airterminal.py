from OCC.Core.gp import gp_Pnt

from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.task.create_openfoam_geometry import \
    create_stl_from_shape_single_solid_name
from bim2sim.utilities.pyocc_tools import PyOCCTools


class AirTerminal:
    def __init__(self, air_type, inlet_shapes, triSurface_path, air_temp,
                 inlet_outlet_type, volumetric_flow=90,
                 increase_small_refinement=0.10,
                 increase_large_refinement=0.20):
        self.air_type = air_type
        self.diffuser_name = air_type + '_diffuser'
        self.source_sink_name = air_type + '_source_sink'
        self.patch_info_type = 'wall'
        self.box_name = air_type + '_box'
        (diffuser_shape, source_sink_shape, box_shape, self.box_min_max_shape,
         self.box_min_max) = inlet_shapes
        if inlet_outlet_type == 'IfcDiffusor':
            raise NotImplementedError
        if inlet_outlet_type == 'StlDiffusor':
            self.tri_geom_diffuser = PyOCCTools.triangulate_bound_shape(
                diffuser_shape)
            self.diffuser_refinement_level = [8, 11]
        elif inlet_outlet_type == 'Plate':
            x1 = self.box_min_max[0][0] - 0.05
            x2 = self.box_min_max[1][0] + 0.05
            y1 = self.box_min_max[0][1] - 0.05
            y2 = self.box_min_max[1][1] + 0.05
            z = self.box_min_max[0][2] - 0.02
            self.tri_geom_diffuser = PyOCCTools.triangulate_bound_shape(
                PyOCCTools.make_faces_from_pnts([
                    gp_Pnt(x1, y1, z),
                    gp_Pnt(x2, y1, z),
                    gp_Pnt(x2, y2, z),
                    gp_Pnt(x1, y2, z)]
                ))
            self.diffuser_refinement_level = [4, 7]
        else: # 'None'
            self.tri_geom_diffuser = None
            self.diffuser_name = None
            self.diffuser_refinement_level = [4, 7]

        self.tri_geom_source_sink = PyOCCTools.triangulate_bound_shape(
            source_sink_shape)
        self.tri_geom_box = PyOCCTools.triangulate_bound_shape(box_shape)
        self.volumetric_flow = volumetric_flow / 3600  # convert to m3/s

        self.air_temp = air_temp
        # write trinangulated shapes to stl
        if self.tri_geom_diffuser:
            create_stl_from_shape_single_solid_name(self.tri_geom_diffuser,
                                                    triSurface_path.as_posix() + '/'
                                                    + self.diffuser_name +
                                                    '.stl', self.diffuser_name)
        create_stl_from_shape_single_solid_name(self.tri_geom_source_sink,
                                                triSurface_path.as_posix() + '/'
                                                + self.source_sink_name +
                                                '.stl', self.source_sink_name)
        create_stl_from_shape_single_solid_name(self.tri_geom_box,
                                                triSurface_path.as_posix() + '/'
                                                + self.box_name + '.stl',
                                                self.box_name)

        # todo: change for oriented boxes?
        self.refinement_zone_small = []
        self.refinement_zone_small.append([c - increase_small_refinement for c
                                           in self.box_min_max[0]])
        self.refinement_zone_small.append([c + increase_small_refinement for c
                                           in self.box_min_max[1]])
        self.refinement_zone_large = []
        self.refinement_zone_large.append(
            [c - increase_large_refinement for c in
             self.box_min_max[0]])
        self.refinement_zone_large.append(
            [c + increase_large_refinement for c in
             self.box_min_max[1]])

    def set_boundary_conditions(self):
        pass
