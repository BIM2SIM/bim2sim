import tempfile
import unittest
from pathlib import Path
from typing import List, Tuple
from unittest import mock

from bim2sim.elements.graphs.hvac_graph import HvacGraph
from bim2sim.elements.hvac_elements import HVACProduct, Pump
from bim2sim.elements.mapping.units import ureg

from bim2sim.export.modelica import ModelicaElement, ModelicaParameter, \
    parse_to_modelica
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.tasks.hvac import (Export, LoadLibrariesStandardLibrary,
                                CreateModelicaModel)
from test.unit.elements.helper import SetupHelperHVAC


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
        cls.playground.sim_settings.regression_variables = []

        # Load libraries as these are required for export
        lib_msl = LoadLibrariesStandardLibrary(cls.playground)
        cls.loaded_libs = lib_msl.run()[0]

        # Instantiate export task and set required values via mocks
        cls.create_modelica_model = CreateModelicaModel(cls.playground)
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

    def run_parameter_test(self, graph: HvacGraph, modelica_model: list,
                           parameters: List[Tuple[str, str]],
                           expected_units: list):
        """
        Runs a parameter test on an element exported to Modelica code.

        This method checks that the specified attributes in the element are
        converted to the expected units and correctly appear in the Modelica
        model's code.

        Args:
            graph: The HvacGraph containing the element to be tested.
            modelica_model: A list containing the modelica model instances.
            parameters: A list of tuples where each tuple contains the name of
                the element attribute and the corresponding modelica parameter.
                The attribute name comes first.
            expected_units: A list of expected units of the parameter in
                Modelica.
        """
        element = graph.elements[0]
        values = [
            element.attributes[param[0]][0].to(expected_units[index]).magnitude
            for index, param in enumerate(parameters)]
        expected_strings = [f'{param[1]}={values[index]}'
                            for index, param in enumerate(parameters)]
        for expected_string in expected_strings:
            self.assertIn(expected_string, modelica_model[0].code())

    def test_to_modelica(self):
        element = HVACProduct()
        modelica_instance = ModelicaElement(element)
        # True boolean
        self.assertEqual('a=true',
                         parse_to_modelica('a', True))
        # False boolean
        self.assertEqual('a=false',
                         parse_to_modelica('a', False))
        # Quantity with unit
        self.assertEqual('a=1',
                         parse_to_modelica('a', 1 * ureg.m))
        # Integer
        self.assertEqual('a=1',
                         parse_to_modelica('a', int(1)))
        # Float
        self.assertEqual('a=1.1',
                         parse_to_modelica('a', float(1.1)))
        # String
        self.assertEqual('a="a"',
                         parse_to_modelica('a', '"a"'))
        # List
        self.assertEqual('a={1,1.1}',
                         parse_to_modelica(
                             'a', [int(1), float(1.1)]))
        # Tuple
        self.assertEqual('a={1,1.1}',
                         parse_to_modelica(
                             'a', (int(1), float(1.1))))
        # Set
        self.assertEqual('a={1,1.1}',
                         parse_to_modelica(
                             'a', {int(1), float(1.1)}))
        # Dict
        self.assertEqual('a(b=1.1)',
                         parse_to_modelica(
                             'a', {'b': 1.1}))
        self.assertEqual('per(pressure(V_flow={1,2},dp={1,2}))',
                         parse_to_modelica(
                             'per',
                             {'pressure': {'V_flow': [1, 2], 'dp': [1, 2]}}))
        # Path
        self.assertEqual(
            'Modelica.Utilities.Files.loadResource("C:\\\\Users")',
            parse_to_modelica(None, Path(r'C:\Users')))

    def test_missing_required_parameter(self):
        """ Test if an AssertionError is raised if a required parameter is not
            provided."""
        graph, pipe = self.helper.get_simple_pipe()
        answers = ()
        with self.assertRaises(AssertionError):
            DebugDecisionHandler(answers).handle(
                self.create_modelica_model.run(self.loaded_libs, graph))

    def test_check_function(self):
        """ Test if the check function for a parameter works. The exported
            parameter 'diameter' should be None since it is set to a negative
            value.
        """
        graph, pipe = self.helper.get_simple_pipe()
        pipe.diameter = -1 * ureg.meter
        answers = ()
        export_elements, connections = DebugDecisionHandler(answers).handle(
            self.create_modelica_model.run(self.loaded_libs, graph))
        modelica_model = self.export_task.run(
            export_elements, connections)
        self.assertIsNone(
            modelica_model[0].modelica_elements[0].parameters['diameter'].value)
        self.assertIsNotNone(
            modelica_model[0].modelica_elements[0].parameters['length'].value)

    def test_pipe_export(self):
        graph, pipe = self.helper.get_simple_pipe()
        pipe.diameter = 0.2 * ureg.meter
        export_elements, connections = DebugDecisionHandler(()).handle(
            self.create_modelica_model.run(self.loaded_libs, graph))
        modelica_model = self.export_task.run(
            export_elements, connections)
        # Test for expected and exported parameters
        parameters = [('diameter', 'diameter'), ('length', 'length')]
        expected_units = [ureg.m, ureg.m]
        self.run_parameter_test(graph, modelica_model, parameters,
                                expected_units)

    def test_valve_export(self):
        graph = self.helper.get_simple_valve()
        answers = (1 * ureg.kg / ureg.h,)
        export_elements, connections = DebugDecisionHandler(answers).handle(
            self.create_modelica_model.run(self.loaded_libs, graph))
        modelica_model = self.export_task.run(
            export_elements, connections)
        parameters = [('nominal_pressure_difference', 'dp_nominal'),
                      ('nominal_mass_flow_rate', 'm_flow_nominal')]
        expected_units = [ureg.bar, ureg.kg / ureg.s]
        self.run_parameter_test(graph, modelica_model, parameters,
                                expected_units)

    def test_junction_export(self):
        graph = self.helper.get_simple_junction()
        answers = ()
        export_elements, connections = DebugDecisionHandler(answers).handle(
            self.create_modelica_model.run(self.loaded_libs, graph))
        modelica_model = self.export_task.run(
            export_elements, connections)
        # Test for expected and exported parameters
        parameters = [('volume', 'V')]
        expected_units = [ureg.m ** 3]
        self.run_parameter_test(graph, modelica_model, parameters,
                                expected_units)

    def test_storage_export(self):
        graph = self.helper.get_simple_storage()
        answers = ()
        export_elements, connections = DebugDecisionHandler(answers).handle(
            self.create_modelica_model.run(self.loaded_libs, graph))
        modelica_model = self.export_task.run(
            export_elements, connections)
        # Test for expected and exported parameters
        parameters = [('volume', 'V')]
        expected_units = [ureg.m ** 3]
        self.run_parameter_test(graph, modelica_model, parameters,
                                expected_units)
