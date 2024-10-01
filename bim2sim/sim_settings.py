"""Module for defining simulation model specific process settings.
This targets both, settings to set for the later simulation and settings for the
model generation process in bim2sim.
"""
import logging
import ast
import os.path
from pathlib import Path
from typing import Union
import sys

from bim2sim.utilities import types
from bim2sim.utilities.types import LOD
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
        if not self.min_value:
            self.min_value = sys.float_info.epsilon
            logger.info(f'No min_value given for sim_setting {self}, assuming'
                        f'smallest float epsilon.')
        if not self.max_value:
            self.max_value = float('inf')
            logger.info(f'No max_value given for sim_setting {self}, assuming'
                        f'biggest float inf.')
        if self.default:
            if self.default > self.max_value or self.default < self.min_value:
                raise AttributeError(
                    f"The specified limits for min_value, max_value and"
                    f"default are contradictory min: {self.min_value} "
                    f"max: {self.max_value}")
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


class StringSetting(Setting):
    def __init__(
            self,
            default=None,
            description: Union[str, None] = None,
            for_frontend: bool = False
    ):
        super().__init__(default, description, for_frontend)

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
        if not isinstance(value, str):
            raise ValueError("The provided value is not a string.")
        else:
            return True


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
            if value is not None:
                try:
                    value = Path(value)
                except TypeError:
                    raise TypeError(
                        f"Could not convert the simulation setting for "
                        f"{self.name} into a path, please check the path.")
            # if default value is None this is ok
            elif value == self.default:
                pass
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

    tolerance_connect_by_position = NumberSetting(
        default=10,
        description="Tolerance for distance for which ports should be "
                    "connected. Based on there position in IFC.",
        for_frontend=True,
        min_value=1
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

    construction_class_doors = ChoiceSetting(
        default='kfw_40',
        choices={
            'kfw_40': 'Doors according to kfw 40 standard',
            'kfw_55': 'Doors according to kfw 55 standard',
            'kfw_70': 'Doors according to kfw 70 standard',
            'kfw_85': 'Doors according to kfw 85 standard',
            'kfw_100': 'Doors according to kfw 100 standard',
            'tabula_de_standard_1_SFH': 'Windows according to german tabula standard 1 for single family '
                                        'houses',
            'tabula_de_retrofit_1_SFH': 'Windows according to german tabula retrofit 1 for single family '
                                        'houses',
            'tabula_de_adv_retrofit_1_SFH': 'Windows according to german tabula advanced retrofit 1 for single '
                                            'family houses',
            'tabula_de_standard_1_TH': 'Windows according to german tabula standard 1 for terraced houses',
            'tabula_de_retrofit_1_TH': 'Windows according to german tabula retrofit 1 for terraced houses',
            'tabula_de_adv_retrofit_1_TH': 'Windows according to german tabula advanced retrofit 1 for terraced houses',
            'tabula_de_standard_1_MFH': 'Windows according to german tabula standard 1 for multi family houses',
            'tabula_de_retrofit_1_MFH': 'Windows according to german tabula retrofit 1 for multi family houses',
            'tabula_de_adv_retrofit_1_MFH': 'Windows according to german tabula advanced retrofit 1 for multi '
                                            'family houses',
            'tabula_de_standard_1_AB': 'Windows according to german tabula standard 1 for apartment blocks',
            'tabula_de_retrofit_1_AB': 'Windows according to german tabula retrofit 1 for apartment blocks',
            'tabula_de_adv_retrofit_1_AB': 'Windows according to german tabula advanced retrofit 1 for '
                                           'apartment blocks',
            'tabula_dk_standard_1_SFH': 'Windows according to danish tabula standard 1 for single family '
                                        'houses'
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
            "n_persons_rooms":
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

    update_emission_parameter_from_oekobdauat = BooleanSetting(
        default=False,
        description='Whether to update material emission parameter from Ökobaudat',
        for_frontend=True
    )
    calculate_lca_building = BooleanSetting(
        default=True,
        description='Whether to calculate lca of building or not',
        for_frontend=True
    )
    calculate_lca_hydraulic_system = BooleanSetting(
        default=True,
        description='Whether to calculate lca of building or not',
        for_frontend=True
    )
    pipe_type = ChoiceSetting(
        default='Stahlrohr',
        choices={
            'Stahlrohr': 'Stahlrohr',
            'Innenverzinne_Kupferrohre_pro_1kg': 'Kupferrohr'
        },
        description='Type of pipe used in hydraulic system'
                    'Should be the same as used in Plugin HydraulicSystem'
    )
    heat_delivery_type = ChoiceSetting(
        default=['Radiator'],
        choices={
            'Radiator': 'Radiator',
            'UFH': 'UFH',
            'UFH+Radiator': 'UFH+Radiator',
            'UFH+Air': 'UFH+Air',
        },
        description='Type of heat delivery'
                    'Should be the same as used in Plugin HydraulicSystem',
        multiple_choice=True,
        for_frontend=True
    )
    ufh_pipe_type = ChoiceSetting(
        default='PP',
        choices={
            'Copper': 'Copper',
            'PEX': 'PEX',
            'PP': 'PP',
        },
        description='Choose pipe material of under floor heating',
        for_frontend=True
    )
    hydraulic_system_material_xlsx = PathSetting(
        default= None,
        description='Path to the excel file which holds information'
                    'about used material in hydraulic system'
                    '(Output of PluginHydraulicSystem)',
        for_frontend=True
    )




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
    edit_mat_result_file_flag = BooleanSetting(
        default=False,
        description='Whether to change dymola mat result file or not.'
                    'Not generic at this time',
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
        description="Choose whether run period for simulation execution "
                    "should be set manually instead of running annual "
                    "simulation."
    )
    run_period_start_month=NumberSetting(
        default=1,
        min_value=1,
        max_value=12,
        description="Choose start month of run period. Requires "
                    "set_run_period==True for activation.",
        for_frontend=True
    )
    run_period_start_day=NumberSetting(
        default=1,
        min_value=1,
        max_value=31,
        description="Choose start day of run period. Requires "
                    "set_run_period==True for activation.",
        for_frontend=True
    )
    run_period_end_month=NumberSetting(
        default=12,
        min_value=1,
        max_value=12,
        description="Choose end month of run period. Requires "
                    "set_run_period==True for activation.",
        for_frontend=True
    )
    run_period_end_day=NumberSetting(
        default=31,
        min_value=1,
        max_value=31,
        description="Choose end day of run period. Requires "
                    "set_run_period==True for activation.",
        for_frontend=True
    )
    plot_singe_zone_guid = ChoiceSetting(
        default='',
        choices={'': "Skip"},
        description="Choose the GlobalId of the IfcSpace for which results "
                    "should be plotted.",
        any_string=True
    )
    # Due to issue #722 this is currently the only way to set AHU values.
    overwrite_ahu_by_settings = BooleanSetting(
        default=True,
        description='Overwrite central AHU settings with the following '
                    'settings.',
    )
    ahu_heating = BooleanSetting(
        default=False,
        description="Choose if the central AHU should provide heating. "
                    "Set overwrite_ahu_by_settings to True, "
                    "otherwise this has no effect. "
    )
    ahu_cooling = BooleanSetting(
        default=False,
        description="Choose if the central AHU should provide cooling."
                    "Set overwrite_ahu_by_settings to True, "
                    "otherwise this has no effect. "
    )
    ahu_dehumidification = BooleanSetting(
        default=False,
        description="Choose if the central AHU should provide "
                    "dehumidification."
                    "Set overwrite_ahu_by_settings to True, "
                    "otherwise this has no effect. "
    )
    ahu_humidification = BooleanSetting(
        default=False,
        description="Choose if the central AHU should provide humidification."
                    "Set overwrite_ahu_by_settings to True, "
                    "otherwise this has no effect. "
    )
    ahu_heat_recovery = BooleanSetting(
        default=False,
        description="Choose if the central AHU should zuse heat recovery."
                    "Set overwrite_ahu_by_settings to True, "
                    "otherwise this has no effect. "
    )
    ahu_heat_recovery_efficiency = NumberSetting(
        default=0.65,
        min_value= 0.5,
        max_value=0.99,
        description="Choose the heat recovery efficiency of the central AHU."
                    "Set overwrite_ahu_by_settings to True, "
                    "otherwise this has no effect. "
    )


class HydraulicSystemSimSettings(BuildingSimSettings):
    def __init__(self):
        super().__init__()
        self.relevant_elements = {*bps_elements.items, *hvac_elements.items,
                                  Material}

    generate_new_building_data = BooleanSetting(
        default=True,
        description="True: Generate new building data out of ifc file"
                    "Else: Load existing building data out of json file"
    )
    generate_new_building_graph = BooleanSetting(
        default=True,
        description="True: Generate new building graph out of ifc file"
                    "Else: Load existing building graph out of json file"
    )
    generate_new_heating_graph = BooleanSetting(
        default=True,
        description="True: Generate new heating graph out of ifc file"
                    "Else: Load existing heating graph out of json file"
    )
    generate_new_building_graph_with_source_nodes = BooleanSetting(
        default=False,
        description="Only for development purposes"
                    "True: Generate new building graph with source nodes out of building graph"
                    "Else: Load existing building graph with source nodes out of json file"
    )
    startpoint_heating_graph_x_axis = NumberSetting(
        default=None,
        min_value=-200,
        max_value=200,
        description="Start point of heating network graph on the x axis",
        for_frontend=True,
    )
    startpoint_heating_graph_y_axis = NumberSetting(
        default=None,
        min_value=-200,
        max_value=200,
        description="Start point of heating network graph on the y axis",
        for_frontend=True,
    )
    startpoint_heating_graph_z_axis = NumberSetting(
        default=None,
        min_value=-200,
        max_value=200,
        description="Start point of heating network graph on the z axis",
        for_frontend=True,
    )
    heat_demand_mat_file_path = PathSetting(
        default=None,
        description='Path to the dymola mat file which was generated by '
                    'bim2sim plugin teaser',
        for_frontend=True,
        mandatory=True
    )
    # TODO convert xlsx into json and translate to english
    hydraulic_components_data_file_path = PathSetting(
        default=Path(__file__).parent /
                'plugins/PluginHydraulicSystem/bim2sim_hydraulicsystem/assets/hydraulic_components.xlsx',
        description='Path to the data file which holds information'
                    'about possible hydraulic system components',
        for_frontend=True,
        mandatory=False
    )
    hydraulic_components_data_file_radiator_sheet = StringSetting(
        default="Stahlrohre",
        description='Name of sheet in hydraulic components data file'
                    'which holds data about the desired radiators',
        for_frontend=True
    )
    hydraulic_components_data_file_pipe_sheet = StringSetting(
        default="Profilierte Flachheizkörper",
        description='Name of sheet in hydraulic components data file'
                    'which holds data about the desired hydraulic pipes',
        for_frontend=True
    )
    one_pump_flag = BooleanSetting(
        default=True,
        description="Flags if only one pump is used"
    )
    heat_delivery_type = ChoiceSetting(
        default=['Radiator'],
        choices={
            'Radiator': 'Radiator',
            'UFH': 'UFH',
            'UFH+Radiator': 'UFH+Radiator',
            'UFH+Air': 'UFH+Air',
        },
        description='Choose type of heat delivery',
        multiple_choice=True,
        for_frontend=True
    )
    ufh_heat_flow_laying_distance_changeover = NumberSetting(
        default=70,
        min_value=0,
        max_value=150,
        description="Heat flow per area of under floor heating at which"
                    "laying distance of ufh changes from 100mm to 200mm",
        for_frontend=True
    )
    ufh_max_heat_flow_per_area = NumberSetting(
        default=100,
        min_value=0,
        max_value=150,
        description="Max heat flow per area of under floor heating"
                    "Further heat flow needs to be delivered e.g. by air or radiator",
        for_frontend=True
    )

    # Material parameter
    g = NumberSetting(
        default=9.81,
        min_value=0,
        max_value=5000,
        description="Gravity in m/s^2",
        for_frontend=True,
    )
    density_fluid = NumberSetting(
        default=1000,
        min_value=0,
        max_value=5000,
        description="Density of heating fluid in kg/m^3",
        for_frontend=True,
    )
    kinematic_velocity_fluid = NumberSetting(
        default=1.002,
        min_value=0,
        max_value=5000,
        description="Kinematic velocity of heating fluid in mm^2/s",
        for_frontend=True,
    )
    c_p_fluid = NumberSetting(
        default=4.18,
        min_value=0,
        max_value=5000,
        description="Heat capacity of heating fluid in kJ/kg/K",
        for_frontend=True,
    )
    v_mean = NumberSetting(
        default=1,
        min_value=0,
        max_value=10,
        description="Mean fluid velocity in m/s",
        for_frontend=True,
    )
    v_max = NumberSetting(
        default=2,
        min_value=0,
        max_value=10,
        description="Max fluid velocity in m/s",
        for_frontend=True,
    )
    p_max = NumberSetting(
        default=10,
        min_value=0,
        max_value=5000,
        description="Max pressure in hydraulic system in bar",
        for_frontend=True,
    )
    f = NumberSetting(
        default=0.02,
        min_value=0,
        max_value=5000,
        description="f value of radiator",
        for_frontend=True,
    )
    t_forward = NumberSetting(
        default=40,
        min_value=0,
        max_value=200,
        description="Forward heating temperature in °C",
        for_frontend=True,
    )
    t_backward = NumberSetting(
        default=30,
        min_value=0,
        max_value=200,
        description="Backward heating temperature in °C",
        for_frontend=True,
    )
    t_room = NumberSetting(
        default=20,
        min_value=0,
        max_value=100,
        description="Room temperature in °C",
        for_frontend=True,
    )
    density_pipe = NumberSetting(
        default=7850,
        min_value=0,
        max_value=100000,
        description="Density of pipe in kg/m^3",
        for_frontend=True,
    )
    absolute_roughness_pipe = NumberSetting(
        default=0.045,
        min_value=0,
        max_value=1,
        description="Absolute roughness of pipe",
        for_frontend=True,
    )

class VentilationSystemSimSettings(BuildingSimSettings):

    def __init__(self):
        super().__init__()
        self.relevant_elements = {*bps_elements.items,
                                      Material}

    ventilation_lca_airflow = BooleanSetting(
        default=True,
        description="Export the figures, plans and .csv data from for"
                    " ventilation supply generation"
    )
    ventilation_lca_export_supply = BooleanSetting(
        default=True,
        description="Export the figures, plans and .csv data from for"
                    " ventilation supply generation"
    )
    ventilation_lca_export_exhaust = BooleanSetting(
        default=True,
        description="Export the figures, plans and .csv data from for"
                    " ventilation exhaust generation"
    )
    ventilation_lca_system = BooleanSetting(
        default=True,
        description="Export the figures, plans and .csv data from for"
                    " ventilation supply generation"
    )

