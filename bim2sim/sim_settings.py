"""Module for defining simulation model specific process settings.
This targets both, settings to set for the later simulation and settings for
the model generation process in bim2sim.
"""

import logging
import ast
import os.path
from typing import Union, Optional, List
import sys
from pydantic import BaseModel, Field, model_validator, field_validator, FilePath
from pydantic_core import PydanticCustomError
from typing_extensions import Self
from enum import Enum

from bim2sim.utilities import types
from bim2sim.utilities.types import LOD
from bim2sim.elements.base_elements import Material
from bim2sim.elements import bps_elements as bps_elements, \
    hvac_elements as hvac_elements
from bim2sim.elements.mapping.ifc2python import check_guid


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

        >>> # create a new simulation setting, name will be taken automatic
        from
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
    defaults = {}

    def reset_settings_to_defaults(self) -> None:
        for name in self.defaults:
            setting = getattr(type(self.bound_simulation_settings), name)
            setting.value = self.defaults[name]

    def __init__(self, bound_simulation_settings):
        super().__init__()
        self.bound_simulation_settings = bound_simulation_settings
        self._create_settings()

    def _create_settings(self):
        """Add all listed settings from the simulation in its attributes."""
        for name in self.names:
            # Loads setting by name
            setting = getattr(type(self.bound_simulation_settings), name)
            self[name] = setting
            self.defaults[setting.name] = setting.value

    @property
    def names(self):
        """
        Returns a generator object with all settings that the bound_simulation_settings owns.
        """
        bound_simulation_settings_class = type(self.bound_simulation_settings)

        for attribute_name in dir(bound_simulation_settings_class):
            # Retrieve the attribute from the class using the name
            attribute = getattr(bound_simulation_settings_class, attribute_name)

            if isinstance(attribute, Setting):
                # If it is, yield the name of the attribute
                yield attribute_name


class Setting(BaseModel, validate_assignment=True, validate_default=True):
    value: None
    name: str = Field(default="set automatically")
    description: Optional[str] = None
    for_frontend: bool = Field(default=False)
    any_string: bool = Field(default=False)
    mandatory: bool = Field(default=False)


    def __set__(self, bound_simulation_settings, value):
        bound_simulation_settings.manager[self.name].value = value

    def __get__(self, bound_simulation_settings, owner):
        if bound_simulation_settings is None:
            return self

        return bound_simulation_settings.manager[self.name].value


class NumberSetting(Setting):
    value: Optional[float]
    min_value: Optional[float] = None
    max_value: Optional[float] = None

    @model_validator(mode='after')
    def check_setting_config(self) -> Self:
        if self.min_value is None:
            self.min_value = sys.float_info.epsilon
            logger.info(f'No min_value given for sim_setting {self}, assuming'
                        f'smallest float epsilon.')

        if self.max_value is None:
            self.max_value = float('inf')
            logger.info(f'No max_value given for sim_setting {self}, assuming'
                        f'biggest float inf.')

        if self.min_value > self.max_value:
            raise PydanticCustomError("contradictory_limits",
                                      f"The specified limits for min_value and max_value are "  # type: ignore[misc]
                                      f"contradictory min: {self.min_value} max: {self.max_value}")

        return self

    @model_validator(mode='after')
    def check_limits(self) -> Self:
        if self.value is not None:
            if not (self.min_value <= self.value <= self.max_value):
                raise PydanticCustomError(
                    "value_out_of_range",
                    f"value ({self.value}) must be between {self.min_value} and {self.max_value}"  # type: ignore[misc]
                )
        return self


class ChoiceSetting(Setting):
    value: Union[str, List[str], Enum]
    choices: dict
    multiple_choice: bool = False

    def _check_for_value_in_choices(self, value):
        if value not in self.choices:
            if not self.any_string:
                raise PydanticCustomError(
                    "value_not_in_choices",
                    f'{value} is no valid value for setting {self.name}, select one of {self.choices}.' # type: ignore[misc]
                )

    @field_validator('choices', mode='after')
    @classmethod
    def check_setting_config(cls, choices):
        for choice in choices:
            # Check for string type, to exclude enums
            if isinstance(choice, str) and "." in choice:
                raise PydanticCustomError("illegal_character",
                                          f"Provided setting {choice} contains character '.', this is prohibited.")  # type: ignore[misc]
        return choices

    @model_validator(mode='after')
    def check_content(self):
        if isinstance(self.value, list):
            if not self.multiple_choice:
                raise PydanticCustomError("one_choice_allowed", f'Only one choice is allowed for setting'  # type: ignore[misc]
                                                                f' {self.name}, but {len(self.value)} choices are given.')  # type: ignore[misc]
            else:
                for val in self.value:
                    self._check_for_value_in_choices(val)
        else:
            # Todo (chg-ext): Check for multiple choices allowed but only one choice given?
            self._check_for_value_in_choices(self.value)

        return self


class PathSetting(Setting):
    value: Optional[FilePath]


class BooleanSetting(Setting):
    value: Optional[bool]


class GuidListSetting(Setting):
    value: Optional[List[str]]

    @field_validator('value', mode='after')
    @classmethod
    def check_value(cls, value):
        for i, guid in enumerate(value):
            if not check_guid(guid):
                raise PydanticCustomError("invalid_guid",
                                          f"Invalid IFC GUID format at index {i}: '{guid}'")  # type: ignore[misc]
        return value


class BaseSimSettings(metaclass=AutoSettingNameMeta):
    """Specification of basic bim2sim simulation settings which are common for
    all simulations"""

    def __init__(self, filters: list = None):
        self.manager = SettingsManager(bound_simulation_settings=self)

        self.relevant_elements = {}
        self.simulated = False

    def load_default_settings(self):
        pass

    def update_from_config(self, config):
        """Updates the simulation settings specification from the config
        file"""
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
                            elif isinstance(set_from_cfg, str) and \
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
        value=False,
        description="Run a Simulation with Dymola after model export?",
        for_frontend=True,
    )

    create_external_elements = BooleanSetting(
        value=False,
        description='Create external elements?',
        for_frontend=True
    )

    max_wall_thickness = NumberSetting(
        value=0.3,
        max_value=0.60,
        min_value=1e-3,
        description='Choose maximum wall thickness as a tolerance for mapping '
                    'opening boundaries to their base surface (Wall). '
                    'Choose 0.3m as a default value.',
        for_frontend=True
    )

    group_unidentified = ChoiceSetting(
        value='fuzzy',
        choices={
            'fuzzy': 'Use fuzzy search to find ifc name similarities',
            'name': 'Only group elements with exact same ifc name',
            'name_and_description': 'Only group elements with the same ifc'
                                    ' name and ifc description'
        },
        description='To reduce the number of decisions by user to identify '
                    'elements which can not be identified automatically by '
                    'the '
                    'system, you can either use simple grouping by same name '
                    'of'
                    ' IFC element or fuzzy search to group based on'
                    ' similarities in name.',
        for_frontend=True,
    )

    group_unidentified_ = ChoiceSetting(
        value='fuzzy',
        choices={
            'fuzzy': 'Use fuzzy search to find ifc name similarities',
            'name': 'Only group elements with exact same ifc name',
            'name_and_description': 'Only group elements with the same ifc'
                                    ' name and ifc description'
        },
        description='To reduce the number of decisions by user to identify '
                    'elements which can not be identified automatically by '
                    'the '
                    'system, you can either use simple grouping by same name '
                    'of'
                    ' IFC element or fuzzy search to group based on'
                    ' similarities in name.',
        for_frontend=True
    )

    fuzzy_threshold = NumberSetting(
        value=0.7,
        min_value=0.5,
        max_value=0.9,
        description='If you want to use fuzzy search in the '
                    'group_unidentified '
                    'setting, you can set the threshold here. A low '
                    'threshold means'
                    ' a small similarity is required for grouping. A too low '
                    'value '
                    'might result in grouping elements which do not represent '
                    'the same IFC type.'
    )

    reset_guids = BooleanSetting(
        value=False,
        description='Reset GlobalIDs from imported IFC if duplicate '
                    'GlobalIDs occur in the IFC. As EnergyPlus evaluates all'
                    'GlobalIDs upper case only, this might also be '
                    'applicable if duplicate non-case-sensitive GlobalIDs '
                    'occur.',
        for_frontend=True
    )

    weather_file_path = PathSetting(
        value=None,
        description='Path to the weather file that should be used for the '
                    'simulation. If no path is provided, we will try to get '
                    'the'
                    'location from the IFC and download a fitting weather'
                    ' file. For Modelica provide .mos files, for EnergyPlus '
                    '.epw files. If the format does not fit, we will try to '
                    'convert.',
        for_frontend=True,
        mandatory=True
    )

    building_rotation_overwrite = NumberSetting(
        value=0,
        min_value=0,
        max_value=359,
        description='Overwrite the (clockwise) building rotation angle in '
                    'degrees.',
        for_frontend=True
    )

    add_space_boundaries = BooleanSetting(
        value=False,
        description='Add space boundaries. Only required for building '
                    'performance simulation and co-simulations.',
        for_frontend=True
    )
    correct_space_boundaries = BooleanSetting(
        value=False,
        description='Apply geometric correction to space boundaries.',
        for_frontend=True
    )
    close_space_boundary_gaps = BooleanSetting(
        value=False,
        description='Close gaps in the set of space boundaries by adding '
                    'additional 2b space boundaries.',
        for_frontend=True
    )

    stories_to_load_guids = GuidListSetting(
        value=[],
        description='List of IFC GUIDs for the specific stories that should '
                    'be loaded. If empty, all stories will be considered '
                    'for loading. This setting is useful for large buildings '
                    'to reduce computational time. Note that loading single '
                    'storeys may lead to missing ceilings if the related '
                    'slab is assigned to the storey above, which may require '
                    'corrections to boundary conditions.'
                    ' It is recommended to include GUIDs of neighboring'
                    ' storeys to reduce boundary condition errors.',
        for_frontend=True,
        mandatory=False
    )


class PlantSimSettings(BaseSimSettings):
    def __init__(self):
        super().__init__(
        )
        self.relevant_elements = {*hvac_elements.items, Material}

    # Todo maybe make every aggregation its own setting with LOD in the future,
    #  but currently we have no usage for this afaik.
    aggregations = ChoiceSetting(
        value=[
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
        value=10,
        description="Tolerance for distance for which ports should be "
                    "connected. Based on there position in IFC.",
        for_frontend=True,
        min_value=1
    )

    verify_connection_by_position = BooleanSetting(
        value=True,
        description="Choose if connection of elements via IfcDistributionPorts"
                    " should be validated by the geometric position of the "
                    "ports."
    )


class BuildingSimSettings(BaseSimSettings):

    def __init__(self):
        super().__init__()
        self.relevant_elements = {*bps_elements.items,
                                  Material}

    layers_and_materials = ChoiceSetting(
        value=LOD.low,
        choices={
            LOD.low: 'Override materials with predefined setups',
            # LOD.full: 'Get all information from IFC and enrich if needed'
        },
        description='Select how existing Material information in IFC should '
                    'be treated.',
        for_frontend=True
    )
    year_of_construction_overwrite = NumberSetting(
        value=None,
        min_value=0,
        max_value=2015,
        description="Force an overwrite of the year of construction as a "
                    "base for the selected construction set.",
        for_frontend=True,
    )
    construction_class_walls = ChoiceSetting(
        value='iwu_heavy',
        choices={
            'iwu_heavy': 'Wall structures according to iwu heavy standard',
            'iwu_light': 'Wall structures according to iwu light standard',
            'kfw_40': 'Wall structures according to kfw 40 standard',
            'kfw_55': 'Wall structures according to kfw 55 standard',
            'kfw_70': 'Wall structures according to kfw 70 standard',
            'kfw_85': 'Wall structures according to kfw 85 standard',
            'kfw_100': 'Wall structures according to kfw 100 standard',
            'tabula_de_standard_1_SFH': 'Wall structures according to german '
                                        'tabula standard 1 for single family '
                                        'houses',
            'tabula_de_standard_2_SFH': 'Wall structures according to german '
                                        'tabula standard 2 for single family '
                                        'houses',
            'tabula_de_retrofit_1_SFH': 'Wall structures according to german '
                                        'tabula retrofit 1 for single family '
                                        'houses',
            'tabula_de_retrofit_2_SFH': 'Wall structures according to german '
                                        'tabula retrofit 2 for single family '
                                        'houses',
            'tabula_de_adv_retrofit_1_SFH': 'Wall structures according to '
                                            'german tabula advanced retrofit '
                                            '1 for single '
                                            'family houses',
            'tabula_de_adv_retrofit_2_SFH': 'Wall structures according to '
                                            'german tabula advanced retrofit '
                                            '2 for '
                                            'single family houses',
            'tabula_de_standard_1_TH': 'Wall structures according to german '
                                       'tabula standard 1 for terraced houses',
            'tabula_de_standard_2_TH': 'Wall structures according to german '
                                       'tabula standard 2 for terraced houses',
            'tabula_de_retrofit_1_TH': 'Wall structures according to german '
                                       'tabula retrofit 1 for terraced houses',
            'tabula_de_retrofit_2_TH': 'Wall structures according to german '
                                       'tabula retrofit 2 for terraced houses',
            'tabula_de_standard_1_MFH': 'Wall structures according to german '
                                        'tabula standard 1 for multi family '
                                        'houses',
            'tabula_de_retrofit_1_MFH': 'Wall structures according to german '
                                        'tabula retrofit 1 for multi family '
                                        'houses',
            'tabula_de_adv_retrofit_1_MFH': 'Wall structures according to '
                                            'german tabula advanced retrofit '
                                            '1 for multi '
                                            'family houses',
            'tabula_de_standard_1_AB': 'Wall structures according to german '
                                       'tabula standard 1 for apartment '
                                       'blocks',
            'tabula_de_adv_retrofit_1_AB': 'Wall structures according to '
                                           'german tabula advanced retrofit '
                                           '1 for '
                                           'apartment blocks',
            'tabula_de_standard': 'Wall structures according to german '
                                  'tabula standard',
            'tabula_dk_standard_1_SFH': 'Wall structures according to danish '
                                        'tabula standard 1 for single family '
                                        'houses',
            'tabula_dk_standard_2_SFH': 'Wall structures according to danish '
                                        'tabula standard 2 for single family '
                                        'houses',
            'tabula_dk_retrofit_1_SFH': 'Wall structures according to danish '
                                        'tabula retrofit 1 for single family '
                                        'houses',
            'tabula_dk_retrofit_2_SFH': 'Wall structures according to danish '
                                        'tabula retrofit 2 for single family '
                                        'houses',
            'tabula_dk_adv_retrofit_1_SFH': 'Wall structures according to '
                                            'danish tabula advanced retrofit '
                                            '1 for single '
                                            'family houses',
            'tabula_dk_adv_retrofit_2_SFH': 'Wall structures according to '
                                            'danish tabula advanced retrofit '
                                            '2 for single '
                                            'family houses',
            'tabula_dk_standard_1_TH': 'Wall structures according to danish '
                                       'tabula standard 1 for terraced houses',
            'tabula_dk_standard_2_TH': 'Wall structures according to danish '
                                       'tabula standard 2 for terraced houses',
            'tabula_dk_retrofit_1_TH': 'Wall structures according to danish '
                                       'tabula retrofit 1 for terraced houses',
            'tabula_dk_retrofit_2_TH': 'Wall structures according to danish '
                                       'tabula retrofit 1 for terraced houses',
            'tabula_dk_adv_retrofit_1_TH': 'Wall structures according to '
                                           'danish tabula advanced retrofit '
                                           '1 for '
                                           'terraced houses',
            'tabula_dk_adv_retrofit_2_TH': 'Wall structures according to '
                                           'danish tabula advanced retrofit '
                                           '1 for '
                                           'terraced houses',
            'tabula_dk_standard_1_AB': 'Wall structures according to danish '
                                       'tabula standard 1 for apartment '
                                       'blocks',
            'tabula_dk_standard_2_AB': 'Wall structures according to danish '
                                       'tabula standard 2 for apartment '
                                       'blocks',
            'tabula_dk_retrofit_1_AB': 'Wall structures according to danish '
                                       'tabula retrofit 1 for apartment '
                                       'blocks',
            'tabula_dk_retrofit_2_AB': 'Wall structures according to danish '
                                       'tabula retrofit 2 for apartment '
                                       'blocks',
            'tabula_dk_adv_retrofit_1_AB': 'Wall structures according to '
                                           'danish tabula advanced retrofit '
                                           '1 for '
                                           'apartment blocks',
            'tabula_dk_adv_retrofit_2_AB': 'Wall structures according to '
                                           'danish tabula advanced retrofit '
                                           '2 for '
                                           'apartment blocks',
            'tabula_dk_standard': 'Wall structures according to danish '
                                  'tabula standard'
        },
        description="Select the most fitting construction class type for"
                    "the walls of the selected building. For all settings but "
                    "kfw_* the  year of construction is required.",
        for_frontend=True
    )

    construction_class_windows = ChoiceSetting(
        value='Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach',
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
            'tabula_de_standard_1_SFH': 'Windows according to german tabula '
                                        'standard 1 for single family '
                                        'houses',
            'tabula_de_standard_2_SFH': 'Windows according to german tabula '
                                        'standard 2 for single family '
                                        'houses',
            'tabula_de_retrofit_1_SFH': 'Windows according to german tabula '
                                        'retrofit 1 for single family '
                                        'houses',
            'tabula_de_retrofit_2_SFH': 'Windows according to german tabula '
                                        'retrofit 2 for single family '
                                        'houses',
            'tabula_de_adv_retrofit_1_SFH': 'Windows according to german '
                                            'tabula advanced retrofit 1 for '
                                            'single '
                                            'family houses',
            'tabula_de_adv_retrofit_2_SFH': 'Windows according to german '
                                            'tabula advanced retrofit 2 for '
                                            'single family houses',
            'tabula_de_standard_1_TH': 'Windows according to german tabula '
                                       'standard 1 for terraced houses',
            'tabula_de_standard_2_TH': 'Windows according to german tabula '
                                       'standard 2 for terraced houses',
            'tabula_de_retrofit_1_TH': 'Windows according to german tabula '
                                       'retrofit 1 for terraced houses',
            'tabula_de_retrofit_2_TH': 'Windows according to german tabula '
                                       'retrofit 2 for terraced houses',
            'tabula_de_standard_1_MFH': 'Windows according to german tabula '
                                        'standard 1 for multi family houses',
            'tabula_de_retrofit_1_MFH': 'Windows according to german tabula '
                                        'retrofit 1 for multi family houses',
            'tabula_de_adv_retrofit_1_MFH': 'Windows according to german '
                                            'tabula advanced retrofit 1 for '
                                            'multi '
                                            'family houses',
            'tabula_de_standard_1_AB': 'Windows according to german tabula '
                                       'standard 1 for apartment blocks',
            'tabula_de_adv_retrofit_1_AB': 'Windows according to german '
                                           'tabula advanced retrofit 1 for '
                                           'apartment blocks',
            'tabula_de_standard': 'Windows according to german tabula '
                                  'standard',
            'tabula_dk_standard_1_SFH': 'Windows according to danish tabula '
                                        'standard 1 for single family '
                                        'houses',
            'tabula_dk_standard_2_SFH': 'Windows according to danish tabula '
                                        'standard 2 for single family '
                                        'houses',
            'tabula_dk_retrofit_1_SFH': 'Windows according to danish tabula '
                                        'retrofit 1 for single family '
                                        'houses',
            'tabula_dk_retrofit_2_SFH': 'Windows according to danish tabula '
                                        'retrofit 2 for single family '
                                        'houses',
            'tabula_dk_adv_retrofit_1_SFH': 'Windows according to danish '
                                            'tabula advanced retrofit 1 for '
                                            'single '
                                            'family houses',
            'tabula_dk_adv_retrofit_2_SFH': 'Windows according to danish '
                                            'tabula advanced retrofit 2 for '
                                            'single '
                                            'family houses',
            'tabula_dk_standard_1_TH': 'Windows according to danish tabula '
                                       'standard 1 for terraced houses',
            'tabula_dk_standard_2_TH': 'Windows according to danish tabula '
                                       'standard 2 for terraced houses',
            'tabula_dk_retrofit_1_TH': 'Windows according to danish tabula '
                                       'retrofit 1 for terraced houses',
            'tabula_dk_retrofit_2_TH': 'Windows according to danish tabula '
                                       'retrofit 1 for terraced houses',
            'tabula_dk_adv_retrofit_1_TH': 'Windows according to danish '
                                           'tabula advanced retrofit 1 for '
                                           'terraced houses',
            'tabula_dk_adv_retrofit_2_TH': 'Windows according to danish '
                                           'tabula advanced retrofit 1 for '
                                           'terraced houses',
            'tabula_dk_standard_1_AB': 'Windows according to danish tabula '
                                       'standard 1 for apartment blocks',
            'tabula_dk_standard_2_AB': 'Windows according to danish tabula '
                                       'standard 2 for apartment blocks',
            'tabula_dk_retrofit_1_AB': 'Windows according to danish tabula '
                                       'retrofit 1 for apartment blocks',
            'tabula_dk_retrofit_2_AB': 'Windows according to danish tabula '
                                       'retrofit 2 for apartment blocks',
            'tabula_dk_adv_retrofit_1_AB': 'Windows according to danish '
                                           'tabula advanced retrofit 1 for '
                                           'apartment blocks',
            'tabula_dk_adv_retrofit_2_AB': 'Windows according to danish '
                                           'tabula advanced retrofit 2 for '
                                           'apartment blocks',
            'tabula_dk_standard': 'Windows according to danish tabula standard'
        },
        description="Select the most fitting construction class type for"
                    " the windows of the selected building.",
    )
    construction_class_doors = ChoiceSetting(
        value='iwu_typical',
        choices={
            'iwu_typical': 'Typical door data based',
            'kfw_40': 'Doors according to kfw 40 standard',
            'kfw_55': 'Doors according to kfw 55 standard',
            'kfw_70': 'Doors according to kfw 70 standard',
            'kfw_85': 'Doors according to kfw 85 standard',
            'kfw_100': 'Doors according to kfw 100 standard',
            'tabula_de_standard_1_SFH': 'Windows according to german tabula '
                                        'standard 1 for single family '
                                        'houses',
            'tabula_de_retrofit_1_SFH': 'Windows according to german tabula '
                                        'retrofit 1 for single family '
                                        'houses',
            'tabula_de_adv_retrofit_1_SFH': 'Windows according to german '
                                            'tabula advanced retrofit 1 for '
                                            'single '
                                            'family houses',
            'tabula_de_standard_1_TH': 'Windows according to german tabula '
                                       'standard 1 for terraced houses',
            'tabula_de_retrofit_1_TH': 'Windows according to german tabula '
                                       'retrofit 1 for terraced houses',
            'tabula_de_adv_retrofit_1_TH': 'Windows according to german '
                                           'tabula advanced retrofit 1 for '
                                           'terraced houses',
            'tabula_de_standard_1_MFH': 'Windows according to german tabula '
                                        'standard 1 for multi family houses',
            'tabula_de_retrofit_1_MFH': 'Windows according to german tabula '
                                        'retrofit 1 for multi family houses',
            'tabula_de_adv_retrofit_1_MFH': 'Windows according to german '
                                            'tabula advanced retrofit 1 for '
                                            'multi '
                                            'family houses',
            'tabula_de_standard_1_AB': 'Windows according to german tabula '
                                       'standard 1 for apartment blocks',
            'tabula_de_retrofit_1_AB': 'Windows according to german tabula '
                                       'retrofit 1 for apartment blocks',
            'tabula_de_adv_retrofit_1_AB': 'Windows according to german '
                                           'tabula advanced retrofit 1 for '
                                           'apartment blocks',
            'tabula_dk_standard_1_SFH': 'Windows according to danish tabula '
                                        'standard 1 for single family '
                                        'houses'
        },
        description="Select the most fitting construction class type for"
                    " the windows of the selected building.",
    )
    heating_tz_overwrite = BooleanSetting(
        value=None,
        description='If True, all thermal zones will be provided with heating,'
                    'if False no heating for thermal zones is provided, '
                    'regardless of information in the IFC or in the use '
                    'condition file.',
        for_frontend=True
    )
    cooling_tz_overwrite = BooleanSetting(
        value=None,
        description='If True, all thermal zones will be provided with cooling,'
                    'if False no cooling for thermal zones is provided, '
                    'regardless of information in the IFC or in the use '
                    'condition file.',
        for_frontend=True
    )
    ahu_tz_overwrite = BooleanSetting(
        value=None,
        description='If True, all thermal zones will be provided with AHU,'
                    'if False no AHU for thermal zones is provided, '
                    'regardless of information in the IFC or in the use '
                    'condition file.',
        for_frontend=True
    )
    prj_use_conditions = PathSetting(
        value=None,
        description="Path to a custom UseConditions.json for the specific "
                    "project, that holds custom usage conditions for this "
                    "project. If this is used, this use_conditions file have "
                    "to hold all information. The basic UseConditions.json "
                    "file is ignored in this case.",
        for_frontend=True
    )
    prj_custom_usages = PathSetting(
        value=None,
        description="Path to a custom customUsages.json for the specific "
                    "project, that holds mappings between space names from "
                    "IFC "
                    "and usage conditions from UseConditions.json.",
        for_frontend=True
    )
    setpoints_from_template = BooleanSetting(
        value=False,
        description="Use template heating and cooling profiles instead of "
                    "setpoints from IFC. Defaults to False, i.e., "
                    "use original data source. Set to True, "
                    "if template-based values should be used instead.",
        for_frontend=True
    )
    use_maintained_illuminance = BooleanSetting(
        value=True,
        description="Use maintained illuminance required per zone based on "
                    "DIN V EN 18599 information to calculate internal loads"
                    "through lighting.",
        for_frontend=True
    )
    sim_results = ChoiceSetting(
        value=[
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
        value=True,
        description='Add space boundaries. Only required for building '
                    'performance simulation and co-simulations.',
        for_frontend=True
    )
    correct_space_boundaries = BooleanSetting(
        value=False,
        description='Apply geometric correction to space boundaries.',
        for_frontend=True
    )
    split_bounds = BooleanSetting(
        value=False,
        description='Whether to convert up non-convex space boundaries or '
                    'not.',
        for_frontend=True
    )
    add_shadings = BooleanSetting(
        value=False,
        description='Whether to add shading surfaces if available or not.',
        for_frontend=True
    )
    split_shadings = BooleanSetting(
        value=False,
        description='Whether to convert up non-convex shading boundaries or '
                    'not.',
        for_frontend=True
    )
    close_space_boundary_gaps = BooleanSetting(
        value=False,
        description='Close gaps in the set of space boundaries by adding '
                    'additional 2b space boundaries.',
        for_frontend=True
    )
    create_plots = BooleanSetting(
        value=False,
        description='Create plots for simulation results after the simulation '
                    'finished.',
        for_frontend=True
    )
    set_run_period = BooleanSetting(
        value=False,
        description="Choose whether run period for simulation execution "
                    "should be set manually instead of running annual "
                    "simulation."
    )
    run_period_start_month = NumberSetting(
        value=1,
        min_value=1,
        max_value=12,
        description="Choose start month of run period. Requires "
                    "set_run_period==True for activation.",
        for_frontend=True
    )
    run_period_start_day = NumberSetting(
        value=1,
        min_value=1,
        max_value=31,
        description="Choose start day of run period. Requires "
                    "set_run_period==True for activation.",
        for_frontend=True
    )
    run_period_end_month = NumberSetting(
        value=12,
        min_value=1,
        max_value=12,
        description="Choose end month of run period. Requires "
                    "set_run_period==True for activation.",
        for_frontend=True
    )
    run_period_end_day = NumberSetting(
        value=31,
        min_value=1,
        max_value=31,
        description="Choose end day of run period. Requires "
                    "set_run_period==True for activation.",
        for_frontend=True
    )
    plot_singe_zone_guid = ChoiceSetting(
        value='',
        choices={'': "Skip"},
        description="Choose the GlobalId of the IfcSpace for which results "
                    "should be plotted.",
        any_string=True
    )
    ahu_heating_overwrite = BooleanSetting(
        value=None,
        description="Choose if the central AHU should provide heating. "
    )
    ahu_cooling_overwrite = BooleanSetting(
        value=None,
        description="Choose if the central AHU should provide cooling."
    )
    ahu_dehumidification_overwrite = BooleanSetting(
        value=None,
        description="Choose if the central AHU should provide "
                    "dehumidification."
    )
    ahu_humidification_overwrite = BooleanSetting(
        value=None,
        description="Choose if the central AHU should provide humidification."
                    "otherwise this has no effect. "
    )
    ahu_heat_recovery_overwrite = BooleanSetting(
        value=None,
        description="Choose if the central AHU should zuse heat recovery."
    )
    ahu_heat_recovery_efficiency_overwrite = NumberSetting(
        value=None,
        min_value=0.5,
        max_value=0.99,
        description="Choose the heat recovery efficiency of the central AHU."
    )
    use_constant_infiltration_overwrite = BooleanSetting(
        value=None,
        description="If only constant base infiltration should be used and no "
                    "dynamic ventilation through e.g. windows."
    )
    base_infiltration_rate_overwrite = NumberSetting(
        value=None,
        min_value=0.001,
        max_value=5,
        description="Overwrite base value for the natural infiltration in 1/h "
                    " without window openings"
    )
