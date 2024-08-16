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
    'FullBody':
        {
            'T': 32,
            'power_fraction': 1
        },
    'Head':
        {
            'T': 36,
            'power_fraction': 0.3
        },
    'Body':
        {
            'T': 30,
            'power_fraction': 0.7
        }
    # todo: further extend dictionary for all bodyparts
}


class BodyPart(OpenFOAMBaseBoundaryFields, OpenFOAMBaseElement):
    def __init__(self, person, key, shape, bbox_min_max=None):
        super().__init__()
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

    def set_boundary_conditions(self):
        self.T = \
            {'type': 'externalWallHeatFluxTemperature',
             'mode': 'power',
             'qr': 'qr',
             'Q': f'{self.power}',
             'qrRelaxation': 0.003,
             'relaxation': 1.0,
             'kappaMethod': 'fluidThermo',
             'kappa': 'fluidThermo',
             'value': f'uniform {self.temperature + 273.15}'
             }


class People(OpenFOAMBaseBoundaryFields, OpenFOAMBaseElement):
    def __init__(self, shape, trsf, person_path, triSurface_path, people_type,
                 bbox_min_max=None, solid_name='person', power=120, temperature=32,
                 increase_small_refinement=0.10,
                 increase_large_refinement=0.20):

        super().__init__()

        self.bbox_min_max = bbox_min_max
        self.solid_name = solid_name + '_' + people_type
        self.stl_name = self.solid_name + '.stl'
        self.triSurface_path = triSurface_path
        self.stl_file_path_name = (triSurface_path.as_posix() + '/' +
                                   self.stl_name)
        self.patch_info_type = 'wall'
        self.refinement_level = [3, 5]
        self.tri_geom = PyOCCTools.triangulate_bound_shape(shape)
        self.point_in_shape = PyOCCTools.get_center_of_volume(self.tri_geom)
        self.power = power
        self.temperature = temperature
        if not bbox_min_max:
            self.bbox_min_max = PyOCCTools.simple_bounding_box(shape)
        body_shapes_dict = self.split_body_part_shapes(person_path, shape,
                                                       triSurface_path, trsf)
        self.body_parts_dict = {key: BodyPart(self, key, value)
                                for key, value in body_shapes_dict.items()}

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
            temp_path = triSurface_path / 'Temp'
            temp_path.mkdir(exist_ok=True)
            for m in person_meshes:
                curr_name = temp_path.as_posix() + '/' + str(m.name,
                                                             encoding='utf-8') + '.stl'
                with open(curr_name, 'wb+') as output_file:
                    m.save(str(m.name, encoding='utf-8'), output_file,
                           mode=stl.Mode.ASCII)
                output_file.close()
            person_head = TopoDS_Shape()
            stl_reader = StlAPI_Reader()
            stl_reader.Read(person_head,
                            temp_path.as_posix() + '/' +
                            "manikinsittinghead.stl")
            person_body = TopoDS_Shape()
            stl_reader = StlAPI_Reader()
            stl_reader.Read(person_body,
                            temp_path.as_posix() + '/' +
                            "manikinsittingbody.stl")
            person_head = BRepBuilderAPI_Transform(person_head, trsf).Shape()
            person_body = BRepBuilderAPI_Transform(person_body, trsf).Shape()
            return {'Head': person_head, 'Body': person_body}
        elif len(person_meshes) == 1:
            # keep original shape
            return {'FullBody': full_shape}
        if len(person_meshes) == 0:
            raise Exception('No meshes found')

    def set_boundary_conditions(self):
        # for body_part in self.body_parts_dict.values():
        #     body_part.set_boundary_conditions()
        self.T = \
            {'type': 'externalWallHeatFluxTemperature',
             'mode': 'power',
             'qr': 'qr',
             'Q': f'{self.power}',
             'qrRelaxation': 0.003,
             'relaxation': 1.0,
             'kappaMethod': 'fluidThermo',
             'kappa': 'fluidThermo',
             'value': f'uniform {self.temperature + 273.15}'
             }

