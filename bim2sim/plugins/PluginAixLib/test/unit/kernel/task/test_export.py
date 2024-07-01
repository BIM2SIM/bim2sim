import tempfile

from bim2sim.elements.graphs.hvac_graph import HvacGraph
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler

from bim2sim.plugins.PluginAixLib.bim2sim_aixlib import LoadLibrariesAixLib
from bim2sim.elements.mapping.units import ureg
from test.unit.elements.helper import SetupHelperHVAC
from test.unit.tasks.hvac.test_export import TestStandardLibraryExports
from bim2sim.elements import hvac_elements as hvac


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

    def tearDown(self) -> None:
        self.helper.reset()

    def test_pump_export(self):
        graph = self.helper.get_simple_pump()
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

    def test_simple_heat_pump_export(self):
        graph = self.helper.get_simple_heat_pump()
        answers = ()
        modelica_model = DebugDecisionHandler(answers).handle(
            self.export_task.run(self.loaded_libs, graph))
        # TODO: there is nothing to test here

    def test_simple_chiller_export(self):
        graph = self.helper.get_simple_chiller()
        answers = ()
        modelica_model = DebugDecisionHandler(answers).handle(
            self.export_task.run(self.loaded_libs, graph))
        element_parameters = {
            'rated_power': graph.elements[0].rated_power,
        }
        modelica_parameters = {
            'rated_power': modelica_model[0].elements[0].export_params[
                'Q_useNominal'],
        }
        self.assertDictEqual(element_parameters, modelica_parameters)

    def test_simple_consumer_export(self):
        graph = self.helper.get_simple_consumer()
        answers = ()
        modelica_model = DebugDecisionHandler(answers).handle(
            self.export_task.run(self.loaded_libs, graph))
        element_parameters = {
            'rated_power': graph.elements[0].rated_power,
        }
        modelica_parameters = {
            'rated_power': modelica_model[0].elements[0].export_params[
                'Q_flow_fixed'],
        }
        # TODO: the test is not very useful here. It does not fail, which is
        #  correct because element_parameters and modelica_parameters are equal
        #  but the modelica model has wrong unit
        self.assertDictEqual(element_parameters, modelica_parameters)
