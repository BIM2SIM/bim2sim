import tempfile
from pathlib import Path
from bim2sim.project import Project
from bim2sim.workflow import Workflow

sample_root = Path(__file__).parent.parent.parent / 'test/TestModels'


class IntegrationBase:
    """Base class mixin for Integration tests"""

    def setUp(self) -> None:
        self.project = None

    def tearDown(self):
        if self.project:
            self.project.delete()
            self.assertFalse(self.project.paths.root.exists())
            self.project = None

    def create_project(self, ifc: str, plugin: str, workflow: Workflow = None):
        """create project in temporary directory which is cleaned automatically after test.

        :param plugin: Project plugin e.g. 'hkesim', 'aixlib', ...
        :param ifc: name of ifc file located in dir TestModels"""
        self.project = Project.create(
            tempfile.TemporaryDirectory(prefix='bim2sim_').name,
            ifc_path=sample_root / ifc,
            plugin=plugin, workflow=workflow)
        return self.project

    # def run_project(self, ifc_file: str, backend: str):
    #     """Create example project and copy ifc if necessary
    #     :param backend: Project backend e.g. 'hkesim', 'aixlib', ...
    #     :param ifc_file: name of ifc file located in dir TestModels
    #     :return: return code of main()
    #     """
    #
    #     project_path = Path(self.temp_dir.name)
    #     path_ifc = Path(__file__).parent.parent / 'TestModels' / ifc_file
    #
    #     if not bim2sim.PROJECT.is_project_folder(project_path):
    #         bim2sim.PROJECT.create(project_path, path_ifc, target=backend)
    #     return_code = bim2sim.main(project_path)
    #     return return_code
