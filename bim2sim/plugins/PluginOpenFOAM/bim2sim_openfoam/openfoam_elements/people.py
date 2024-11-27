import stl
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCC.Core.StlAPI import StlAPI_Reader
from OCC.Core.TopoDS import TopoDS_Shape
from stl import mesh
from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.openfoam_elements.openfoam_base_boundary_conditions import \
    OpenFOAMBaseBoundaryFields
from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.openfoam_elements.openfoam_base_element import \
    OpenFOAMBaseElement
from bim2sim.utilities.pyocc_tools import PyOCCTools

body_part_boundary_conditions = {
    # detailed temperatures represent clothing/skin temperatures according to
    # Yamamoto et al. 2023, Case 3 (3rd) (average for left and right
    # temperatures), and face temperature has been defined according to Zhu
    # et al. (2007). All body part temperatures have been mapped to MORPHEUS
    # body part definitions (19 body parts).
    'FullBody':
        {
            'T': 32,
            'power_fraction': 1,
            'hr_hc': 0
        },
    'manikinsittinghead':
        {
            'T': 36,
            'power_fraction': 0.3,
            'hr_hc': 0
        },
    'manikinsittingbody':
        {
            'T': 30,
            'power_fraction': 0.7,
            'hr_hc': 0
        },
    'abdomen':
        {
            'T': 27.25,
            'power_fraction': 0,
            'hr_hc': 7.81
        },

    'head_back':
        {
            'T': 32.43,
            'power_fraction': 0,
            'hr_hc': 9.89
        },
    'head_face':
        {
            'T': 35.9,
            'power_fraction': 0,
            'hr_hc': 9.92
        },
    'left_foot':
        {
            'T': 29.33,
            'power_fraction': 0,
            'hr_hc': 20.615
        },
    'left_hand':
        {
            'T': 32,
            'power_fraction': 0,
            'hr_hc': 8.2
        },
    'left_lower_arm':
        {
            'T': 26.225,
            'power_fraction': 0,
            'hr_hc': 7.815
        },
    'left_lower_leg':
        {
            'T': 25.21,
            'power_fraction': 0,
            'hr_hc': 14.32
        },
    'left_shoulder':
        {
            'T': 25.865,
            'power_fraction': 0,
            'hr_hc': 8.35
        },
    'left_upper_arm':
        {
            'T': 26.225,
            'power_fraction': 0,
            'hr_hc': 7.815
        },
    'left_upper_leg':
        {
            'T': 26.195,
            'power_fraction': 0,
            'hr_hc': 4.06
        },
    'neck':
        {
            'T': 31.25,
            'power_fraction': 0,
            'hr_hc': 9.27
        },
    'right_foot':
        {
            'T': 29.33,
            'power_fraction': 0,
            'hr_hc': 20.615
        },
    'right_hand':
        {
            'T': 32,
            'power_fraction': 0,
            'hr_hc': 8.2
        },
    'right_lower_arm':
        {
            'T': 26.225,
            'power_fraction': 0,
            'hr_hc': 7.815
        },
    'right_lower_leg':
        {
            'T': 25.21,
            'power_fraction': 0,
            'hr_hc': 14.32
        },
    'right_shoulder':
        {
            'T': 25.865,
            'power_fraction': 0,
            'hr_hc': 8.35
        },
    'right_upper_arm':
        {
            'T': 26.225,
            'power_fraction': 0,
            'hr_hc': 7.815
        },
    'right_upper_leg':
        {
            'T': 26.195,
            'power_fraction': 0,
            'hr_hc': 4.06
        },
    'thorax':
        {
            'T': 26.645,
            'power_fraction': 0,
            'hr_hc': 7.985
        },
}


class BodyPart(OpenFOAMBaseBoundaryFields, OpenFOAMBaseElement):
    def __init__(self, person, key, shape, bbox_min_max=None):
        super().__init__()
        self.radiation_model = person.radiation_model
        self.key = key
        self.solid_name = person.solid_name + '_' + key
        self.stl_name = self.solid_name + '.stl'
        self.bbox_min_max = bbox_min_max
        self.stl_file_path_name = (person.triSurface_path.as_posix() + '/' +
                                   self.stl_name)
        self.patch_info_type = person.patch_info_type
        self.refinement_level = person.refinement_level
        self.tri_geom = PyOCCTools.triangulate_bound_shape(shape)
        self.point_in_shape = PyOCCTools.get_center_of_volume(self.tri_geom)
        if not bbox_min_max:
            self.bbox_min_max = PyOCCTools.simple_bounding_box(shape)
        self.power = body_part_boundary_conditions[key]['power_fraction'] * person.power
        self.temperature = body_part_boundary_conditions[key]['T']
        self.area = PyOCCTools.get_shape_area(self.tri_geom)
        self.scaled_surface = PyOCCTools.scale_shape_absolute(self.tri_geom,
                                                              person.scale_surface_factor)
        self.heat_flux = body_part_boundary_conditions[key][
                             'hr_hc']*(self.temperature-21)
        # todo: remove hardcoded 21 degC and replace with actual
        #  indoor air temperature

    def set_boundary_conditions(self):
        if self.radiation_model == 'none':
            qr = 'none'
        else:
            qr = 'qr'
        if self.power == 0:
            # self.T = \
            #     {'type': 'externalWallHeatFluxTemperature',
            #      'mode': 'flux',
            #      'qr': f"{qr}",
            #      'q': f'{self.heat_flux}',
            #      'qrRelaxation': 0.003,
            #      'relaxation': 1.0,
            #      'kappaMethod': 'fluidThermo',
            #      'kappa': 'fluidThermo',
            #      'value': f'uniform {self.temperature + 273.15}'
            #      }
            self.T = {'type': 'fixedValue',
                      'value': f'uniform {self.temperature + 273.15}'
                      }
        else:
            self.T = \
                {'type': 'externalWallHeatFluxTemperature',
                 'mode': 'power',
                 'qr': f"{qr}",
                 'Q': f'{self.power}',
                 'qrRelaxation': 0.003,
                 'relaxation': 1.0,
                 'kappaMethod': 'fluidThermo',
                 'kappa': 'fluidThermo',
                 'value': f'uniform {self.temperature + 273.15}'
                 }


class People(OpenFOAMBaseBoundaryFields, OpenFOAMBaseElement):
    def __init__(self, shape, trsf, person_path, triSurface_path,
                 people_type, radiation_model, scale,
                 bbox_min_max=None, solid_name='person', power=120, temperature=32,
                 increase_small_refinement=0.10,
                 increase_large_refinement=0.20):

        super().__init__()
        self.radiation_model = radiation_model
        self.bbox_min_max = bbox_min_max
        self.solid_name = solid_name + '_' + people_type
        self.stl_name = self.solid_name + '.stl'
        self.triSurface_path = triSurface_path
        self.stl_file_path_name = (triSurface_path.as_posix() + '/' +
                                   self.stl_name)
        self.patch_info_type = 'wall'
        self.refinement_level = [3, 7]
        self.tri_geom = PyOCCTools.triangulate_bound_shape(shape)
        self.point_in_shape = PyOCCTools.get_center_of_volume(self.tri_geom)
        self.power = power
        self.temperature = temperature
        self.scale_surface_factor = scale
        if not bbox_min_max:
            self.bbox_min_max = PyOCCTools.simple_bounding_box(shape)
        body_shapes_dict = self.split_body_part_shapes(person_path, shape,
                                                       triSurface_path, trsf)
        self.body_parts_dict = {key: BodyPart(self, key, value)
                                for key, value in body_shapes_dict.items()}
        self.area = PyOCCTools.get_shape_area(self.tri_geom)
        self.scaled_surface = PyOCCTools.create_offset_shape(self.tri_geom,
                                                             0.03)

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

    @staticmethod
    def split_body_part_shapes(person_path, full_shape, triSurface_path, trsf):
        person_meshes = []
        for m in mesh.Mesh.from_multi_file(person_path):
            person_meshes.append(m)
        if len(person_meshes) > 1:
            temp_path = triSurface_path / 'Temp/person'
            temp_path.mkdir(exist_ok=True)
            for m in person_meshes:
                curr_name = temp_path.as_posix() + '/' + str(m.name,
                                                             encoding='utf-8') + '.stl'
                with open(curr_name, 'wb+') as output_file:
                    m.save(str(m.name, encoding='utf-8'), output_file,
                           mode=stl.Mode.ASCII)
                output_file.close()
            part_dict = {}
            for part_stl in temp_path.glob('*'):
                part_name = part_stl.name.split('.')[0]
                part_shape = TopoDS_Shape()
                stl_reader = StlAPI_Reader()
                stl_reader.Read(part_shape, str(part_stl))
                part_shape = BRepBuilderAPI_Transform(part_shape, trsf).Shape()
                part_dict.update({part_name: part_shape})
            return part_dict
        elif len(person_meshes) == 1:
            # keep original shape
            return {'FullBody': full_shape}
        if len(person_meshes) == 0:
            raise Exception('No meshes found')

    def set_boundary_conditions(self):
        # for body_part in self.body_parts_dict.values():
        #     body_part.set_boundary_conditions()
        if self.radiation_model == 'none':
            qr = 'none'
        else:
            qr = 'qr'
        self.T = \
            {'type': 'externalWallHeatFluxTemperature',
             'mode': 'power',
             'qr': f"{qr}",
             'Q': f'{self.power}',
             'qrRelaxation': 0.003,
             'relaxation': 1.0,
             'kappaMethod': 'fluidThermo',
             'kappa': 'fluidThermo',
             'value': f'uniform {self.temperature + 273.15}'
             }

