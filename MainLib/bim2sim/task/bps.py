"""This module holds tasks related to bps"""

import itertools
import json
import ast

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
from bim2sim.decision import ListDecision, BoolDecision, RealDecision
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
from bim2sim.task.bps_f.bps_functions import get_matches_list, filter_instances, \
    get_pattern_usage, vector_angle, angle_equivalent, real_decision_user_input
    # get_material_value_templates_resumed
from bim2sim.kernel.units import conversion


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


class Prepare(ITask):
    """Prepares bim2sim instances to later export"""
    reads = ('instances', 'ifc',)
    touches = ('instances',)

    # materials = {}
    # property_error = {}
    instance_template = {}

    @Task.log
    def run(self, workflow, instances, ifc):
        self.logger.info("setting verifications")
        building = filter_instances(instances, 'Building')[0]
        for guid, ins in instances.items():
            self.layers_verification(ins, building)

        storeys = filter_instances(instances, 'Storey')

        tz_inspect = tz_detection.Inspect(self, workflow)
        tz_inspect.run(ifc, storeys)
        instances.update(tz_inspect.instances)

        for guid, ins in instances.items():
            new_orientation = self.orientation_verification(ins)
            if new_orientation is not None:
                ins.orientation = new_orientation

        tz_bind = tz_detection.Bind(self, workflow)
        tz_bind.run(instances)

        return instances,

    @staticmethod
    def orientation_verification(instance):
        supported_classes = {'Window', 'OuterWall', 'OuterDoor', 'Wall', 'Door'}
        if instance.__class__.__name__ in supported_classes:
            new_angles = list(set([space_boundary.orientation for space_boundary in instance.space_boundaries]))
            # new_angles = list(set([space_boundary.orientation - space_boundary.thermal_zones[0].orientation for space_boundary in instance.space_boundaries]))
            if len(new_angles) > 1:
                return None
            # no true north necessary
            new_angle = angle_equivalent(new_angles[0])
            # new angle return
            if new_angle - instance.orientation > 0.1:
                return new_angle

    @classmethod
    def layers_verification(cls, instance, building):
        supported_classes = {'OuterWall', 'Wall', 'InnerWall', 'Door', 'InnerDoor', 'OuterDoor', 'Roof', 'Floor',
                             'GroundFloor', 'Window'}
        instance_type = instance.__class__.__name__
        if instance_type in supported_classes:
            # through the type elements enrichment without comparisons
            if instance_type not in cls.instance_template:
                type_elements_decision = BoolDecision(
                    question="Do you want for all %ss to be enriched before any calculation "
                             "with the type elements template," % type(instance).__name__,
                    global_key="type_elements_%s" % type(instance).__name__,
                    collect=False)
                type_elements_decision.decide()
                if type_elements_decision.value:
                    return cls.template_layers_creation(instance, building)
            else:
                return cls.template_layers_creation(instance, building)
            u_value_verification = cls.compare_with_template(instance, building)
            # comparison with templates value
            if u_value_verification is False:
                cls.logger.warning("u_value verification failed, the %s u value is "
                                    "doesn't correspond to the year of construction. Please create new layer set" %
                                    type(instance).__name__)
                return cls.layer_creation(instance, building)
            # instance.layers = [] # probe
            layers_width = 0
            layers_r = 0
            for layer in instance.layers:
                layers_width += layer.thickness
                if layer.thermal_conduc is not None:
                    if layer.thermal_conduc > 0:
                        layers_r += layer.thickness / layer.thermal_conduc

            # critical failure // check units again
            width_discrepancy = abs(instance.width - layers_width) / instance.width if \
                (instance.width is not None and instance.width > 0) else 9999
            u_discrepancy = abs(instance.u_value - 1 / layers_r) / instance.u_value if \
                (instance.u_value is not None and instance.u_value > 0) else 9999
            if width_discrepancy > 0.2 or u_discrepancy > 0.2:
                cls.logger.warning("Width or U Value discrepancy found. Please create new layer set")
                cls.layer_creation(instance, building)

    def layer_creation(self, instance, building):
        decision_layers = ListDecision("the following layer creation methods were found",
                                       choices=['Manual layers creation (from zero)',
                                                'Template layers creation (based on given u value)'],
                                       allow_skip=True, allow_load=True, allow_save=True,
                                       collect=False, quick_decide=not True)
        decision_layers.decide()
        if decision_layers.value == 'Manual layers creation (from zero)':
            self.manual_layers_creation(instance, building)
        elif decision_layers.value == 'Template layers creation (based on given u value)':
            self.template_layers_creation(instance, building)

    def manual_layers_creation(self, instance, building):
        instance.layers = []
        layers_width = 0
        layers_r = 0
        layers_number_dec = RealDecision("Enter value for the number of layers",
                                         # global_key="layers_number_%s" % instance.name,
                                         allow_skip=False, allow_load=True, allow_save=True,
                                         collect=False, quick_decide=False)
        layers_number_dec.decide()
        layers_number = int(layers_number_dec.value)
        layer_number = 1
        while layer_number <= layers_number:
            if layer_number == layers_number:
                thickness_value = instance.width-layers_width
            else:
                layer_thickness = RealDecision("Enter value for thickness of layer %d, it muss be <= %r" %
                                               (layer_number, instance.width-layers_width),
                                               # global_key="thickness layer_%s_%d" % (instance.name, layer_number),
                                               allow_skip=False, allow_load=True, allow_save=True,
                                               collect=False, quick_decide=False)
                layer_thickness.decide()
                thickness_value = layer_thickness.value
            material_input = input("Enter material for the layer %d (it will be searched or manual input)" % layer_number)
            new_layer = elements.Layer.create_additional_layer(thickness_value, material=material_input)
            instance.layers.append(new_layer)
            layers_width += new_layer.thickness
            layers_r += new_layer.thickness / new_layer.thermal_conduc
            if layers_width >= instance.width:
                break
            layer_number += 1

        instance.u_value = 1/layers_r
        # check validity of new u value e
        while self.compare_with_template(instance, building) is False:
            self.logger.warning("The created layers does not comply with the valid u_value range, "
                                "please create new layer set")
            self.layer_creation(instance, building)
        pass

    @classmethod
    def template_layers_creation(cls, instance, building):
        instance.layers = []
        layers_width = 0
        layers_r = 0
        template = cls.get_instance_template(instance, building)
        if template is not None:
            for i_layer, layer_props in template['layer'].items():
                new_layer = elements.Layer.create_additional_layer(
                    layer_props['thickness'], instance, material=layer_props['material']['name'])
                instance.layers.append(new_layer)
                layers_width += new_layer.thickness
                layers_r += new_layer.thickness / new_layer.thermal_conduc
            instance.width = layers_width
            instance.u_value = 1 / layers_r
        # with template comparison not necessary
        pass

    @classmethod
    def compare_with_template(cls, instance, building):
        template_options = []
        if instance.u_value is None:
            return False
        year_of_construction = building.year_of_construction
        if year_of_construction is None:
            year_decision = RealDecision("Enter value for the year of construction",
                                         global_key="year",
                                         allow_skip=False, allow_load=True, allow_save=True,
                                         collect=False, quick_decide=False)
            year_decision.decide()
            year_of_construction = int(year_decision.value.m)
        else:
            year_of_construction = int(building.year_of_construction)

        instance_templates = dict(DataClass(used_param=3).element_bind)
        material_templates = dict(DataClass(used_param=2).element_bind)
        instance_type = type(instance).__name__
        for i in instance_templates[instance_type]:
            years = ast.literal_eval(i)
            if years[0] <= year_of_construction <= years[1]:
                for type_e in instance_templates[instance_type][i]:
                    # relev_info = instance_templates[instance_type][i][type_e]
                    # if instance_type == 'InnerWall':
                    #     layers_r = 2 / relev_info['inner_convection']
                    # else:
                    #     layers_r = 1 / relev_info['inner_convection'] + 1 / relev_info['outer_convection']
                    layers_r = 0
                    for layer, data_layer in instance_templates[instance_type][i][type_e]['layer'].items():
                        material_tc = material_templates[data_layer['material']['material_id']]['thermal_conduc']
                        layers_r += data_layer['thickness'] / material_tc
                    template_options.append(1 / layers_r)  # area?
                break

        template_options.sort()
        # check u_value
        if template_options[0]*0.8 <= instance.u_value <= template_options[1]*1.2:
            return True
        return False

    @classmethod
    def get_instance_template(cls, instance, building):

        instance_type = type(instance).__name__
        instance_templates = dict(DataClass(used_param=3).element_bind)
        if instance_type in cls.instance_template:
            return cls.instance_template[instance_type]

        year_of_construction = building.year_of_construction
        if year_of_construction is None:
            year_decision = RealDecision("Enter value for the year of construction",
                                         global_key="year",
                                         allow_skip=False, allow_load=True, allow_save=True,
                                         collect=False, quick_decide=False)
            year_decision.decide()
            building.year_of_construction = int(year_decision.value.m)

        year_of_construction = int(building.year_of_construction)
        template_options = []
        for i in instance_templates[instance_type]:
            years = ast.literal_eval(i)
            if years[0] <= year_of_construction <= years[1]:
                template_options = instance_templates[instance_type][i]
                break

        if len(template_options.keys()) > 0:
            decision_template = ListDecision("the following construction types were "
                                             "found for year %s and instance type %s"
                                             % (year_of_construction, instance_type),
                                             choices=list(template_options.keys()),
                                             global_key="bpsTemplate.%s" % instance.guid,
                                             allow_skip=True, allow_load=True, allow_save=True,
                                             collect=False, quick_decide=not True)
            if decision_template.value is None:
                decision_template.decide()
            template_value = template_options[decision_template.value]
            cls.instance_template[instance_type] = template_value
            return template_value


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
                         # 'OuterDoor': OuterWall,
                         # 'InnerDoor': InnerWall
                         }

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
        if instance.t_set_heat:
            tz.use_conditions.set_temp_heat = conversion(instance.t_set_heat, '°C', 'K').magnitude
        if instance.t_set_cool:
            tz.use_conditions.set_temp_cool = conversion(instance.t_set_cool, '°C', 'K').magnitude

        tz.use_conditions.cooling_profile = [conversion(25, '°C', 'K').magnitude] * 25
        tz.use_conditions.with_cooling = instance.with_cooling
        if PROJECT.PAPER:
            tz.use_conditions.cooling_profile = [conversion(25, '°C', 'K').magnitude] * 25
            tz.use_conditions.with_cooling = instance.with_cooling
            tz.use_conditions.use_constant_infiltration = True
            tz.use_conditions.infiltration_rate = 0.2

        return tz

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
    def _invalid_property_filter(cls, teaser_instance, instance, key, aux):
        """Filter the invalid property values and fills it with a template or an user given value,
        if value is valid, returns the value
        invalid value: ZeroDivisionError on thermal zone calculations"""
        error_properties = ['density', 'thickness', 'heat_capac',
                            'thermal_conduc']  # properties that are vital to thermal zone calculations
        white_list_properties = ['orientation']
        if (aux is None or aux == 0) and key not in white_list_properties:
            # name from instance to store in error dict
            if hasattr(instance, 'material'):
                name_error = instance.material
            else:
                name_error = instance.name
            try:
                aux = cls.property_error[name_error][key]
            # redundant case for invalid properties
            except KeyError:
                if key in error_properties:
                    if hasattr(instance, 'get_material_properties'):
                        aux = instance.get_material_properties(key)
                    while aux is None or aux == 0:
                        aux = float(input('please enter a valid value for %s from %s' % (key, name_error)))
                    if name_error not in cls.property_error:
                        cls.property_error[name_error] = {}
                    cls.property_error[name_error][key] = aux
        # set attr on teaser instance
        setattr(teaser_instance, key, aux)

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
                cls._invalid_property_filter(layer, layer_instance, 'thickness', layer_instance.thickness)
                cls._material_related(layer, layer_instance, bldg)
        # property getter if instance doesn't have any materials/layers
        else:
            if getattr(bldg, 'year_of_construction') is None:
                bldg.year_of_construction = int(input("Please provide a valid year of construction for building: "))
            template_options, years_group = cls._get_instance_template(teaser_instance, bldg)
            template_value = None
            if len(template_options) > 1:
                decision_template = ListDecision("the following construction types were "
                                                 "found for year %s and instance type %s"
                                                 % (bldg.year_of_construction, type(teaser_instance).__name__),
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
        material = Material(parent=layer)
        cls._teaser_property_getter(material, layer_instance, layer_instance.finder.templates)

    @classmethod
    def _get_instance_template(cls, teaser_instance, bldg):
        default = ['heavy', 'light', 'EnEv']
        year_group = [1995, 2015]  # default year group
        prj = bldg.parent
        instance_type = type(teaser_instance).__name__
        instance_templates = dict(prj.data.element_bind)
        del instance_templates["version"]
        if bldg.name in cls.instance_template:
            if instance_type in cls.instance_template[bldg.name]:
                year_group = str(cls.instance_template[bldg.name][instance_type][0])
                selected_template = cls.instance_template[bldg.name][instance_type][1]
                aux_template = '%s_%s_%s' % (instance_type, year_group, selected_template)
                # if aux_template in instance_templates:
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

        # prj.weather_file_path = utilities.get_full_path(
        #     os.path.join(
        #         'D:/09_OfflineArbeiten/Bim2Sim/Validierung_EP_TEASER/Resources/DEU_NW_Aachen.105010_TMYx.mos'))
        # self.logger.info(Decision.summary())
        # import pickle
        #
        # filename = os.path.join('D:/09_OfflineArbeiten/Bim2Sim/Validierung_EP_TEASER/TEASERPickles/teaser_pickled_Inst')
        # outfile = open(filename, 'wb')
        # pickle.dump(prj, outfile)
        # outfile.close()
        #
        # with open(os.path.join(
        #         'D:/09_OfflineArbeiten/Bim2Sim/Validierung_EP_TEASER/TEASERPickles/teaser_pickled_Inst'), 'rb') as f:
        #     prj = pickle.load(f)
        #
        # print('test')
        # self.logger.info(Decision.summary())
        # Decision.decide_collected()
        # Decision.save(PROJECT.decisions)
        #
        # Decision.save(
        #     os.path.join('D:/09_OfflineArbeiten/Bim2Sim/Validierung_EP_TEASER/TEASERPickles/current_decisions.json'))
        # prj.calc_all_buildings()

        prj.export_aixlib(path=PROJECT.root / 'export' / 'TEASEROutput')
        print()

