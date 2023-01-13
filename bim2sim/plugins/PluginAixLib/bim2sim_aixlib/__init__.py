import re
from ast import literal_eval

from bim2sim.export.modelica import standardlibrary
from bim2sim.kernel.element import Material
from bim2sim.kernel.elements import hvac as hvac_elements
from bim2sim.plugins import Plugin
from bim2sim.plugins.PluginAixLib.bim2sim_aixlib.models import AixLib
from bim2sim.task import base, common, hvac
from bim2sim.workflow import PlantSimulation


class LoadLibrariesAixLib(base.ITask):
    """Load AixLib library for export"""
    touches = ('libraries', )

    def run(self, workflow, **kwargs):
        return (standardlibrary.StandardLibrary, AixLib),


class PluginAixLib(Plugin):
    name = 'AixLib'
    default_workflow = PlantSimulation
    allowed_workflows = [PlantSimulation]
    tasks = {LoadLibrariesAixLib}
    elements = {*hvac_elements.items, Material}
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
            # semicolon to match modelica syntax
            value = str(value)
            value = re.sub('(,[^,]*),', r'\1;', value)
            setattr(self, key, value)
