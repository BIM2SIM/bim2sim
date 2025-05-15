import tempfile
import unittest

from bim2sim.elements.aggregation.hvac_aggregations import \
    ConsumerHeatingDistributorModule
from bim2sim.elements.mapping.units import ureg
from bim2sim.plugins.PluginHKESim.bim2sim_hkesim import LoadLibrariesHKESim
from test.unit.tasks.hvac.test_export import TestStandardLibraryExports


class TestHKESimExport(TestStandardLibraryExports):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # Load libraries as these are required for export
        lib_hkesim = LoadLibrariesHKESim(cls.playground)
        cls.loaded_libs = lib_hkesim.run()[0]

    def test_boiler_export(self):
        graph = self.helper.get_simple_boiler()
        answers = ()
        reads = (self.loaded_libs, graph)
        modelica_model = self.run_task(answers, reads)
        parameters = [('rated_power', 'Q_nom'),
                      ('return_temperature', 'T_set')]
        expected_units = [ureg.watt, ureg.kelvin]
        self.run_parameter_test(graph, modelica_model, parameters,
                                expected_units)

    def test_radiator_export(self):
        graph = self.helper.get_simple_radiator()
        answers = ()
        reads = (self.loaded_libs, graph)
        modelica_model = self.run_task(answers, reads)
        parameters = [('rated_power', 'Q_flow_nominal'),
                      ('return_temperature', 'Tout_max')]
        expected_units = [ureg.watt, ureg.kelvin]
        self.run_parameter_test(graph, modelica_model, parameters,
                                expected_units)

    def test_pump_export(self):
        graph, _ = self.helper.get_simple_pump()
        answers = ()
        reads = (self.loaded_libs, graph)
        modelica_model = self.run_task(answers, reads)
        parameters = [('rated_height', 'head_set'),
                      ('rated_volume_flow', 'Vflow_set'),
                      ('rated_power', 'P_nom')]
        expected_units = [ureg.meter, ureg.meter ** 3 / ureg.hour, ureg.watt]
        self.run_parameter_test(graph, modelica_model, parameters,
                                expected_units)

    @unittest.skip
    def test_three_way_valve_export(self):
        # TODO: there are no parameters to test for
        raise NotImplementedError

    def test_consumer_heating_distributor_module_export(self):
        # Set up the test graph and model
        graph = self.helper.get_simple_consumer_heating_distributor_module()
        answers = ()
        reads = (self.loaded_libs, graph)
        modelica_model = self.run_task(answers, reads)
        # Get the ConsumerHeatingDistributorModule element
        element = next(element for element in graph.elements
                       if isinstance(element,
                                     ConsumerHeatingDistributorModule))

        # Get parameter values from element
        flow_temp_0 = element.flow_temperature.magnitude
        return_temp_0 = element.return_temperature.magnitude
        flow_temp_1 = element.flow_temperature.magnitude
        return_temp_1 = element.return_temperature.magnitude
        consumers = iter(element.consumers)
        rated_power_0 = next(consumers).rated_power.to(ureg.watt).magnitude
        rated_power_1 = next(consumers).rated_power.to(ureg.watt).magnitude

        # Define the expected parameter strings in modelica model code
        expected_strings = [
            f"Tconsumer={{{flow_temp_0},{return_temp_0}}}",
            f"Tconsumer1={{{flow_temp_0},{return_temp_0}}}",
            f"Tconsumer2={{{flow_temp_1},{return_temp_1}}}",
            f"c1Qflow_nom={rated_power_0}",
            f"c2Qflow_nom={rated_power_1}",
            "useHydraulicSeparator=false",
            "c1TControl=false",
            "c2TControl=false",
            "c1OpenEnd=false",
            "c1OpenEnd=false",
            "isConsumer2=true"]

        # Assert that each expected string is in the modelica_model code
        for expected_string in expected_strings:
            self.assertIn(expected_string,
                          modelica_model[0].render_modelica_code())

    def test_boiler_module_export(self):
        graph = self.helper.get_simple_generator_one_fluid()
        answers = ()
        reads = (self.loaded_libs, graph)
        modelica_model = self.run_task(answers, reads)
        element = graph.elements[0]
        rated_power = element.rated_power.to(ureg.watt).magnitude
        flow_temp = element.flow_temperature.to(ureg.kelvin).magnitude
        return_temp = element.return_temperature.to(ureg.kelvin).magnitude
        expected_strings = [
            f"Theating={{{flow_temp},{return_temp}}}",
            f"Qflow_nom={rated_power}",
        ]
        for expected_string in expected_strings:
            self.assertIn(expected_string,
                          modelica_model[0].render_modelica_code())

    def test_heat_pump_export(self):
        graph = self.helper.get_simple_heat_pump()
        answers = ()
        reads = (self.loaded_libs, graph)
        modelica_model = self.run_task(answers, reads)
        parameters = [('rated_power', 'Qcon_nom')]
        expected_units = [ureg.watt]
        self.run_parameter_test(graph, modelica_model, parameters,
                                expected_units)

    def test_chiller_export(self):
        graph = self.helper.get_simple_chiller()
        answers = ()
        reads = (self.loaded_libs, graph)
        modelica_model = self.run_task(answers, reads)
        parameters = [('rated_power', 'Qev_nom'),
                      ('nominal_COP', 'EER_nom')]
        expected_units = [ureg.watt, ureg.dimensionless]
        self.run_parameter_test(graph, modelica_model, parameters,
                                expected_units)

    def test_chp_export(self):
        graph = self.helper.get_simple_chp()
        answers = ()
        reads = (self.loaded_libs, graph)
        modelica_model = self.run_task(answers, reads)
        parameters = [('rated_power', 'P_nom')]
        expected_units = [ureg.watt]
        self.run_parameter_test(graph, modelica_model, parameters,
                                expected_units)

    def test_cooling_tower_export(self):
        graph = self.helper.get_simple_cooling_tower()
        answers = ()
        reads = (self.loaded_libs, graph)
        modelica_model = self.run_task(answers, reads)
        parameters = [('rated_power', 'Qflow_nom')]
        expected_units = [ureg.watt]
        self.run_parameter_test(graph, modelica_model, parameters,
                                expected_units)
