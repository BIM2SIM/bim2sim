from pathlib import Path

from bim2sim.sim_settings import BuildingSimSettings, BooleanSetting, \
    ChoiceSetting, PathSetting


class EnergyPlusSimSettings(BuildingSimSettings):
    """Defines simulation settings for EnergyPlus Plugin.

    This class defines the simulation settings for the EnergyPlus Plugin. It
    inherits all choices from the BuildingSimulation settings. EnergyPlus
    specific settings are added here, such as simulation control parameters
    and export settings.
    """
    cfd_export = BooleanSetting(
        default=False,
        description='Whether to use CFD export for this simulation or not.',
        for_frontend=True
    )
    split_bounds = BooleanSetting(
        default=False,
        description='Whether to convert up non-convex space boundaries or '
                    'not.',
        for_frontend=True
    )
    add_shadings = BooleanSetting(
        default=True,
        description='Whether to add shading surfaces if available or not.',
        for_frontend=True
    )
    split_shadings = BooleanSetting(
        default=False,
        description='Whether to convert up non-convex shading boundaries or '
                    'not.',
        for_frontend=True
    )
    run_full_simulation = BooleanSetting(
        default=False,
        description='Choose simulation period.',
        for_frontend=True
    )
    ep_version = ChoiceSetting(
        default='9-4-0',
        choices={
            '9-2-0': 'EnergyPlus Version 9-2-0',
            '9-4-0': 'EnergyPlus Version 9-4-0',
            '9-6-0': 'EnergyPlus Version 9-6-0',
            '22-2-0': 'EnergyPlus Version 22-2-0',  # todo: Test latest version
            '24-1-0': 'EnergyPlus Version 22-2-0'  # todo: Test latest version
        },
        description='Choose EnergyPlus Version',
        for_frontend=True,
        any_string=True
    )
    ep_install_path = PathSetting(
        default=Path('/usr/local/EnergyPlus-9-4-0/'),
        description='Choose EnergyPlus Installation Path',
        for_frontend=False,
    )
    system_sizing = BooleanSetting(
        default=True,
        description='Whether to do system sizing calculations in EnergyPlus '
                    'or not.',
        for_frontend=True
    )
    run_for_sizing_periods = BooleanSetting(
        default=False,
        description='Whether to run the EnergyPlus simulation for sizing '
                    'periods or not.',
        for_frontend=True
    )
    run_for_weather_period = BooleanSetting(
        default=True,
        description='Whether to run the EnergyPlus simulation for weather '
                    'file period or not.',
        for_frontend=True
    )
    solar_distribution = ChoiceSetting(
        default='FullExterior',
        choices={
            'FullExterior': 'Full exterior solar distribution',
            'FullInteriorAndExterior': 'Full interior and exterior solar '
                                       'distribution'
        },
        description='Choose solar distribution.',
        for_frontend=True
    )
    add_window_shading = ChoiceSetting(
        default=None,
        choices={
            None: 'Do not add window shading',
            'Interior': 'Add an interior shade in EnergyPlus',
            'Exterior': 'Add an exterior shade in EnergyPlus',
        },
        description='Choose window shading.',
        for_frontend=True,
    )
    output_format = ChoiceSetting(
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
    unit_conversion = ChoiceSetting(
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
    output_keys = ChoiceSetting(
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
    correct_space_boundaries = BooleanSetting(
        default=True,
        description='Apply geometric correction to space boundaries.',
        for_frontend=True
    )
    close_space_boundary_gaps = BooleanSetting(
        default=True,
        description='Close gaps in the set of space boundaries by adding '
                    'additional 2b space boundaries.',
        for_frontend=True
    )
    add_natural_ventilation = BooleanSetting(
        default=True,
        description='Add natural ventilation to the building. Natural '
                    'ventilation is not available when cooling is activated.',
        for_frontend=True
    )
