"""EnergyPlus plugin for bim2sim

Holds logic to run a simulation based on prepared ifc data
"""
from bim2sim.plugins import Plugin
from bim2sim.task import common, bps
from bim2sim.simulation_settings import BuildingSimSettings, Setting

from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus import task as ep_tasks


class EnergyPlusSimSettings(BuildingSimSettings):
    """Defines simulation settings for EnergyPlus Plugin.

    This class defines the simulation settings for the EnergyPlus Plugin. It
    inherits all choices from the BuildingSimulation settings. EnergyPlus
    specific settings are added here, such as simulation control parameters
    and export settings.
    """
    cfd_export = Setting(
        default=False,
        choices={
            False: 'Do not use CFD export',
            True: 'Use CFD export'
        },
        description='Whether to use CFD export for this simulation or not.',
        for_frontend=True
    )
    split_bounds = Setting(
        default=False,
        choices={
            False: 'Keep non-convex space boundaries as they are',
            True: 'Split up non-convex boundaries in convex shapes'
        },
        description='Whether to convert up non-convex space boundaries or '
                    'not.',
        for_frontend=True
    )
    add_shadings = Setting(
        default=True,
        choices={
            True: 'Add shading surfaces if available',
            False: 'Do not add shading surfaces even if available'
        },
        description='Whether to add shading surfaces if available or not.',
        for_frontend=True
    )
    split_shadings = Setting(
        default=False,
        choices={
            False: 'Keep non-convex shading boundaries as they are',
            True: 'Split up non-convex shading boundaries in convex shapes'
        },
        description='Whether to convert up non-convex shading boundaries or '
                    'not.',
        for_frontend=True
    )
    run_full_simulation = Setting(
        default=False,
        choices={
            True: 'Run annual simulation',
            False: 'Run design day simulation'
        },
        description='Choose simulation period.',
        for_frontend=True
    )
    ep_version = Setting(
        default='9-4-0',
        choices={
            '9-2-0': 'EnergyPlus Version 9-2-0',
            '9-4-0': 'EnergyPlus Version 9-4-0',
            '22-2-0': 'EnergyPlus Version 22-2-0'  # todo: Test latest version
        },
        description='Choose EnergyPlus Version',
        for_frontend=True,
        any_string=True
    )
    ep_install_path = Setting(
        default=f'D:/04_Programme/EnergyPlus-9-4-0/',
        # default=f'/usr/local/EnergyPlus-9-4-0/',
        choices={
            f'/usr/local/EnergyPlus-9-4-0/': 'ubuntu-default',
            f'/usr/local/EnergyPlus-{ep_version.default}/':
                'ubuntu-path-choice',
            f'C:/EnergyPlus/EnergyPlusV{ep_version.default}/':
                'windows-default'
        },
        description='Choose EnergyPlus Installation Path',
        for_frontend=False,
        any_string=True
    )
    system_sizing = Setting(
        default=True,
        choices={
            True: 'Do system sizing calculation',
            False: 'Not do system sizing calculation'
        },
        description='Whether to do system sizing calculations in EnergyPlus '
                    'or not.',
        for_frontend=True
    )
    run_for_sizing_periods = Setting(
        default=False,
        choices={
            True: 'Run simulation for system sizing periods',
            False : 'Do not run simulation for system sizing periods'
        },
        description='Whether to run the EnergyPlus simulation for sizing '
                    'periods or not.',
        for_frontend=True
    )
    run_for_weather_period = Setting(
        default=True,
        choices={
            True: 'Run simulation for weather file period',
            False: 'Do not run simulation for weather file period'
        },
        description='Whether to run the EnergyPlus simulation for weather '
                    'file period or not.',
        for_frontend=True
    )
    solar_distribution = Setting(
        default='FullExterior',
        choices={
            'FullExterior': 'Full exterior solar distribution',
            'FullInteriorAndExterior': 'Full interior and exterior solar '
                                       'distribution'
        },
        description='Choose solar distribution.',
        for_frontend=True
    )
    output_format = Setting(
        default='CommaAndHTML',
        choices={
            'Comma': 'Output format Comma (.csv)',
            'Tab': 'Output format Tab (.tab)',
            'Fixed': 'Output format Fixed (.txt)',
            'HTML': 'Output format HTML (.htm)',
            'XML': 'Output format XML (.xml)',
            'CommaAndHTML': 'Output format CommaAndHTML',
            'TabAndHTML': 'Output format TabAndHTML',
            'XMLAndHTML': 'Output format TabAndHTML',
            'All': 'All output formats.',
        },
        description='Choose output format for result files.',
        for_frontend=True
    )
    unit_conversion = Setting(
        default='JtoKWH',
        choices={
            'None': 'No unit conversions',
            'JtoKWH': 'Convert Joule into kWh (1/3600000)',
            'JtoMJ': 'Joule converted into Megajoule (1/1000000)',
            'JtoGJ': 'Joule converted into Gigajoule',
            'InchPound': 'Convert all tabular values to common Inch-Pound ' \
                         'equivalent.'
        },
        description='Choose unit conversion for result files.',
        for_frontend=True
    )
    output_keys = Setting(
        default=['output_outdoor_conditions', 'output_zone_temperature',
                 'output_zone', 'output_infiltration', 'output_meters'],
        choices={
            'output_outdoor_conditions': 'Add outputs for outdoor conditions.',
            'output_internal_gains': 'Add output for internal gains.',
            'output_zone_temperature': 'Add output for zone mean and '
                                       'operative temperature.',
            'output_zone': 'Add heating and cooling rates and energy on zone '
                           'level.',
            'output_infiltration': 'Add output for zone infiltration.',
            'output_meters': 'Add heating and cooling meters.',
            'output_dxf': 'Output a dxf of the building geometry.',
        },
        description='Choose groups of output variables (multiple choice).',
        multiple_choice=True,
        for_frontend=True
    )


class PluginEnergyPlus(Plugin):
    name = 'EnergyPlus'
    sim_settings = EnergyPlusSimSettings
    default_tasks = [
        common.LoadIFC,
        common.CheckIfc,
        common.CreateElements,
        bps.CreateSpaceBoundaries,
        bps.Prepare,
        common.BindStoreys,
        bps.EnrichUseConditions,
        bps.Verification,  # LOD.full
        bps.EnrichMaterial,  # LOD.full
        ep_tasks.EPGeomPreprocessing,
        ep_tasks.AddSpaceBoundaries2B,
        ep_tasks.WeatherEnergyPlus,
        ep_tasks.CreateIdf,
        ep_tasks.IdfPostprocessing,
        ep_tasks.ExportIdfForCfd,
        ep_tasks.RunEnergyPlusSimulation,
    ]
