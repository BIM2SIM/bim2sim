"""TEASER plugin for bim2sim

Holds logic to run a simulation based on prepared ifc data
"""
import inspect

import bim2sim.plugins.PluginTEASER.bim2sim_teaser.task as teaser_task
from bim2sim.plugins import Plugin
from bim2sim.plugins.PluginTEASER.bim2sim_teaser.models import TEASER
from bim2sim.task import common, bps, base
from bim2sim.simulation_settings import BuildingSimSettings, Setting
from bim2sim.utilities.types import LOD

from bim2sim.task.bps.bind_tz import CombineThermalZones


class TEASERSimSettings(BuildingSimSettings):
    """Defines simulation settings for TEASER Plugin.

    This class defines the simulation settings for the TEASER Plugin. It
    inherits all choices from the BuildingSimulation settings. TEASER
    specific settings are added here..
    """
    criteria_functions = {}
    for name, func in dict(
            inspect.getmembers(CombineThermalZones,
                               predicate=inspect.ismethod)).items():
        if name.startswith('group_thermal_zones_'):
            criteria_functions[func] = name.replace('group_thermal_zones_by_',
                                                    '').replace('_', ' ')

    zoning_setup = Setting(
        default=LOD.low,
        choices={
            LOD.low: 'All IfcSpaces of the building will be merged into '
                     'one thermal zone.',
            LOD.medium: 'IfcSpaces of the building will be merged together'
                        ' based on selected zoning criteria.',
            LOD.full: 'Every IfcSpace will be a separate thermal zone'
        },
        description='Select the criteria based on which thermal zones will '
                    'be aggreated.',
        for_frontend=True
    )

    zoning_criteria = Setting(
        default=CombineThermalZones.group_thermal_zones_by_usage,
        choices=criteria_functions,
        for_frontend=True
    )


class LoadLibrariesTEASER(base.ITask):
    """Load AixLib library for export"""
    touches = ('libraries', )

    def run(self, **kwargs):
        return (TEASER,),


class PluginTEASER(Plugin):
    name = 'TEASER'
    sim_settings = TEASERSimSettings()
    default_tasks = [
        common.LoadIFC,
        common.CheckIfc,
        common.CreateElements,
        bps.CreateSpaceBoundaries,
        bps.Prepare,
        common.BindStoreys,
        bps.EnrichUseConditions,
        bps.Verification,
        bps.EnrichMaterial,
        bps.DisaggregationCreation,
        bps.CombineThermalZones,
        teaser_task.WeatherTEASER,
        LoadLibrariesTEASER,
        teaser_task.ExportTEASER,
        teaser_task.SimulateModel,
    ]
