import re
from ast import literal_eval

from bim2sim.export.modelica import standardlibrary
from bim2sim.kernel.element import Material
from bim2sim.kernel.elements import hvac as hvac_elements
from bim2sim.plugins import Plugin
from bim2sim.plugins.PluginModelica.bim2sim_modelica import PluginModelica
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus import PluginEnergyPlus

from bim2sim.task import base, common, hvac
from bim2sim.simulation_settings import CoSimulation


class PluginCoSimModelica(Plugin):
    name = 'Modelica'
    default_settings = CoSimulation

    export_library = 'AixLib'  # todo load this
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
        hvac.CheckIfc,
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
