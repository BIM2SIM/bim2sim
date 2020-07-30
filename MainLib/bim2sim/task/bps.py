"""This module holds tasks related to bps"""

import itertools
import json

from bim2sim.task.base import Task, ITask
from bim2sim.filter import TypeFilter
from bim2sim.kernel.element import Element, ElementEncoder, BasePort
# from bim2sim.kernel.bps import ...
from bim2sim.export import modelica
from bim2sim.decision import Decision
from bim2sim.project import PROJECT
from bim2sim.kernel import finder
from bim2sim.task.sub_tasks import tz_detection
from bim2sim.kernel import elements, disaggregation
from bim2sim.kernel.finder import TemplateFinder
from bim2sim.enrichment_data import element_input_json
from bim2sim.enrichment_data.data_class import DataClass
from bim2sim.decision import ListDecision
from teaser.project import Project
from teaser.logic.buildingobjects.building import Building
from teaser.logic.buildingobjects.thermalzone import ThermalZone
from teaser.logic.buildingobjects.useconditions import UseConditions
from teaser.logic.buildingobjects.buildingphysics.outerwall import OuterWall
from teaser.logic.buildingobjects.buildingphysics.floor import Floor
from teaser.logic.buildingobjects.buildingphysics.rooftop import Rooftop
from teaser.logic.buildingobjects.buildingphysics.groundfloor import GroundFloor
from teaser.logic.buildingobjects.buildingphysics.ceiling import Ceiling
from teaser.logic.buildingobjects.buildingphysics.window import Window
from teaser.logic.buildingobjects.buildingphysics.innerwall import InnerWall
from teaser.logic.buildingobjects.buildingphysics.layer import Layer
from teaser.logic.buildingobjects.buildingphysics.material import Material
from teaser.logic import utilities
import os
from bim2sim.task.bps_f.bps_functions import orientation_verification



class SetIFCTypesBPS(ITask):
    """Set list of relevant IFC types"""
    touches = ('relevant_ifc_types', )

    def run(self, workflow):
        IFC_TYPES = workflow.relevant_ifc_types
        return IFC_TYPES,


class Inspect(ITask):
    """Analyses IFC and creates Element instances.
    Elements are stored in .instances dict with guid as key"""

    reads = ('ifc', )
    touches = ('instances', )

    def __init__(self):
        super().__init__()
        self.instances = {}
        pass

    @Task.log
    def run(self, workflow, ifc):
        self.logger.info("Creates python representation of relevant ifc types")

        Element.finder = finder.TemplateFinder()
        Element.finder.load(PROJECT.finder)
        for ifc_type in workflow.relevant_ifc_types:
            try:
                entities = ifc.by_type(ifc_type)
                for entity in entities:
                    element = Element.factory(entity, ifc_type)
                    self.instances[element.guid] = element
            except RuntimeError:
                pass

        self.logger.info("Found %d building elements", len(self.instances))

        tz_inspect = tz_detection.Inspect(self, workflow)
        tz_inspect.run(ifc)
        self.instances.update(tz_inspect.instances)

        for guid, ins in self.instances.items():
            verification = orientation_verification(ins)
            if verification is not None:
                self.instances[guid].orientation = verification

        return self.instances,

    @staticmethod
    def filter_instances(instances, type_name):
        """Filters the inspected instances by type name (e.g. Wall) and
        returns them as list"""
        instances_filtered = []
        for instance in instances.values():
            if instance.__str__() == type_name:
                instances_filtered.append(instance)
        return instances_filtered


class ExportIDF(ITask):
    """Exports an EnergyPlus input file (IDF) by using the information from IFC"""


# class ExportTEASER(ITask):
#     """Exports a Modelica model with TEASER by using the found information
#     from IFC"""
#
#     reads = ('instances', 'ifc', )
#     final = True
#
#     # @staticmethod
#     # def _default_instance_properties(instance, parent):
#         # instance_switcher = {
#         #     'Building': Building,
#         #     'ThermalZone': ThermalZone,
#         #     'OuterWall': OuterWall,
#         #     'InnerWall': InnerWall,
#         #     'Floor': Floor,
#         #     'Window': Window
#         # }
#         # default_switcher = {
#         #     'Building': {'used_library_calc': 'AixLib',
#         #                  'name': instance.name,
#         #                  ''},
#         #     'ThermalZone': {},
#         #     'OuterWall': {},
#         #     'InnerWall': {},
#         #     'Floor': {},
#         #     'Window': {}
#         # }
#
#
#     @staticmethod
#     def _create_thermal_zone(instance, bldg):
#         """Creates a thermalzone in TEASER by a given BIM2SIM instance"""
#         tz = ThermalZone(parent=bldg)
#         tz.name = instance.name
#         tz.area = instance.area
#         tz.volume = tz.area * instance.height
#         # todo: infiltration rate
#         tz.use_conditions = UseConditions(parent=tz)
#         tz.use_conditions.load_use_conditions(instance.usage)
#         # todo make kelvin celsius robust
#         tz.use_conditions.set_temp_heat = \
#             instance.t_set_heat + 273.15
#         tz.use_conditions.set_temp_cool = \
#             instance.t_set_cool + 273.15
#         tz.number_of_elements = 2
#         return tz
#
#     # @staticmethod
#     # def _create_inner_walls(tz, instances):
#     #     for inner_wall in instances:
#     #         in_wall = InnerWall(parent=tz)
#     #         in_wall.name = inner_wall.name
#     #         in_wall.area = inner_wall.area
#     #         for layer_instance in inner_wall.layers:
#     #             layer = Layer(parent=in_wall)
#     #             layer.thickness = layer_instance.thickness
#     #             # todo material
#     #             material = Material(parent=layer)
#     #             # material.load_material_template(
#     #             #     mat_name=,
#     #             #     data_class=prj.data,
#     #             # )
#     #
#     # @staticmethod
#     # def _create_outer_walls(tz, instances):
#     #     for outer_wall in instances:
#     #         out_wall = OuterWall(parent=tz)
#     #         out_wall.name = outer_wall.name
#     #         out_wall.area = outer_wall.area
#     #         out_wall.tilt = outer_wall.tilt
#     #         # todo orientation not working yet
#     #         out_wall.orientation = outer_wall.orientation
#     #         for layer_instance in outer_wall.layers:
#     #             layer = Layer(parent=out_wall)
#     #             layer.thickness = layer_instance.thickness
#     #             # todo material
#     #             material = Material(parent=layer)
#     #             # material.load_material_template(
#     #             #     mat_name=,
#     #             #     data_class=prj.data,
#     #             # )
#     #
#     # @staticmethod
#     # def _create_wall_like_elements(tz, instances):
#     #     """ creates TEASER instances for all wall like elements, including
#     #     Floors, Ceilings, Roofs"""
#     #     mapping = {
#     #         elements.GroundFloor: GroundFloor,
#     #         elements.Floor: Floor,
#     #         elements.Ceiling: Ceiling,
#     #         elements.Roof: Rooftop,
#     #     }
#     #     # for instance in instances:
#     #     #
#     #     #     element =
#     #     # Inner- and OuterWalls
#     #
#     #
#     # @staticmethod
#     # def _create_ground_floors(tz, instances):
#     #     for ground_floor in instances:
#     #         gf = GroundFloor(parent=tz)
#     #         gf.name = ground_floor.name
#     #         gf.area = ground_floor.area
#     #         gf.tilt = ground_floor.tilt
#     #         # todo orientation not working yet
#     #         gf.orientation = ground_floor.orientation
#     #         for layer_instance in gf.layers:
#     #             layer = Layer(parent=gf)
#     #             layer.thickness = layer_instance.thickness
#     #             # todo material
#     #             material = Material(parent=layer)
#     #             # material.load_material_template(
#     #             #     mat_name=,
#     #             #     data_class=prj.data,
#     #             # )
#
#     @Task.log
#     def run(self, workflow, instances, ifc):
#         # mapping_dict = {
#         #     elements.Floor.instances: Floor,
#         #     elements.Window.instances: Window,
#         #     elements.Roof.instances: Rooftop,
#         #     elements.Wall.outer_walls: OuterWall,
#         #     elements.Wall.inner_walls: InnerWall
#         # }
#
#         self.logger.info("Export to TEASER")
#         prj = Project(load_data=True)
#         prj.name = ifc.by_type('IfcProject')[0].Name
#         prj.data.load_uc_binding()
#         bldg_instances = Inspect.filter_instances(instances, 'Building')
#
#         for bldg_instance in bldg_instances:
#             bldg = Building(parent=prj)
#             bldg.used_library_calc = 'AixLib'
#
#             bldg.name = bldg_instance.name
#             bldg.year_of_construction = bldg_instance.year_of_construction
#             bldg.number_of_floors = bldg_instance.number_of_storeys
#             bldg.net_leased_area = bldg_instance.net_area
#             tz_instances = bps_inspect.filter_instances('ThermalZone')
#             for tz_instance in tz_instances:
#                 tz = self._create_thermal_zone(tz_instance, bldg)
#                 for bound_element in tz_instance.bound_elements:
#                     if isinstance(bound_element, elements.InnerWall):
#                         in_wall = InnerWall(parent=tz)
#                         in_wall.name = bound_element.name
#                         in_wall.area = bound_element.area
#                         in_wall.load_type_element(
#                             year=bldg.year_of_construction, construction="light"
#                         )
#                         # todo material
#                     elif isinstance(bound_element, elements.OuterWall):
#                         out_wall = OuterWall(parent=tz)
#                         out_wall.name = bound_element.name
#                         out_wall.area = bound_element.area
#                         out_wall.tilt = bound_element.tilt
#                         if bound_element.guid == '16DNNqzfP2thtfaOflvsKA':
#                             out_wall.orientation = 90 + 50
#                         elif bound_element.guid == '25fsbPyk15VvuXI':
#                             out_wall.orientation = 50
#                         elif bound_element.guid == '1bzfVsJqn8De5PukCrqylz':
#                             out_wall.orientation = 270 + 50
#                         elif bound_element.guid in ['3rPX_Juz59peXXY6wDJl18',
#                                                     '0knNIAVBPBFvBy_m5QVHsU']:
#                             out_wall.orientation = 180 + 50
#                         for layer_instance in bound_element.layers:
#                             layer = Layer(parent=out_wall)
#                             layer.thickness = layer_instance.thickness
#                             material = Material(parent=layer)
#                             # todo remove hardcode
#                             material.load_material_template(
#                                 mat_name='lightweight_concrete_Vermiculit_470'
#                                 ,
#                                 data_class=prj.data,
#                             )
#                     elif isinstance(bound_element, elements.Window):
#                         window = Window(parent=tz)
#                         window.name = bound_element.name
#                         window.area = bound_element.area
#                         window.load_type_element(
#                             year=bldg.year_of_construction, construction="EnEv"
#                         )
#                         window.innner_convection = 0.6
#                         if bound_element.guid == '2uYaWLoMXGPW4zZLca_BWr' or \
#                                 bound_element.guid == '1c0Yk5iLrVR4e3y5gEUEKa':
#                             window.orientation = 90 + 50
#                         elif bound_element.guid == '2OW0PH61vS77xxyX1o74u8' or \
#                                 bound_element.guid == '2cFXkmvNz6q8TXoCpAWu5Y':
#                             window.orientation = 50
#                         elif bound_element.guid == '2o6xwVLCqc7RJXOAHbb1iq' or \
#                                 bound_element.guid == \
#                                 '1edW1mWMGQA1AyF6LZE0rZ' or \
#                                 bound_element.guid == '0B6UMAQb_hdSR0n26dQbUu':
#                             window.orientation = 270 + 50
#                         elif bound_element.guid == '2NE9qKcWUF2uoVhRSqTd_a' or \
#                                 bound_element.guid == '0seqbT9MlcQAX_K0YLzD86':
#                             window.orientation = 180 + 50
#                         if window.orientation is None:
#                             print('damn')
#                     elif type(bound_element == disaggregation.SubSlab):
#                         slab_element = None
#                         if type(bound_element.parent) == elements.Floor:
#                             slab_element = Floor(parent=tz)
#                         if type(bound_element.parent) == elements.GroundFloor:
#                             slab_element = GroundFloor(parent=tz)
#                         if type(bound_element.parent) == elements.Roof:
#                             slab_element = Rooftop(parent=tz)
#                             # todo remove hardcode
#                             if bound_element.parent.guid \
#                                     == '2IxUUNUVPB6Ob$eicCfP2N':
#                                 slab_element.orientation = 90 + 50
#                             elif bound_element.parent.guid \
#                                     == '07Enbsqm9C7AQC9iyBwfSD':
#                                 slab_element.orientation = 270 + 50
#                             if slab_element.orientation is None:
#                                 print('damn')
#                         slab_element.area = bound_element.area
#                         slab_element.load_type_element(
#                             year=bldg.year_of_construction, construction="light"
#                         )
#
#                     # elif type(bound_element == disaggregation.SubRoof):
#                     #     roof_element = Rooftop(parent=tz)
#                     #     roof_element.area = bound_element.area
#                 # prj.calc_all_buildings()
#                 tz.calc_zone_parameters()
#
#             prj.export_aixlib()
#
#             print(bound_element)
#             # elif isinstance(bound_element, disaggregation.SubSlab):
#             #     print(bound_element)
#             # else:
#             #     print(bound_element.__class_)
#             # elif bound_element.__class__ == disaggregation.SubSlab:
#             #     print('test')
#             #     ground_floor = GroundFloor(parent=tz)
#             #     ground_floor.name = bound_element.name
#             #     ground_floor.area = bound_element.area
#             # print('test')
#             # inner_walls = bps_inspect.filter_instances('InnerWall')
#             # for inner_wall in inner_walls:
#             #     in_wall = InnerWall(parent=tz)
#             #     in_wall.name = inner_wall.name
#             #     in_wall.area = inner_wall.area
#             #     for layer_instance in inner_wall.layers:
#             #         layer = Layer(parent=in_wall)
#             #         layer.thickness = layer_instance.thickness
#             #         # todo material
#             #         # material = Material(parent=layer)
#             #         # material.load_material_template(
#             #         #     mat_name=,
#             #         #     data_class=prj.data,
#             #         # )
#
#             # outer_walls = bps_inspect.filter_instances('OuterWall')
#             # for outer_wall in outer_walls:
#             #     out_wall = OuterWall(parent=tz)
#             #     out_wall.name = outer_wall.name
#             #     out_wall.area = outer_wall.area
#             #     out_wall.tilt = outer_wall.tilt
#             #     if outer_wall.guid == '16DNNqzfP2thtfaOflvsKA':
#             #         out_wall.orientation = 90 + 50
#             #     elif outer_wall.guid == '25fsbPyk15VvuXI':
#             #         out_wall.orientation = 50
#             #     elif outer_wall.guid == '1bzfVsJqn8De5PukCrqylz':
#             #         out_wall.orientation = 270 + 50
#             #     elif outer_wall.guid == '3rPX_Juz59peXXY6wDJl18':
#             #         out_wall.orientation = 180 + 50
#             #     for layer_instance in outer_wall.layers:
#             #         layer = Layer(parent=out_wall)
#             #         layer.thickness = layer_instance.thickness
#             # ground_floors = bps_inspect.filter_instances('GroundFloor')
#             # for ground_floor in ground_floors:
#             #     grou_floor = GroundFloor(parent=tz)
#             #     grou_floor.name = ground_floor.name
#             #     grou_floor.area = ground_floor.area
#             #
#             # pass
#         # for bldg in instances.bBuilding
#
#
#
#
#
# class ExportTEASERMultizone(ITask):
#     """Exports a Modelica model with TEASER by using the found information
#     from IFC"""
#
#     reads = ('instances', )
#     final = True
#
#     @staticmethod
#     def _create_thermal_zone(instance, bldg):
#         """Creates a thermalzone in TEASER by a given BIM2SIM instance"""
#         tz = ThermalZone(parent=bldg)
#         tz.name = instance.name
#         if instance.area is not None:
#             tz.area = instance.area
#         tz.volume = instance.net_volume
#         # todo: infiltration rate
#         tz.use_conditions = UseConditions(parent=tz)
#         tz.use_conditions.load_use_conditions("Living")
#         # tz.use_conditions.load_use_conditions(instance.usage)
#         # todo make kelvin celsius robust
#         tz.use_conditions.set_temp_heat = \
#             instance.t_set_heat + 273.15
#         tz.use_conditions.set_temp_cool = \
#             297.15
#         tz.number_of_elements = 2
#         tz.use_conditions.with_cooling = True
#         return tz
#
#
#     def run(self, workflow, instances):
#         # mapping_dict = {
#         #     elements.Floor.instances: Floor,
#         #     elements.Window.instances: Window,
#         #     elements.Roof.instances: Rooftop,
#         #     elements.Wall.outer_walls: OuterWall,
#         #     elements.Wall.inner_walls: InnerWall
#         # }
#
#         self.logger.info("Export to TEASER")
#         prj = Project(load_data=True)
#         #Todo get project name (not set to PROJECT yet)
#         prj.name = 'Testproject'
#         prj.data.load_uc_binding()
#         bldg_instances = Inspect.filter_instances(instances, 'Building')
#         print('test')
#
#         for bldg_instance in bldg_instances:
#             bldg = Building(parent=prj)
#             bldg.used_library_calc = 'AixLib'
#             bldg.name = bldg_instance.name
#             bldg.year_of_construction = bldg_instance.year_of_construction
#             bldg.number_of_floors = bldg_instance.number_of_storeys
#             bldg.net_leased_area = bldg_instance.net_area
#             tz_instances = Inspect.filter_instances(instances, 'ThermalZone')
#             for tz_instance in tz_instances:
#                 tz = self._create_thermal_zone(tz_instance, bldg)
#                 for bound_element in tz_instance.bound_elements:
#                     if isinstance(bound_element, elements.InnerWall)\
#                             or isinstance(bound_element,
#                                           disaggregation.SubInnerWall):
#                         in_wall = InnerWall(parent=tz)
#                         in_wall.name = bound_element.name
#                         in_wall.area = bound_element.area
#                         in_wall.orientation = int(bound_element.orientation)
#                         if bound_element.orientation is None:
#                             print('damn')
#                         in_wall.load_type_element(
#                             year=bldg.year_of_construction,
#                             construction="heavy")
#                             # todo material
#                     elif type(bound_element) == elements.OuterWall or \
#                             type(bound_element) == disaggregation.SubOuterWall:
#                         out_wall = OuterWall(parent=tz)
#                         out_wall.name = bound_element.name
#                         out_wall.area = bound_element.area
#                         out_wall.tilt = bound_element.tilt
#                         out_wall.orientation = int(bound_element.orientation)
#                         if bound_element.orientation is None:
#                             print('damn')
#                         if type(bound_element) == elements.OuterWall:
#                             layer_instances = bound_element.layers
#                         elif type(bound_element) == \
#                                 disaggregation.SubOuterWall:
#                             layer_instances = bound_element.parent.layers
#                         for layer_instance in layer_instances:
#                             layer = Layer(parent=out_wall)
#                             layer.thickness = layer_instance.thickness
#                             material = Material(parent=layer)
#                             # todo remove hardcode
#                             material.load_material_template(
#                                 mat_name='Vermiculit_bulk_density_170_100deg'
#                                 ,
#                                 data_class=prj.data,
#                                 )
#                     elif isinstance(bound_element, elements.Window):
#                         window = Window(parent=tz)
#                         window.name = bound_element.name
#                         window.area = bound_element.area
#                         window.load_type_element(
#                             year=bldg.year_of_construction, construction="EnEv"
#                         )
#                         window.innner_convection = 0.6
#                         window.orientation = int(bound_element.orientation)
#                         if window.orientation is None:
#                             print('damn')
#                     elif isinstance(bound_element, elements.Roof) or \
#                         isinstance(bound_element, disaggregation.SubRoof):
#                         roof_element = Rooftop(parent=tz)
#                         # todo remove hardcode
#                         roof_element.orientation = -1
#                         roof_element.area = bound_element.area
#                         roof_element.load_type_element(
#                             year=bldg.year_of_construction, construction="heavy"
#                         )
#                     elif isinstance(bound_element, elements.Floor) or \
#                         isinstance(bound_element, disaggregation.SubFloor):
#                         floor_element = Floor(parent=tz)
#                         floor_element.area = bound_element.area
#                         floor_element.orientation = -2
#                         floor_element.load_type_element(
#                             year=bldg.year_of_construction, construction="heavy"
#                         )
#                     elif isinstance(bound_element, elements.GroundFloor) or \
#                         isinstance(bound_element, disaggregation.SubGroundFloor):
#                         gfloor_element = GroundFloor(parent=tz)
#                         gfloor_element.orientation = -2
#                         gfloor_element.area = bound_element.area
#                         gfloor_element.load_type_element(
#                             year=bldg.year_of_construction, construction="heavy"
#                         )
#
#                 # catch error for no inner walls areas
#                 if len(tz.inner_walls) ==0:
#                     in_wall = InnerWall(parent=tz)
#                     in_wall.name = "dummy"
#                     in_wall.area = 0.01
#                     in_wall.load_type_element(
#                         year=bldg.year_of_construction,
#                         construction="heavy")
#                 try:
#                     tz.calc_zone_parameters()
#                 except:
#                     pass
#             bldg.calc_building_parameter(number_of_elements=2)
#             prj.weather_file_path = utilities.get_full_path(
#                 os.path.join(
#                     "D:/09_OfflineArbeiten/Bausim2020/RefResults_FZKHaus"
#                     "/KIT_CampusEPW.mos"))
#             prj.export_aixlib()
#
# class ExportTEASERSingleZone(Task):
#     """Exports a Modelica model with TEASER by using the found information
#     from IFC"""
#     #todo: for this LOD the slab sicing must be deactivated and building
#     # elements must be only included once in the thermalzone even if they are
#     # holded by different IfcSpaces
#     @staticmethod
#     def _create_thermal_single_zone(instances, bldg):
#         """Creates a thermalzone in TEASER by a given BIM2SIM instance"""
#         tz = ThermalZone(parent=bldg)
#         tz.name = "SingleZoneFZK"
#         tz.use_conditions = UseConditions(parent=tz)
#         tz.use_conditions.load_use_conditions("Living")
#         # set_temp_heat_median = sum((instance.t_set_heat + 273.15) *
#         #                            instance.area *
#         #                            instance.height for instance in
#         #                            instances) / \
#         #                        sum(instance.area * instance.height for
#         #                            instance in instances)
#         # set_temp_cool_median = sum((instance.t_set_cool + 273.15) *
#         #                            instance.area *
#         #                            instance.height for instance in
#         #                            instances) / \
#         #                        sum(instance.area * instance.height for
#         #                            instance in instances)
#         tz.area = 0
#         tz.volume = 0
#         for instance in instances:
#             tz.area += instance.area
#             tz.volume += instance.net_volume
#         # todo: infiltration rate
#         # todo make kelvin celsius robust
#         tz.number_of_elements = 2
#         tz.use_conditions.with_cooling = True
#         return tz
#
#
#     def run(self, workflow, bps_inspect):
#         # mapping_dict = {
#         #     elements.Floor.instances: Floor,
#         #     elements.Window.instances: Window,
#         #     elements.Roof.instances: Rooftop,
#         #     elements.Wall.outer_walls: OuterWall,
#         #     elements.Wall.inner_walls: InnerWall
#         # }
#
#         self.logger.info("Export to TEASER")
#         # raise NotImplementedError("Not working probably at the moment")
#         prj = Project(load_data=True)
#         #Todo get project name (not set to PROJECT yet)
#         prj.name = 'Testproject'
#         prj.data.load_uc_binding()
#         bldg_instances = bps_inspect.filter_instances('Building')
#
#         for bldg_instance in bldg_instances:
#             bldg = Building(parent=prj)
#             bldg.used_library_calc = 'AixLib'
#
#             bldg.name = bldg_instance.name
#             bldg.year_of_construction = bldg_instance.year_of_construction
#             bldg.number_of_floors = bldg_instance.number_of_storeys
#             bldg.net_leased_area = bldg_instance.net_area
#             tz_instances = bps_inspect.filter_instances('ThermalZone')
#             tz = self._create_thermal_single_zone(tz_instances, bldg)
#
#             for bound_element in bps_inspect.instances.values():
#                 if isinstance(bound_element, elements.InnerWall)\
#                         or isinstance(bound_element,
#                                       disaggregation.SubInnerWall):
#                     in_wall = InnerWall(parent=tz)
#                     in_wall.name = bound_element.name
#                     in_wall.area = bound_element.area
#                     in_wall.orientation = int(bound_element.orientation)
#                     if bound_element.orientation is None:
#                         print('damn')
#                     in_wall.load_type_element(
#                         year=bldg.year_of_construction,
#                         construction="heavy")
#                         # todo material
#                 elif type(bound_element) == elements.OuterWall or \
#                         type(bound_element) == disaggregation.SubOuterWall:
#                     out_wall = OuterWall(parent=tz)
#                     out_wall.name = bound_element.name
#                     out_wall.area = bound_element.area
#                     out_wall.tilt = bound_element.tilt
#                     out_wall.orientation = int(bound_element.orientation)
#                     if bound_element.orientation is None:
#                         print('damn')
#                     if type(bound_element) == elements.OuterWall:
#                         layer_instances = bound_element.layers
#                     elif type(bound_element) == \
#                             disaggregation.SubOuterWall:
#                         layer_instances = bound_element.parent.layers
#                     for layer_instance in layer_instances:
#                         layer = Layer(parent=out_wall)
#                         layer.thickness = layer_instance.thickness
#                         material = Material(parent=layer)
#                         # todo remove hardcode
#                         material.load_material_template(
#                             mat_name='Vermiculit_bulk_density_170_100deg'
#                             ,
#                             data_class=prj.data,
#                             )
#                 elif isinstance(bound_element, elements.Window):
#                     window = Window(parent=tz)
#                     window.name = bound_element.name
#                     window.area = bound_element.area
#                     window.load_type_element(
#                         year=bldg.year_of_construction, construction="EnEv"
#                     )
#                     window.innner_convection = 0.6
#                     window.orientation = int(bound_element.orientation)
#                     if window.orientation is None:
#                         print('damn')
#                 elif isinstance(bound_element, elements.Roof) or \
#                     isinstance(bound_element, disaggregation.SubRoof):
#                     roof_element = Rooftop(parent=tz)
#                     # todo remove hardcode
#                     roof_element.orientation = -1
#                     roof_element.area = bound_element.area
#                     roof_element.load_type_element(
#                         year=bldg.year_of_construction, construction="heavy"
#                     )
#                 elif isinstance(bound_element, elements.Floor) or \
#                     isinstance(bound_element, disaggregation.SubFloor):
#                     floor_element = Floor(parent=tz)
#                     floor_element.area = bound_element.area
#                     floor_element.orientation = -2
#                     floor_element.load_type_element(
#                         year=bldg.year_of_construction, construction="heavy"
#                     )
#                 elif isinstance(bound_element, elements.GroundFloor) or \
#                     isinstance(bound_element, disaggregation.SubGroundFloor):
#                     gfloor_element = GroundFloor(parent=tz)
#                     gfloor_element.orientation = -2
#                     gfloor_element.area = bound_element.area
#                     gfloor_element.load_type_element(
#                         year=bldg.year_of_construction, construction="heavy"
#                     )
#
#                 # catch error for no inner walls areas
#                 if len(tz.inner_walls) ==0:
#                     in_wall = InnerWall(parent=tz)
#                     in_wall.name = "dummy"
#                     in_wall.area = 0.01
#                     in_wall.load_type_element(
#                         year=bldg.year_of_construction,
#                         construction="heavy")
#
#             tz.calc_zone_parameters()
#             bldg.calc_building_parameter(number_of_elements=2)
#             prj.export_aixlib()
#
#
