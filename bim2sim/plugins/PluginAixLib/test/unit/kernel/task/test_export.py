import unittest

from bim2sim.plugins.PluginAixLib.bim2sim_aixlib import LoadLibrariesAixLib
from bim2sim.elements.mapping.units import ureg
from test.unit.tasks.hvac.test_export import TestStandardLibraryExports


class TestAixLibExport(TestStandardLibraryExports):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        lib_aixlib = LoadLibrariesAixLib(cls.playground)
        cls.loaded_libs = lib_aixlib.run()[0]

    @unittest.skip
    def test_boiler_export(self):
        raise NotImplementedError

    def test_radiator_export(self):
        graph = self.helper.get_simple_radiator()
        answers = ()
        reads = (self.loaded_libs, graph)
        modelica_model = self.run_task(answers, reads)
        parameters = [('rated_power', 'Q_flow_nominal'),
                      ('flow_temperature', 'T_a_nominal'),
                      ('return_temperature', 'T_b_nominal')]
        expected_units = [ureg.watt, ureg.celsius, ureg.celsius]
        self.run_parameter_test(graph, modelica_model, parameters,
                                expected_units)

    def test_pump_export(self):
        graph, _ = self.helper.get_simple_pump()
        answers = ()
        reads = (self.loaded_libs, graph)
        modelica_model = self.run_task(answers, reads)
        element = graph.elements[0]
        V_flow = element.rated_volume_flow.to(ureg.m ** 3 / ureg.s).magnitude
        dp = element.rated_pressure_difference.to(ureg.pascal).magnitude
        expected_string = (f"per(pressure("
                           f"V_flow={{{0 * V_flow},{1 * V_flow},{2 * V_flow}}},"
                           f"dp={{{2 * dp},{1 * dp},{0 * dp}}}"
                           f"))")
        self.assertIn(expected_string, modelica_model[0].code())

    def test_consumer_export(self):
        graph, _ = self.helper.get_simple_consumer()
        answers = ()
        reads = (self.loaded_libs, graph)
        modelica_model = self.run_task(answers, reads)
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
        reads = (self.loaded_libs, graph)
        modelica_model = self.run_task(answers, reads)
        parameters = [('nominal_pressure_difference', 'dpValve_nominal'),
                      ('nominal_mass_flow_rate', 'm_flow_nominal')]
        expected_units = [ureg.pascal, ureg.kg / ureg.s]
        self.run_parameter_test(graph, modelica_model, parameters,
                                expected_units)

    def test_heat_pump_export(self):
        graph = self.helper.get_simple_heat_pump()
        answers = ()
        reads = (self.loaded_libs, graph)
        modelica_model = self.run_task(answers, reads)
        parameters = [('rated_power', 'Q_useNominal')]
        expected_units = [ureg.watt]
        self.run_parameter_test(graph, modelica_model, parameters,
                                expected_units)

    def test_chiller_export(self):
        graph = self.helper.get_simple_chiller()
        answers = ()
        reads = (self.loaded_libs, graph)
        modelica_model = self.run_task(answers, reads)
        parameters = [('rated_power', 'Q_useNominal')]
        expected_units = [ureg.watt]
        self.run_parameter_test(graph, modelica_model, parameters,
                                expected_units)

    @unittest.skip
    def test_consumer_CHP_export(self):
        raise NotImplementedError

    def test_storage_export(self):
        graph = self.helper.get_simple_storage()
        answers = ()
        reads = (self.loaded_libs, graph)
        modelica_model = self.run_task(answers, reads)
        parameters = [('height', 'hTank'), ('diameter', 'dTank')]
        expected_units = [ureg.meter, ureg.meter]
        element = graph.elements[0]
        expected_values = [
            element.attributes[param[0]][0].to(expected_units[index]).magnitude
            for index, param in enumerate(parameters)]
        param_value_pairs = [f"{param[1]}={value}" for param, value in
                             zip(parameters, expected_values)]
        expected_string = f"data({','.join(param_value_pairs)})"
        self.assertIn(expected_string, modelica_model[0].code())
