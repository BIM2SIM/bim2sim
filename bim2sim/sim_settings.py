"""Module for defining simulation model specific process settings.
This targets both, settings to set for the later simulation and settings for the
model generation process in bim2sim.
"""
import logging
import ast
import os.path
from pathlib import Path
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
        mandatory: whether a setting needs to be set
    """

    def __init__(
            self,
            default=None,
            description: Union[str, None] = None,
            for_frontend: bool = False,
            any_string: bool = False,
            mandatory=False
    ):
        self.name = None  # set by AutoSettingNameMeta
        self.default = default
        self.value = None
        self.description = description
        self.for_webapp = for_frontend
        self.any_string = any_string
        self.mandatory = mandatory
        self.manager = None

    def initialize(self, manager):
        """Link between manager stored setting and direct setting of simulation
        """
        if not self.name:
            raise AttributeError("Attribute.name not set!")
        self.check_setting_config()
        self.manager = manager
        self.manager[self.name] = self
        self.manager[self.name].value = None

    def check_setting_config(self):
        """Checks if the setting is configured correctly"""
        return True

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

    def check_value(self, bound_simulation_settings, value):
        """Checks the value that should be set for correctness

        Args:
            bound_simulation_settings: the sim setting belonging to the value
            value: value that should be checked for correctness
        Returns:
            True: if check was successful
        Raises:
            ValueError: if check was not successful
            """
        return True

    def __set__(self, bound_simulation_settings, value):
        """This is the set function that sets the value in the simulation
        setting when calling sim_settings.<setting_name> = <value>"""
        if self.check_value(bound_simulation_settings, value):
            self._inner_set(bound_simulation_settings, value)


class NumberSetting(Setting):
    def __init__(
            self,
            default=None,
            description: Union[str, None] = None,
            for_frontend: bool = False,
            any_string: bool = False,
            min_value: float = None,
            max_value: float = None
    ):
        super().__init__(default, description, for_frontend, any_string)
        self.min_value = min_value
        self.max_value = max_value

    def check_setting_config(self):
        """Make sure min and max values are reasonable"""
        if self.min_value > self.max_value:
            raise AttributeError(
                f"The specified limits for min_value and max_value are "
                f"contradictory min: {self.min_value} max: {self.max_value}")
        else:
            return True

    def check_value(self, bound_simulation_settings, value):
        """Checks the value that should be set for correctness

        Checks if value is in limits.
        Args:
            bound_simulation_settings: the sim setting belonging to the value
            value: value that should be checked for correctness
        Returns:
            True: if check was successful
        Raises:
            ValueError: if check was not successful
            """
        # None is allowed for settings that should not be used at all but have
        #  number values if used
        if value is None:
            return True
        if not isinstance(value, (float, int)):
            raise ValueError("The provided value is not a number.")
        if self.min_value <= value <= self.max_value:
            return True
        else:
            raise ValueError(
                f"The provided value is not inside the limits: min: "
                f"{self.min_value}, max: {self.max_value}, value: {value}")


class ChoiceSetting(Setting):
    def __init__(
            self,
            default=None,
            description: Union[str, None] = None,
            for_frontend: bool = False,
            any_string: bool = False,
            choices: dict = None,
            multiple_choice: bool = False
    ):
        super().__init__(default, description, for_frontend, any_string)
        self.choices = choices
        self.multiple_choice = multiple_choice

    def check_setting_config(self):
        """make sure str choices don't hold '.' as this is seperator for enums.
        """
        for choice in self.choices:
            if isinstance(choice, str) and '.' in choice:
                if '.' in choice:
                    raise AttributeError(
                        f"Provided setting {choice} has a choice with character"
                        f" '.', this is prohibited.")
        return True

    def check_value(self, bound_simulation_settings, value):
        """Checks the value that should be set for correctness

        Checks if the selected value is in choices.
        Args:
            bound_simulation_settings: the sim setting belonging to the value
            value: value that should be checked for correctness
        Returns:
            True: if check was successful
        Raises:
            ValueError: if check was not successful
            """
        choices = bound_simulation_settings.manager[self.name].choices
        if isinstance(value, list):
            if not self.multiple_choice:
                raise ValueError(f'Only one choice is allowed for setting'
                                 f' {self.name}, but {len(value)} choices '
                                 f'are given.')
            for val in value:
                self.check_value(bound_simulation_settings, val)
            return True
        else:
            if self.any_string and not isinstance(value, str):
                raise ValueError(f'{value} is no valid value for setting '
                                 f'{self.name}, please enter a string.')
            elif value not in choices and not self.any_string:
                raise ValueError(f'{value} is no valid value for setting '
                                 f'{self.name}, select one of {choices}.')
            else:
                return True


class PathSetting(Setting):
    def check_value(self, bound_simulation_settings, value):
        """Checks the value that should be set for correctness

        Checks if the value is a valid path
        Args:
            bound_simulation_settings: the sim setting belonging to the value
            value: value that should be checked for correctness
        Returns:
            True: if check was successful
        Raises:
            ValueError: if check was not successful
            """
        # check for existence
        # TODO #556 Do not check default path for existence because this might
        #  not exist on system. This is a hack and should be solved when
        #  improving communication between config and settings
        if not value == self.default:
            if not value.exists():
                raise FileNotFoundError(
                    f"The path provided for '{self.name}' does not exist."
                    f" Please check the provided setting path which is: "
                    f"{str(value)}")
        return True

    def __set__(self, bound_simulation_settings, value):
        """This is the set function that sets the value in the simulation setting
        when calling sim_settings.<setting_name> = <value>"""
        if not isinstance(value, Path):
            if value:
                try:
                    value = Path(value)
                except TypeError:
                    raise TypeError(
                        f"Could not convert the simulation setting for "
                        f"{self.name} into a path, please check the path.")
            else:
                raise ValueError(f"No Path provided for setting {self.name}.")
        if self.check_value(bound_simulation_settings, value):
            self._inner_set(bound_simulation_settings, value)


class BooleanSetting(Setting):
    def check_value(self, bound_simulation_settings, value):
        if not isinstance(value, bool):
            raise ValueError(f"The provided value {value} is not a Boolean")
        else:
            return True


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
                            set_from_cfg = ast.literal_eval(str(set_from_cfg))
                        except (ValueError, SyntaxError):
                            logger.warning(f'Failed literal evaluation of '
                                           f'{set_from_cfg}. Proceeding.')
                        if isinstance(set_from_cfg, str):
                            # handle all strings that are file paths, before
                            # handling Enums
                            if os.path.isfile(set_from_cfg):
                                val = set_from_cfg
                            # handle Enums (will not be found by literal_eval)
                            elif isinstance(set_from_cfg, str) and\
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
                                # handle all other strings
                                val = set_from_cfg
                        else:
                            # handle all other data types
                            val = set_from_cfg
                        setattr(self, setting, val)
                        n_loaded_settings += 1
                    else:
                        raise TypeError(
                            f'Config entry for {setting} is no string. '
                            f'Please use strings only in config.')
        logger.info(f'Loaded {n_loaded_settings} settings from config file.')

    def check_mandatory(self):
        """Check if mandatory settings have a value."""
        for setting in self.manager.values():
            if setting.mandatory:
                if not setting.value:
                    raise ValueError(
                        f"Attempted to run project. Simulation setting "
                        f"{setting.name} is not specified, "
                        f"but is marked as mandatory. Please configure "
                        f"{setting.name} before running your project.")

    dymola_simulation = BooleanSetting(
        default=False,
        description='Run a Simulation with Dymola after model export?',
        for_frontend=True
    )
    create_external_elements = BooleanSetting(
        default=False,
        description='Create external elements?',
        for_frontend=True
    )
    max_wall_thickness = NumberSetting(
        default=0.3,
        max_value=0.60,
        min_value=1e-3,
        description='Choose maximum wall thickness as a tolerance for mapping '
                    'opening boundaries to their base surface (Wall). '
                    'Choose 0.3m as a default value.',
        for_frontend=True
    )

    group_unidentified = ChoiceSetting(
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
    fuzzy_threshold = NumberSetting(
        default=0.7,
        min_value=0.5,
        max_value=0.9,
        description='If you want to use fuzzy search in the group_unidentified '
                    'setting, you can set the threshold here. A low threshold means'
                    ' a small similarity is required for grouping. A too low value '
                    'might result in grouping elements which do not represent '
                    'the same IFC type.'
    )

    reset_guids = BooleanSetting(
        default=False,
        description='Reset GlobalIDs from imported IFC if duplicate '
                    'GlobalIDs occur in the IFC. As EnergyPlus evaluates all'
                    'GlobalIDs upper case only, this might also be '
                    'applicable if duplicate non-case-sensitive GlobalIDs '
                    'occur.',
        for_frontend=True
    )

    weather_file_path = PathSetting(
        default=None,
        description='Path to the weather file that should be used for the '
                    'simulation. If no path is provided, we will try to get the'
                    'location from the IFC and download a fitting weather'
                    ' file. For Modelica provide .mos files, for EnergyPlus '
                    '.epw files. If the format does not fit, we will try to '
                    'convert.',
        for_frontend=True,
        mandatory=True
    )
    add_space_boundaries = BooleanSetting(
        default=False,
        description='Add space boundaries. Only required for building '
                    'performance simulation and co-simulations.',
        for_frontend=True
    )
    correct_space_boundaries = BooleanSetting(
        default=False,
        description='Apply geometric correction to space boundaries.',
        for_frontend=True
    )
    close_space_boundary_gaps = BooleanSetting(
        default=False,
        description='Close gaps in the set of space boundaries by adding '
                    'additional 2b space boundaries.',
        for_frontend=True
    )


class PlantSimSettings(BaseSimSettings):
    def __init__(self):
        super().__init__(
        )
        self.relevant_elements = {*hvac_elements.items, Material}

    # Todo maybe make every aggregation its own setting with LOD in the future,
    #  but currently we have no usage for this afaik.
    aggregations = ChoiceSetting(
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
                                  Material}

    layers_and_materials = ChoiceSetting(
        default=LOD.low,
        choices={
            LOD.low: 'Override materials with predefined setups',
            # LOD.full: 'Get all information from IFC and enrich if needed'
        },
        description='Select how existing Material information in IFC should '
                    'be treated.',
        for_frontend=True
    )
    construction_class_walls = ChoiceSetting(
        default='iwu_heavy',
        choices={
            'iwu_heavy': 'Wall structures according to iwu heavy standard',
            'iwu_light': 'Wall structures according to iwu light standard',
            'kfw_40': 'Wall structures according to kfw 40 standard',
            'kfw_55': 'Wall structures according to kfw 55 standard',
            'kfw_70': 'Wall structures according to kfw 70 standard',
            'kfw_85': 'Wall structures according to kfw 85 standard',
            'kfw_100': 'Wall structures according to kfw 100 standard',
            'tabula_de_standard_1_SFH': 'Wall structures according to german tabula standard 1 for single family '
                                        'houses',
            'tabula_de_standard_2_SFH': 'Wall structures according to german tabula standard 2 for single family '
                                        'houses',
            'tabula_de_retrofit_1_SFH': 'Wall structures according to german tabula retrofit 1 for single family '
                                        'houses',
            'tabula_de_retrofit_2_SFH': 'Wall structures according to german tabula retrofit 2 for single family '
                                        'houses',
            'tabula_de_adv_retrofit_1_SFH': 'Wall structures according to german tabula advanced retrofit 1 for single '
                                            'family houses',
            'tabula_de_adv_retrofit_2_SFH': 'Wall structures according to german tabula advanced retrofit 2 for '
                                            'single family houses',
            'tabula_de_standard_1_TH': 'Wall structures according to german tabula standard 1 for terraced houses',
            'tabula_de_standard_2_TH': 'Wall structures according to german tabula standard 2 for terraced houses',
            'tabula_de_retrofit_1_TH': 'Wall structures according to german tabula retrofit 1 for terraced houses',
            'tabula_de_retrofit_2_TH': 'Wall structures according to german tabula retrofit 2 for terraced houses',
            'tabula_de_standard_1_MFH': 'Wall structures according to german tabula standard 1 for multi family houses',
            'tabula_de_retrofit_1_MFH': 'Wall structures according to german tabula retrofit 1 for multi family houses',
            'tabula_de_adv_retrofit_1_MFH': 'Wall structures according to german tabula advanced retrofit 1 for multi '
                                            'family houses',
            'tabula_de_standard_1_AB': 'Wall structures according to german tabula standard 1 for apartment blocks',
            'tabula_de_adv_retrofit_1_AB': 'Wall structures according to german tabula advanced retrofit 1 for '
                                           'apartment blocks',
            'tabula_de_standard': 'Wall structures according to german tabula standard',
            'tabula_dk_standard_1_SFH': 'Wall structures according to danish tabula standard 1 for single family '
                                        'houses',
            'tabula_dk_standard_2_SFH': 'Wall structures according to danish tabula standard 2 for single family '
                                        'houses',
            'tabula_dk_retrofit_1_SFH': 'Wall structures according to danish tabula retrofit 1 for single family '
                                        'houses',
            'tabula_dk_retrofit_2_SFH': 'Wall structures according to danish tabula retrofit 2 for single family '
                                        'houses',
            'tabula_dk_adv_retrofit_1_SFH': 'Wall structures according to danish tabula advanced retrofit 1 for single '
                                            'family houses',
            'tabula_dk_adv_retrofit_2_SFH': 'Wall structures according to danish tabula advanced retrofit 2 for single '
                                            'family houses',
            'tabula_dk_standard_1_TH': 'Wall structures according to danish tabula standard 1 for terraced houses',
            'tabula_dk_standard_2_TH': 'Wall structures according to danish tabula standard 2 for terraced houses',
            'tabula_dk_retrofit_1_TH': 'Wall structures according to danish tabula retrofit 1 for terraced houses',
            'tabula_dk_retrofit_2_TH': 'Wall structures according to danish tabula retrofit 1 for terraced houses',
            'tabula_dk_adv_retrofit_1_TH': 'Wall structures according to danish tabula advanced retrofit 1 for '
                                           'terraced houses',
            'tabula_dk_adv_retrofit_2_TH': 'Wall structures according to danish tabula advanced retrofit 1 for '
                                           'terraced houses',
            'tabula_dk_standard_1_AB': 'Wall structures according to danish tabula standard 1 for apartment blocks',
            'tabula_dk_standard_2_AB': 'Wall structures according to danish tabula standard 2 for apartment blocks',
            'tabula_dk_retrofit_1_AB': 'Wall structures according to danish tabula retrofit 1 for apartment blocks',
            'tabula_dk_retrofit_2_AB': 'Wall structures according to danish tabula retrofit 2 for apartment blocks',
            'tabula_dk_adv_retrofit_1_AB': 'Wall structures according to danish tabula advanced retrofit 1 for '
                                           'apartment blocks',
            'tabula_dk_adv_retrofit_2_AB': 'Wall structures according to danish tabula advanced retrofit 2 for '
                                           'apartment blocks',
            'tabula_dk_standard': 'Wall structures according to danish tabula standard'
        },
        description="Select the most fitting construction class type for"
                    "the walls of the selected building.",
        for_frontend=True
    )

    construction_class_windows = ChoiceSetting(
        default='Waermeschutzverglasung, dreifach',
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
            'tabula_de_standard_1_SFH': 'Windows according to german tabula standard 1 for single family '
                                        'houses',
            'tabula_de_standard_2_SFH': 'Windows according to german tabula standard 2 for single family '
                                        'houses',
            'tabula_de_retrofit_1_SFH': 'Windows according to german tabula retrofit 1 for single family '
                                        'houses',
            'tabula_de_retrofit_2_SFH': 'Windows according to german tabula retrofit 2 for single family '
                                        'houses',
            'tabula_de_adv_retrofit_1_SFH': 'Windows according to german tabula advanced retrofit 1 for single '
                                            'family houses',
            'tabula_de_adv_retrofit_2_SFH': 'Windows according to german tabula advanced retrofit 2 for '
                                            'single family houses',
            'tabula_de_standard_1_TH': 'Windows according to german tabula standard 1 for terraced houses',
            'tabula_de_standard_2_TH': 'Windows according to german tabula standard 2 for terraced houses',
            'tabula_de_retrofit_1_TH': 'Windows according to german tabula retrofit 1 for terraced houses',
            'tabula_de_retrofit_2_TH': 'Windows according to german tabula retrofit 2 for terraced houses',
            'tabula_de_standard_1_MFH': 'Windows according to german tabula standard 1 for multi family houses',
            'tabula_de_retrofit_1_MFH': 'Windows according to german tabula retrofit 1 for multi family houses',
            'tabula_de_adv_retrofit_1_MFH': 'Windows according to german tabula advanced retrofit 1 for multi '
                                            'family houses',
            'tabula_de_standard_1_AB': 'Windows according to german tabula standard 1 for apartment blocks',
            'tabula_de_adv_retrofit_1_AB': 'Windows according to german tabula advanced retrofit 1 for '
                                           'apartment blocks',
            'tabula_de_standard': 'Windows according to german tabula standard',
            'tabula_dk_standard_1_SFH': 'Windows according to danish tabula standard 1 for single family '
                                        'houses',
            'tabula_dk_standard_2_SFH': 'Windows according to danish tabula standard 2 for single family '
                                        'houses',
            'tabula_dk_retrofit_1_SFH': 'Windows according to danish tabula retrofit 1 for single family '
                                        'houses',
            'tabula_dk_retrofit_2_SFH': 'Windows according to danish tabula retrofit 2 for single family '
                                        'houses',
            'tabula_dk_adv_retrofit_1_SFH': 'Windows according to danish tabula advanced retrofit 1 for single '
                                            'family houses',
            'tabula_dk_adv_retrofit_2_SFH': 'Windows according to danish tabula advanced retrofit 2 for single '
                                            'family houses',
            'tabula_dk_standard_1_TH': 'Windows according to danish tabula standard 1 for terraced houses',
            'tabula_dk_standard_2_TH': 'Windows according to danish tabula standard 2 for terraced houses',
            'tabula_dk_retrofit_1_TH': 'Windows according to danish tabula retrofit 1 for terraced houses',
            'tabula_dk_retrofit_2_TH': 'Windows according to danish tabula retrofit 1 for terraced houses',
            'tabula_dk_adv_retrofit_1_TH': 'Windows according to danish tabula advanced retrofit 1 for '
                                           'terraced houses',
            'tabula_dk_adv_retrofit_2_TH': 'Windows according to danish tabula advanced retrofit 1 for '
                                           'terraced houses',
            'tabula_dk_standard_1_AB': 'Windows according to danish tabula standard 1 for apartment blocks',
            'tabula_dk_standard_2_AB': 'Windows according to danish tabula standard 2 for apartment blocks',
            'tabula_dk_retrofit_1_AB': 'Windows according to danish tabula retrofit 1 for apartment blocks',
            'tabula_dk_retrofit_2_AB': 'Windows according to danish tabula retrofit 2 for apartment blocks',
            'tabula_dk_adv_retrofit_1_AB': 'Windows according to danish tabula advanced retrofit 1 for '
                                           'apartment blocks',
            'tabula_dk_adv_retrofit_2_AB': 'Windows according to danish tabula advanced retrofit 2 for '
                                           'apartment blocks',
            'tabula_dk_standard': 'Windows according to danish tabula standard'
        },
        description="Select the most fitting construction class type for"
                    " the windows of the selected building.",
    )
    year_of_construction_overwrite = NumberSetting(
        default=None,
        min_value=0,
        max_value=2015,
        description="Force an overwrite of the year of construction as a "
                    "base for the selected construction set.",
        for_frontend=True,
    )    
    heating = BooleanSetting(
        default=True,
        description='Whether the building should be supplied with heating.',
        for_frontend=True
    )
    cooling = BooleanSetting(
        default=False,
        description='Whether the building should be supplied with cooling.',
        for_frontend=True
    )
    deactivate_ahu = BooleanSetting(
        default=False,
        description='If True the AHU unit will be deactivated for all thermal'
                    ' zones, even if the fitting use condition uses an AHU.',
        for_frontend=True
    )
    prj_use_conditions = PathSetting(
        default=None,
        description="Path to a custom UseConditions.json for the specific "
                    "project, that holds custom usage conditions for this "
                    "project.",
        for_frontend=True
    )
    prj_custom_usages = PathSetting(
        default=None,
        description="Path to a custom customUsages.json for the specific "
                    "project, that holds mappings between space names from IFC "
                    "and usage conditions from UseConditions.json.",
        for_frontend=True
    )
    setpoints_from_template = BooleanSetting(
        default=False,
        description="Use template heating and cooling profiles instead of "
                    "setpoints from IFC. Defaults to False, i.e., "
                    "use original data source. Set to True, "
                    "if template-based values should be used instead.",
        for_frontend=True
    )
    sim_results = ChoiceSetting(
        default=[
            "heat_demand_total", "cool_demand_total",
            "heat_demand_rooms", "cool_demand_rooms",
            "heat_energy_total", "cool_energy_total",
            "heat_energy_rooms", "cool_energy_rooms",
            "air_temp_out", "operative_temp_rooms", "air_temp_rooms",
            "internal_gains_machines_rooms", "internal_gains_persons_rooms",
            "internal_gains_lights_rooms", "n_persons_rooms",
            "infiltration_rooms", "mech_ventilation_rooms",
            "heat_set_rooms", "cool_set_rooms"

                 ],
        choices={
            "heat_demand_total":
                "Total heating demand (power) as time series data",
            "cool_demand_total":
                "Total cooling demand (power) as time series data",
            "heat_demand_rooms":
                "Zone based heating demand (power) as time series data",
            "cool_demand_rooms":
                "Zone based cooling demand (power) as time series data",
            "heat_energy_total":
                "Total heating energy as time series data",
            "cool_energy_total":
                "Total cooling energy as time series data",
            "heat_energy_rooms":
                "Zone based heating energy as time series data",
            "cool_energy_rooms":
                "Zone cooling heating energy as time series data",
            "air_temp_out":
                "Outdoor air temperature as time series data",
            "operative_temp_rooms":
                "Zone based operative temperature as time series data",
            "air_temp_rooms":
                "Zone based indoor air temperature as time series data",
            "internal_gains_machines_rooms":
                "Internal gains through machines in W as time series data",
            "internal_gains_persons_rooms":
                "Internal gains through persons in W as time series data",
            "internal_gains_lights_rooms":
                "Internal gains through lights in W as time series data",
            "amount_persons_rooms":
                "Total amount of occupying persons as time series data",
            "infiltration_rooms":
                "Infiltration into room in 1/h as time series data",
            "mech_ventilation_rooms":
                "Mechanical ventilation flow in m³/h as time series data",
            "heat_set_rooms":
                "Heating set point in °C time series data",
            "cool_set_rooms":
                "Cooling set point in °C time series data",
        },
        multiple_choice=True,
    )
    add_space_boundaries = BooleanSetting(
        default=True,
        description='Add space boundaries. Only required for building '
                    'performance simulation and co-simulations.',
        for_frontend=True
    )
    correct_space_boundaries = BooleanSetting(
        default=False,
        description='Apply geometric correction to space boundaries.',
        for_frontend=True
    )
    split_bounds = BooleanSetting(
        default=False,
        description='Whether to convert up non-convex space boundaries or '
                    'not.',
        for_frontend=True
    )
    add_shadings = BooleanSetting(
        default=False,
        description='Whether to add shading surfaces if available or not.',
        for_frontend=True
    )
    split_shadings = BooleanSetting(
        default=False,
        description='Whether to convert up non-convex shading boundaries or '
                    'not.',
        for_frontend=True
    )
    close_space_boundary_gaps = BooleanSetting(
        default=False,
        description='Close gaps in the set of space boundaries by adding '
                    'additional 2b space boundaries.',
        for_frontend=True
    )
    fix_type_mismatches_with_sb = BooleanSetting(
        default=True,
        description='The definition of IFC elements might be faulty in some '
                    'IFCs. E.g. Roofs or Groundfloors that are defined as'
                    'Slabs with predefined type FLOOR. When activated, '
                    'the bim2sim elements are corrected based on the space '
                    'boundary information regarding external/internal.',
        for_frontend=True
    )
    create_plots = BooleanSetting(
        default=False,
        description='Create plots for simulation results after the simulation '
                    'finished.',
        for_frontend=True
    )


class CFDSimSettings(BaseSimSettings):
    # todo make something useful
    def __init__(self):
        super().__init__()
        self.relevant_elements = \
            {*bps_elements.items, Material}


# TODO dont use BuildingSimSettings as basis for LCA anymore
class LCAExportSettings(BuildingSimSettings):
    """Life Cycle Assessment analysis with CSV Export of the selected BIM Model
     """
    def __init__(self):
        super().__init__()
        self.relevant_elements = {*bps_elements.items, *hvac_elements.items,
                                  Material}



# TODO #511 Plugin specific sim_settings temporary needs to be stored here to
#  prevent import problems during integration tests
class TEASERSimSettings(BuildingSimSettings):
    """Defines simulation settings for TEASER Plugin.

    This class defines the simulation settings for the TEASER Plugin. It
    inherits all choices from the BuildingSimulation settings. TEASER
    specific settings are added here..
    """

    zoning_setup = ChoiceSetting(
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

    zoning_criteria = ChoiceSetting(
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
            '22-2-0': 'EnergyPlus Version 22-2-0'  # todo: Test latest version
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


class ComfortSimSettings(EnergyPlusSimSettings):
    def __init__(self):
        super().__init__()

    prj_use_conditions = PathSetting(
        default=Path(__file__).parent /
                'plugins/PluginComfort/bim2sim_comfort/assets'
                '/UseConditionsComfort.json',
        description="Path to a custom UseConditions.json for the specific "
                    "comfort application. These use conditions have "
                    "comfort-based use conditions as a default.",
        for_frontend=True
    )
    use_dynamic_clothing = BooleanSetting(
        default=False,
        description='Use dynamic clothing according to ASHRAE 55 standard.',
        for_frontend=True
    )
    rename_plot_keys = BooleanSetting(
        default=False,
        description='Rename room names for plot results',
        for_frontend=True
    )
    rename_plot_keys_path = PathSetting(
        default=Path(__file__).parent /
                'plugins/PluginComfort/bim2sim_comfort/assets/rename_plot_keys'
                '.json',
        description="Path for renaming the zone keys for plot results. Path "
                    "to a json file with pairs of current keys and new keys. ",
        for_frontend=True
    )