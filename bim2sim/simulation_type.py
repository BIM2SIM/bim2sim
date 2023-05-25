"""Module for defining workflows"""
import logging
import ast
from typing import Union

from bim2sim.utilities.types import LOD

logger = logging.getLogger(__name__)


class AutoSettingNameMeta(type):
    """Adds the name to every WorkFlowSetting attribute based on its instance
    name.

    This makes the definition of an extra attribute 'name' obsolete, as the
    attributes 'name' is automatic defined based on the instance name.


    Example:
        >>> # create new Workflow for your awesome simulation
        >>> class MyAwesomeSimulationWorfklow(SimType):
        ...     def __init__(self):
        ...         super().__init__()

        >>> # create a new WorkflowSetting, name will be taken automatic from
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

        >>> # create a workflow instance and get the value
        >>> my_awesome_workflow = MyAwesomeSimulationWorfklow()
        >>> # get initial value which is always none
        >>> print(my_awesome_workflow.make_simulation_extra_fast)
        None
        >>> # set default values and get the value
        >>> my_awesome_workflow.load_default_settings()
        >>> print(my_awesome_workflow.make_simulation_extra_fast)
        True
"""

    def __init__(cls, name, bases, namespace):
        super(AutoSettingNameMeta, cls).__init__(name, bases, namespace)
        # get all namespace objects
        for name, obj in namespace.items():
            # filter for WorkflowSettings
            if isinstance(obj, Setting):
                # provide name of the setting as attribute
                obj.name = name


class SettingsManager(dict):
    """Manages the different settings of a workflow.

    The manager is needed to maintain the different attributes of a workflow
    (e.g. choices) while making the read and write access to the setting still
    easy. This way you can call workflow.<setting_name> and get the value
    directly while under workflow.manager.<setting_name> you can still find all
    information.
    """

    def __init__(self, bound_workflow):
        super().__init__()
        self.bound_workflow = bound_workflow
        self._create_settings_in_workflow()

    def _create_settings_in_workflow(self):
        """Add all listed settings from the workflow in its attributes."""
        for name in self.names:
            setting = getattr(type(self.bound_workflow), name)
            setting.initialize(self)

    @property
    def names(self):
        """Returns a generator object with all settings that the bound_workflow
         owns."""
        return (name for name in dir(type(self.bound_workflow))
                if isinstance(getattr(type(self.bound_workflow), name),
                              Setting))


class Setting:
    """Define different settings regarding model creation and simulation.

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
        """Link between manager stored setting and direct setting of workflow"""
        if not self.name:
            raise AttributeError("Attribute.name not set!")
        self.manager = manager
        self.manager[self.name] = self
        self.manager[self.name].value = None

    def load_default(self):
        if not self.value:
            self.value = self.default

    def __get__(self, bound_workflow, owner):
        """This is the get function that provides the value of the
        workflow setting when calling workflow.<setting_name>"""
        if bound_workflow is None:
            return self

        return self._inner_get(bound_workflow)

    def _inner_get(self, bound_workflow):
        """Gets the value for the setting from the manager."""
        return bound_workflow.manager[self.name].value

    def _inner_set(self, bound_workflow, value):
        """Sets the value for the setting inside the manager."""
        bound_workflow.manager[self.name].value = value

    def __set__(self, bound_workflow, value):
        """This is the set function that sets the value in the workflow setting
        when calling workflow.<setting_name> = <value>"""
        choices = bound_workflow.manager[self.name].choices
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
                    self._inner_set(bound_workflow, value)
        else:
            if self.any_string and not isinstance(value, str):
                raise ValueError(f'{value} is no valid value for setting '
                                 f'{self.name}, please enter a string.')
            elif value not in choices and not self.any_string:
                raise ValueError(f'{value} is no valid value for setting '
                                 f'{self.name}, select one of {choices}.')
            else:
                self._inner_set(bound_workflow, value)


class SimType(metaclass=AutoSettingNameMeta):
    """Specification of a bim2sim Workflow that is defined by settings."""

    def __init__(self,
                 filters: list = None):
        self.manager = SettingsManager(bound_workflow=self)

        self.filters = filters if filters else []
        self.ifc_units = {}  # dict to store project related units
        self.relevant_elements = []
        self.simulated = False
        self.load_default_settings()

    def load_default_settings(self):
        """loads default values for all settings"""
        for setting in self.manager.values():
            setting.load_default()

    def update_from_config(self, config):
        """Updates the workflow specification from the config file"""
        n_loaded_settings = 0
        for cat, settings in config.items():
            # dont load settings which are not workflow relevant
            if cat.lower() not in [
                self.__class__.__name__.lower(),
                'Generic Workflow Settings'
            ]:
                continue
            from_cfg_cat = config[cat]
            for setting in settings:
                if not hasattr(self, setting):
                    raise AttributeError(
                        f'{setting} is no allowed setting for '
                        f'workflow {self.__class__.__name__} ')
                else:
                    from_cfg_set = from_cfg_cat.get(setting)
                    if from_cfg_set is None:
                        continue
                    elif isinstance(from_cfg_set, str):
                        # convert to readable python object
                        try:
                            # todo ast.literal_eval is safer but not safe.
                            from_cfg_set = ast.literal_eval(from_cfg_set)
                        except (ValueError, SyntaxError):
                            pass
                        # int must be converted to LOD (int is type of bool)
                        if isinstance(from_cfg_set, int) and \
                                not isinstance(from_cfg_set, bool):
                            val = LOD(from_cfg_set)
                        else:
                            val = from_cfg_set
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


class PlantSimulation(SimType):
    def __init__(self):
        super().__init__(
        )

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


class BuildingSimulation(SimType):

    def __init__(self):
        super().__init__()

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


# todo move chosen criteria function from bind_tz decision to here
# WorkflowSetting(
#     name='zoning_criteria',
#     manager=self.setting,
#     default=LOD.low,
#     choices={
#     },
#     for_webapp=True
#     # manager=self.settings,

class EnergyPlusSimulation(BuildingSimulation):
    """Defines workflow settings for EnergyPlus Plugin.

    This class defines the workflow settings for the EnergyPlus Plugin. It
    inherits all choices from the BuildingSimulation workflow. EnergyPlus
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


<<<<<<< Updated upstream:bim2sim/simulation_type.py
class CFDSimulation(SimType):
=======
<<<<<<< Updated upstream:bim2sim/workflow.py
class CFDWorkflow(Workflow):
=======
class CoSimulation(BuildingSimulation, PlantSimulation):
    ...


class CFDSimulation(SimType):
>>>>>>> Stashed changes:bim2sim/simulation_type.py
>>>>>>> Stashed changes:bim2sim/workflow.py
    # todo make something useful
    pass


class LCAExport(SimType):
    """Life Cycle Assessment analysis with CSV Export of the selected BIM Model
     """
    pass
