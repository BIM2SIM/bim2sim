import unittest

from bim2sim.decision.decisionhandler import DebugDecisionHandler

from bim2sim.decision.console import ConsoleDecisionHandler

from test.unit.kernel.aggregation.test_parallelpumps import ParallelPumpHelper
from bim2sim.kernel import aggregation
from bim2sim.task.hvac import Export
from bim2sim.workflow import PlantSimulation
from bim2sim.plugins.PluginAixLib.bim2sim_aixlib import LoadLibrariesAixLib


# class TestAixLibExport():

    # TODO primary goal is to export the parallelpump test and see how connections come out
    #  therefore we need to run a task without any project and can't use the existing DebugDecisioHandler due to missing project
    #  for generic usage in the future we need a class like DebugDecisionHandler to run single tasks, or maybe inistiate a DebugPlayground

if __name__ == '__main__':
# def parallelpump_export(self):
    print('TESTTEST')
    parallelPumpHelper = ParallelPumpHelper()
    graph, flags = parallelPumpHelper.get_setup_pumps4()
    matches, meta = aggregation.ParallelPump.find_matches(graph)
    agg_pump = aggregation.ParallelPump(graph, matches[0], **meta[0])
    graph.merge(
        mapping=agg_pump.get_replacement_mapping(),
        inner_connections=agg_pump.inner_connections,
    )
    workflow = PlantSimulation()
    lib_aixlib = LoadLibrariesAixLib()
    export_task = Export()
    ConsoleDecisionHandler().handle(export_task.run(workflow, lib_aixlib.run(workflow)[0], graph))

    # for test, answers in zip(test, answers) in export_task.run(workflow, lib_aixlib.run(workflow)[0], graph):
    #     print('test')
    print('test')
