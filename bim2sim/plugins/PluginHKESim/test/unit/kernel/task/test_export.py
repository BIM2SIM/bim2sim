import tempfile
import unittest

from bim2sim.elements.mapping.units import ureg
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.plugins.PluginHKESim.bim2sim_hkesim import LoadLibrariesHKESim
from test.unit.tasks.hvac.test_export import TestStandardLibraryExports


class TestHKESimExport(TestStandardLibraryExports):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        # Load libraries as these are required for export
        libraries = LoadLibrariesHKESim(cls.playground)
        cls.loaded_libs = libraries.run()[0]
        # Set project name
        cls.export_task.prj_name = 'TestHKESimExport'

    def setUp(self) -> None:
        # Set export path to temporary path
        self.export_path = tempfile.TemporaryDirectory(prefix='bim2sim')
        self.export_task.paths.export = self.export_path.name

    def tearDown(self) -> None:
        self.helper.reset()

    def test_boiler_export(self):
        graph = self.helper.get_simple_boiler()
        answers = ()
        modelica_model = DebugDecisionHandler(answers).handle(
            self.export_task.run(self.loaded_libs, graph))
        parameters = [('rated_power', 'Q_nom'),
                      ('return_temperature', 'T_set')]
        expected_units = [ureg.watt, ureg.kelvin]
        self.run_parameter_test(graph, modelica_model, parameters,
                                expected_units)

    def test_radiator_export(self):
        graph = self.helper.get_simple_radiator()
        answers = ()
        modelica_model = DebugDecisionHandler(answers).handle(
            self.export_task.run(self.loaded_libs, graph))
        parameters = [('rated_power', 'Q_flow_nominal'),
                      ('return_temperature', 'Tout_max')]
        expected_units = [ureg.watt, ureg.kelvin]
        self.run_parameter_test(graph, modelica_model, parameters,
                                expected_units)

    def test_pump_export(self):
        graph = self.helper.get_simple_pump()
        answers = ()
        modelica_model = DebugDecisionHandler(answers).handle(
            self.export_task.run(self.loaded_libs, graph))
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

    @unittest.skip
    def test_consumer_heating_distributor_module_export(self):
        raise NotImplementedError

    def test_boiler_module_export(self):
        graph = self.helper.get_simple_generator_one_fluid()
        answers = ()
        modelica_model = DebugDecisionHandler(answers).handle(
            self.export_task.run(self.loaded_libs, graph))
        parameters = [('rated_power', 'Qflow_nom')]
        expected_units = [ureg.watt]
        self.run_parameter_test(graph, modelica_model, parameters,
                                expected_units)

    def test_heat_pump_export(self):
        graph = self.helper.get_simple_heat_pump()
        answers = ()
        modelica_model = DebugDecisionHandler(answers).handle(
            self.export_task.run(self.loaded_libs, graph))
        parameters = [('rated_power', 'Qcon_nom')]
        expected_units = [ureg.watt]
        self.run_parameter_test(graph, modelica_model, parameters,
                                expected_units)

    def test_chiller_export(self):
        graph = self.helper.get_simple_chiller()
        answers = ()
        modelica_model = DebugDecisionHandler(answers).handle(
            self.export_task.run(self.loaded_libs, graph))
        parameters = [('rated_power', 'Qev_nom'),
                      ('nominal_COP', 'EER_nom')]
        expected_units = [ureg.watt, ureg.dimensionless]
        self.run_parameter_test(graph, modelica_model, parameters,
                                expected_units)

    def test_chp_export(self):
        graph = self.helper.get_simple_chp()
        answers = ()
        modelica_model = DebugDecisionHandler(answers).handle(
            self.export_task.run(self.loaded_libs, graph))
        parameters = [('rated_power', 'P_nom')]
        expected_units = [ureg.watt]
        self.run_parameter_test(graph, modelica_model, parameters,
                                expected_units)

    def test_cooling_tower_export(self):
        graph = self.helper.get_simple_cooling_tower()
        answers = ()
        modelica_model = DebugDecisionHandler(answers).handle(
            self.export_task.run(self.loaded_libs, graph))
        parameters = [('rated_power', 'Qflow_nom')]
        expected_units = [ureg.watt]
        self.run_parameter_test(graph, modelica_model, parameters,
                                expected_units)
