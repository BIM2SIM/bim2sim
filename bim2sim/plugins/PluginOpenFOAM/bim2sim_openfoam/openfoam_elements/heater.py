from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCC.Core.TopoDS import TopoDS_Compound, TopoDS_Builder
from OCC.Core.gp import gp_Pnt

from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.task.init_openfoam import \
    create_stl_from_shape_single_solid_name
from bim2sim.utilities.pyocc_tools import PyOCCTools


class Heater:
    def __init__(self, heater_shape, triSurface_path, total_heating_power,
                 increase_small_refinement=0.05, increase_large_refinement=0.1):
        self.tri_geom = PyOCCTools.triangulate_bound_shape(heater_shape)
        self.radiation_power = total_heating_power * 0.3
        self.convective_power = total_heating_power * 0.7
        self.bound_element_type = 'SpaceHeater'
        self.patch_info_type = 'wall'
        self.solid_name = 'heater'
        self.stl_name = 'Heater'
        self.surf_temp = 50.0
        self.porous_media_name = 'porous_media'
        self.stl_file_path_name = (triSurface_path.as_posix() + '/' +
                                   self.stl_name + '.stl')
        self.refinement_level = [2, 3]
        self.porous_media_file_path = (triSurface_path.as_posix() + '/' +
                                       self.porous_media_name + '.stl')
        self.porous_media_tri_geom, self.porous_media_min_max = (
            self.create_porous_media_tri_geom())
        # todo: change for oriented boxes?
        self.refinement_zone_small = []
        self.refinement_zone_small.append([c - increase_small_refinement for c
                                           in self.porous_media_min_max[0]])
        self.refinement_zone_small.append([c + increase_small_refinement for c
                                           in self.porous_media_min_max[1]])
        self.refinement_zone_large = []
        self.refinement_zone_large.append(
            [c - increase_large_refinement for c in
             self.porous_media_min_max[0]])
        self.refinement_zone_large.append(
            [c + increase_large_refinement for c in
             self.porous_media_min_max[1]])

        # create stl for Heater geometry
        create_stl_from_shape_single_solid_name(self.tri_geom,
                                                self.stl_file_path_name,
                                                self.solid_name)
        create_stl_from_shape_single_solid_name(self.porous_media_tri_geom,
                                                self.porous_media_file_path,
                                                self.porous_media_name)

    def create_porous_media_tri_geom(self):
        # add porous media
        porous_media_geom_min_max = PyOCCTools.simple_bounding_box(
            self.tri_geom)
        porous_media_geom = BRepPrimAPI_MakeBox(
            gp_Pnt(*porous_media_geom_min_max[0]),
            gp_Pnt(*porous_media_geom_min_max[1])).Shape()
        porous_face_list = PyOCCTools.get_faces_from_shape(porous_media_geom)
        porous_shape = TopoDS_Compound()
        builder = TopoDS_Builder()
        builder.MakeCompound(porous_shape)
        for shape in porous_face_list:
            builder.Add(porous_shape, shape)
        porous_media_geom = porous_shape

        porous_media_tri_geom = PyOCCTools.triangulate_bound_shape(
            porous_media_geom)

        return porous_media_tri_geom, porous_media_geom_min_max
