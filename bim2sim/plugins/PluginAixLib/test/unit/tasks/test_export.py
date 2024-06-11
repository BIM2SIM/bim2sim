import tempfile

from bim2sim import ConsoleDecisionHandler
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler

from bim2sim.plugins.PluginAixLib.bim2sim_aixlib import LoadLibrariesAixLib
from bim2sim.elements.mapping.units import ureg
from test.unit.tasks.hvac.test_export import TestStandardLibraryExports
from test.unit.elements.aggregation.test_consumer import ConsumerHelper


class TestAixLibExport(TestStandardLibraryExports):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        lib_aixlib = LoadLibrariesAixLib(cls.playground)
        cls.loaded_libs = lib_aixlib.run()[0]
        cls.export_task.prj_name = 'TestAixLibExport'

    def setUp(self) -> None:
        # Set export path to temporary path
        self.export_path = tempfile.TemporaryDirectory(prefix='bim2sim')
        self.export_task.paths.export = self.export_path.name
        # TODO does this work?
        self.export_task.playground.sim_settings.outer_heat_ports = True

    def tearDown(self) -> None:
        self.helper.reset()


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

    # TODO #624 Write tests for all components of AixLib

    def test_radiator_export(self):
        graph = self.helper.get_radiator()
        answers = ()

        modelica_model = DebugDecisionHandler(answers).handle(
            self.export_task.run(self.loaded_libs, graph))
        print('test')

    def test_outer_heat_ports(self):
        answers = ()
        self.helper = ConsumerHelper()
        graph, flags = self.helper.get_setup_system2()

        modelica_model = ConsoleDecisionHandler().handle(
            self.export_task.run(self.loaded_libs, graph))
        print('test')