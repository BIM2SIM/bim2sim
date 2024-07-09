import tempfile
import unittest
from pathlib import Path

from bim2sim import ConsoleDecisionHandler, run_project
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

    @unittest.skip
    def test_boiler_export(self):
        raise NotImplementedError

    def test_simple_radiator_export(self):
        graph = self.helper.get_simple_radiator()
        answers = (1, 1, 10)
        handler = ConsoleDecisionHandler()
        modelica_model = ConsoleDecisionHandler().handle(
            self.export_task.run(self.loaded_libs, graph))
        # modelica_model = DebugDecisionHandler(answers).handle(
        #     self.export_task.run(self.loaded_libs, graph))
        parameters = [('rated_power', 'Q_flow_nominal'),
                      ('flow_temperature', 'T_a_nominal'),
                      ('return_temperature', 'T_b_nominal')]
        expected_units = [ureg.watt, ureg.celsius, ureg.celsius]
        self.run_parameter_test(graph, modelica_model, parameters,
                                expected_units)

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
            "per": modelica_model[0].elements[0].modelica_records['per'],
        }
        self.assertDictEqual(
            pump_modelica_params_expected, pump_modelica_params)

    def test_consumer_export(self):
        graph = self.helper.get_simple_consumer()
        answers = ()
        modelica_model = ConsoleDecisionHandler().handle(
            self.export_task.run(self.loaded_libs, graph))
        # modelica_model = DebugDecisionHandler(answers).handle(
        #     self.export_task.run(self.loaded_libs, graph))
        parameters = [('rated_power', 'Q_flow_fixed')]
        expected_units = [ureg.watt]
        self.run_parameter_test(graph, modelica_model, parameters,
                                expected_units)

    @unittest.skip
    def test_consumer_heating_distributor_module_export(self):
        raise NotImplementedError

    @unittest.skip
    def test_consumer_boiler_aggregation_export(self):
        raise NotImplementedError

    @unittest.skip
    def test_consumer_distributor_export(self):
        raise NotImplementedError

    def test_three_way_valve_export(self):
        graph = self.helper.get_simple_three_way_valve()
        answers = (1 * ureg.kg / ureg.s,)
        modelica_model = DebugDecisionHandler(answers).handle(
            self.export_task.run(self.loaded_libs, graph))
        parameters = [('nominal_pressure_difference', 'dpValve_nominal'),
                      ('nominal_mass_flow_rate', 'm_flow_nominal')]
        expected_units = [ureg.pascal, ureg.kg / ureg.s]
        self.run_parameter_test(graph, modelica_model, parameters,
                                expected_units)

    @unittest.skip
    def test_heat_pump_export(self):
        graph = self.helper.get_simple_heat_pump()
        answers = ()
        modelica_model = DebugDecisionHandler(answers).handle(
            self.export_task.run(self.loaded_libs, graph))
        parameters = [('rated_power', 'Q_useNominal')]
        expected_units = [ureg.watt]
        self.run_parameter_test(graph, modelica_model, parameters,
                                expected_units)
        # TODO: test fails due to wrong units, see #542

    @unittest.skip
    def test_chiller_export(self):
        graph = self.helper.get_simple_chiller()
        answers = ()
        modelica_model = DebugDecisionHandler(answers).handle(
            self.export_task.run(self.loaded_libs, graph))
        parameters = [('rated_power', 'Q_useNominal')]
        expected_units = [ureg.watt]
        # TODO: test fails due to wrong units, see #542
        self.run_parameter_test(graph, modelica_model, parameters,
                                expected_units)

    @unittest.skip
    def test_consumer_CHP_export(self):
        raise NotImplementedError

    def test_storage_export(self):
        graph = self.helper.get_simple_storage()
        answers = ()
        modelica_model = DebugDecisionHandler(answers).handle(
            self.export_task.run(self.loaded_libs, graph))
        parameters = [('height', 'hTank'), ('diameter', 'dTank')]
        expected_units = [ureg.meter, ureg.meter]
        # TODO: find generalized way to check record parameters
        element = graph.elements[0]
        expected_values = [
            element.attributes[param[0]][0].to(expected_units[index]).magnitude
            for index, param in enumerate(parameters)]
        param_value_pairs = [f"{param[1]}={value}" for param, value in
                             zip(parameters, expected_values)]
        expected_string = f"data({','.join(param_value_pairs)})"
        self.assertIn(expected_string, modelica_model[0].code())
