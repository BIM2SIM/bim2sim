import re
from ast import literal_eval

from bim2sim.export.modelica import standardlibrary
from bim2sim.kernel.element import Material
from bim2sim.kernel.elements import hvac as hvac_elements
from bim2sim.plugins import Plugin
from bim2sim.plugins.PluginModelica.bim2sim_modelica import PluginModelica
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus import PluginEnergyPlus

<<<<<<< Updated upstream
from bim2sim.task import base, common, hvac
from bim2sim.simulation_type import CoSimulation


class PluginCoSimModelica(Plugin):
    name = 'Modelica'
    default_workflow = CoSimulation

    export_library = 'AixLib'  # todo load this
    allowed_workflows = [CoSimulation]
    # tasks = {LoadLibrariesAixLib}
    elements = {*hvac_elements.items, Material}


    tasks = []
    tasks.extend(PluginModelica.default_tasks)
    tasks.extend(PluginEnergyPlus.default_tasks)

    tasks_loading
    tasks_processing
    tasks_export

    default_tasks = [
        common.LoadIFC,
        hvac.CheckIfcHVAC,
        common.CreateElements,
        hvac.ConnectElements,
        hvac.MakeGraph,
        hvac.ExpansionTanks,
        hvac.Reduce,
        hvac.DeadEnds,
        LoadLibrariesAixLib,
        hvac.Export,
    ]

    def create_modelica_table_from_list(self, curve):
        """

        :param curve:
        :return:
        """
        curve = literal_eval(curve)
        for key, value in curve.iteritems():
            # add first and last value to make sure there is a constant
            # behaviour before and after the given heating curve
            value = [value[0] - 5, value[1]] + value + [value[-2] + 5,
                                                        value[-1]]
            # transform to string and replace every second comma with a
            # semicolon to match_graph modelica syntax
            value = str(value)
            value = re.sub('(,[^,]*),', r'\1;', value)
            setattr(self, key, value)
=======
from bim2sim.simulation_type import CoSimulation


class PluginSpawnOfEP(Plugin):
    name = 'SpawnOfEP'
    default_workflow = CoSimulation  # todo: this is currently empty

    export_hvac_library = 'AixLib'  # todo: this has currently no impact
    allowed_workflows = [CoSimulation]

    # combine elements from both Plugins
    elements = set()
    elements.update(PluginModelica.elements)
    elements.update(PluginEnergyPlus.elements)

    # combine tasks from both Plugins
    default_tasks = []
    default_tasks.extend(PluginModelica.default_tasks)
    default_tasks.extend(PluginEnergyPlus.default_tasks)
    # make sure that tasks only occur once
    # todo: this won't work always. We need to separate tasks that occur in
    #  multiple Plugins  (LoadIFC, CheckIFC and CreateElements) from the rest
    default_tasks = set(default_tasks)
>>>>>>> Stashed changes
