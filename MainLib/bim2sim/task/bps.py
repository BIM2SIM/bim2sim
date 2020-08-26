"""This module holds tasks related to bps"""

import itertools
import json

from OCC.Display.SimpleGui import init_display
from OCC.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCC.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Extrema import Extrema_ExtFlag_MIN
from OCC.gp import gp_Trsf, gp_Vec, gp_XYZ

from bim2sim.task.base import Task, ITask
from bim2sim.filter import TypeFilter
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
from teaser.logic.buildingobjects.buildingphysics.door import Door
from teaser.logic import utilities
import os
from bim2sim.task.bps_f.bps_functions import orientation_verification
from bim2sim.kernel.units import conversion



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


class ExportTEASER(ITask):
    """Exports a Modelica model with TEASER by using the found information
    from IFC"""

    reads = ('instances', 'ifc', )
    final = True

    materials = {}
    insts = []

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
        prj.name = element.Name
        prj.data.load_uc_binding()

        return prj

    @classmethod
    def _create_building(cls, instance, parent):
        """Creates a building in TEASER by a given BIM2SIM instance
        Parent: Project"""
        bldg = Building(parent=parent)
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

    @staticmethod
    def _teaser_property_getter(teaser_instance, instance, templates):
        """get and set all properties necessary to create a Teaser Instance from a BIM2Sim Instance,
        based on the information on the base.json exporter"""
        sw = type(teaser_instance).__name__
        if sw == 'Rooftop':
            sw = 'Roof'
        for key, value in templates['base'][sw]['exporter']['teaser'].items():
            if isinstance(value, list):
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
                setattr(teaser_instance, key, value)

    @classmethod
    def _create_teaser_instance(cls, instance, parent, bldg):
        """creates a teaser instances with a given parent and BIM2SIM instance
        get exporter necessary properties, from a given instance
        Parent: ThermalZone"""
        # determine if is instance or subinstance (disaggregation)
        if hasattr(instance, 'parent'):
            sw = type(instance.parent).__name__
            templates = instance.parent.finder.templates
        else:
            sw = type(instance).__name__
            templates = instance.finder.templates

        teaser_class = cls.instance_switcher.get(sw)
        if teaser_class is None:
            print('teaser class for instance not found')
        teaser_instance = teaser_class(parent=parent)

        cls._teaser_property_getter(teaser_instance, instance, templates)
        cls._instance_related(teaser_instance, instance, bldg)

        return teaser_instance

    @classmethod
    def _bind_instances_to_zone(cls, tz, tz_instance, bldg):
        """create and bind the instances of a given thermal zone to a teaser instance thermal zone"""
        for bound_element in tz_instance.bound_elements:
            inst = cls._create_teaser_instance(bound_element, tz, bldg)
            cls.insts.append(inst)

    @classmethod
    def _instance_related(cls, teaser_instance, instance, bldg):
        """instance specific function, layers creation
        if layers not given, loads template"""
        if len(instance.layers) > 0:
            for layer_instance in instance.layers:
                layer = Layer(parent=teaser_instance)
                layer.thickness = layer_instance.thickness
                cls._material_related(layer, layer_instance, bldg)
        else:
            construction_type = {InnerWall: 'light',
                                 OuterWall: 'light',
                                 Window: "EnEv",
                                 Rooftop: 'light',
                                 Floor: 'light',
                                 GroundFloor: 'light',
                                 Door: "EnEv"}

            construction = construction_type.get(type(teaser_instance))
            teaser_instance.load_type_element(year=bldg.year_of_construction, construction=construction)

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

                cls.materials[layer_instance.material] = decision1.value
                material_name = decision1.value

            material.load_material_template(
                mat_name=material_name,
                data_class=prj.data,
            )

    @Task.log
    def run(self, workflow, instances, ifc):
        self.logger.info("Export to TEASER")
        prj = self._create_project(ifc.by_type('IfcProject')[0])

        bldg_instances = Inspect.filter_instances(instances, 'Building')
        for bldg_instance in bldg_instances:
            bldg = self._create_building(bldg_instance, prj)
            tz_instances = Inspect.filter_instances(instances, 'ThermalZone')
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
        bldg_instances = Inspect.filter_instances(instances, 'Building')
        print('test')

        for bldg_instance in bldg_instances:
            bldg = Building(parent=prj)
            bldg.used_library_calc = 'AixLib'
            bldg.name = bldg_instance.name
            bldg.year_of_construction = bldg_instance.year_of_construction
            bldg.number_of_floors = bldg_instance.number_of_storeys
            bldg.net_leased_area = bldg_instance.net_area
            tz_instances = Inspect.filter_instances(instances, 'ThermalZone')
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


class ExportEP(ITask):
    """Exports an EnergyPlus model based on IFC information"""

    reads = ('instances', 'ifc', )
    final = True

    @Task.log
    def run(self, workflow, instances, ifc):
        self._get_parents_and_children(instances)
        self._move_children_to_parents(instances)
        self._display_shape_of_space_boundaries(instances)

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
            for opening in b_inst.ifc.HasOpenings:
                if hasattr(opening.RelatedOpeningElement, 'HasFillings'):
                    for fill in opening.RelatedOpeningElement.HasFillings:
                        opening_obj = b_inst.objects[fill.RelatedBuildingElement.GlobalId]
                        if not hasattr(b_inst, 'related_openings'):
                            setattr(b_inst, 'related_openings', [])
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
                for bound in zone.space_boundaries:
                    try:
                        display.DisplayShape(bound.bound_shape, color=colors[(col - 1) % len(colors)])
                    except:
                        continue
                # display.DisplayShape(zone.space_shape, color=colors[(col - 1) % len(colors)])
        display.FitAll()
        start_display()
