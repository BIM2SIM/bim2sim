"""This module holds tasks related to bps"""

import itertools
import json

from bim2sim.task.base import Task, ITask
# from bim2sim.filter import TypeFilter
from bim2sim.kernel.element import Element, ElementEncoder, BasePort, SubElement
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
from bim2sim.task.bps_f.bps_functions import orientation_verification, get_matches_list, filter_instances, get_pattern_usage
from bim2sim.kernel.units import conversion
from googletrans import Translator
import re

translator = Translator()


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
    reads = ('instances', 'ifc', )
    final = True

    materials = {}
    property_error = {}

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
        error_properties = ['density', 'thickness'] # properties that are vital to thermal zone calculations

        if (aux is None or aux == 0) and key != 'orientation':
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
        # orientation case (in which is valid a 0)
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
                    cls._invalid_property_filter(teaser_instance, instance, key, aux)
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
        if isinstance(instance.layers, list) and len(instance.layers) > 0:
            for layer_instance in instance.layers:
                layer = Layer(parent=teaser_instance)
                cls._invalid_property_filter(layer, layer_instance, 'thickness', layer_instance.thickness)
                cls._material_related(layer, layer_instance, bldg)
        else:
            if getattr(bldg, 'year_of_construction') is None:
                bldg.year_of_construction = int(input("Please provide a valid year of construction for building: "))
            template_options = cls._get_instance_template(teaser_instance, bldg)
            decision_template = None
            if len(template_options) > 0:
                decision_template = ListDecision("the following construction types were "
                                                 "found for year %s and instance %s"
                                                 % (bldg.year_of_construction, teaser_instance.name),
                                                 choices=list(template_options),
                                                 allow_skip=True, allow_load=True, allow_save=True,
                                                 collect=False, quick_decide=not True)
                decision_template.decide()
            teaser_instance.load_type_element(year=bldg.year_of_construction, construction=decision_template.value)

    @classmethod
    def _material_related(cls, layer, layer_instance, bldg):
        """material instance specific functions, get properties of material and creates Material in teaser,
        if material or properties not given, loads material template"""
        material = Material(parent=layer)
        cls._teaser_property_getter(material, layer_instance, layer_instance.finder.templates)

    @staticmethod
    def _get_instance_template(teaser_instance, bldg):
        default = ['heavy', 'light', 'EnEv']
        prj = bldg.parent
        instance_type = type(teaser_instance).__name__
        instance_templates = dict(prj.data.element_bind)
        del instance_templates["version"]
        template_options = []
        for i in instance_templates:
            years = instance_templates[i]['building_age_group']
            if instance_type in i and years[0] <= bldg.year_of_construction <= years[1]:
                template_options.append(instance_templates[i]['construction_type'])
        if len(template_options) == 0:
            return default
        return template_options

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


class ExportTEASERMultizone(ITask):
    """Exports a Modelica model with TEASER by using the found information
    from IFC"""

    reads = ('instances', )
    final = True

    @staticmethod
    def _create_thermal_zone(instance, bldg):
        """Creates a thermalzone in TEASER by a given BIM2SIM instance"""
        tz = ThermalZone(parent=bldg)
        tz.name = instance.name
        if instance.area is not None:
            tz.area = instance.area
        tz.volume = instance.net_volume
        # todo: infiltration rate
        tz.use_conditions = UseConditions(parent=tz)
        tz.use_conditions.load_use_conditions("Living")
        # tz.use_conditions.load_use_conditions(instance.usage)
        # todo make kelvin celsius robust
        tz.use_conditions.set_temp_heat = \
            instance.t_set_heat + 273.15
        tz.use_conditions.set_temp_cool = \
            297.15
        tz.number_of_elements = 2
        tz.use_conditions.with_cooling = True
        return tz


    def run(self, workflow, instances):
        # mapping_dict = {
        #     elements.Floor.instances: Floor,
        #     elements.Window.instances: Window,
        #     elements.Roof.instances: Rooftop,
        #     elements.Wall.outer_walls: OuterWall,
        #     elements.Wall.inner_walls: InnerWall
        # }

        self.logger.info("Export to TEASER")
        prj = Project(load_data=True)
        #Todo get project name (not set to PROJECT yet)
        prj.name = 'Testproject'
        prj.data.load_uc_binding()
        bldg_instances = filter_instances(instances, 'Building')
        print('test')

        for bldg_instance in bldg_instances:
            bldg = Building(parent=prj)
            bldg.used_library_calc = 'AixLib'
            bldg.name = bldg_instance.name
            bldg.year_of_construction = bldg_instance.year_of_construction
            bldg.number_of_floors = bldg_instance.number_of_storeys
            bldg.net_leased_area = bldg_instance.net_area
            tz_instances = filter_instances(instances, 'ThermalZone')
            for tz_instance in tz_instances:
                tz = self._create_thermal_zone(tz_instance, bldg)
                for bound_element in tz_instance.bound_elements:
                    if isinstance(bound_element, elements.InnerWall)\
                            or isinstance(bound_element,
                                          disaggregation.SubInnerWall):
                        in_wall = InnerWall(parent=tz)
                        in_wall.name = bound_element.name
                        in_wall.area = bound_element.area
                        in_wall.orientation = int(bound_element.orientation)
                        if bound_element.orientation is None:
                            print('damn')
                        in_wall.load_type_element(
                            year=bldg.year_of_construction,
                            construction="heavy")
                            # todo material
                    elif type(bound_element) == elements.OuterWall or \
                            type(bound_element) == disaggregation.SubOuterWall:
                        out_wall = OuterWall(parent=tz)
                        out_wall.name = bound_element.name
                        out_wall.area = bound_element.area
                        out_wall.tilt = bound_element.tilt
                        out_wall.orientation = int(bound_element.orientation)
                        if bound_element.orientation is None:
                            print('damn')
                        if type(bound_element) == elements.OuterWall:
                            layer_instances = bound_element.layers
                        elif type(bound_element) == \
                                disaggregation.SubOuterWall:
                            layer_instances = bound_element.parent.layers
                        for layer_instance in layer_instances:
                            layer = Layer(parent=out_wall)
                            layer.thickness = layer_instance.thickness
                            material = Material(parent=layer)
                            # todo remove hardcode
                            material.load_material_template(
                                mat_name='Vermiculit_bulk_density_170_100deg'
                                ,
                                data_class=prj.data,
                                )
                    elif isinstance(bound_element, elements.Window):
                        window = Window(parent=tz)
                        window.name = bound_element.name
                        window.area = bound_element.area
                        window.load_type_element(
                            year=bldg.year_of_construction, construction="EnEv"
                        )
                        window.innner_convection = 0.6
                        window.orientation = int(bound_element.orientation)
                        if window.orientation is None:
                            print('damn')
                    elif isinstance(bound_element, elements.Roof) or \
                        isinstance(bound_element, disaggregation.SubRoof):
                        roof_element = Rooftop(parent=tz)
                        # todo remove hardcode
                        roof_element.orientation = -1
                        roof_element.area = bound_element.area
                        roof_element.load_type_element(
                            year=bldg.year_of_construction, construction="heavy"
                        )
                    elif isinstance(bound_element, elements.Floor) or \
                        isinstance(bound_element, disaggregation.SubFloor):
                        floor_element = Floor(parent=tz)
                        floor_element.area = bound_element.area
                        floor_element.orientation = -2
                        floor_element.load_type_element(
                            year=bldg.year_of_construction, construction="heavy"
                        )
                    elif isinstance(bound_element, elements.GroundFloor) or \
                        isinstance(bound_element, disaggregation.SubGroundFloor):
                        gfloor_element = GroundFloor(parent=tz)
                        gfloor_element.orientation = -2
                        gfloor_element.area = bound_element.area
                        gfloor_element.load_type_element(
                            year=bldg.year_of_construction, construction="heavy"
                        )

                # catch error for no inner walls areas
                if len(tz.inner_walls) ==0:
                    in_wall = InnerWall(parent=tz)
                    in_wall.name = "dummy"
                    in_wall.area = 0.01
                    in_wall.load_type_element(
                        year=bldg.year_of_construction,
                        construction="heavy")
                try:
                    tz.calc_zone_parameters()
                except:
                    pass
            bldg.calc_building_parameter(number_of_elements=2)
            prj.weather_file_path = utilities.get_full_path(
                os.path.join(
                    "D:/09_OfflineArbeiten/Bausim2020/RefResults_FZKHaus"
                    "/KIT_CampusEPW.mos"))
            prj.export_aixlib()

class ExportTEASERSingleZone(Task):
    """Exports a Modelica model with TEASER by using the found information
    from IFC"""
    #todo: for this LOD the slab sicing must be deactivated and building
    # elements must be only included once in the thermalzone even if they are
    # holded by different IfcSpaces
    @staticmethod
    def _create_thermal_single_zone(instances, bldg):
        """Creates a thermalzone in TEASER by a given BIM2SIM instance"""
        tz = ThermalZone(parent=bldg)
        tz.name = "SingleZoneFZK"
        tz.use_conditions = UseConditions(parent=tz)
        tz.use_conditions.load_use_conditions("Living")
        # set_temp_heat_median = sum((instance.t_set_heat + 273.15) *
        #                            instance.area *
        #                            instance.height for instance in
        #                            instances) / \
        #                        sum(instance.area * instance.height for
        #                            instance in instances)
        # set_temp_cool_median = sum((instance.t_set_cool + 273.15) *
        #                            instance.area *
        #                            instance.height for instance in
        #                            instances) / \
        #                        sum(instance.area * instance.height for
        #                            instance in instances)
        tz.area = 0
        tz.volume = 0
        for instance in instances:
            tz.area += instance.area
            tz.volume += instance.net_volume
        # todo: infiltration rate
        # todo make kelvin celsius robust
        tz.number_of_elements = 2
        tz.use_conditions.with_cooling = True
        return tz


    def run(self, workflow, bps_inspect):
        # mapping_dict = {
        #     elements.Floor.instances: Floor,
        #     elements.Window.instances: Window,
        #     elements.Roof.instances: Rooftop,
        #     elements.Wall.outer_walls: OuterWall,
        #     elements.Wall.inner_walls: InnerWall
        # }

        self.logger.info("Export to TEASER")
        # raise NotImplementedError("Not working probably at the moment")
        prj = Project(load_data=True)
        #Todo get project name (not set to PROJECT yet)
        prj.name = 'Testproject'
        prj.data.load_uc_binding()
        bldg_instances = bps_inspect.filter_instances('Building')

        for bldg_instance in bldg_instances:
            bldg = Building(parent=prj)
            bldg.used_library_calc = 'AixLib'

            bldg.name = bldg_instance.name
            bldg.year_of_construction = bldg_instance.year_of_construction
            bldg.number_of_floors = bldg_instance.number_of_storeys
            bldg.net_leased_area = bldg_instance.net_area
            tz_instances = bps_inspect.filter_instances('ThermalZone')
            tz = self._create_thermal_single_zone(tz_instances, bldg)

            for bound_element in bps_inspect.instances.values():
                if isinstance(bound_element, elements.InnerWall)\
                        or isinstance(bound_element,
                                      disaggregation.SubInnerWall):
                    in_wall = InnerWall(parent=tz)
                    in_wall.name = bound_element.name
                    in_wall.area = bound_element.area
                    in_wall.orientation = int(bound_element.orientation)
                    if bound_element.orientation is None:
                        print('damn')
                    in_wall.load_type_element(
                        year=bldg.year_of_construction,
                        construction="heavy")
                        # todo material
                elif type(bound_element) == elements.OuterWall or \
                        type(bound_element) == disaggregation.SubOuterWall:
                    out_wall = OuterWall(parent=tz)
                    out_wall.name = bound_element.name
                    out_wall.area = bound_element.area
                    out_wall.tilt = bound_element.tilt
                    out_wall.orientation = int(bound_element.orientation)
                    if bound_element.orientation is None:
                        print('damn')
                    if type(bound_element) == elements.OuterWall:
                        layer_instances = bound_element.layers
                    elif type(bound_element) == \
                            disaggregation.SubOuterWall:
                        layer_instances = bound_element.parent.layers
                    for layer_instance in layer_instances:
                        layer = Layer(parent=out_wall)
                        layer.thickness = layer_instance.thickness
                        material = Material(parent=layer)
                        # todo remove hardcode
                        material.load_material_template(
                            mat_name='Vermiculit_bulk_density_170_100deg'
                            ,
                            data_class=prj.data,
                            )
                elif isinstance(bound_element, elements.Window):
                    window = Window(parent=tz)
                    window.name = bound_element.name
                    window.area = bound_element.area
                    window.load_type_element(
                        year=bldg.year_of_construction, construction="EnEv"
                    )
                    window.innner_convection = 0.6
                    window.orientation = int(bound_element.orientation)
                    if window.orientation is None:
                        print('damn')
                elif isinstance(bound_element, elements.Roof) or \
                    isinstance(bound_element, disaggregation.SubRoof):
                    roof_element = Rooftop(parent=tz)
                    # todo remove hardcode
                    roof_element.orientation = -1
                    roof_element.area = bound_element.area
                    roof_element.load_type_element(
                        year=bldg.year_of_construction, construction="heavy"
                    )
                elif isinstance(bound_element, elements.Floor) or \
                    isinstance(bound_element, disaggregation.SubFloor):
                    floor_element = Floor(parent=tz)
                    floor_element.area = bound_element.area
                    floor_element.orientation = -2
                    floor_element.load_type_element(
                        year=bldg.year_of_construction, construction="heavy"
                    )
                elif isinstance(bound_element, elements.GroundFloor) or \
                    isinstance(bound_element, disaggregation.SubGroundFloor):
                    gfloor_element = GroundFloor(parent=tz)
                    gfloor_element.orientation = -2
                    gfloor_element.area = bound_element.area
                    gfloor_element.load_type_element(
                        year=bldg.year_of_construction, construction="heavy"
                    )

                # catch error for no inner walls areas
                if len(tz.inner_walls) ==0:
                    in_wall = InnerWall(parent=tz)
                    in_wall.name = "dummy"
                    in_wall.area = 0.01
                    in_wall.load_type_element(
                        year=bldg.year_of_construction,
                        construction="heavy")

            tz.calc_zone_parameters()
            bldg.calc_building_parameter(number_of_elements=2)
            prj.export_aixlib()


