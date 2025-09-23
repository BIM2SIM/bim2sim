from pathlib import Path

from bim2sim.sim_settings import BuildingSimSettings, BooleanSetting, \
    ChoiceSetting, PathSetting, NumberSetting


class EnergyPlusSimSettings(BuildingSimSettings):
    """Defines simulation settings for EnergyPlus Plugin.

    This class defines the simulation settings for the EnergyPlus Plugin. It
    inherits all choices from the BuildingSimulation settings. EnergyPlus
    specific settings are added here, such as simulation control parameters
    and export settings.
    """
    cfd_export = BooleanSetting(
        value=False,
        description='Whether to use CFD export for this simulation or not.',
        for_frontend=True
    )
    split_bounds = BooleanSetting(
        value=False,
        description='Whether to convert up non-convex space boundaries or '
                    'not.',
        for_frontend=True
    )
    add_shadings = BooleanSetting(
        value=True,
        description='Whether to add shading surfaces if available or not.',
        for_frontend=True
    )
    split_shadings = BooleanSetting(
        value=False,
        description='Whether to convert up non-convex shading boundaries or '
                    'not.',
        for_frontend=True
    )
    run_full_simulation = BooleanSetting(
        value=False,
        description='Choose simulation period.',
        for_frontend=True
    )
    ep_version = ChoiceSetting(
        value='9-4-0',
        choices={
            '9-2-0': 'EnergyPlus Version 9-2-0',
            '9-4-0': 'EnergyPlus Version 9-4-0',
            '22-2-0': 'EnergyPlus Version 22-2-0'  # todo: Test latest version
        },
        description='Choose EnergyPlus Version',
        for_frontend=True,
        any_string=True
    )
    ep_install_path = PathSetting(
        value=Path('/usr/local/EnergyPlus-9-4-0/'),
        description='Choose EnergyPlus Installation Path',
        for_frontend=False,
    )
    system_sizing = BooleanSetting(
        value=True,
        description='Whether to do system sizing calculations in EnergyPlus '
                    'or not.',
        for_frontend=True
    )
    run_for_sizing_periods = BooleanSetting(
        value=False,
        description='Whether to run the EnergyPlus simulation for sizing '
                    'periods or not.',
        for_frontend=True
    )
    run_for_weather_period = BooleanSetting(
        value=True,
        description='Whether to run the EnergyPlus simulation for weather '
                    'file period or not.',
        for_frontend=True
    )
    system_weather_sizing = ChoiceSetting(
        default='Typical',
        choices={'Typical': 'SummerTypical and WinterTypical for system '
                            'sizing.',
                 'Extreme': 'SummerExtreme and WinterExtreme for system '
                            'sizing.',
                 'DesignDay': 'DesignDay for system sizing. Choose this '
                              'option if neither SummerExtreme nor '
                              'SummerTypical days are available in weather '
                              'file.'},
        description='Choose whether to perform the system sizing for '
                     'DesignDays, extreme weather periods, typical weather '
                     'periods. Default=Typical (i.e., apply system sizing for '
                     'typical summer/winter days). '
    )
    weather_file_for_sizing = PathSetting(
        default=None,
        description='Path to the weather file that should be used for system '
                    'sizing in EnergyPlus',
        for_frontend=True,
        mandatory=False
    )
    enforce_system_sizing = BooleanSetting(
        default=False,
        description='Choose True if you want to enforce HVAC Sizing to sizing '
                    'period settings (limit heating and cooling capacity) '
                    'instead of autosizing.',
        for_frontend=True
    )
    solar_distribution = ChoiceSetting(
        value='FullExterior',
        choices={
            'FullExterior': 'Full exterior solar distribution',
            'FullInteriorAndExterior': 'Full interior and exterior solar '
                                       'distribution'
        },
        description='Choose solar distribution.',
        for_frontend=True
    )
    add_window_shading = ChoiceSetting(
        value=None,
        choices={
            None: 'Do not add window shading',
            'Interior': 'Add an interior shade in EnergyPlus',
            'Exterior': 'Add an exterior shade in EnergyPlus',
        },
        description='Choose window shading.',
        for_frontend=True,
    )
    output_format = ChoiceSetting(
        value='CommaAndHTML',
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
        value='JtoKWH',
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
        value=['output_outdoor_conditions', 'output_zone_temperature',
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
        value=True,
        description='Apply geometric correction to space boundaries.',
        for_frontend=True
    )
    close_space_boundary_gaps = BooleanSetting(
        value=True,
        description='Close gaps in the set of space boundaries by adding '
                    'additional 2b space boundaries.',
        for_frontend=True
    )
    add_natural_ventilation = BooleanSetting(
        value=True,
        description='Add natural ventilation to the building. Natural '
                    'ventilation is not available when cooling is activated.',
        for_frontend=True
    )
    hvac_off_at_night = BooleanSetting(
        default=False, description='Disable all HVAC systems at night from '
                                   '10pm to 6am.'
    )
    control_operative_temperature = BooleanSetting(
        default=False, description='Use operative temperature instead of air '
                                   'temperature for zonal temperature control.'
    )
    ventilation_demand_control = ChoiceSetting(
        default=None,
        choices={None: 'No demand control for mechanical ventilation.',
                 'OccupancySchedule': 'Demand control based on occupancy '
                                      'schedule.'},
        description='Choose if mechanical ventilation should be demand '
                    'controlled. Default is None. '
    )
    outdoor_air_economizer = ChoiceSetting(
        default='NoEconomizer',
        choices={'NoEconomizer': 'No outdoor air economizer is applied.',
                 'DifferentialDryBulb': 'The outdoor air economizer is '
                                        'applied based on the differential '
                                        'dry bulb temperature.',
                 'DifferentialEnthalpy': 'The outdoor air economizer is '
                                        'applied based on the differential '
                                        'enthalpy.'},
        description='Choose which type of outdoor air economizer should be '
                    'applied to reduce cooling loads by an increased outdoor '
                    'air flow if cooling loads can be reduced. Default is '
                    '"NoEconomizer".'
    )
    heat_recovery_type = ChoiceSetting(
        default='Enthalpy',
        choices={'Enthalpy': 'Use Enthalpy Heat Recovery.',
                 'Sensible': 'Use Sensible Heat Recovery.',
                 'None': 'No Heat Recovery'},
        description='Choose which type of heat recovery should be applied for '
                    'mechanical ventilation.'
    )
    heat_recovery_sensible = NumberSetting(
        default=0.8, min_value=0, max_value=1,
        description='Choose the sensible heat recovery effectiveness. '
                    'Default: 0.8.'
    )
    heat_recovery_latent = NumberSetting(
        default=0.7, min_value=0, max_value=1,
        description='Choose the latent heat recovery effectiveness. Only '
                    'applicable if heat_recovery_type="Enthalpy". Default: 0.7.'
    )
    outdoor_air_per_person = NumberSetting(
        default=7,
        min_value=0, max_value=25,
        description='Outdoor air per person in l/s. Defaults to 7 l/s '
                    'according to DIN EN 16798-1, Category II.'
    )
    outdoor_air_per_area = NumberSetting(
        default=0.7, min_value=0, max_value=10,
        description='Outdoor air per floor area in l/s. Defaults to 0.7 l/(s '
                    'm2) according to DIN EN 16798-1, Category II for low '
                    'emission buildings.'
    )
    residential = BooleanSetting(
        default=False, description='Choose True to use residential settings '
                                   'for natural ventilation (DIN4108-2), '
                                   'False for non-residential houses.'
    )
    natural_ventilation_approach = ChoiceSetting(
        default="Simple",
        description='Choose calculation approach for natural ventilation.',
        choices={
            "Simple": "use simplified ventilation based on TEASER templates.",
            "DIN4108": "use DIN4108-2 for natural ventilation."
        }
    )
