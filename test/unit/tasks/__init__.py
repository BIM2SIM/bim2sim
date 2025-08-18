import inspect
import tempfile
import unittest
from typing import Union
from unittest import mock

from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.sim_settings import BaseSimSettings
from bim2sim.tasks.base import ITask
from test.unit.elements.helper import SetupHelper


class TestTask(unittest.TestCase):
    """Base class for all task-related tests.

    Provides common setup and teardown functionality including:
    - Mock playground, project, and paths
    - Temporary export directory
    - Settings management
    - Helper reset

    To use this, please overwrite the abstract class methods
    simSettingsClass(), testTask() and helper() in your own test class.
    """

    @classmethod
    def setUpClass(cls) -> None:
        """Set up infrastructure that remains constant for all test methods."""
        if cls is TestTask:
            raise unittest.SkipTest("Skip TestTask tests, it's a base class")

        # Set up playground, project and paths via mocks
        cls.playground = mock.Mock()
        project = mock.Mock()
        paths = mock.Mock()
        cls.playground.project = project
        cls.playground.sim_settings = cls.simSettingsClass()

        cls.test_task = cls.testTask()
        cls.test_task.paths = paths
        cls.export_path = tempfile.TemporaryDirectory(prefix='bim2sim')
        cls.test_task.paths.export = cls.export_path.name

        # Setup helper
        cls.helper = cls.helper()

    def setUp(self) -> None:
        """Set up infrastructure that needs to be fresh for each test."""
        # Set up temporary export directory
        self.test_task.prj_name = f'TestTask{self.__class__.__name__}'

    def tearDown(self) -> None:
        """Clean up after each test method."""
        self.helper.reset()
        self.playground.sim_settings.load_default_settings()

    def run_task(self, answers, reads):
        if inspect.isgeneratorfunction(self.test_task.run):
            return DebugDecisionHandler(answers).handle(self.test_task.run(*reads))
        else:
            return self.test_task.run(*reads)

    @classmethod
    def simSettingsClass(cls) -> Union[BaseSimSettings, None]:
        return None

    @classmethod
    def testTask(cls) -> Union[ITask, None]:
        return None

    @classmethod
    def helper(cls) -> Union[SetupHelper, None]:
        return None
