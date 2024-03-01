import stl
from stl import mesh

from bim2sim.tasks.base import ITask
from bim2sim.utilities.pyocc_tools import PyOCCTools
from butterfly.butterfly import blockMeshDict, snappyHexMeshDict


class CreateOpenFOAMMeshing(ITask):
    """This ITask initializes the OpenFOAM Meshing.
    """

    reads = ('openfoam_case', 'openfoam_elements')
    touches = ('openfoam_case', 'openfoam_elements')

    def __init__(self, playground):
        super().__init__(playground)

    def run(self, openfoam_case, openfoam_elements):
        # create blockMesh based on surface geometry
        self.create_blockMesh(openfoam_case, openfoam_elements)
        # create snappyHexMesh based on surface types
        self.create_snappyHexMesh(openfoam_case, openfoam_elements)

        return openfoam_case, openfoam_elements

    @staticmethod
    def create_blockMesh(openfoam_case, openfoam_elements, resize_factor=0.1,
                         mesh_size=0.08,
                         shape=None):
        if not shape:
            shape = openfoam_case.current_zone.space_shape
        (min_pt, max_pt) = PyOCCTools.simple_bounding_box(shape)
        scaled_min_pt = []
        scaled_max_pt = []
        len_xyz = []
        for p1, p2 in zip(min_pt, max_pt):
            p1 -= resize_factor
            p2 += resize_factor
            len_xyz.append(p2 - p1)
            scaled_min_pt.append(p1)
            scaled_max_pt.append(p2)

        # calculate number of cells per xyz direction
        n_div_xyz = (round(len_xyz[0] / mesh_size),
                     round(len_xyz[1] / mesh_size),
                     round(len_xyz[2] / mesh_size))
        openfoam_case.blockMeshDict = blockMeshDict.BlockMeshDict.from_min_max(
            scaled_min_pt, scaled_max_pt, n_div_xyz=n_div_xyz)
        openfoam_case.blockMeshDict.save(openfoam_case.openfoam_dir)

    def create_snappyHexMesh(self, openfoam_case, openfoam_elements, ):
        stl_name = "space_" + openfoam_case.current_zone.guid
        region_names = []
        regions = {}
        mesh_objects = mesh.Mesh.from_multi_file(
            openfoam_case.openfoam_triSurface_dir /
            str(stl_name + '.stl'),
            mode=stl.Mode.ASCII)
        for obj in mesh_objects:
            region_names.append(str(obj.name, encoding='utf-8'))
        for name in region_names:
            regions.update({name: {'name': name}})
        openfoam_case.snappyHexMeshDict = snappyHexMeshDict.SnappyHexMeshDict()
        openfoam_case.snappyHexMeshDict.add_stl_geometry(
            str("space_" + openfoam_case.current_zone.guid), regions)

        # self.snappyHexMesh.values['geometry']['regions'].update(regions)
        location_in_mesh = (
            str('(' +
                str(
                    openfoam_case.current_zone.space_center.Coord()[
                        0]) + ' ' +
                str(
                    openfoam_case.current_zone.space_center.Coord()[
                        1]) + ' ' +
                str(
                    openfoam_case.current_zone.space_center.Coord()[
                        2]) + ')'
                ))
        openfoam_case.snappyHexMeshDict.values['castellatedMeshControls'][
            'locationInMesh'] = location_in_mesh
        self.set_refinementSurfaces(openfoam_case, openfoam_elements,
                                    region_names)
        openfoam_case.snappyHexMeshDict.values['castellatedMeshControls'][
            'refinementSurfaces'].update(openfoam_case.refinementSurfaces)

        openfoam_case.snappyHexMeshDict.save(openfoam_case.openfoam_dir)

    @staticmethod
    def set_refinementSurfaces(openfoam_case, openfoam_elements,
                               region_names,
                               default_refinement_level=[1, 2]):
        stl_name = "space_" + openfoam_case.current_zone.guid

        refinementSurface_regions = {}

        for obj in openfoam_elements:
            refinementSurface_regions.update(
                {obj.solid_name:
                    {
                        'level': '({} {})'.format(
                            int(obj.refinement_level[0]),
                            int(obj.refinement_level[1])),
                        'patchInfo':
                            {'type': obj.patch_info_type}}})

        openfoam_case.refinementSurfaces = {stl_name:
            {
                'level': '({} {})'.format(
                    int(default_refinement_level[0]),
                    int(default_refinement_level[
                            1])),
                'regions': refinementSurface_regions
            }}
