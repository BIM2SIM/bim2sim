"""TEASER plugin for bim2sim

Holds logic to run a simulation based on prepared ifc data
"""
import bim2sim.plugins.PluginTEASER.bim2sim_teaser.task as teaser_task
from bim2sim.plugins import Plugin
from bim2sim.plugins.PluginTEASER.bim2sim_teaser.models import TEASER
from bim2sim.tasks import common, bps, base
from bim2sim.sim_settings import BuildingSimSettings, Setting
from bim2sim.utilities.types import LOD


class TEASERSimSettings(BuildingSimSettings):
    """Defines simulation settings for TEASER Plugin.

    This class defines the simulation settings for the TEASER Plugin. It
    inherits all choices from the BuildingSimulation settings. TEASER
    specific settings are added here..
    """

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
        default='usage',
        choices={
            'external': 'Group all thermal zones that have contact to the '
                        'exterior together and all thermal zones that do '
                        'not have contact to exterior.',
            'usage': 'Group all thermal zones that have the same usage.',
            'external and orientation': 'Like external, but takes orientation'
                                        ' (North, east, south, west) into '
                                        'account as well',
            'external, orientation and usage': 'Combines the prior options.',
            'use all criteria': 'Uses all prior options and adds glass '
                                'percentage of the rooms as additional criteria'
                                ' and only groups rooms if they are adjacent '
                                'to each other.'
        },
        description='Criteria to aggregate thermal zones that is used, if '
                    '"zoning_setup" is set to LOD.medium',
        for_frontend=True
    )

    deactivate_ahu = Setting(
        default=False,
        choices={
            True: 'Deactives the AHU for all thermal zones.',
            False: 'If a thermal zone uses an AHU will be decided based on the '
                   'given IFC data and the usage used for enrichment.'
        },
        description='If True the AHU unit will be deactivated for all thermal'
                    ' zones, even if the fitting use condition uses an AHU.',
        for_frontend=True
    )


class LoadLibrariesTEASER(base.ITask):
    """Load AixLib library for export"""
    touches = ('libraries', )

    def run(self, **kwargs):
        return (TEASER,),


class PluginTEASER(Plugin):
    name = 'TEASER'
    sim_settings = TEASERSimSettings
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
