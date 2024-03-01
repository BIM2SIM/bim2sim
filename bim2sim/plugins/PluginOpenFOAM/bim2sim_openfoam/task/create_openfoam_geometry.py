import shutil
import tempfile
from pathlib import Path

import stl
from OCC.Core.StlAPI import StlAPI_Writer
from stl import mesh

from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam.openfoam_elements.stlbound import \
    StlBound
from bim2sim.tasks.base import ITask


class CreateOpenFOAMGeometry(ITask):
    """This ITask initializes the OpenFOAM Geometry.
    """

    reads = ('openfoam_case', 'elements', 'idf')
    touches = ('openfoam_case', 'openfoam_elements')

    def __init__(self, playground):
        super().__init__(playground)

    def run(self, openfoam_case, elements, idf):
        openfoam_elements = dict
        self.init_zone(openfoam_case,
            elements, idf, openfoam_elements,
            space_guid=self.playground.sim_settings.select_space_guid)
        #todo: add geometry for heater and air terminals

        # setup geometry for constant
        self.create_triSurface(openfoam_case, openfoam_elements)

        return openfoam_case, openfoam_elements

    @staticmethod
    def init_zone(openfoam_case, elements, idf, openfoam_elements,
                  space_guid='2RSCzLOBz4FAK$_wE8VckM'):
        # guid '2RSCzLOBz4FAK$_wE8VckM' Single office has no 2B bounds
        # guid '3$f2p7VyLB7eox67SA_zKE' Traffic area has 2B bounds

        openfoam_case.current_zone = elements[space_guid]
        openfoam_case.current_bounds = openfoam_case.current_zone.space_boundaries
        if hasattr(openfoam_case.current_zone, 'space_boundaries_2B'):
            openfoam_case.current_bounds += openfoam_case.current_zone.space_boundaries_2B
        for bound in openfoam_case.current_bounds:
            new_stl_bound = StlBound(bound, idf)
            openfoam_elements[new_stl_bound.solid_name] = new_stl_bound
            # openfoam_case.stl_bounds.append(new_stl_bound)



    @staticmethod
    def create_triSurface(openfoam_case, openfoam_elements):
        temp_stl_path = Path(
            tempfile.TemporaryDirectory(
                prefix='bim2sim_temp_stl_files_').name)
        temp_stl_path.mkdir(exist_ok=True)
        with (open(openfoam_case.openfoam_triSurface_dir /
                   str("space_" + openfoam_case.current_zone.guid + ".stl"),
                   'wb+') as output_file):
            for stl_bound in openfoam_elements:
                stl_path_name = temp_stl_path.as_posix() + '/' + \
                                stl_bound.solid_name + '.stl'
                stl_writer = StlAPI_Writer()
                stl_writer.SetASCIIMode(True)
                stl_writer.Write(stl_bound.tri_geom, stl_path_name)
                sb_mesh = mesh.Mesh.from_file(stl_path_name)
                sb_mesh.save(stl_bound.solid_name, output_file,
                             mode=stl.Mode.ASCII)
        output_file.close()
        if temp_stl_path.exists() and temp_stl_path.is_dir():
            shutil.rmtree(temp_stl_path)
