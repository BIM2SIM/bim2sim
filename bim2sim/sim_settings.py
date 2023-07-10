"""Module for defining simulation model specific process settings.
This targets both, settings to set for the later simulation and settings for the
model generation process in bim2sim.
"""
import logging
import ast
from typing import Union

from bim2sim.utilities import types
from bim2sim.utilities.types import LOD, ZoningCriteria
from bim2sim.elements.base_elements import Material
from bim2sim.elements import bps_elements as bps_elements,\
    hvac_elements as hvac_elements

logger = logging.getLogger(__name__)


class AutoSettingNameMeta(type):
    """Adds the name to every SimulationSetting attribute based on its instance
    name.

    This makes the definition of an extra attribute 'name' obsolete, as the
    attributes 'name' is automatic defined based on the instance name.


    Example:
        >>> # create new simulation settings for your awesome simulation
        >>> class MyAwesomeSimulationSettings(BaseSimSettings):
        ...     def __init__(self):
        ...         super().__init__()

        >>> # create a new simulation setting, name will be taken automatic from
        >>> # instance name
        >>> make_simulation_extra_fast = Setting(
        ...     default=True,
        ...     choices={
            ...         True: 'This simulation will be incredible fast.',
            ...         False: 'This simulation will be increbdile slow.'
            ...     },
            ...     description='Run the simulation in extra fast mode?',
            ...     for_frontend=True
            ... )

        >>> # create a SimulationSettings instance and get the value
        >>> my_awesome_settings = MyAwesomeSimulationSettings()
        >>> # get initial value which is always none
        >>> print(my_awesome_settings.make_simulation_extra_fast)
        None
        >>> # set default values and get the value
        >>> my_awesome_settings.load_default_settings()
        >>> print(my_awesome_settings.make_simulation_extra_fast)
        True
"""

    def __init__(cls, name, bases, namespace):
        super(AutoSettingNameMeta, cls).__init__(name, bases, namespace)
        # get all namespace objects
        for name, obj in namespace.items():
            # filter for settings of simulaiton
            if isinstance(obj, Setting):
                # provide name of the setting as attribute
                obj.name = name


class SettingsManager(dict):
    """Manages the different settings of a SimulationSettings instance.

    The manager is needed to maintain the different attributes of a simulation
    (e.g. choices) while making the read and write access to the setting still
    easy. This way you can call sim_settings.<setting_name> and get the value
    directly while under sim_settings.manager.<setting_name> you can still find
    all information.

    Args:
        bound_simulation_settings: instance of sim_settings this manager is
        bound to. E.g. BuildingSimSettings.
    """

    def __init__(self, bound_simulation_settings):
        super().__init__()
        self.bound_simulation_settings = bound_simulation_settings
        self._create_settings()

    def _create_settings(self):
        """Add all listed settings from the simulation in its attributes."""
        for name in self.names:
            setting = getattr(type(self.bound_simulation_settings), name)
            setting.initialize(self)

    @property
    def names(self):
        """Returns a generator object with all settings that the
         bound_simulation_settings owns."""
        return (name for name in dir(type(self.bound_simulation_settings))
                if isinstance(getattr(type(self.bound_simulation_settings), name),
                              Setting))


class Setting:
    """Define specific settings regarding model creation and simulation.

    Args:
        default: default value that will be applied when calling load_default()
        choices: dict of possible choice for this setting as key and a
        description per choice as value
        description: description of what the settings does as Str
        for_frontend: should this setting be shown in the frontend
        multiple_choice: allows multiple choice
        any_string: any string is allowed instead of a given choice
    """

    def __init__(

            self,
            default=None,
            choices: dict = None,
            description: Union[str, None] = None,
            for_frontend: bool = False,
            multiple_choice: bool = False,
            any_string: bool = False
    ):
        self.name = None  # set by AutoSettingNameMeta
        self.default = default
        self.value = None
        self.choices = choices
        self.description = description
        self.for_webapp = for_frontend
        self.multiple_choice = multiple_choice
        self.any_string = any_string
        self.manager = None

    def initialize(self, manager):
        """Link between manager stored setting and direct setting of simulation
        """
        if not self.name:
            raise AttributeError("Attribute.name not set!")
        self.check_choices()
        self.manager = manager
        self.manager[self.name] = self
        self.manager[self.name].value = None

    def check_choices(self):
        """make sure str choices don't hold '.' as this is seperator for enums.
        """
        for choice in self.choices:
            if isinstance(choice, str) and '.' in choice:
                if '.' in choice:
                    raise AttributeError(
                        f"Provided setting {choice} has a choice with character"
                        f" '.', this is prohibited.")

    def load_default(self):
        if not self.value:
            self.value = self.default

    def __get__(self, bound_simulation_settings, owner):
        """This is the get function that provides the value of the
        simulation setting when calling sim_settings.<setting_name>"""
        if bound_simulation_settings is None:
            return self

        return self._inner_get(bound_simulation_settings)

    def _inner_get(self, bound_simulation_settings):
        """Gets the value for the setting from the manager."""
        return bound_simulation_settings.manager[self.name].value

    def _inner_set(self, bound_simulation_settings, value):
        """Sets the value for the setting inside the manager."""
        bound_simulation_settings.manager[self.name].value = value

    def __set__(self, bound_simulation_settings, value):
        """This is the set function that sets the value in the simulation setting
        when calling sim_settings.<setting_name> = <value>"""
        choices = bound_simulation_settings.manager[self.name].choices
        if isinstance(value, list):
            if not self.multiple_choice:
                raise ValueError(f'Only one choice is allowed for setting'
                                 f' {self.name}, but {len(value)} choices '
                                 f'are given.')
            for val in value:
                if val not in choices:
                    raise ValueError(f'{val} is no valid value for setting '
                                     f'{self.name}, select one of {choices}.')
                else:
                    self._inner_set(bound_simulation_settings, value)
        else:
            if self.any_string and not isinstance(value, str):
                raise ValueError(f'{value} is no valid value for setting '
                                 f'{self.name}, please enter a string.')
            elif value not in choices and not self.any_string:
                raise ValueError(f'{value} is no valid value for setting '
                                 f'{self.name}, select one of {choices}.')
            else:
                self._inner_set(bound_simulation_settings, value)


class BaseSimSettings(metaclass=AutoSettingNameMeta):
    """Specification of basic bim2sim simulation settings which are common for
    all simulations"""

    def __init__(self,
                 filters: list = None):
        self.manager = SettingsManager(bound_simulation_settings=self)

        self.relevant_elements = {}
        self.simulated = False
        self.load_default_settings()

    def load_default_settings(self):
        """loads default values for all settings"""
        for setting in self.manager.values():
            setting.load_default()

    def update_from_config(self, config):
        """Updates the simulation settings specification from the config file"""
        n_loaded_settings = 0
        for cat, settings in config.items():
            # don't load settings which are not simulation relevant
            if cat.lower() not in [
                self.__class__.__name__.lower(),
                'Generic Simulation Settings'
            ]:
                continue
            cat_from_cfg = config[cat]
            for setting in settings:
                if not hasattr(self, setting):
                    raise AttributeError(
                        f'{setting} is no allowed setting for '
                        f'simulation {self.__class__.__name__} ')
                else:
                    set_from_cfg = cat_from_cfg.get(setting)
                    if set_from_cfg is None:
                        continue
                    elif isinstance(set_from_cfg, str):
                        # convert to readable python object
                        try:
                            # todo ast.literal_eval is safer but not safe.
                            set_from_cfg = ast.literal_eval(set_from_cfg)
                        except (ValueError, SyntaxError):
                            pass
                        # handle Enums (will not be found by literal_eval)
                        if isinstance(set_from_cfg, str) and\
                                '.' in set_from_cfg:
                            enum_type, enum_val = set_from_cfg.split('.')
                            # convert str to enum
                            try:
                                enum_type = getattr(types, enum_type)
                                val = getattr(enum_type, enum_val)
                            except AttributeError:
                                raise AttributeError(
                                    f" Tried to create the enumeration "
                                    f"{enum_type} but it doesn't exist.")
                        else:
                            val = set_from_cfg
                        setattr(self, setting, val)
                        n_loaded_settings += 1
                    else:
                        raise TypeError(
                            f'Config entry for {setting} is no string. '
                            f'Please use strings only in config.')
        logger.info(f'Loaded {n_loaded_settings} settings from config file.')

    dymola_simulation = Setting(
        default=False,
        choices={
            True: 'Run a Simulation with Dymola afterwards',
            False: 'Run no Simulation and only export model'
        },
        description='Run a Simulation after model export?',
        for_frontend=True
    )
    create_external_elements = Setting(
        default=False,
        choices={
            True: 'Create external elements',
            False: 'Create external elements'
        },
        description='Create external elements?',
        for_frontend=True
    )
    max_wall_thickness = Setting(
        default=0.3,
        choices={
            1e-3: 'Tolerance only for opening displacement',
            0.30: 'Maximum Wall Thickness of 0.3m',
            0.35: 'Maximum Wall Thickness of 0.35m',
            0.40: 'Maximum Wall Thickness of 0.4m'
        },
        description='Choose maximum wall thickness as a tolerance for mapping '
                    'opening boundaries to their base surface (Wall). '
                    'Choose 0.3m as a default value.',
        for_frontend=True
    )

    group_unidentified = Setting(
        default='fuzzy',
        choices={
            'fuzzy': 'Use fuzzy search to find name similarities',
            'name': 'Only group elements with exact same name'
        },
        description='To reduce the number of decisions by user to identify '
                    'elements which can not be identified automatically by the '
                    'system, you can either use simple grouping by same name of'
                    ' IFC element or fuzzy search to group based on'
                    ' similarities in name.',
        for_frontend=True
    )
    fuzzy_threshold = Setting(
        default=0.7,
        choices={
            0.5: 'Threshold of 0.5',
            0.6: 'Threshold of 0.6',
            0.7: 'Threshold of 0.7',
            0.8: 'Threshold of 0.8',
            0.9: 'Threshold of 0.9'
        },
        description='If you want to use fuzzy search in the group_unidentified '
                    'setting, you can set the threshold here. A low threshold means'
                    ' a small similarity is required for grouping. A too low value '
                    'might result in grouping elements which do not represent '
                    'the same IFC type.'
    )

    reset_guids = Setting(
        default=False,
        choices={
            True: 'Reset GlobalIDs from IFC ',
            False: 'Keep GlobalIDs from IFC'
        },
        description='Reset GlobalIDs from imported IFC if duplicate '
                    'GlobalIDs occur in the IFC. As EnergyPlus evaluates all'
                    'GlobalIDs upper case only, this might also be '
                    'applicable if duplicate non-case-sensitive GlobalIDs '
                    'occur.',
        for_frontend=True
    )


class PlantSimSettings(BaseSimSettings):
    def __init__(self):
        super().__init__(
        )
        self.relevant_elements = {*hvac_elements.items, Material}

    # Todo maybe make every aggregation its own setting with LOD in the future,
    #  but currently we have no usage for this afaik.
    aggregations = Setting(
        default=[
            'UnderfloorHeating',
            'PipeStrand',
            'Consumer',
            'ParallelPump',
            'ConsumerHeatingDistributorModule',
            'GeneratorOneFluid',
        ],
        choices={
            'UnderfloorHeating': 'Aggregate underfloor heating circuits',
            'Consumer': 'Aggregate consumers',
            'PipeStrand': 'Aggregate strands of pipes',
            'ParallelPump': 'Aggregate parallel pumps',
            'ConsumerHeatingDistributorModule': 'Aggregate consumer and '
                                                'distributor to one module',
            'GeneratorOneFluid': 'Aggregate the generator and its circuit to '
                                 'one module',
        },
        description="Which aggregations should be applied on the hydraulic "
                    "network",
        multiple_choice=True,
        for_frontend=True
    )


class BuildingSimSettings(BaseSimSettings):

    def __init__(self):
        super().__init__()
        self.relevant_elements = {*bps_elements.items,
                                  Material} - {bps_elements.Plate}

    layers_and_materials = Setting(
        default=LOD.low,
        choices={
            LOD.low: 'Override materials with predefined setups',
            LOD.full: 'Get all information from IFC and enrich if needed'
        },
        description='Select how existing Material information in IFC should '
                    'be treated.',
        for_frontend=True
    )

    construction_class_walls = Setting(
        default='heavy',
        choices={
            'heavy': 'Heavy wall structures.',
            'light': 'Light wall structures.'
        },
        description="Select the most fitting type of construction class for"
                    " the walls of the selected building.",
        for_frontend=True
    )
    construction_class_windows = Setting(
        default='Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach',
        choices={
            'Holzfenster, zweifach':
                'Zeifachverglasung mit Holzfenstern',
            'Kunststofffenster, Isolierverglasung':
                'Isolierverglasung mit Kunststofffensern',
            'Alu- oder Stahlfenster, Isolierverglasung':
                'Isolierverglasung mit Alu- oder Stahlfenstern',
            'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach':
                'Wärmeschutzverglasung (zweifach) mit Alu- oder '
                'Stahlfenstern',
            'Waermeschutzverglasung, dreifach':
                'Wärmeschutzverglasung (dreifach)',
        },
        description="Select the most fitting type of construction class for"
                    " the windows of the selected building.",
    )
    heating = Setting(
        default=True,
        choices={
            False: 'Do not supply building with heating',
            True: 'Supply building with heating'
        },
        description='Whether the building should be supplied with heating.',
        for_frontend=True
    )
    cooling = Setting(
        default=False,
        choices={
            False: 'Do not supply building with cooling',
            True: 'Supply building with cooling'
        },
        description='Whether the building should be supplied with cooling.',
        for_frontend=True
    )
    
    deactivate_ahu = Setting(
        default=False,
        choices={
            True: 'Deactivates the AHU for all thermal zones.',
            False: 'If a thermal zone uses an AHU will be decided based on the '
                   'given IFC data and the usage used for enrichment.'
        },
        description='If True the AHU unit will be deactivated for all thermal'
                    ' zones, even if the fitting use condition uses an AHU.',
        for_frontend=True
    )


class CFDSimSettings(BaseSimSettings):
    # todo make something useful
    def __init__(self):
        super().__init__()
        self.relevant_elements = \
            {*bps_elements.items, Material} - {bps_elements.Plate}


class LCAExportSettings(BaseSimSettings):
    """Life Cycle Assessment analysis with CSV Export of the selected BIM Model
     """
    def __init__(self):
        super().__init__()
        self.relevant_elements = \
            {*hvac_elements.items} | {*bps_elements.items} | {Material}


# TODO #511 Plugin specific sim_settings temporary needs to be stored here to
#  prevent import problems during integration tests
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
        default=ZoningCriteria.usage,
        choices={
            ZoningCriteria.external:
                'Group all thermal zones that have contact to the exterior'
                ' together and all thermal zones that do not have contact to'
                ' exterior.',
            ZoningCriteria.external_orientation:
                'Like external, but takes orientation '
                '(North, east, south, west)'
                ' into account as well',
            ZoningCriteria.usage:
                'Group all thermal zones that have the same usage.',
            ZoningCriteria.external_orientation_usage:
                'Combines the prior options.',
            ZoningCriteria.all_criteria:
                'Uses all prior options and adds glass percentage of the rooms'
                ' as additional criteria and only groups rooms if they are'
                ' adjacent to each other.'
        },
        for_frontend=True
    )


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
        default=f'/usr/local/EnergyPlus-9-4-0/',
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
