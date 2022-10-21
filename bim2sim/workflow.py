"""Module for defining workflows"""

from enum import Enum
from typing import Union


class AutoSettingNameMeta(type):
    """Adds the name to every WorkFlowSetting attribute based on its instance
    name.

    This makes the definition of an extra attribute 'name' obsolete, as the
    attributes 'name' is automatic defined based on the instance name.


    Example:
    >>> # create new Workflow for your awesome simulation
    >>> class MyAwesomeSimulationWorfklow(Workflow):
    ...
    ...     def __init__(self):
    ...         super().__init__()
    >>> # create a new WorkflowSetting, name will be taken automatic from
    ... #  instance name
    ... make_simulation_extra_fast = WorkflowSetting(
    ...     default=True,
    ...     choices={
    ...         True: 'This simulation will be incredible fast.',
    ...         False: 'This simulation will be increbdile slow.'
    ...     },
    ...     description='Run the simulation in extra fast mode?',
    ...     for_frontend=True
    ... )
        # create a workflow instance and get the value
    >>> my_awesome_workflow = MyAwesomeSimulationWorfklow()
    ... # get initial value which is always none
    ... print(my_awesome_workflow.make_simulation_extra_fast)
    None
    ... # set default values and get the value
    ... my_awesome_workflow.load_default_settings()
    ... print(my_awesome_workflow.make_simulation_extra_fast)
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
            for_frontend: bool = False
    ):
        self.name = None  # set by AutoSettingNameMeta
        self.default = default
        self.value = None
        self.choices = choices
        self.description = description
        self.for_webapp = for_frontend
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
        if value not in choices:
            raise ValueError(f'No valid value for {self.name}, '
                             f'select one of {choices} .')
        else:
            _value = value
        self._inner_set(bound_workflow, _value)


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
        # todo #191 refactor
        # todo iteratve over all settings and get them from conifg. maybe move
        #  to other type of file (toml?)
        # self.pipes = LOD(config['Aggregation'].getint('Pipes', 2))
        # self.underfloorheatings = LOD(config['Aggregation'].getint(
        #     'UnderfloorHeating', 2))
        # self.pumps = LOD(config['Aggregation'].getint('Pumps', 2))
        pass
        # todo
        # if not self.layers_and_materials:
        #     self.layers_and_materials = LOD(config['LayersAndMaterials'].getint(
        #         'LayersAndMaterials', 2))
        # if not self.construction_class_walls:
        #     self.construction_class_walls = LOD(config['ConstructionClassWalls'].getint(
        #         'ConstructionClass', 2))
        # if not self.construction_class_windows:
        #     self.construction_class_windows = LOD(config['ConstructionClassWindows'].getint(
        #         'ConstructionClass', 2))

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
    # todo add new parameters for heating, cooling, zone aggregation, hvac aggregation
    def __init__(self):
        super().__init__(
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

    # todo not used in code yet (enrich_material.py)
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

    # todo not used in code yet (enrich_material.py)
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
# todo move chosen criteria function from bind_tz decision to here
# WorkflowSetting(
#     name='zoning_criteria',
#     manager=self.setting,
#     default=LOD.low,
#     choices={
#     },
#     for_webapp=True
#     # manager=self.settings,


class CFDWorkflowDummy(Workflow):
    # todo make something useful
    def __init__(self):
        super().__init__(
        )

# class BPSMultiZoneSeparatedLayersFull(Workflow):
#     """Building performance simulation with every space as single zone
#     separated from each other - no aggregation.
#     Detailed layer information required."""
#
#     def __init__(self):
#         super().__init__(
#             # hull=LOD.medium,
#             # consumer=LOD.low,
#             # generator=LOD.ignore,
#             # hvac=LOD.low,
#             # spaces=LOD.full,
#             # layers=LOD.low,
#             layers_and_materials=LOD.full,
#         )
#
#
# class BPSMultiZoneSeparatedLayersLow(Workflow):
#     """Building performance simulation with every space as single zone
#     separated from each other - no aggregation.
#     Not existing layer information is enriched by templates."""
#
#     def __init__(self):
#         super().__init__(
#             # hull=LOD.medium,
#             # consumer=LOD.low,
#             # generator=LOD.ignore,
#             # hvac=LOD.low,
#             # spaces=LOD.full,
#             layers_and_materials=LOD.low,
#         )
#
#
# class BPSMultiZoneCombinedLayersFull(Workflow):
#     """Building performance simulation with aggregation based on zone
#     aggregation algorithms.
#     Detailed layer information required."""
#
#     def __init__(self):
#         super().__init__(
#             # hull=LOD.medium,
#             # consumer=LOD.low,
#             # generator=LOD.ignore,
#             # hvac=LOD.low,
#             # spaces=LOD.medium,
#             layers_and_materials=LOD.full,
#         )
#         self.materials = None
#
#
# class BPSMultiZoneCombinedLayersLow(Workflow):
#     """Building performance simulation with aggregation based on zone
#     aggregation algorithms.
#     Not existing layer information is enriched by templates."""
#
#     def __init__(self):
#         super().__init__(
#             # hull=LOD.medium,
#             # consumer=LOD.low,
#             # generator=LOD.ignore,
#             # hvac=LOD.low,
#             # spaces=LOD.medium,
#             layers_and_materials=LOD.low,
#         )
#
#
# class BPSMultiZoneAggregatedLayersLow(Workflow):
#     """Building performance simulation with spaces aggregated.
#      Not existing layer information is enriched by templates."""
#
#     def __init__(self):
#         super().__init__(
#             # hull=LOD.medium,
#             # consumer=LOD.low,
#             # generator=LOD.ignore,
#             # hvac=LOD.low,
#             # spaces=LOD.medium,
#             layers_and_materials=LOD.low,
#         )
#
#
# class BPSMultiZoneAggregatedLayersLowSimulation(Workflow):
#     """Building performance simulation with spaces aggregated.
#      Not existing layer information is enriched by templates."""
#
#     def __init__(self):
#         super().__init__(
#             # hull=LOD.medium,
#             # consumer=LOD.low,
#             # generator=LOD.ignore,
#             # hvac=LOD.low,
#             # spaces=LOD.medium,
#             layers_and_materials=LOD.low,
#             dymola_simulation=True
#         )
#
#
# class BPSMultiZoneAggregatedLayersFull(Workflow):
#     """Building performance simulation with spaces aggregated.
#     Detailed layer information required."""
#
#     def __init__(self):
#         super().__init__(
#             # hull=LOD.medium,
#             # consumer=LOD.low,
#             # generator=LOD.ignore,
#             # hvac=LOD.low,
#             # spaces=LOD.medium,
#             layers_and_materials=LOD.full,
#         )
#
#
# class BPSOneZoneAggregatedLayersLow(Workflow):
#     """Building performance simulation with all rooms aggregated to one thermal
#     zone. Not existing layer information is enriched by templates."""
#
#     def __init__(self):
#         super().__init__(
#             # hull=LOD.medium,
#             # consumer=LOD.low,
#             # generator=LOD.ignore,
#             # hvac=LOD.low,
#             # spaces=LOD.low,
#             layers_and_materials=LOD.low,
#             # layers=LOD.full,
#         )
#
#
# class BPSOneZoneAggregatedLayersFull(Workflow):
#     """Building performance simulation with all rooms aggregated to one thermal
#     zone. Detailed layer information required."""
#
#     def __init__(self):
#         super().__init__(
#             # hull=LOD.medium,
#             # consumer=LOD.low,
#             # generator=LOD.ignore,
#             # hvac=LOD.low,
#             # spaces=LOD.low,
#             layers_and_materials=LOD.full,
#         )
#
#
# class BPSMultiZoneSeparatedEP(Workflow):
#     """Building performance simulation with every space as single zone
#     separated from each other - no aggregation,
#     used within the EnergyPlus Workflow"""
#
#     def __init__(self):
#         super().__init__(
#             # hull=LOD.medium,
#             # consumer=LOD.low,
#             # generator=LOD.ignore,
#             # hvac=LOD.low,
#             # spaces=LOD.full,
#             layers_and_materials=LOD.low,
#             create_external_elements=True,
#             # consider IfcExternalSpatialElements
#             cfd_export=False,
#         )
#
#
# class BPSMultiZoneSeparatedEPfull(Workflow):
#     """Building performance simulation with every space as single zone
#     separated from each other - no aggregation,
#     used within the EnergyPlus Workflow"""
#
#     def __init__(self):
#         super().__init__(
#             # hull=LOD.medium,
#             # consumer=LOD.low,
#             # generator=LOD.ignore,
#             # hvac=LOD.low,
#             # spaces=LOD.full,
#             layers_and_materials=LOD.full,
#             create_external_elements=True,
#             # consider IfcExternalSpatialElements
#             cfd_export=False,
#         )
#
#
# class BPSMultiZoneSeparatedEPforCFD(Workflow):
#     """Building performance simulation with every space as single zone
#     separated from each other - no aggregation,
#     used within the EnergyPlus Workflow for CFD export (exports STL and
#     surface inside face temperatures)"""
#
#     def __init__(self):
#         super().__init__(
#             # hull=LOD.medium,
#             # consumer=LOD.low,
#             # generator=LOD.ignore,
#             # hvac=LOD.low,
#             # spaces=LOD.full,
#             layers_and_materials=LOD.low,
#             create_external_elements=True,
#             # consider IfcExternalSpatialElements
#             cfd_export=True,
#         )
#
#
# class CFDWorkflowDummy(Workflow):
#     # todo make something useful
#     def __init__(self):
#         super().__init__(
#             # hull=LOD.medium,
#             # consumer=LOD.low,
#             # generator=LOD.ignore,
#             # hvac=LOD.low,
#             # spaces=LOD.full,
#             layers_and_materials=LOD.full,
#             create_external_elements=True,
#             # consider IfcExternalSpatialElements
#         )
