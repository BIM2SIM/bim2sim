import tempfile
from pathlib import Path
from typing import Union

from bim2sim.project import Project
from bim2sim.workflow import Workflow


class IntegrationBase:
    """Base class mixin for Integration tests"""

    def setUp(self) -> None:
        self.project = None

    def tearDown(self):
        if self.project:
            self.project.delete()
            self.assertFalse(self.project.paths.root.exists())
            self.project = None

    def create_project(
            self, ifc: str, plugin: str, workflow: Workflow = None) -> Project:
        """create project in temporary directory which is cleaned automatically
         after test.

        Args:
            ifc: name of ifc file located in dir TestModels
            plugin: e.g. 'hkesim', 'aixlib', ...
            workflow: bim2sim workflow

        Returns:
            project: bim2sim project
        """
        self.project = Project.create(
            tempfile.TemporaryDirectory(prefix='bim2sim_').name,
            ifc_path=self.model_path_base() / self.model_domain_path() / ifc,
            plugin=plugin, workflow=workflow)
        return self.project

    @staticmethod
    def model_path_base() -> Path:
        return Path(__file__).parent.parent.parent / 'test/TestModels'

    def model_domain_path(self) -> Union[str, None]:
        return None


class RegressionTestBase(IntegrationBase):
    """Base class for regression tests."""
    def setUp(self):
        self.results_src_dir = None
        self.results_dst_dir = None
        self.tester = None
        super().setUp()

    def create_regression_setup(self, tolerance):
        raise NotImplementedError

    def run_regression_test(self):
        raise NotImplementedError
    
    def model_domain_path(self) -> str:
        return 'BPS'