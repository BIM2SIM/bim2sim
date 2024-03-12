import tempfile
import unittest
from unittest import mock

from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler

from bim2sim.tasks.hvac import Export, LoadLibrariesStandardLibrary
from test.unit.elements.helper import SetupHelperHVAC
from bim2sim.elements.mapping.units import ureg


class TestStandardLibraryExports(unittest.TestCase):
    export_task = None
    loaded_libs = None
    helper = None
    export_path = None
    playground = None

    @classmethod
    def setUpClass(cls) -> None:
        # Set up playground, project and paths via mocks
        cls.playground = mock.Mock()
        project = mock.Mock()
        paths = mock.Mock()
        cls.playground.project = project

        # Load libraries as these are required for export
        lib_msl = LoadLibrariesStandardLibrary(cls.playground)
        cls.loaded_libs = lib_msl.run()[0]

        # Instantiate export task and set required values via mocks
        cls.export_task = Export(cls.playground)
        cls.export_task.prj_name = 'TestStandardLibrary'
        cls.export_task.paths = paths

        cls.helper = SetupHelperHVAC()

    def setUp(self) -> None:
        # Set export path to temporary path
        self.export_path = tempfile.TemporaryDirectory(prefix='bim2sim')
        self.export_task.paths.export = self.export_path.name

    def tearDown(self) -> None:
        self.helper.reset()

    def test_pipe_export(self):
        graph = self.helper.get_pipe()
        answers = (1,)

        modelica_model = DebugDecisionHandler(answers).handle(
            self.export_task.run(self.loaded_libs, graph))
        pipe_export_params_expected = {
            'diameter': graph.elements[0].diameter,
            'length': graph.elements[0].length
        }
        pipe_export_params = {
            'diameter': modelica_model[0].elements[0].export_params[
                'diameter'],
            'length': modelica_model[0].elements[0].export_params['length']
        }
        pipe_modelica_params_expected = {
            "diameter": str(graph.elements[0].diameter.to(ureg.m).m),
            "length": str(graph.elements[0].length.to(ureg.m).m)
        }
        pipe_modelica_params = {
            'diameter': modelica_model[0].elements[0].modelica_export_dict[
                'diameter'],
            'length': modelica_model[0].elements[0].modelica_export_dict[
                'length']
        }

        self.assertDictEqual(
            pipe_export_params_expected, pipe_export_params)
        self.assertDictEqual(
            pipe_modelica_params_expected, pipe_modelica_params)

    # TODO #624 Write tests for all components of MSL
