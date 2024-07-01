import tempfile

from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.plugins.PluginHKESim.bim2sim_hkesim import LoadLibrariesHKESim
from test.unit.elements.helper import SetupHelperHVAC
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

    def test_simple_boiler_export(self):
        graph = self.helper.get_simple_boiler()
        answers = ()
        modelica_model = DebugDecisionHandler(answers).handle(
            self.export_task.run(self.loaded_libs, graph))
        element_parameters = {
            'rated_power': graph.elements[0].rated_power,
            'return_temperature': graph.elements[0].return_temperature
        }
        modelica_parameters = {
            'rated_power': modelica_model[0].elements[0].export_params['Q_nom'],
            'return_temperature': modelica_model[0].elements[0].export_params[
                'T_set']
        }
        self.assertDictEqual(element_parameters, modelica_parameters)

    def test_simple_radiator_export(self):
        graph = self.helper.get_simple_radiator()
        answers = ()
        modelica_model = DebugDecisionHandler(answers).handle(
            self.export_task.run(self.loaded_libs, graph))
        element_parameters = {
            'rated_power': graph.elements[0].rated_power,
            'return_temperature': graph.elements[0].return_temperature
        }
        modelica_parameters = {
            'rated_power': modelica_model[0].elements[0].export_params[
                'Q_flow_nominal'],
            'return_temperature': modelica_model[0].elements[0].export_params[
                'Tout_max']
        }
        self.assertDictEqual(element_parameters, modelica_parameters)

    def test_simple_heat_pump_export(self):
        graph = self.helper.get_simple_heat_pump()
        answers = ()
        modelica_model = DebugDecisionHandler(answers).handle(
            self.export_task.run(self.loaded_libs, graph))
        print()
        # TODO: there is nothing to test here

    def test_simple_chiller_export(self):
        graph = self.helper.get_simple_chiller()
        answers = ()
        modelica_model = DebugDecisionHandler(answers).handle(
            self.export_task.run(self.loaded_libs, graph))
        element_parameters = {
            'rated_power': graph.elements[0].rated_power,
            'nominal_COP': graph.elements[0].nominal_COP,
        }
        modelica_parameters = {
            'rated_power': modelica_model[0].elements[0].export_params[
                'Qev_nom'],
            'nominal_COP': modelica_model[0].elements[0].export_params[
                'EER_nom']
        }
        self.assertDictEqual(element_parameters, modelica_parameters)

    def test_simple_cooling_power(self):
        graph = self.helper.get_simple_cooling_tower()
        answers = ()
        modelica_model = DebugDecisionHandler(answers).handle(
            self.export_task.run(self.loaded_libs, graph))
        element_parameters = {
            'rated_power': graph.elements[0].rated_power
        }
        modelica_parameters = {
            'rated_power': modelica_model[0].elements[0].export_params[
                'Qflow_nom']
        }
        self.assertDictEqual(element_parameters, modelica_parameters)
