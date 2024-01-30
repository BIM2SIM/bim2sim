import tempfile
import unittest
from pathlib import Path
from unittest import mock

import bim2sim.elements.aggregation.hvac_aggregations
from bim2sim.elements.graphs.hvac_graph import HvacGraph
from bim2sim.kernel.decision.console import ConsoleDecisionHandler
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler

from test.unit.elements.aggregation.test_parallelpumps import \
    ParallelPumpHelper
from test.unit.elements.aggregation.test_pipestrand import StrandHelper
from bim2sim.tasks.hvac import Export
from bim2sim.sim_settings import PlantSimSettings
from bim2sim.plugins.PluginAixLib.bim2sim_aixlib import LoadLibrariesAixLib
from test.unit.elements.helper import SetupHelperHVAC
from bim2sim.elements import hvac_elements as hvac
from bim2sim.elements.mapping.units import ureg




class SetupHelperAixLibComponents(SetupHelperHVAC):

    def get_pipe(self):
        pipe = self.element_generator(
            hvac.Pipe,
            diameter=0.03 * ureg.m,
            length=1 * ureg.m)
        return HvacGraph([pipe])

    def get_pump(self):
        pump = self.element_generator(
            hvac.Pump,
            rated_mass_flow=1,
            rated_pressure_difference=100)
        return HvacGraph([pump])

    def get_Boiler(self):
        self.element_generator(hvac.Boiler, ...)


class TestAixLibExport(unittest.TestCase):
    export_task = None
    loaded_libs = None
    helper = None

    @classmethod
    def setUpClass(cls):
        playground = mock.Mock()
        project = mock.Mock
        playground.project = project
        paths = mock.Mock
        # load libraries as these are required for export
        lib_aixlib = LoadLibrariesAixLib(playground)
        cls.loaded_libs = lib_aixlib.run()[0]
        # instantiate export task and set required values via mocks
        cls.export_task = Export(playground)
        cls.export_task.prj_name = 'Test'
        # cls.export_task.paths = paths
        # temp_dir = tempfile.TemporaryDirectory(
        #     prefix='bim2sim_')
        # # cls.export_task.paths.export = temp_dir.name
        # cls.export_task.paths.export = Path("D:/01_Kurzablage/st_exportasdvfiyhxcv")
        cls.setup_helper_aixlib = SetupHelperAixLibComponents()

    def test_pipe_export(self):
        # TODO solve problem with path (maybe via project mock)
        graph = self.setup_helper_aixlib.get_pipe()
        temp_dir = tempfile.TemporaryDirectory(
            prefix='bim2sim_')
        self.export_task.paths = temp_dir.name
        answers = ()
        modelica_model = DebugDecisionHandler(answers).handle(
            self.export_task.run(self.loaded_libs, graph))
        # assertEqual
        pipe_ele_params = {
            'diameter': graph.elements[0].diameter,
            'length': graph.elements[0].length
        }
        # ConsoleDecisionHandler().handle(export_task.run(loaded_libs, graph))
        pipe_modelica_params = {
            'diameter': modelica_model[0].elements[0].params['diameter'],
            'length': modelica_model[0].elements[0].params['length']
        }
        self.assertDictEqual(pipe_ele_params, pipe_modelica_params)

    #
    # parallelPumpHelper = ParallelPumpHelper()
    # graph, flags = parallelPumpHelper.get_setup_pumps4()
    # matches, meta = bim2sim.elements.aggregation.hvac_aggregations
    # .ParallelPump.find_matches(graph)
    # agg_pump = bim2sim.elements.aggregation.hvac_aggregations
    # .ParallelPump(graph, matches[0], **meta[0])
    # graph.merge(
    #     mapping=agg_pump.get_replacement_mapping(),
    #     inner_connections=agg_pump.inner_connections,
    # )
    # playground = mock.Mock()
    # project = mock.Mock
    # playground.project = project
    # paths = mock.Mock
    # # load libraries as these are required for export
    # lib_aixlib = LoadLibrariesAixLib(playground)
    # loaded_libs = lib_aixlib.run()[0]
    # # instantiate export task and set required values via mocks
    # export_task = Export(playground)
    # export_task.prj_name = 'Test'
    # export_task.paths = paths
    # export_task.paths.export = Path("D:/01_Kurzablage/test_export")
    # # run export task with ConsoleDecisionHandler
    # answers = (1,1,1)
    # # DebugDecisionHandler(answers).handle(export_task.run(loaded_libs,
    # graph))
    # ConsoleDecisionHandler().handle(export_task.run(loaded_libs, graph))
    # # for test, answers in zip(test, answers) in export_task.run(workflow,
    # lib_aixlib.run(workflow)[0], graph):
    # #     print('test')
    # print('test')
