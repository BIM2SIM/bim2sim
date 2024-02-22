import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bim2sim.elements.graphs.hvac_graph import HvacGraph
from bim2sim.kernel.decision.console import ConsoleDecisionHandler
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler

from test.unit.elements.aggregation.test_parallelpumps import \
    ParallelPumpHelper
from test.unit.elements.aggregation.test_pipestrand import StrandHelper
from bim2sim.tasks.hvac import Export
from bim2sim.plugins.PluginAixLib.bim2sim_aixlib import LoadLibrariesAixLib
from test.unit.elements.helper import SetupHelperHVAC
from bim2sim.elements import hvac_elements as hvac
from bim2sim.elements.mapping.units import ureg


class SetupHelperAixLibComponents(SetupHelperHVAC):

    def get_pipe(self):
        pipe = self.element_generator(
            hvac.Pipe,
            diameter=0.02 * ureg.m,
            length=1 * ureg.m
        )
        return HvacGraph([pipe])

    def get_pump(self):
        pump = self.element_generator(
            hvac.Pump,
            rated_volume_flow=1 * ureg.m ** 3 / ureg.s,
            rated_pressure_difference=10000 * ureg.N / (ureg.m ** 2))
        return HvacGraph([pump])

    def get_Boiler(self):
        self.element_generator(hvac.Boiler, ...)


class TestAixLibExport(unittest.TestCase):
    export_task = None
    loaded_libs = None
    helper = None
    export_path = None

    @classmethod
    def setUpClass(cls) -> None:
        # Set up playground, project and paths via mocks
        playground = mock.Mock()
        project = mock.Mock()
        paths = mock.Mock()
        playground.project = project

        # Load libraries as these are required for export
        lib_aixlib = LoadLibrariesAixLib(playground)
        cls.loaded_libs = lib_aixlib.run()[0]

        # Instantiate export task and set required values via mocks
        cls.export_task = Export(playground)
        cls.export_task.prj_name = 'TestAixLibExport'
        cls.export_task.paths = paths

        cls.helper = SetupHelperAixLibComponents()

    def setUp(self) -> None:
        # Set export path to temporary path
        self.export_path = tempfile.TemporaryDirectory(prefix='bim2sim')
        self.export_task.paths.export = self.export_path.name

    def tearDown(self) -> None:
        self.helper.reset()

    # TODO move to modelica base export (not AixLib) and remove
    #  based_on_diameter stuff
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

    def test_pump_export(self):
        graph = self.helper.get_pump()
        answers = ()

        modelica_model = DebugDecisionHandler(answers).handle(
            self.export_task.run(self.loaded_libs, graph))
        v_flow_expected = [
            0 * graph.elements[0].rated_volume_flow,
            graph.elements[0].rated_volume_flow,
            2 * graph.elements[0].rated_volume_flow
        ]
        dp_expected = [
            2 * graph.elements[0].rated_pressure_difference,
            graph.elements[0].rated_pressure_difference,
            0 * graph.elements[0].rated_pressure_difference
        ]
        pump_export_params_expected = {
            "per": {
                "pressure":
                    {
                        "V_flow": v_flow_expected,
                        "dp": dp_expected
                    }
            }
        }
        pump_export_params = {
            "per": modelica_model[0].elements[0].export_records["per"]
        }
        # TODO when export_unit problem is fixed for records, this can be
        #  simplified regarding the unit handling
        pump_modelica_params_expected = {
            "per": f'pressure(V_flow='
                   f'{[v_flow_i.to(ureg.m ** 3 / ureg.s).m for v_flow_i in v_flow_expected]},'
                   f'dp={[dp_i.m for dp_i in dp_expected]})'
            .replace(
                "[", "{").replace(
                "]", "}").replace(
                " ", "")
        }
        pump_modelica_params = {
            "per": modelica_model[0].elements[0].modelica_export_dict[
                'per'],
        }

        self.assertDictEqual(
            pump_export_params_expected, pump_export_params)
        self.assertDictEqual(
            pump_modelica_params_expected, pump_modelica_params)
