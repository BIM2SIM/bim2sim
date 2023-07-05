import re
from ast import literal_eval

import bim2sim.tasks.common.check_ifc
import bim2sim.tasks.common.create_elements
import bim2sim.tasks.common.load_ifc
import bim2sim.tasks.hvac.connect_elements
import bim2sim.tasks.hvac.export
import bim2sim.tasks.hvac.make_graph
import bim2sim.tasks.hvac.reduce
from bim2sim.export.modelica import standardlibrary
from bim2sim.plugins import Plugin
from bim2sim.plugins.PluginAixLib.bim2sim_aixlib.models import AixLib
from bim2sim.tasks import base, common, hvac
from bim2sim.sim_settings import PlantSimSettings


class LoadLibrariesAixLib(base.ITask):
    """Load AixLib library for export"""
    touches = ('libraries', )

    def run(self, **kwargs):
        return (standardlibrary.StandardLibrary, AixLib),

    def overwrite_standarlib_models(self):
        pass


class PluginAixLib(Plugin):
    name = 'AixLib'
    sim_settings = PlantSimSettings
    tasks = {LoadLibrariesAixLib}
    default_tasks = [
        bim2sim.tasks.common.load_ifc.LoadIFC,
        bim2sim.tasks.common.check_ifc.CheckIfc,
        bim2sim.tasks.common.create_elements.CreateElements,
        bim2sim.tasks.hvac.connect_elements.ConnectElements,
        bim2sim.tasks.hvac.make_graph.MakeGraph,
        hvac.ExpansionTanks,
        bim2sim.tasks.hvac.reduce.Reduce,
        hvac.DeadEnds,
        LoadLibrariesAixLib,
        bim2sim.tasks.hvac.export.Export,
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
