from OCC.Core.gp import gp_Pnt

from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.openfoam_elements.openfoam_base_boundary_conditions import \
    OpenFOAMBaseBoundaryFields
from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.openfoam_elements.openfoam_base_element import \
    OpenFOAMBaseElement
from bim2sim.utilities.pyocc_tools import PyOCCTools


class AirDiffuser(OpenFOAMBaseBoundaryFields, OpenFOAMBaseElement):
    def __init__(self, shape, triSurface_path, air_type,
                 inlet_outlet_type, bbox_min_max, solid_name='diffuser'):
        super().__init__()
        self.solid_name = air_type + '_' + solid_name
        self.patch_info_type = 'wall'
        self.stl_name = self.solid_name + '.stl'
        self.stl_file_path_name = (triSurface_path.as_posix() + '/' +
                                   self.stl_name)
        self.refinement_level = [7, 9]

        if inlet_outlet_type == 'IfcDiffusor':
            raise NotImplementedError
        if inlet_outlet_type == 'StlDiffusor':
            self.tri_geom = PyOCCTools.triangulate_bound_shape(
                shape)
            self.refinement_level = [8, 11]
        elif inlet_outlet_type == 'Plate':
            x1 = bbox_min_max[0][0] - 0.05
            x2 = bbox_min_max[1][0] + 0.05
            y1 = bbox_min_max[0][1] - 0.05
            y2 = bbox_min_max[1][1] + 0.05
            z = bbox_min_max[0][2] - 0.02
            self.tri_geom = PyOCCTools.triangulate_bound_shape(
                PyOCCTools.make_faces_from_pnts([
                    gp_Pnt(x1, y1, z),
                    gp_Pnt(x2, y1, z),
                    gp_Pnt(x2, y2, z),
                    gp_Pnt(x1, y2, z)]
                ))
            self.refinement_level = [4, 7]
        else:
            self.tri_geom = None
            self.solid_name = None
            self.refinement_level = [4, 7]


class AirSourceSink(OpenFOAMBaseBoundaryFields, OpenFOAMBaseElement):
    def __init__(self, shape, triSurface_path, air_type, volumetric_flow,
                 air_temp, solid_name='source_sink'):
        super().__init__()
        self.solid_name = air_type + '_' + solid_name
        self.patch_info_type = 'wall'
        self.stl_name = self.solid_name + '.stl'
        self.stl_file_path_name = (triSurface_path.as_posix() + '/' +
                                   self.stl_name)
        self.refinement_level = [2, 3]
        self.tri_geom = PyOCCTools.triangulate_bound_shape(shape)
        self.volumetric_flow = volumetric_flow / 3600  # convert to m3/s
        self.temperature = air_temp


class AirBox(OpenFOAMBaseBoundaryFields, OpenFOAMBaseElement):
    def __init__(self, shape, triSurface_path, air_type, solid_name='box'):
        super().__init__()
        self.solid_name = air_type + '_' + solid_name
        self.patch_info_type = 'wall'
        self.stl_name = self.solid_name + '.stl'
        self.stl_file_path_name = (triSurface_path.as_posix() + '/' +
                                   self.stl_name)
        self.refinement_level = [2, 3]
        self.tri_geom = PyOCCTools.triangulate_bound_shape(shape)


class AirTerminal:
    def __init__(self, air_type, inlet_shapes, triSurface_path,
                 inlet_outlet_type, solid_name='AirTerminal', air_temp =
                 293.15,
                 volumetric_flow=90,
                 increase_small_refinement=0.10,
                 increase_large_refinement=0.20):
        self.air_type = air_type
        self.solid_name = air_type + '_' + solid_name
        (diffuser_shape, source_sink_shape, box_shape, self.bbox_min_max_shape,
         self.bbox_min_max) = inlet_shapes
        self.diffuser = AirDiffuser(diffuser_shape, triSurface_path, air_type,
                                    inlet_outlet_type, self.bbox_min_max)
        self.source_sink = AirSourceSink(source_sink_shape, triSurface_path,
                                         air_type, volumetric_flow, air_temp)
        self.box = AirBox(box_shape, triSurface_path, air_type)


        self.refinement_zone_small = []
        self.refinement_zone_small.append([c - increase_small_refinement for c
                                           in self.bbox_min_max[0]])
        self.refinement_zone_small.append([c + increase_small_refinement for c
                                           in self.bbox_min_max[1]])
        self.refinement_zone_large = []
        self.refinement_zone_large.append(
            [c - increase_large_refinement for c in
             self.bbox_min_max[0]])
        self.refinement_zone_large.append(
            [c + increase_large_refinement for c in
             self.bbox_min_max[1]])

    def set_boundary_conditions(self, air_temp):
        # set air temperature
        self.source_sink.temperature = air_temp
        pass
