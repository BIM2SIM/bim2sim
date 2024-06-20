import tempfile
import unittest
from unittest import mock

from bim2sim import ConsoleDecisionHandler
from bim2sim.elements.graphs.hvac_graph import HvacGraph
from bim2sim.elements.mapping.units import ureg
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.plugins.PluginHKESim.bim2sim_hkesim import LoadLibrariesHKESim
from test.unit.elements.helper import SetupHelperHVAC
from bim2sim.elements import hvac_elements as hvac
from bim2sim.tasks.hvac import Export


class SetupHelperHKESimComponents(SetupHelperHVAC):

    def get_simple_boiler(self):
        boiler = self.element_generator(
            hvac.Boiler,
            rated_power=100 * ureg.kilowatt,
            return_temperature=90 * ureg.celsius
        )
        return HvacGraph([boiler])

    def get_simple_radiator(self):
        radiator = self.element_generator(
            hvac.SpaceHeater,
            rated_power=20 * ureg.kilowatt,
            return_temperature=70 * ureg.celsius
        )
        return HvacGraph([radiator])


class TestHKESimExport(unittest.TestCase):
    export_task = None
    loaded_libraries = None
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
        libraries = LoadLibrariesHKESim(playground)
        cls.loaded_libraries = libraries.run()[0]

        # Instantiate export task and set required values via mocks
        cls.export_task = Export(playground)
        cls.export_task.prj_name = cls.__name__
        cls.export_task.paths = paths

        cls.helper = SetupHelperHKESimComponents()

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
            self.export_task.run(self.loaded_libraries, graph))
        element_parameters = {
            'rated_power': graph.elements[0].rated_power,
            'return_temperature': graph.elements[0].return_temperature
        }
        modelica_parameters = {
            'rated_power': modelica_model[0].elements[0].export_params['Q_nom'],
            'return_temperature': modelica_model[0].elements[0].export_params['T_set']
        }
        self.assertDictEqual(element_parameters, modelica_parameters)

    def test_simple_radiator_export(self):
        graph = self.helper.get_simple_radiator()
        answers = ()
        modelica_model = DebugDecisionHandler(answers).handle(
            self.export_task.run(self.loaded_libraries, graph))
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

