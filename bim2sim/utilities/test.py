import os
import tempfile
from pathlib import Path
from typing import Union

from bim2sim.project import Project


class IntegrationBase:
    """Base class mixin for Integration tests"""

    def setUp(self) -> None:
        self.project = None
        self.is_ci = any(var in os.environ for var in (
            'GITLAB_CI', 'TRAVIS', 'CIRCLECI', 'GITHUB_ACTIONS'
        ))
        print(f"Current Infrastructure is CI: {self.is_ci}")

    def tearDown(self):
        if self.project:
            self.project.delete()
            self.assertFalse(self.project.paths.root.exists())
            self.project = None

    def create_project(
            self, ifc_names: dict,
            plugin: str) -> Project:
        """create project in temporary directory which is cleaned automatically
         after test.

        Args:
            ifc_names: dict with key: IFCDomain and value: name of ifc located
             in directory test/resources/hydraulic/ifc
            plugin: e.g. 'hkesim', 'aixlib', ...

        Returns:
            project: bim2sim project
        """
        # create paths to IFCs based on ifc_names dict
        ifc_paths = {}
        for domain, ifc_name in ifc_names.items():
            ifc_paths[domain] = \
                self.test_resources_path() / self.model_domain_path() / \
                "ifc" / ifc_name

        self.project = Project.create(
            tempfile.TemporaryDirectory(prefix='bim2sim_').name,
            ifc_paths=ifc_paths,
            plugin=plugin)
        # set weather file data
        self.set_test_weather_file()
        return self.project

    @staticmethod
    def test_resources_path() -> Path:
        return Path(__file__).parent.parent.parent / 'test/resources'

    def model_domain_path(self) -> Union[str, None]:
        return None

    def set_test_weather_file(self):
        """Set the weather file path."""
        raise NotImplementedError("")


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
        return 'arch'
