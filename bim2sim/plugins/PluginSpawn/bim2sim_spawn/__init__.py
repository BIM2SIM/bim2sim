from bim2sim.plugins import Plugin
# from bim2sim.plugins.PluginModelica.bim2sim_modelica import PluginModelica
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus import PluginEnergyPlus
# import bim2sim.plugins.PluginSpawnOfEP.bim2sim_spawn.tasks as spawn_tasks
from bim2sim.sim_settings import CoSimulation


# # TODO: this is just a concept and not working already
class PluginSpawnOfEP(Plugin):
    name = 'SpawnOfEP'
    sim_settings = CoSimulation  # todo: this is currently empty

    export_hvac_library = 'AixLib'  # todo: this has currently no impact

    # combine elements from both Plugins
    elements = set()
    # elements.update(PluginModelica.elements)
    elements.update(PluginEnergyPlus.elements)

    # combine tasks from both Plugins
    default_tasks = []
    # default_tasks.extend(PluginModelica.default_tasks)
    default_tasks.extend(PluginEnergyPlus.default_tasks)

    # default_tasks.append(spawn_tasks.GetZoneConnections)
    # default_tasks.append(spawn_tasks.CoSimExport)

    # make sure that tasks only occur once
    # todo: this won't work always. We need to separate tasks that occur in
    #  multiple Plugins  (LoadIFC, CheckIFC and CreateElements) from the rest
    default_tasks = set(default_tasks)
