from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCC.Core.TopoDS import TopoDS_Compound, TopoDS_Builder
from OCC.Core.gp import gp_Pnt

from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.openfoam_elements.openfoam_base_boundary_conditions import \
    OpenFOAMBaseBoundaryFields
from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.openfoam_elements.openfoam_base_element import \
    OpenFOAMBaseElement
from bim2sim.utilities.pyocc_tools import PyOCCTools


class HeaterSurface(OpenFOAMBaseBoundaryFields, OpenFOAMBaseElement):
    def __init__(self, name_prefix, heater_shape, triSurface_path,
                 radiative_power):
        super().__init__()
        self.tri_geom = PyOCCTools.triangulate_bound_shape(heater_shape)
        self.power = radiative_power
        self.bound_element_type = 'SpaceHeater'
        self.patch_info_type = 'wall'
        self.solid_name = name_prefix + '_surface'
        self.stl_name = self.solid_name + '.stl'
        self.temperature = 40.0
        self.stl_file_path_name = (triSurface_path.as_posix() + '/' +
                                   self.stl_name)
        self.refinement_level = [2, 6]
        self.bound_area = PyOCCTools.get_shape_area(self.tri_geom)


class PorousMedia(OpenFOAMBaseBoundaryFields, OpenFOAMBaseElement):
    def __init__(self, name_prefix, heater_shape, triSurface_path,
                                 convective_power):
        super().__init__()
        self.solid_name = name_prefix + '_porous_media'
        self.stl_name = self.solid_name + '.stl'
        self.stl_file_path_name = (triSurface_path.as_posix() + '/' +
                                   self.stl_name)
        self.power = convective_power
        self.refinement_level = [2, 6]
        self.tri_geom, self.bbox_min_max = (
            self.create_porous_media_tri_geom(heater_shape))

    @staticmethod
    def create_porous_media_tri_geom(heater_shape):
        # todo: change for oriented boxes?
        # todo: move to PyOCCTools?
        # add porous media
        porous_media_geom_min_max = PyOCCTools.simple_bounding_box(
            heater_shape)
        porous_media_geom = BRepPrimAPI_MakeBox(
            gp_Pnt(*porous_media_geom_min_max[0]),
            gp_Pnt(*porous_media_geom_min_max[1])).Shape()
        # todo: check why compound is created from bounding box shape (
        #  additional computational overhead, redundant?)
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


class Heater:
    def __init__(self, name, heater_shape, triSurface_path, radiation_model,
                 total_heating_power=0,
                 increase_small_refinement=0.05, increase_large_refinement=0.1):
        self.solid_name = name
        self.radiation_model = radiation_model
        self.radiation_power = 0  # total_heating_power * 0.3
        self.convective_power = 0  # total_heating_power * 0.7
        self.bound_element_type = 'SpaceHeater'
        self.heater_surface = HeaterSurface(self.solid_name, heater_shape,
                                            triSurface_path,
                                            self.radiation_power)
        self.porous_media = PorousMedia(self.solid_name, heater_shape,
                                        triSurface_path,
                                        self.convective_power)

        self.refinement_level = [2, 6]
        self.refinement_zone_small = []
        self.refinement_zone_small.append([c - increase_small_refinement for c
                                           in
                                           self.porous_media.bbox_min_max[0]])
        self.refinement_zone_small.append([c + increase_small_refinement for c
                                           in
                                           self.porous_media.bbox_min_max[1]])
        self.refinement_zone_large = []
        self.refinement_zone_large.append(
            [c - increase_large_refinement for c in
             self.porous_media.bbox_min_max[0]])
        self.refinement_zone_large.append(
            [c + increase_large_refinement for c in
             self.porous_media.bbox_min_max[1]])

    def set_boundary_conditions(self, total_heating_power, percent_radiation):
        if self.radiation_model == 'none':
            qr = 'none'
        else:
            qr = 'qr'
        self.radiation_power = total_heating_power * percent_radiation
        self.convective_power = total_heating_power * (1-percent_radiation)

        self.porous_media.power = self.convective_power
        # radiation
        self.heater_surface.power = self.radiation_power
        self.heater_surface.heat_flux = self.radiation_power / (self.heater_surface.bound_area * 2)
        self.heater_surface.T = \
            {'type': 'externalWallHeatFluxTemperature',
             'mode': 'power',
             'qr': f"{qr}",
             'Q': f'{self.heater_surface.power}',
             'qrRelaxation': 0.003,
             'relaxation': 1.0,
             'kappaMethod': 'fluidThermo',
             'kappa': 'fluidThermo',
             'value': f'uniform {self.heater_surface.temperature + 273.15}'
             }
