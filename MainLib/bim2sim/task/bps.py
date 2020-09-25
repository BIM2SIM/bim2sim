"""This module holds tasks related to bps"""

import itertools
import json
import ifcopenshell

from OCC.Display.SimpleGui import init_display
from OCC.BRepBuilderAPI import \
    BRepBuilderAPI_MakeFace, \
    BRepBuilderAPI_MakeEdge, \
    BRepBuilderAPI_MakeWire, BRepBuilderAPI_Transform, BRepBuilderAPI_MakeVertex, BRepBuilderAPI_MakeShape
from OCC.ShapeAnalysis import ShapeAnalysis_ShapeContents
from OCC.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Extrema import Extrema_ExtFlag_MIN
from OCC.gp import gp_Trsf, gp_Vec, gp_XYZ, gp_Pln, gp_Pnt
from OCC.TopoDS import topods_Wire, topods_Face, topods_Compound, TopoDS_Compound, TopoDS_Builder, topods_Vertex
from OCC.TopAbs import TopAbs_FACE, TopAbs_WIRE, TopAbs_SHAPE, TopAbs_VERTEX
from OCC.TopExp import TopExp_Explorer
from OCC.BRep import BRep_Tool
from OCC.BRepTools import BRepTools_WireExplorer, breptools_UVBounds
from OCC.Geom import Handle_Geom_Plane
from geomeppy import IDF
from OCC.BRepAlgoAPI import BRepAlgoAPI_Cut, BRepAlgoAPI_Section
from OCC.StlAPI import StlAPI_Writer
from OCC.BRepMesh import BRepMesh_IncrementalMesh
from OCC.BRepGProp import brepgprop_SurfaceProperties
from OCC.BRepPrimAPI import BRepPrimAPI_MakeHalfSpace, BRepPrimAPI_MakeBox
from OCC.GProp import GProp_GProps
from OCC.BRepAlgoAPI import BRepAlgoAPI_Common
from OCC.Bnd import Bnd_Box
from OCC.BRepBndLib import brepbndlib_Add
from stl import stl
from stl import mesh


from bim2sim.task.base import Task, ITask
# from bim2sim.filter import TypeFilter
from bim2sim.kernel.element import Element, ElementEncoder, BasePort, SubElement
from bim2sim.kernel.elements import SpaceBoundary2B, SpaceBoundary
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
from bim2sim.decision import ListDecision, BoolDecision
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
from teaser.logic.buildingobjects.buildingphysics.door import Door
from teaser.logic import utilities
import os
from bim2sim.task.bps_f.bps_functions import orientation_verification, get_matches_list, filter_instances, \
    get_pattern_usage
from bim2sim.kernel.units import conversion
from OCC.Display.SimpleGui import init_display


class SetIFCTypesBPS(ITask):
    """Set list of relevant IFC types"""
    touches = ('relevant_ifc_types',)

    def run(self, workflow):
        IFC_TYPES = workflow.relevant_ifc_types
        return IFC_TYPES,


class Inspect(ITask):
    """Analyses IFC and creates Element instances.
    Elements are stored in .instances dict with guid as key"""

    reads = ('ifc',)
    touches = ('instances',)

    def __init__(self):
        super().__init__()
        self.instances = {}
        pass

    @Task.log
    def run(self, workflow, ifc):
        self.logger.info("Creates python representation of relevant ifc types")

        Element.finder = finder.TemplateFinder()
        Element.finder.load(PROJECT.finder)

        workflow.relevant_ifc_types = self.use_doors(workflow.relevant_ifc_types)
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
    def use_doors(relevant_ifc_types):
        ifc_list = list(relevant_ifc_types)
        doors_decision = BoolDecision(question="Do you want for the doors to be considered on the bps analysis?",
                                      collect=False)
        doors_decision.decide()
        if not doors_decision.value:
            ifc_list.remove('IfcDoor')
        return tuple(ifc_list)


class ExportTEASER(ITask):
    """Exports a Modelica model with TEASER by using the found information
    from IFC"""
    reads = ('instances', 'ifc',)
    final = True

    materials = {}
    property_error = {}
    instance_template = {}

    instance_switcher = {'OuterWall': OuterWall,
                         'InnerWall': InnerWall,
                         'Floor': Floor,
                         'Window': Window,
                         'GroundFloor': GroundFloor,
                         'Roof': Rooftop,
                         'Door': Door}

    @staticmethod
    def _create_project(element):
        """Creates a project in TEASER by a given BIM2SIM instance
        Parent: None"""
        prj = Project(load_data=True)
        if len(element.Name) != 0:
            prj.name = element.Name
        else:
            prj.name = element.LongName
        prj.data.load_uc_binding()
        return prj

    @classmethod
    def _create_building(cls, instance, parent):
        """Creates a building in TEASER by a given BIM2SIM instance
        Parent: Project"""
        bldg = Building(parent=parent)
        # name is important here
        cls._teaser_property_getter(bldg, instance, instance.finder.templates)
        cls.instance_template[bldg.name] = {}  # create instance template dict
        return bldg

    @classmethod
    def _create_thermal_zone(cls, instance, parent):
        """Creates a thermal zone in TEASER by a given BIM2SIM instance
        Parent: Building"""
        tz = ThermalZone(parent=parent)
        cls._teaser_property_getter(tz, instance, instance.finder.templates)
        tz.volume = instance.area * instance.height
        tz.use_conditions = UseConditions(parent=tz)
        tz.use_conditions.load_use_conditions(instance.usage)
        tz.use_conditions.set_temp_heat = conversion(instance.t_set_heat, '°C', 'K').magnitude
        tz.use_conditions.set_temp_cool = conversion(instance.t_set_cool, '°C', 'K').magnitude
        return tz

    @classmethod
    def _invalid_property_filter(cls, teaser_instance, instance, key, aux):
        """Filter the invalid property values and fills it with a template or an user given value,
        if value is valid, returns the value
        invalid value: ZeroDivisionError on thermal zone calculations"""
        error_properties = ['density', 'thickness']  # properties that are vital to thermal zone calculations
        white_list_properties = ['orientation']
        if (aux is None or aux == 0) and key not in white_list_properties:
            # name from instance to store in error dict
            name_error = instance.name
            if hasattr(instance, 'material'):
                name_error = instance.material
            try:
                aux = cls.property_error[name_error][key]
            # redundant case for invalid properties
            except KeyError:
                if key in error_properties:
                    if hasattr(instance, '_get_material_properties'):
                        aux = instance._get_material_properties(key)
                    while aux is None or aux == 0:
                        aux = float(input('please enter a valid value for %s from %s' % (key, name_error)))
                # check indentation
                if name_error not in cls.property_error:
                    cls.property_error[name_error] = {}
                if key not in cls.property_error[name_error]:
                    cls.property_error[name_error][key] = aux
        # set attr on teaser instance
        setattr(teaser_instance, key, aux)

    @classmethod
    def _teaser_property_getter(cls, teaser_instance, instance, templates):
        """get and set all properties necessary to create a Teaser Instance from a BIM2Sim Instance,
        based on the information on the base.json exporter"""
        sw = type(teaser_instance).__name__
        if sw == 'Rooftop':
            sw = 'Roof'
        for key, value in templates['base'][sw]['exporter']['teaser'].items():
            if isinstance(value, list):
                # get property from instance (instance dependant on instance)
                if value[0] == 'instance':
                    aux = getattr(instance, value[1])
                    if type(aux).__name__ == 'Quantity':
                        aux = aux.magnitude
                    if aux is not None:
                        try:
                            setattr(teaser_instance, key, aux)
                        except ZeroDivisionError:
                            return True
                    else:
                        return True
            else:
                # get property from json (fixed property)
                setattr(teaser_instance, key, value)

    @classmethod
    def _create_teaser_instance(cls, instance, parent, bldg):
        """creates a teaser instances with a given parent and BIM2SIM instance
        get exporter necessary properties, from a given instance
        Parent: ThermalZone"""
        # determine if is instance or subinstance (disaggregation) get templates from instance
        if hasattr(instance, 'parent'):
            sw = type(instance.parent).__name__
            templates = instance.parent.finder.templates
        else:
            sw = type(instance).__name__
            templates = instance.finder.templates

        teaser_class = cls.instance_switcher.get(sw)
        if teaser_class is not None:
            teaser_instance = teaser_class(parent=parent)
            cls._teaser_property_getter(teaser_instance, instance, templates)
            cls._instance_related(teaser_instance, instance, bldg)

    @classmethod
    def _bind_instances_to_zone(cls, tz, tz_instance, bldg):
        """create and bind the instances of a given thermal zone to a teaser instance thermal zone"""
        for bound_element in tz_instance.bound_elements:
            cls._create_teaser_instance(bound_element, tz, bldg)

    @classmethod
    def _instance_related(cls, teaser_instance, instance, bldg):
        """instance specific function, layers creation
        if layers not given, loads template"""
        # property getter if instance has materials/layers
        if isinstance(instance.layers, list) and len(instance.layers) > 0:
            for layer_instance in instance.layers:
                layer = Layer(parent=teaser_instance)
                layer.thickness = layer_instance.thickness
                cls._material_related(layer, layer_instance, bldg)
        # property getter if instance doesn't have any materials/layers
        else:
            if getattr(bldg, 'year_of_construction') is None:
                bldg.year_of_construction = int(input("Please provide a valid year of construction for building: "))
            template_options, years_group = cls._get_instance_template(teaser_instance, bldg)
            template_value = None
            if len(template_options) > 1:
                decision_template = ListDecision("the following construction types were "
                                                 "found for year %s and instance %s (%s)"
                                                 % (bldg.year_of_construction, teaser_instance.name,
                                                    type(teaser_instance).__name__),
                                                 choices=template_options,
                                                 allow_skip=True, allow_load=True, allow_save=True,
                                                 collect=False, quick_decide=not True)
                decision_template.decide()
                template_value = decision_template.value
            elif len(template_options) == 1:
                template_value = template_options[0]
            cls.instance_template[bldg.name][type(teaser_instance).__name__] = [years_group, template_value]
            teaser_instance.load_type_element(year=bldg.year_of_construction, construction=template_value)

    @classmethod
    def _material_related(cls, layer, layer_instance, bldg):
        """material instance specific functions, get properties of material and creates Material in teaser,
        if material or properties not given, loads material template"""
        prj = bldg.parent
        material = Material(parent=layer)
        material_ref = ''.join([i for i in layer_instance.material if not i.isdigit()]).lower().strip()
        error = cls._teaser_property_getter(material, layer_instance, layer_instance.finder.templates)
        if error is True:
            try:
                material_name = cls.materials[layer_instance.material]
            except KeyError:
                Materials_DEU = layer_instance.parent.finder.templates['base']['Material']['DEU']
                material_templates = dict(prj.data.material_bind)
                del material_templates['version']

                for k in Materials_DEU:
                    if material_ref in k:
                        material_ref = Materials_DEU[k]

                options = {}
                for k in material_templates:
                    if material_ref in material_templates[k]['name']:
                        options[k] = material_templates[k]
                while len(options) == 0:
                    decision_ = input(
                        "Material not found, enter value for the material:")
                    material_ref = decision_
                    for k in material_templates:
                        if material_ref in material_templates[k]['name']:
                            options[k] = material_templates[k]

                materials_options = [material_templates[k]['name'] for k in options]
                decision1 = None
                if len(materials_options) > 0:
                    decision1 = ListDecision("one or more attributes of the material %s for %s are not valid, "
                                             "select one of the following templates to continue"
                                             % (layer_instance.material, layer_instance.parent.name),
                                             choices=list(materials_options),
                                             allow_skip=True, allow_load=True, allow_save=True,
                                             collect=False, quick_decide=not True)
                    decision1.decide()

    @classmethod
    def _get_instance_template(cls, teaser_instance, bldg):
        default = ['heavy', 'light', 'EnEv']
        year_group = [1995, 2015]  # default year group
        prj = bldg.parent
        instance_type = type(teaser_instance).__name__
        instance_templates = dict(prj.data.element_bind)
        del instance_templates["version"]
        if bldg.name in cls.instance_template:
            teaser_name = type(teaser_instance).__name__
            if teaser_name in cls.instance_template[bldg.name]:
                year_group = str(cls.instance_template[bldg.name][teaser_name][0])
                selected_template = cls.instance_template[bldg.name][teaser_name][1]
                aux_template = '%s_%s_%s' % (instance_type, year_group, selected_template)
                if aux_template in instance_templates:
                    return [selected_template], year_group

        template_options = []
        for i in instance_templates:
            years = instance_templates[i]['building_age_group']
            if i.startswith(instance_type) and years[0] <= bldg.year_of_construction <= years[1]:
                template_options.append(instance_templates[i]['construction_type'])
                year_group = years
        if len(template_options) == 0:
            return default, year_group
        return template_options, year_group

    @Task.log
    def run(self, workflow, instances, ifc):
        self.logger.info("Export to TEASER")
        prj = self._create_project(ifc.by_type('IfcProject')[0])
        bldg_instances = filter_instances(instances, 'Building')
        for bldg_instance in bldg_instances:
            bldg = self._create_building(bldg_instance, prj)
            tz_instances = filter_instances(instances, 'ThermalZone')
            for tz_instance in tz_instances:
                tz = self._create_thermal_zone(tz_instance, bldg)
                self._bind_instances_to_zone(tz, tz_instance, bldg)
                tz.calc_zone_parameters()
            bldg.calc_building_parameter()
        prj.calc_all_buildings()
        prj.export_aixlib()
        print()


# class ExportTEASERMultizone(ITask):
#     """Exports a Modelica model with TEASER by using the found information
#     from IFC"""
#
#     reads = ('instances',)
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
#         # Todo get project name (not set to PROJECT yet)
#         prj.name = 'Testproject'
#         prj.data.load_uc_binding()
#         bldg_instances = filter_instances(instances, 'Building')
#         print('test')
#
#         for bldg_instance in bldg_instances:
#             bldg = Building(parent=prj)
#             bldg.used_library_calc = 'AixLib'
#             bldg.name = bldg_instance.name
#             bldg.year_of_construction = bldg_instance.year_of_construction
#             bldg.number_of_floors = bldg_instance.number_of_storeys
#             bldg.net_leased_area = bldg_instance.net_area
#             tz_instances = filter_instances(instances, 'ThermalZone')
#             for tz_instance in tz_instances:
#                 tz = self._create_thermal_zone(tz_instance, bldg)
#                 for bound_element in tz_instance.bound_elements:
#                     if isinstance(bound_element, elements.InnerWall) \
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
#                         # todo material
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
#                             )
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
#                             isinstance(bound_element, disaggregation.SubRoof):
#                         roof_element = Rooftop(parent=tz)
#                         # todo remove hardcode
#                         roof_element.orientation = -1
#                         roof_element.area = bound_element.area
#                         roof_element.load_type_element(
#                             year=bldg.year_of_construction, construction="heavy"
#                         )
#                     elif isinstance(bound_element, elements.Floor) or \
#                             isinstance(bound_element, disaggregation.SubFloor):
#                         floor_element = Floor(parent=tz)
#                         floor_element.area = bound_element.area
#                         floor_element.orientation = -2
#                         floor_element.load_type_element(
#                             year=bldg.year_of_construction, construction="heavy"
#                         )
#                     elif isinstance(bound_element, elements.GroundFloor) or \
#                             isinstance(bound_element, disaggregation.SubGroundFloor):
#                         gfloor_element = GroundFloor(parent=tz)
#                         gfloor_element.orientation = -2
#                         gfloor_element.area = bound_element.area
#                         gfloor_element.load_type_element(
#                             year=bldg.year_of_construction, construction="heavy"
#                         )
#
#                 # catch error for no inner walls areas
#                 if len(tz.inner_walls) == 0:
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
#
# class ExportTEASERSingleZone(Task):
#     """Exports a Modelica model with TEASER by using the found information
#     from IFC"""
#
#     # todo: for this LOD the slab sicing must be deactivated and building
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
#         # Todo get project name (not set to PROJECT yet)
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
#                 if isinstance(bound_element, elements.InnerWall) \
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
#                     # todo material
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
#                         )
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
#                         isinstance(bound_element, disaggregation.SubRoof):
#                     roof_element = Rooftop(parent=tz)
#                     # todo remove hardcode
#                     roof_element.orientation = -1
#                     roof_element.area = bound_element.area
#                     roof_element.load_type_element(
#                         year=bldg.year_of_construction, construction="heavy"
#                     )
#                 elif isinstance(bound_element, elements.Floor) or \
#                         isinstance(bound_element, disaggregation.SubFloor):
#                     floor_element = Floor(parent=tz)
#                     floor_element.area = bound_element.area
#                     floor_element.orientation = -2
#                     floor_element.load_type_element(
#                         year=bldg.year_of_construction, construction="heavy"
#                     )
#                 elif isinstance(bound_element, elements.GroundFloor) or \
#                         isinstance(bound_element, disaggregation.SubGroundFloor):
#                     gfloor_element = GroundFloor(parent=tz)
#                     gfloor_element.orientation = -2
#                     gfloor_element.area = bound_element.area
#                     gfloor_element.load_type_element(
#                         year=bldg.year_of_construction, construction="heavy"
#                     )
#
#                 # catch error for no inner walls areas
#                 if len(tz.inner_walls) == 0:
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


class ExportEP(ITask):
    """Exports an EnergyPlus model based on IFC information"""

    reads = ('instances', 'ifc',)
    final = True

    @Task.log
    def run(self, workflow, instances, ifc):
        # geometric preprocessing before export
        self.logger.info("Geometric preprocessing for EnergyPlus Export started ...")
        self.logger.info("Compute relationships between space boundaries")
        self._get_parents_and_children(instances)
        self._move_children_to_parents(instances)
        self._get_neighbor_bounds(instances)
        self._compute_2b_bound_gaps(instances)
        self._move_bounds_to_centerline(instances)
        self._fill_2b_gaps(instances)
        # self._vertex_scaled_centerline_bounds(instances)
        # self._intersect_scaled_centerline_bounds(instances)
        self.logger.info("Geometric preprocessing for EnergyPlus Export finished!")
        self.logger.info("IDF generation started ...")
        idf = self._init_idf()
        self._init_zone(instances, idf)
        self._set_simulation_control(idf)
        idf.set_default_constructions()
        self._export_geom_to_idf(instances, idf)
        self._set_output_variables(idf)
        idf.save()
        self.logger.info("IDF generation finished!")

        idf.view_model()
        self._export_to_stl_for_cfd(instances, idf)
        self._display_shape_of_space_boundaries(instances)
        idf.run(output_directory=str(PROJECT.root) + "/export/EP-results/", readvars=True)

    def _intersect_centerline_bounds(self, instances):
        for inst in instances:
            if instances[inst].ifc_type != "IfcSpace":
                continue
            space_obj = instances[inst]
            for bound in space_obj.space_boundaries:
                halfspaces = []
                bbox = Bnd_Box()
                if hasattr(bound, 'related_parent_bound'):
                    continue
                if not hasattr(bound, 'bound_shape_cl'):
                    continue
                for other_bound in space_obj.space_boundaries:
                    if hasattr(bound, 'related_parent_bound'):
                        continue
                    if other_bound.ifc.GlobalId == bound.ifc.GlobalId:
                        continue
                    if hasattr(other_bound, 'bound_shape_cl'):
                        halfspace = self._create_halfspaces(other_bound.bound_shape_cl, space_obj)
                        brepbndlib_Add(other_bound.bound_shape_cl, bbox)
                    else:
                        halfspace = self._create_halfspaces(other_bound.bound_shape, space_obj)
                        brepbndlib_Add(other_bound.bound_shape, bbox)
                    halfspaces.append(halfspace)
                halfspace = self._create_halfspaces(bound.bound_shape_cl, space_obj)
                halfspaces.append(halfspace)
                brepbndlib_Add(bound.bound_shape_cl, bbox)
                common_shape = BRepPrimAPI_MakeBox(bbox.CornerMin(), bbox.CornerMax()).Shape()
                for halfspace in halfspaces:
                    bound_prop = GProp_GProps()
                    brepgprop_SurfaceProperties(halfspace, bound_prop)
                    area = bound_prop.Mass()
                    if area == 0:
                        continue
                    #todo: fix common_shape no longer returns zero-area compound
                    temp_comm = BRepAlgoAPI_Common(common_shape, halfspace.Reversed()).Shape()
                    comm_prop = GProp_GProps()
                    brepgprop_SurfaceProperties(temp_comm, comm_prop)
                    temp_area = comm_prop.Mass()
                    if temp_area == 0:
                        temp_comm = BRepAlgoAPI_Common(common_shape, halfspace).Shape()
                        comm_prop = GProp_GProps()
                        brepgprop_SurfaceProperties(temp_comm, comm_prop)
                        temp_area = comm_prop.Mass()
                        if temp_area == 0:
                            continue
                    common_shape = temp_comm
                space_obj.space_shape_cl = common_shape
                faces = self.get_faces_from_shape(space_obj.space_shape_cl)
                bound_cl_prop = GProp_GProps()
                brepgprop_SurfaceProperties(bound.bound_shape_cl, bound_cl_prop)
                for face in faces:
                    distance = BRepExtrema_DistShapeShape(face, bound.bound_shape_cl, Extrema_ExtFlag_MIN).Value()
                    if distance == 0:
                        max_area = bound_cl_prop.Mass()
                        face_prop = GProp_GProps()
                        brepgprop_SurfaceProperties(face, face_prop)
                        face_center = face_prop.CentreOfMass()

                        cl_center = bound_cl_prop.CentreOfMass()
                        center_dist = face_center.Distance(cl_center) ** 2
                        if center_dist < 0.5:
                            this_area = face_prop.Mass()
                            if this_area > max_area:
                                bound.bound_shape_cl = face
                                print("newShape", bound_cl_prop.Mass(), face_prop.Mass())

    @staticmethod
    def get_center_of_face(face):
        prop = GProp_GProps()
        center = brepgprop_SurfaceProperties(face, prop)
        center = prop.CentreOfMass()
        print("CENTER", center.Coord())
        return center


    def scale_face(self, face, factor):
        center = self.get_center_of_face(face)
        trsf = gp_Trsf()
        trsf.SetScale(center, factor)
        face_scaled = BRepBuilderAPI_Transform(face, trsf).Shape()
        return face_scaled

    def _intersect_scaled_centerline_bounds(self, instances):
        for inst in instances:
            if instances[inst].ifc_type != "IfcSpace":
                continue
            space_obj = instances[inst]
            bbox = Bnd_Box()
            halfspaces = []
            for bound in space_obj.space_boundaries:
                if hasattr(bound, 'related_parent_bound'):
                    continue
                if not hasattr(bound, 'bound_shape_cl'):
                    continue
                if not hasattr(bound, 'scaled_bound_cl'):
                    bound.scaled_bound_cl = self.scale_face(bound.bound_shape_cl, 1.3)
                halfspace = self._create_halfspaces(bound.scaled_bound_cl, space_obj)
                halfspaces.append(halfspace)
                brepbndlib_Add(bound.bound_shape_cl, bbox)
            if hasattr(space_obj, 'space_boundaries_2B'):
                for bound_b in space_obj.space_boundaries_2B:
                    if not hasattr(bound_b, 'bound_shape_cl'):
                        print("no bound shape 2b")
                        continue
                    bound.scaled_bound_cl = self.scale_face(bound_b.bound_shape_cl, 1.3)
                    halfspace = self._create_halfspaces(bound.scaled_bound_cl, space_obj)
                    halfspaces.append(halfspace)
                    brepbndlib_Add(bound_b.bound_shape, bbox)
            common_shape = BRepPrimAPI_MakeBox(bbox.CornerMin(), bbox.CornerMax()).Solid()
            for halfspace in halfspaces:
                bound_prop = GProp_GProps()
                brepgprop_SurfaceProperties(halfspace, bound_prop)
                area = bound_prop.Mass()
                if area == 0:
                    continue
                #todo: fix common_shape no longer returns zero-area compound
                temp_comm = BRepAlgoAPI_Common(common_shape, halfspace).Shape()
                comm_prop = GProp_GProps()
                brepgprop_SurfaceProperties(temp_comm, comm_prop)
                temp_area = comm_prop.Mass()
                if temp_area == 0:
                    temp_comm = BRepAlgoAPI_Common(common_shape, halfspace).Shape()
                    comm_prop = GProp_GProps()
                    brepgprop_SurfaceProperties(temp_comm, comm_prop)
                    temp_area = comm_prop.Mass()
                    if temp_area == 0:
                        continue
                common_shape = temp_comm
            space_obj.space_shape_cl = common_shape
            faces = self.get_faces_from_shape(space_obj.space_shape_cl)
            for bound in space_obj.space_boundaries:
                if hasattr(bound, 'related_parent_bound'):
                    continue
                if not hasattr(bound, 'bound_shape_cl'):
                    continue
                bound_cl_prop = GProp_GProps()
                brepgprop_SurfaceProperties(bound.bound_shape_cl, bound_cl_prop)
                for face in faces:
                    distance = BRepExtrema_DistShapeShape(face, bound.bound_shape_cl, Extrema_ExtFlag_MIN).Value()
                    if distance < 1e-3:
                        max_area = bound_cl_prop.Mass()
                        face_prop = GProp_GProps()
                        brepgprop_SurfaceProperties(face, face_prop)
                        face_center = face_prop.CentreOfMass()

                        cl_center = bound_cl_prop.CentreOfMass()
                        center_dist = face_center.Distance(cl_center) ** 2
                        if center_dist < 0.5:
                            this_area = face_prop.Mass()
                            if this_area > max_area:
                                bound.bound_shape_cl = face
                                print("newShape", bound_cl_prop.Mass(), face_prop.Mass())
            print('WAIT')

    @staticmethod
    def _create_halfspaces(bound_shape, space_obj):
        try:
            halfspace = BRepPrimAPI_MakeHalfSpace(bound_shape, space_obj.space_center).Solid()
            print("Not a compound")
        except:
            an_exp = TopExp_Explorer(bound_shape, TopAbs_FACE)
            while an_exp.More():
                shape = topods_Face(an_exp.Current())
                an_exp.Next()
            halfspace = BRepPrimAPI_MakeHalfSpace(shape, space_obj.space_center).Solid()
        return halfspace

    def _move_bounds_to_centerline(self, instances):
        for inst in instances:
            # self._intersect_centerline_bounds(instances)
            if instances[inst].ifc_type != "IfcRelSpaceBoundary":
                continue
            inst_obj = instances[inst]
            if not hasattr(inst_obj, 'bound_instance'):
                continue
            if inst_obj.bound_instance is None:
                continue
            if inst_obj.is_external:
                if hasattr(inst_obj, 'related_parent_bound'):
                    continue
                center_shape = BRepBuilderAPI_MakeVertex(inst_obj.thermal_zones[0].space_center).Shape()
                center_dist = BRepExtrema_DistShapeShape(
                    inst_obj.bound_shape,
                    center_shape,
                    Extrema_ExtFlag_MIN
                ).Value()
                if hasattr(inst_obj.bound_instance, 'thickness'):
                    thickness = inst_obj.bound_instance.thickness
                elif hasattr(inst_obj.bound_instance.layers[0], 'thickness'):
                    thickness = inst_obj.bound_instance.layers[0].thickness
                else:
                    thickness = 0.2
                prod_vec = []
                for i in inst_obj.bound_normal.Coord():
                    prod_vec.append(thickness * i)

                # move to center between corresponding boundaries
                trsf = gp_Trsf()
                coord = gp_XYZ(*prod_vec)
                vec = gp_Vec(coord)
                trsf.SetTranslation(vec)
                inst_obj.bound_shape_cl = BRepBuilderAPI_Transform(inst_obj.bound_shape, trsf).Shape()
                # check if boundary has been moved correctly
                # and otherwise move again in reversed direction
                new_distance = BRepExtrema_DistShapeShape(
                    inst_obj.bound_shape_cl,
                    center_shape,
                    Extrema_ExtFlag_MIN
                ).Value()
                if new_distance > center_dist:
                    continue
                else:
                    prod_vec = []
                    for i in inst_obj.bound_normal.Reversed().Coord():
                        prod_vec.append(half_dist * i)
                    trsf = gp_Trsf()
                    coord = gp_XYZ(*prod_vec)
                    vec = gp_Vec(coord)
                    trsf.SetTranslation(vec)
                    inst_obj.bound_shape_cl = BRepBuilderAPI_Transform(inst_obj.bound_shape, trsf).Shape()

            if not hasattr(inst_obj, 'related_bound'):
                continue
            if inst_obj.related_bound is None:
                continue
            if inst_obj.is_external:
                continue
            distance = BRepExtrema_DistShapeShape(inst_obj.bound_shape, inst_obj.related_bound.bound_shape, Extrema_ExtFlag_MIN).Value()
            half_dist = distance/2

            prod_vec = []
            for i in inst_obj.bound_normal.Coord():
                prod_vec.append(half_dist * i)

            # move to center between corresponding boundaries
            trsf = gp_Trsf()
            coord = gp_XYZ(*prod_vec)
            vec = gp_Vec(coord)
            trsf.SetTranslation(vec)
            inst_obj.bound_shape_cl = BRepBuilderAPI_Transform(inst_obj.bound_shape, trsf).Shape()
            if hasattr(inst_obj, 'bound_neighbors_2b'):
                for b_bound in inst_obj.bound_neighbors_2b:
                    if not IdfObject._compare_direction_of_normals(inst_obj.bound_normal, b_bound.bound_normal):
                        continue
                    b_bound.bound_shape_cl = BRepBuilderAPI_Transform(b_bound.bound_shape, trsf).Shape()
            # check if boundary has been moved correctly
            # and otherwise move again in reversed direction
            new_distance = BRepExtrema_DistShapeShape(
                inst_obj.bound_shape_cl,
                inst_obj.related_bound.bound_shape,
                Extrema_ExtFlag_MIN
            ).Value()
            if new_distance < distance:
                continue
            else:
                prod_vec = []
                for i in inst_obj.bound_normal.Reversed().Coord():
                    prod_vec.append(half_dist * i)
                trsf = gp_Trsf()
                coord = gp_XYZ(*prod_vec)
                vec = gp_Vec(coord)
                trsf.SetTranslation(vec)
                inst_obj.bound_shape_cl = BRepBuilderAPI_Transform(inst_obj.bound_shape, trsf).Shape()
                if hasattr(inst_obj, 'bound_neighbors_2b'):
                    for b_bound in inst_obj.bound_neighbors_2b:
                        if not IdfObject._compare_direction_of_normals(inst_obj.bound_normal, b_bound.bound_normal):
                            continue
                        b_bound.bound_shape_cl = BRepBuilderAPI_Transform(b_bound.bound_shape, trsf).Shape()

    def _fill_2b_gaps(self, instances):
        for inst in instances:
            if instances[inst].ifc_type != "IfcRelSpaceBoundary":
                continue
            bound = instances[inst]
            if not hasattr(bound, 'bound_shape_cl'):
                continue
            if not hasattr(bound, 'bound_neighbors_2b'):
                continue
            for b_bound in bound.bound_neighbors_2b:
                for neighbor in b_bound.bound_neighbors:
                    if neighbor == bound:
                        continue
                    if not hasattr(neighbor, 'bound_shape_cl'):
                        continue
                    # if not bound.bound_instance == neighbor.bound_instance:
                    #     continue
                    sb_neighbor = neighbor
                    check1 = IdfObject._compare_direction_of_normals(bound.bound_normal, sb_neighbor.bound_normal)
                    check2 = IdfObject._compare_direction_of_normals(bound.bound_normal, b_bound.bound_normal)
                    if not (check1 and check2):
                        continue
                    distance = BRepExtrema_DistShapeShape(bound.bound_shape_cl, sb_neighbor.bound_shape_cl, Extrema_ExtFlag_MIN).Value()
                    if distance < 1e-3:
                        continue
                    if distance > 0.4:
                        continue

                    neigh_normal = (sb_neighbor.bound_center - bound.bound_center)
                    neigh_normal.Normalize()
                    anExp = TopExp_Explorer(bound.bound_shape_cl, TopAbs_VERTEX)
                    result_vert = []
                    moved_vert_count = 0
                    while anExp.More():
                        prod_vec = []
                        vert = anExp.Current()
                        vertex = topods_Vertex(vert)
                        pnt_v1 = BRep_Tool.Pnt(vertex)
                        dist = BRepExtrema_DistShapeShape(vertex, sb_neighbor.bound_shape_cl, Extrema_ExtFlag_MIN).Value()

                        if (dist - distance)**2 < 1e-2:
                            for i in neigh_normal.Coord():
                                prod_vec.append(i * dist/2)
                            trsf = gp_Trsf()
                            coord = gp_XYZ(*prod_vec)
                            vec = gp_Vec(coord)
                            trsf.SetTranslation(vec)
                            pnt_v1.Transform(trsf)

                            result_vert.append(pnt_v1)
                            moved_vert_count +=1
                        else:
                            result_vert.append(pnt_v1)
                        anExp.Next()
                        anExp.Next()
                    result_vert.append(result_vert[0])
                    new_face1 = SpaceBoundary._make_faces_from_pnts(result_vert)

                    neigh_normal = neigh_normal.Reversed()
                    anExp = TopExp_Explorer(sb_neighbor.bound_shape_cl, TopAbs_VERTEX)
                    result_vert = []
                    while anExp.More():
                        prod_vec = []
                        vert = anExp.Current()
                        vertex = topods_Vertex(vert)
                        pnt_v1 = BRep_Tool.Pnt(vertex)
                        dist = BRepExtrema_DistShapeShape(vertex, bound.bound_shape_cl, Extrema_ExtFlag_MIN).Value()

                        if (dist - distance)**2 < 1e-2:
                            for i in neigh_normal.Coord():
                                prod_vec.append(i * dist / 2)
                            trsf = gp_Trsf()
                            coord = gp_XYZ(*prod_vec)
                            vec = gp_Vec(coord)
                            trsf.SetTranslation(vec)
                            pnt_v1.Transform(trsf)

                            result_vert.append(pnt_v1)
                            moved_vert_count +=1
                        else:
                            result_vert.append(pnt_v1)
                        anExp.Next()
                        anExp.Next()
                    result_vert.append(result_vert[0])
                    new_face2 = SpaceBoundary._make_faces_from_pnts(result_vert)
                    new_dist = BRepExtrema_DistShapeShape(new_face1, new_face2, Extrema_ExtFlag_MIN).Value()
                    if new_dist > 1e-3:
                        continue
                    bound.bound_shape_cl = new_face1
                    sb_neighbor.bound_shape_cl = new_face2
                    # todo: compute new area for bound_shape_cl and compare to area of related bound
                    # todo: assign reversed bound_shape_cl to related bound if area of related bound is smaller



    def _export_geom_to_idf(self, instances, idf):
        for inst in instances:
            if instances[inst].ifc_type != "IfcRelSpaceBoundary":
                continue
            inst_obj = instances[inst]
            idfp = IdfObject(inst_obj, idf)
            if idfp.skip_bound:
                # idf.popidfobject(idfp.key, -1)
                self.logger.warning("Boundary with the GUID %s (%s) is skipped (due to missing boundary conditions)!", idfp.name, idfp.surface_type)
                continue

    def _export_to_stl_for_cfd(self, instances, idf):
        self.logger.info("Export STL for CFD")
        stl_name = idf.idfname.replace('.idf', '')
        stl_name = stl_name.replace(str(PROJECT.root) + "/export/", '')
        self.export_bounds_to_stl(instances, stl_name)
        self.export_2B_bounds_to_stl(instances, stl_name)
        self.combine_stl_files(stl_name)

    @staticmethod
    def combine_stl_files(stl_name):
        stl_dir = str(PROJECT.root) + "/export/"
        with open(stl_dir+stl_name + "_combined_STL.stl", 'wb+') as output_file:
            for i in os.listdir(stl_dir+'STL/'):
                if os.path.isfile(os.path.join(stl_dir+'STL/',i)) and (stl_name + "_cfd_") in i:
                    sb_mesh = mesh.Mesh.from_file(stl_dir+'STL/'+i)
                    mesh_name = i.split("_",1)[-1]
                    mesh_name = mesh_name.replace(".stl", "")
                    mesh_name = mesh_name.replace("$", "___")
                    sb_mesh.save(mesh_name, output_file, mode=stl.Mode.ASCII)


    @staticmethod
    def _init_idf():
        """
        Initialize the idf with general idf settings and set default weather data.
        :return:
        """
        # path = '/usr/local/EnergyPlus-9-2-0/'
        path = '/usr/local/EnergyPlus-9-3-0/'
        IDF.setiddname(path + 'Energy+.idd')
        idf = IDF(path + "ExampleFiles/Minimal.idf")
        idf.idfname = str(PROJECT.root) + "/export/temp.idf"

        idf.epw = "USA_CO_Golden-NREL.724666_TMY3.epw"
        return idf


    def _init_zone(self, instances, idf):
        """
        Creates one idf zone per space and initializes with default HVAC Template
        :param idf: idf file object
        :param stat: HVAC Template
        :param space: Space (created from IfcSpace)
        :return: idf file object, idf zone object
        """

        stat = self._set_hvac_template(idf, name="stat1", heating_sp=20, cooling_sp=25)

        for inst in instances:
            if instances[inst].ifc_type == "IfcSpace":
                space = instances[inst]
                zone = idf.newidfobject(
                    'ZONE',
                    Name=space.ifc.GlobalId,
                    Volume=space.space_volume
                )
                idf.newidfobject(
                    "HVACTEMPLATE:ZONE:IDEALLOADSAIRSYSTEM",
                    Zone_Name=zone.Name,
                    Template_Thermostat_Name=stat.Name,
                )


    @staticmethod
    def _set_hvac_template(idf, name, heating_sp, cooling_sp):
        """
        Set default HVAC Template
        :param idf: idf file object
        :return: stat (HVAC Template)
        """
        stat = idf.newidfobject(
            "HVACTEMPLATE:THERMOSTAT",
            Name="Zone " + name,
            Constant_Heating_Setpoint=heating_sp,
            Constant_Cooling_Setpoint=cooling_sp,
        )
        return stat

    @staticmethod
    def _set_simulation_control(idf):
        """
        Set simulation control parameters.
        :param idf: idf file object
        :return: idf file object
        """
        for sim_control in idf.idfobjects["SIMULATIONCONTROL"]:
            print("")
            sim_control.Do_Zone_Sizing_Calculation = "Yes"
            sim_control.Do_System_Sizing_Calculation = "Yes"
            sim_control.Do_Plant_Sizing_Calculation = "Yes"
            sim_control.Run_Simulation_for_Sizing_Periods = "No"
            sim_control.Run_Simulation_for_Weather_File_Run_Periods = "Yes"
        # return idf

    @staticmethod
    def _set_output_variables(idf):
        """
        Adds userdefined output variables to the idf file
        :param idf: idf file object
        :return: idf file object
        """
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Ideal Loads Supply Air Total Heating Energy",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Ideal Loads Supply Air Total Cooling Energy",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Site Outdoor Air Drybulb Temperature",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Mean Air Temperature",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone People Occupant Count",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone People Convective Heating Rate",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Electric Equipment Convective Heating Rate",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Ideal Loads Zone Sensible Cooling Rate",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Zone Ideal Loads Zone Sensible Heating Rate",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject(
            "OUTPUT:VARIABLE",
            Variable_Name="Surface Inside Face Temperature",
            Reporting_Frequency="Hourly",
        )
        idf.newidfobject("OUTPUT:SURFACES:DRAWING",
                         Report_Type="DXF")
        idf.newidfobject("OUTPUT:DIAGNOSTICS",
                         Key_1="DisplayAdvancedReportVariables",
                         Key_2="DisplayExtraWarnings")
        return idf

    @staticmethod
    def _get_neighbor_bounds(instances):
        for inst in instances:
            this_obj = instances[inst]
            if this_obj.ifc_type != 'IfcRelSpaceBoundary':
                continue
            neighbors = this_obj.bound_neighbors

    @staticmethod
    def _move_children_to_parents(instances):
        """move external opening boundaries to related parent boundary (e.g. wall)"""
        for inst in instances:
            if hasattr(instances[inst], 'related_parent_bound'):
                opening_obj = instances[inst]
                # only external openings need to be moved
                # all other are properly placed within parent boundary
                if opening_obj.is_external:
                    distance = BRepExtrema_DistShapeShape(
                        opening_obj.bound_shape,
                        opening_obj.related_parent_bound.bound_shape,
                        Extrema_ExtFlag_MIN
                    ).Value()

                    prod_vec = []
                    for i in opening_obj.bound_normal.Coord():
                        prod_vec.append(distance*i)

                    # moves opening to parent boundary
                    trsf = gp_Trsf()
                    coord = gp_XYZ(*prod_vec)
                    vec = gp_Vec(coord)
                    trsf.SetTranslation(vec)

                    opening_obj.bound_shape_org = opening_obj.bound_shape
                    opening_obj.bound_shape = BRepBuilderAPI_Transform(opening_obj.bound_shape, trsf).Shape()

                    # check if opening has been moved to boundary correctly
                    # and otherwise move again in reversed direction
                    new_distance = BRepExtrema_DistShapeShape(
                        opening_obj.bound_shape,
                        opening_obj.related_parent_bound.bound_shape,
                        Extrema_ExtFlag_MIN
                    ).Value()
                    if new_distance > 1e-3:
                        prod_vec = []
                        op_normal = opening_obj.bound_normal.Reversed()
                        for i in op_normal.Coord():
                            prod_vec.append(new_distance * i)
                        trsf = gp_Trsf()
                        coord = gp_XYZ(*prod_vec)
                        vec = gp_Vec(coord)
                        trsf.SetTranslation(vec)
                        opening_obj.bound_shape = BRepBuilderAPI_Transform(opening_obj.bound_shape, trsf).Shape()

    @staticmethod
    def _get_parents_and_children(instances):
        """get parent-children relationships between IfcElements (e.g. Windows, Walls)
        and the corresponding relationships of their space boundaries"""
        for inst in instances:
            inst_obj = instances[inst]
            inst_type = inst_obj.ifc_type
            if inst_type != 'IfcRelSpaceBoundary':
                continue
            inst_obj_space = inst_obj.ifc.RelatingSpace
            b_inst = inst_obj.bound_instance
            if b_inst is None:
                continue
            # assign opening elems (Windows, Doors) to parents and vice versa
            if not hasattr(b_inst.ifc, 'HasOpenings'):
                continue
            if len(b_inst.ifc.HasOpenings) == 0:
                continue
            for opening in b_inst.ifc.HasOpenings:
                if hasattr(opening.RelatedOpeningElement, 'HasFillings'):
                    for fill in opening.RelatedOpeningElement.HasFillings:
                        opening_obj = b_inst.objects[fill.RelatedBuildingElement.GlobalId]
                        if not hasattr(b_inst, 'related_openings'):
                            setattr(b_inst, 'related_openings', [])
                        if opening_obj in b_inst.related_openings:
                            continue
                        b_inst.related_openings.append(opening_obj)
                        if not hasattr(opening_obj, 'related_parent'):
                            setattr(opening_obj, 'related_parent', [])
                        opening_obj.related_parent = b_inst
            # assign space boundaries of opening elems (Windows, Doors) to parents and vice versa
            if not hasattr(b_inst, 'related_openings'):
                continue
            if not hasattr(inst_obj, 'related_opening_bounds'):
                setattr(inst_obj, 'related_opening_bounds', [])
            for opening in b_inst.related_openings:
                for op_bound in opening.space_boundaries:
                    if op_bound.ifc.RelatingSpace == inst_obj_space:
                        if op_bound in inst_obj.related_opening_bounds:
                            continue
                        distance = BRepExtrema_DistShapeShape(
                            op_bound.bound_shape,
                            inst_obj.bound_shape,
                            Extrema_ExtFlag_MIN
                        ).Value()
                        if distance > 0.3:
                            continue
                        inst_obj.related_opening_bounds.append(op_bound)
                        if not hasattr(op_bound, 'related_parent_bound'):
                            setattr(op_bound, 'related_parent_bound', [])
                            op_bound.related_parent_bound = inst_obj

    @staticmethod
    def _display_shape_of_space_boundaries(instances):
        """Display topoDS_shapes of space boundaries"""
        display, start_display, add_menu, add_function_to_menu = init_display()
        colors = ['blue', 'red', 'magenta', 'yellow', 'green', 'white', 'cyan']
        col = 0
        for inst in instances:
            if instances[inst].ifc_type == 'IfcSpace':
                col += 1
                zone = instances[inst]
                if not hasattr(zone, 'space_boundaries_2B'):
                    continue
                for bound in zone.space_boundaries_2B:
                    try:
                        display.DisplayShape(bound.bound_shape, color=colors[(col - 1) % len(colors)])
                    except:
                        continue
                # display.DisplayShape(zone.space_shape, color=colors[(col - 1) % len(colors)])
                # display.DisplayShape(zone.b_bound_shape, color=colors[(col - 1) % len(colors)])
        display.FitAll()
        start_display()

    def export_bounds_to_stl(self, instances, stl_name):
        """
        This function exports a space to an idf file.
        :param idf: idf file object
        :param space: Space instance
        :param zone: idf zone object
        :return:
        """
        for inst in instances:
            if instances[inst].ifc_type != "IfcRelSpaceBoundary":
                continue
            inst_obj = instances[inst]
            if inst_obj.physical:
                name = inst_obj.ifc.GlobalId
                stl_dir = str(PROJECT.root) + "/export/STL/"
                this_name = stl_dir + str(stl_name) + "_cfd_" + str(name) + ".stl"
                os.makedirs(os.path.dirname(stl_dir), exist_ok=True)

                inst_obj.cfd_face = inst_obj.bound_shape
                if hasattr(inst_obj, 'related_opening_bounds'):
                    for opening in inst_obj.related_opening_bounds:
                        inst_obj.cfd_face = BRepAlgoAPI_Cut(inst_obj.cfd_face, opening.bound_shape).Shape()

                triang_face = BRepMesh_IncrementalMesh(inst_obj.cfd_face, 1)

                # Export to STL
                stl_writer = StlAPI_Writer()
                stl_writer.SetASCIIMode(True)

                stl_writer.Write(triang_face.Shape(), this_name)

    def _compute_2b_bound_gaps(self, instances):
        self.logger.info("Generate space boundaries of type 2B")
        for inst in instances:
            if instances[inst].ifc_type != "IfcSpace":
                continue
            space_obj = instances[inst]
            space_obj.b_bound_shape = space_obj.space_shape
            for bound in space_obj.space_boundaries:
                if bound.bound_area == 0:
                    continue
                bound_prop = GProp_GProps()
                brepgprop_SurfaceProperties(space_obj.b_bound_shape, bound_prop)
                b_bound_area = bound_prop.Mass()
                if b_bound_area == 0:
                    continue
                distance = BRepExtrema_DistShapeShape(
                    space_obj.b_bound_shape,
                    bound.bound_shape,
                    Extrema_ExtFlag_MIN).Value()
                if distance > 1e-6:
                    continue
                space_obj.b_bound_shape = BRepAlgoAPI_Cut(space_obj.b_bound_shape, bound.bound_shape).Shape()

            faces = self.get_faces_from_shape(space_obj.b_bound_shape)
            self.create_2B_space_boundaries(faces, space_obj)


    def export_2B_bounds_to_stl(self, instances, stl_name):
        for inst in instances:
            if instances[inst].ifc_type != "IfcSpace":
                continue
            space_obj = instances[inst]
            bound_prop = GProp_GProps()
            brepgprop_SurfaceProperties(space_obj.b_bound_shape, bound_prop)
            area = bound_prop.Mass()
            if area > 0:
                name = space_obj.ifc.GlobalId + "_2B"
                stl_dir = str(PROJECT.root) + "/export/STL/"
                this_name = stl_dir + str(stl_name) + "_cfd_" + str(name) + ".stl"
                os.makedirs(os.path.dirname(stl_dir), exist_ok=True)

                triang_face = BRepMesh_IncrementalMesh(space_obj.b_bound_shape, 1)

                # Export to STL
                stl_writer = StlAPI_Writer()
                stl_writer.SetASCIIMode(True)

                stl_writer.Write(triang_face.Shape(), this_name)

    def create_2B_space_boundaries(self, faces, space_obj):
        space_obj.space_boundaries_2B = []
        for i, face in enumerate(faces):
            b_bound = SpaceBoundary2B()
            b_bound.bound_shape = face
            b_bound.guid = space_obj.ifc.GlobalId + "_2B_" + str("%003.f"%(i+1))
            b_bound.thermal_zones.append(space_obj)
            space_obj.space_boundaries_2B.append(b_bound)

            for bound in space_obj.space_boundaries:
                distance = BRepExtrema_DistShapeShape(bound.bound_shape, b_bound.bound_shape, Extrema_ExtFlag_MIN).Value()
                if distance == 0:
                    b_bound.bound_neighbors.append(bound)
                    if not hasattr(bound, 'bound_neighbors_2b'):
                        bound.bound_neighbors_2b = []
                    bound.bound_neighbors_2b.append(b_bound)

    @staticmethod
    def get_faces_from_shape(b_bound_shape):
        faces = []
        an_exp = TopExp_Explorer(b_bound_shape, TopAbs_FACE)
        while an_exp.More():
            face = topods_Face(an_exp.Current())
            faces.append(face)
            an_exp.Next()
        return faces


class IdfObject():
    def __init__(self, inst_obj, idf):
        self.name = inst_obj.ifc.GlobalId
        self.building_surface_name = None
        self.key = None
        self.out_bound_cond = ''
        self.out_bound_cond_obj = ''
        self.sun_exposed = ''
        self.wind_exposed = ''
        self.surface_type = None
        self.virtual_physical = None
        self.construction_name = None
        self.zone_name = inst_obj.ifc.RelatingSpace.GlobalId
        self.related_bound = inst_obj.related_bound
        self.skip_bound = False
        self.bound_shape = inst_obj.bound_shape

        if hasattr(inst_obj, 'related_parent_bound'):
            self.key = "FENESTRATIONSURFACE:DETAILED"
        else:
            self.key = "BUILDINGSURFACE:DETAILED"

        if hasattr(inst_obj, 'related_parent_bound'):
            self.building_surface_name = inst_obj.related_parent_bound.ifc.GlobalId


        self._map_surface_types(inst_obj)
        self._map_boundary_conditions(inst_obj)
        #todo: fix material definitions!
        self._define_materials(inst_obj, idf)
        if self.construction_name == None:
            self._set_construction_name()
        obj = self._set_idfobject_attributes(idf)
        if obj is not None:
            self._set_idfobject_coordinates(obj, idf, inst_obj)

    def _define_materials(self, inst_obj, idf):
        #todo: define default property_sets
        #todo: request missing values from user-inputs
        if inst_obj.bound_instance is None and self.out_bound_cond == "Surface":
            idf_constr = idf.idfobjects['CONSTRUCTION:AIRBOUNDARY'.upper()]
            included = False
            for cons in idf_constr:
                if 'Air Wall' in cons.Name:
                    included = True
            if included==False:
                idf.newidfobject("CONSTRUCTION:AIRBOUNDARY",
                                 Name='Air Wall',
                                 Solar_and_Daylighting_Method='GroupedZones',
                                 Radiant_Exchange_Method='GroupedZones',
                                 Air_Exchange_Method='SimpleMixing',
                                 Simple_Mixing_Air_Changes_per_Hour=0.5,
                                 )
            self.construction_name = 'Air Wall'

        # if inst_obj.bound_instance.ifc_type is ("IfcWindow" or "IfcDoor"):
        #     return
        if hasattr(inst_obj.bound_instance, 'layers'):
            if inst_obj.bound_instance.layers == None or len(inst_obj.bound_instance.layers) == 0:
                return
            construction_name = self.surface_type
            for layer in inst_obj.bound_instance.layers:
                if layer.guid == None:
                    return
                construction_name = construction_name + layer.guid[-4:]
                if inst_obj.bound_instance.ifc_type is not ("IfcWindow" or "IfcDoor"):
                    idf_materials = idf.idfobjects['Material'.upper()]
                    included = False
                    for mat in idf_materials:
                        if layer.guid in mat.Name:
                            included = True
                    if included:
                        continue
                    else:
                        # todo: use thermal transmittance if available (--> finder)
                        if layer.thickness is None:
                            thickness = 0.1
                        else:
                            thickness = layer.thickness
                        if layer.density in {None, 0}:
                            density = 1000
                        else:
                            density = layer.density
                        if layer.thermal_conduc is None:
                            conductivity = 0.1
                        else:
                            conductivity = layer.thermal_conduc
                        if layer.heat_capac is None:
                            heat_capacity = 1000
                        else:
                            heat_capacity = layer.heat_capac

                        idf.newidfobject("MATERIAL",
                                         Name=layer.guid,
                                         Roughness="Rough",
                                         Thickness=thickness,
                                         Conductivity=conductivity,
                                         Density=density,
                                         Specific_Heat=heat_capacity
                                         )
                else:
                    idf_op_materials = idf.idfobjects['WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM'.upper()]
                    included = False
                    for mat in idf_op_materials:
                        if layer.guid in mat.Name:
                            included = True
                    if included:
                        continue
                    else:
                        if layer.thickness is None:
                            thickness = 0.1
                        else:
                            thickness = layer.thickness
                        if layer.thermal_conduc is None:
                            conductivity = 0.1
                        else:
                            conductivity = layer.thermal_conduc

                        if layer.thermal_transmittance is not None:
                            ufactor = layer.thermal_transmittance
                        else:
                            try:
                                #todo: use finder to get transmittance
                                #todo: ensure thermal_transmittance is not applied to multiple layers
                                psw = inst_obj.bound_instance.get_propertyset('Pset_WindowCommon')
                                ufactor = psw['ThermalTransmittance']
                            except:
                                ufactor = 1/(0.13+thickness/conductivity+0.04)
                        # if layer.solar_heat_gain_coefficient is None:
                        #     solar_heat_gain_coefficient = 0.763
                        # else:
                        #     solar_heat_gain_coefficient = layer.solar_heat_gain_coefficient
                        # if layer.visible_transmittance is None:
                        #     visible_transmittance = 0.8
                        # else:
                        #     visible_transmittance = layer.visible_transmittance

                        idf.newidfobject("WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM",
                                         Name=layer.guid,
                                         UFactor=ufactor,
                                         Solar_Heat_Gain_Coefficient=0.763,
                                         Visible_Transmittance=0.8
                                         )
            idf_constr = idf.idfobjects['Construction'.upper()]
            included = False
            self.construction_name = construction_name
            for cons in idf_constr:
                if construction_name in cons.Name:
                    included = True
            if not included:
                if len(inst_obj.bound_instance.layers) == 1:
                    idf.newidfobject("CONSTRUCTION",
                                     Name=construction_name,
                                     Outside_Layer=inst_obj.bound_instance.layers[0].guid)
                if len(inst_obj.bound_instance.layers) > 1:
                    if inst_obj.bound_instance.ifc_type is ("IfcWindow" or "IfcDoor"):
                        #todo: Add construction implementation for openings with >1 layer
                        #todo: required construction: gas needs to be bounded by solid surfaces
                        self.construction_name = None
                        return
                    other_layers = {}
                    for i, layer in enumerate(inst_obj.bound_instance.layers[1:]):
                        other_layers.update({'Layer_' + str(i+2): layer.guid})
                    idf.newidfobject("CONSTRUCTION",
                                            Name=construction_name,
                                            Outside_Layer=inst_obj.bound_instance.layers[0].guid,
                                            **other_layers
                                            )




    def _set_construction_name(self):
        if self.surface_type == "Wall":
            self.construction_name = "Project Wall"
            # construction_name = "FZK Exterior Wall"
        if self.surface_type == "Roof":
            # construction_name = "Project Flat Roof"
            self.construction_name = "Project Flat Roof"
        if self.surface_type == "Ceiling":
            self.construction_name = "Project Ceiling"
        if self.surface_type == "Floor":
            self.construction_name = "Project Floor"
        if self.surface_type == "Door":
            self.construction_name = "Project Door"
        if self.surface_type == "Window":
            self.construction_name = "Project External Window"

    def _set_idfobject_coordinates(self, obj, idf, inst_obj):
        # validate bound_shape
        # self._check_for_vertex_duplicates()

        # write validated bound_shape to obj
        obj_pnts = self._get_points_of_face(self.bound_shape)
        obj_coords = []
        for pnt in obj_pnts:
            obj_coords.append(pnt.Coord())
        try:
            obj.setcoords(obj_coords)
        except:
            return

        circular_shape = self.get_circular_shape(obj_pnts)

        try:
            if (3 <= len(obj_coords) <= 120 and self.key == "BUILDINGSURFACE:DETAILED") \
                    or (3 <= len(obj_coords) <= 4 and self.key == "FENESTRATIONSURFACE:DETAILED"):
                obj.setcoords(obj_coords)
            elif circular_shape is True and self.surface_type != 'Door':
                self._process_circular_shapes(idf, obj_coords, obj, inst_obj)
            else:
                self._process_other_shapes(inst_obj, obj)
        except:
            print("Element", self.name, "NOT EXPORTED")

    # def _check_for_vertex_duplicates(self):
    #     if self.related_bound is not None:
    #         nb_vert_this = self._get_number_of_vertices(self.bound_shape)
    #         nb_vert_other = self._get_number_of_vertices(self.related_bound.bound_shape)
    #         # if nb_vert_this != nb_vert_other:
    #         setattr(self, 'bound_shape_org', self.bound_shape)
    #         vert_list1 = self._get_vertex_list_from_face(self.bound_shape)
    #         vert_list1 = self._remove_vertex_duplicates(vert_list1)
    #         vert_list1.reverse()
    #         vert_list1 = self._remove_vertex_duplicates(vert_list1)
    #
    #         setattr(self.related_bound, 'bound_shape_org', self.related_bound.bound_shape)
    #         vert_list2 = self._get_vertex_list_from_face(self.related_bound.bound_shape)
    #         vert_list2 = self._remove_vertex_duplicates(vert_list2)
    #         vert_list2.reverse()
    #         vert_list2 = self._remove_vertex_duplicates(vert_list2)
    #
    #         if len(vert_list1) == len(vert_list2):
    #             self.bound_shape = self._make_face_from_vertex_list(vert_list1)
    #             self.related_bound.bound_shape = self._make_face_from_vertex_list(vert_list2)


    def _set_idfobject_attributes(self, idf):
        if self.surface_type is not None:
            if self.key == "BUILDINGSURFACE:DETAILED":
                if self.surface_type.lower() in {"DOOR".lower(), "Window".lower()}:
                    self.surface_type = "Wall"
                obj = idf.newidfobject(
                    self.key,
                    Name=self.name,
                    Surface_Type=self.surface_type,
                    Construction_Name=self.construction_name,
                    Outside_Boundary_Condition=self.out_bound_cond,
                    Outside_Boundary_Condition_Object=self.out_bound_cond_obj,
                    Zone_Name=self.zone_name,
                    Sun_Exposure=self.sun_exposed,
                    Wind_Exposure=self.wind_exposed,
                )
            # elif self.building_surface_name is None or self.out_bound_cond_obj is None:
            #     self.skip_bound = True
            #     return
            else:
                obj = idf.newidfobject(
                    self.key,
                    Name=self.name,
                    Surface_Type=self.surface_type,
                    Construction_Name=self.construction_name,
                    Building_Surface_Name=self.building_surface_name,
                    Outside_Boundary_Condition_Object=self.out_bound_cond_obj,
                )
            return obj

    def _map_surface_types(self, inst_obj):
        """
        This function maps the attributes of a SpaceBoundary instance to idf surface type
        :param elem: SpaceBoundary instance
        :return: idf surface_type
        """
        elem = inst_obj.bound_instance
        surface_type = None
        if elem != None:
            if elem.ifc_type == "IfcWallStandardCase" or elem.ifc_type == "IfcWall":
                surface_type = 'Wall'
            elif elem.ifc_type == "IfcDoor":
                surface_type = "Door"
            elif elem.ifc_type == "IfcWindow":
                surface_type = "Window"
            elif elem.ifc_type == "IfcRoof":
                surface_type = "Roof"
            elif elem.ifc_type == "IfcSlab":
                # if "floor" in str(elem).lower():
                #     surface_type = "Floor"
                # elif "roof" in str(elem).lower():
                #     surface_type = "Roof"
                # else:
                #     surface_type = "Floor"
                #TODO: Include Ceiling

                if inst_obj.top_bottom == "BOTTOM":
                    surface_type = "Floor"
                elif inst_obj.top_bottom == "TOP":
                    surface_type = "Ceiling"
                    if inst_obj.related_bound is None or inst_obj.is_external:
                        surface_type = "Roof"
        elif inst_obj.physical == False:
            ftc = inst_obj.thermal_zones[0].space_center.XYZ() - inst_obj.bound_center
            ftc.Normalize()
            if ftc.Dot(inst_obj.bound_normal) < 0:
                self.bound_shape = inst_obj.bound_shape.Reversed()
            # surface_type = "VIRTUAL"
            if not self._compare_direction_of_normals(inst_obj.bound_normal, gp_XYZ(0, 0, 1)):
                surface_type = 'Wall'
            else:
                if inst_obj.top_bottom == "BOTTOM":
                    surface_type = "Floor"
                elif inst_obj.top_bottom == "TOP":
                    surface_type = "Ceiling"
        self.surface_type = surface_type

    def _map_boundary_conditions(self, inst_obj):
        """
        This function maps the boundary conditions of a SpaceBoundary instance
        to the idf space boundary conditions
        :return:
        """
        if inst_obj.is_external and inst_obj.physical:
            self.out_bound_cond = 'Outdoors'
            self.sun_exposed = 'SunExposed'
            self.wind_exposed = 'WindExposed'
            self.out_bound_cond_obj = ''

        elif self.surface_type == "Floor" and inst_obj.related_bound is None:
            self.out_bound_cond = "Ground"
            self.sun_exposed = 'NoSun'
            self.wind_exposed = 'NoWind'
        elif inst_obj.related_bound is not None:# or elem.virtual_physical == "VIRTUAL": # elem.internal_external == "INTERNAL"
            self.out_bound_cond = 'Surface'
            self.out_bound_cond_obj = inst_obj.related_bound.ifc.GlobalId
            self.sun_exposed = 'NoSun'
            self.wind_exposed = 'NoWind'
        # elif inst_obj.bound_instance is not None and inst_obj.bound_instance.ifc_type == "IfcWindow":
        elif self.key == "FENESTRATIONSURFACE:DETAILED":
            # if elem.rel_elem.type == "IfcWindow":
            self.out_bound_cond = 'Outdoors'
            self.sun_exposed = 'SunExposed'
            self.wind_exposed = 'WindExposed'
            self.out_bound_cond_obj = ''
        elif self.related_bound is None:
            self.out_bound_cond = 'Outdoors'
            self.sun_exposed = 'SunExposed'
            self.wind_exposed = 'WindExposed'
            self.out_bound_cond_obj = ''
        else:
            self.skip_bound = True

    @staticmethod
    def _compare_direction_of_normals(normal1, normal2):
        """
        Compare the direction of two surface normals (vectors).
        True, if direction is same or reversed
        :param normal1: first normal (gp_Pnt)
        :param normal2: second normal (gp_Pnt)
        :return: True/False
        """
        dotp = normal1.Dot(normal2)
        check = False
        if 1-1e-2 < dotp ** 2 < 1+1e-2:
            check = True
        return check

    @staticmethod
    def _get_points_of_face(bound_shape):
        """
        This function returns a list of gp_Pnt of a Surface
        :param face: TopoDS_Shape (Surface)
        :return: pnt_list (list of gp_Pnt)
        """
        an_exp = TopExp_Explorer(bound_shape, TopAbs_WIRE)
        pnt_list = []

        while an_exp.More():
            wire = topods_Wire(an_exp.Current())
            w_exp = BRepTools_WireExplorer(wire)
            while w_exp.More():
                pnt1 = BRep_Tool.Pnt(w_exp.CurrentVertex())
                pnt_list.append(pnt1)
                w_exp.Next()
            an_exp.Next()
        return pnt_list

    @staticmethod
    def get_circular_shape(obj_pnts):
        """
        This function checks if a SpaceBoundary has a circular shape.
        :param obj_pnts: SpaceBoundary vertices (list of coordinate tuples)
        :return: True if shape is circular
        """
        circular_shape = False
        # compute if shape is circular:
        if len(obj_pnts) > 4:
            pnt = obj_pnts[0]
            pnt2 = obj_pnts[1]
            distance_prev = pnt.Distance(pnt2)
            pnt = pnt2
            for pnt2 in obj_pnts[2:]:
                distance = pnt.Distance(pnt2)
                if (distance_prev - distance) ** 2 < 0.01:
                    circular_shape = True
                    pnt = pnt2
                    distance_prev = distance
                else:
                    continue
        return circular_shape

    @staticmethod
    def _process_circular_shapes(idf, obj_coords, obj, inst_obj):
        """
        This function processes circular boundary shapes. It converts circular shapes
        to triangular shapes.
        :param idf: idf file object
        :param obj_coords: coordinates of an idf object
        :param obj: idf object
        :param elem: SpaceBoundary instance
        :return:
        """
        # print("CIRCULAR")
        drop_count = int(len(obj_coords) / 8)
        drop_list = obj_coords[0::drop_count]
        pnt = drop_list[0]
        counter = 0
        for pnt2 in drop_list[1:]:
            counter += 1
            new_obj = idf.copyidfobject(obj)
            new_obj.Name = str(obj.Name) + '_' + str(counter)
            new_obj.setcoords([pnt, pnt2, inst_obj.bound_center.Coord()])
            pnt = pnt2
        new_obj = idf.copyidfobject(obj)

        new_obj.Name = str(obj.Name) + '_' + str(counter + 1)
        new_obj.setcoords([drop_list[-1], drop_list[0], inst_obj.bound_center.Coord()])
        idf.removeidfobject(obj)

    @staticmethod
    def _process_other_shapes(inst_obj, obj):
        """
        This function processes non-circular shapes with too many vertices
        by approximation of the shape utilizing the UV-Bounds from OCC
        (more than 120 vertices for BUILDINGSURFACE:DETAILED
        and more than 4 vertices for FENESTRATIONSURFACE:DETAILED)
        :param elem: SpaceBoundary Instance
        :param obj: idf object
        :return:
        """
        # print("TOO MANY EDGES")
        obj_pnts = []
        exp = TopExp_Explorer(inst_obj.bound_shape, TopAbs_FACE)
        face = topods_Face(exp.Current())
        umin, umax, vmin, vmax = breptools_UVBounds(face)
        surf = BRep_Tool.Surface(face)
        plane = Handle_Geom_Plane.DownCast(surf).GetObject()
        plane = gp_Pln(plane.Location(), plane.Axis().Direction())
        new_face = BRepBuilderAPI_MakeFace(plane,
                                           umin,
                                           umax,
                                           vmin,
                                           vmax).Face().Reversed()

        face_exp = TopExp_Explorer(new_face, TopAbs_WIRE)
        w_exp = BRepTools_WireExplorer(topods_Wire(face_exp.Current()))
        while w_exp.More():
            wire_vert = w_exp.CurrentVertex()
            obj_pnts.append(BRep_Tool.Pnt(wire_vert))
            w_exp.Next()

        obj_coords = []
        for pnt in obj_pnts:
            obj_coords.append(pnt.Coord())
        obj.setcoords(obj_coords)


    # @staticmethod
    # def _remove_vertex_duplicates(vert_list):
    #     for i, vert in enumerate(vert_list):
    #         edge_pp_p = BRepBuilderAPI_MakeEdge(vert_list[(i) % (len(vert_list) - 1)],
    #                                             vert_list[(i + 1) % (len(vert_list) - 1)]).Shape()
    #         distance = BRepExtrema_DistShapeShape(vert_list[(i + 2) % (len(vert_list) - 1)], edge_pp_p,
    #                                               Extrema_ExtFlag_MIN)
    #         if 0 < distance.Value() < 0.001:
    #             # first: project close vertex to edge
    #             edge = BRepBuilderAPI_MakeEdge(vert_list[(i) % (len(vert_list) - 1)],
    #                                                 vert_list[(i + 1) % (len(vert_list) - 1)]).Edge()
    #             projector = GeomAPI_ProjectPointOnCurve(BRep_Tool.Pnt(vert_list[(i + 2) % (len(vert_list) - 1)]),
    #                                                     BRep_Tool.Curve(edge)[0])
    #             np = projector.NearestPoint()
    #             vert_list[(i + 2) % (len(vert_list) - 1)] = BRepBuilderAPI_MakeVertex(np).Vertex()
    #             # delete additional vertex
    #             vert_list.pop((i + 1) % (len(vert_list) - 1))
    #     return vert_list
    #
    # @staticmethod
    # def _make_face_from_vertex_list(vert_list):
    #     an_edge = []
    #     for i in range(len(vert_list[:-1])):
    #         edge = BRepBuilderAPI_MakeEdge(vert_list[i], vert_list[i + 1]).Edge()
    #         an_edge.append(edge)
    #     a_wire = BRepBuilderAPI_MakeWire()
    #     for edge in an_edge:
    #         a_wire.Add(edge)
    #     a_wire = a_wire.Wire()
    #     a_face = BRepBuilderAPI_MakeFace(a_wire).Face()
    #
    #     return a_face.Reversed()
    #
    # @staticmethod
    # def _get_vertex_list_from_face(face):
    #     an_exp = TopExp_Explorer(face, TopAbs_WIRE)
    #     vert_list = []
    #     while an_exp.More():
    #         wire = topods_Wire(an_exp.Current())
    #         w_exp = BRepTools_WireExplorer(wire)
    #         while w_exp.More():
    #             vert1 = w_exp.CurrentVertex()
    #             vert_list.append(vert1)
    #             w_exp.Next()
    #         an_exp.Next()
    #     vert_list.append(vert_list[0])
    #
    #     return vert_list
    #
    # @staticmethod
    # def _get_number_of_vertices(shape):
    #     shape_analysis = ShapeAnalysis_ShapeContents()
    #     shape_analysis.Perform(shape)
    #     nb_vertex = shape_analysis.NbVertices()
    #
    #     return nb_vertex
    #
