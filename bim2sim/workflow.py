"""Module for defining workflows"""
import logging
import ast
from enum import Enum
from typing import Union

logger = logging.getLogger(__name__)


class AutoSettingNameMeta(type):
    """Adds the name to every WorkFlowSetting attribute based on its instance
    name.

    This makes the definition of an extra attribute 'name' obsolete, as the
    attributes 'name' is automatic defined based on the instance name.


    Example:
        >>> # create new Workflow for your awesome simulation
        >>> class MyAwesomeSimulationWorfklow(Workflow):
        ...     def __init__(self):
        ...         super().__init__()

        >>> # create a new WorkflowSetting, name will be taken automatic from
        >>> # instance name
        >>> make_simulation_extra_fast = WorkflowSetting(
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
            if isinstance(obj, WorkflowSetting):
                # provide name of the setting as attribute
                obj.name = name


class LOD(Enum):
    """Level of detail in form of an enumeration. The different meaning depends
    on the specific WorkflowSetting."""
    ignore = 0
    low = 1
    medium = 2
    full = 3


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
                              WorkflowSetting))


class WorkflowSetting:
    """WorkflowSettings to define different settings of a bim2sim workflow.

    The WorkflowSettings

    Args:
        default: default value that will be applied when calling load_default()
        choices: dict of possible choice for this setting as key and a
        description per choice as value
        description: description of what the settings does as Str
        for_frontend: should this setting be shown in the frontend
    """

    def __init__(

            self,
            default=None,
            choices: dict = None,
            description: Union[str, None] = None,
            for_frontend: bool = False,
            multiple_choice: bool = False
    ):
        self.name = None  # set by AutoSettingNameMeta
        self.default = default
        self.value = None
        self.choices = choices
        self.description = description
        self.for_webapp = for_frontend
        self.multiple_choice = multiple_choice
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
            if value not in choices:
                raise ValueError(f'{value} is no valid value for setting '
                                 f'{self.name}, select one of {choices}.')
            else:
                self._inner_set(bound_workflow, value)


class Workflow(metaclass=AutoSettingNameMeta):
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
                        if isinstance(from_cfg_set, int) and\
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

    dymola_simulation = WorkflowSetting(
        default=False,
        choices={
            True: 'Run a Simulation with Dymola afterwards',
            False: 'Run no Simulation and only export model'
        },
        description='Run a Simulation after model export?',
        for_frontend=True
    )
    create_external_elements = WorkflowSetting(
        default=False,
        choices={
            True: 'Create external elements',
            False: 'Create external elements'
        },
        description='Create external elements?',
        for_frontend=True
    )


class PlantSimulation(Workflow):
    def __init__(self):
        super().__init__(
        )
    # Todo maybe make every aggregation its own setting with LOD in the future,
    #  but currently we have no usage for this afaik.
    aggregations = WorkflowSetting(
        default=[
            'UnderfloorHeating',
            'Consumer',
            'PipeStrand',
            'ParallelPump',
            'ConsumerHeatingDistributorModule',
            'GeneratorOneFluid',
        ],
        choices={
            'UnderfloorHeating': 'Aggregate underfloor heating circuits',
            'Consumer': 'Aggregate consumers',
            'PipeStrand': 'Aggregate strands of pipes',
            'ParallelPump': 'Aggregate parallel pumps',
            # 'ParallelSpaceHeater': 'Aggregate parallel space heaters',
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


class BuildingSimulation(Workflow):

    def __init__(self):
        super().__init__()

    layers_and_materials = WorkflowSetting(
        default=LOD.low,
        choices={
            LOD.low: 'Override materials with predefined setups',
            LOD.full: 'Get all information from IFC and enrich if needed'
        },
        description='Select how existing Material information in IFC should '
                    'be treated.',
        for_frontend=True
    )
    zoning_setup = WorkflowSetting(
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
    construction_class_walls = WorkflowSetting(
        default='heavy',
        choices={
            'heavy': 'Heavy wall structures.',
            'light': 'Light wall structures.'
        },
        description="Select the most fitting type of construction class for"
                    " the walls of the selected building.",
        for_frontend=True
    )
    construction_class_windows = WorkflowSetting(
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
    cfd_export = WorkflowSetting(
        default=False,
        choices={
            False: 'Do not use CFD export',
            True: 'Use CFD export'
        },
        description='Whether to use CFD export for this simulation or not.',
        for_frontend=True
    )
    heating = WorkflowSetting(
        default=True,
        choices={
            False: 'Do not supply building with heating',
            True: 'Supply building with heating'
        },
        description='Whether the building should be supplied with heating.',
        for_frontend=True
    )
    cooling = WorkflowSetting(
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


class CFDWorkflow(Workflow):
    # todo make something useful
    pass


class LCAExport(Workflow):
    """Life Cycle Assessment analysis with CSV Export of the selected BIM Model
     """
    pass
