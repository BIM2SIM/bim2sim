import tempfile
from pathlib import Path
from shutil import copytree, rmtree

from bim2sim.project import Project
from bim2sim.utilities.test import IntegrationBase
from bim2sim.simulation_type import SimType


class IntegrationBaseTeaserInteractive(IntegrationBase):

    def tearDown(self):

        temp_dir = Path(self.project.paths.export)
        debug_dir = Path.home() / "BIM2SIMDebugOutput"
        if debug_dir.is_dir():
            rmtree(debug_dir)
        copytree(temp_dir, debug_dir)
        super().tearDown()

    def create_project(self, ifc: Path, plugin: str, workflow: SimType = None):
        """create project in temporary directory which is cleaned automatically after test.

        :param plugin: Project plugin e.g. 'hkesim', 'aixlib', ...
        :param ifc: name of ifc file located in dir TestModels"""
        self.project = Project.create(tempfile.TemporaryDirectory(prefix='bim2sim_').name,
                                      ifc_path=ifc, plugin=plugin, workflow=workflow)
        return self.project
