import inspect

from bim2sim.task.base import Task, ITask
from bim2sim.decision import BoolDecision, ListDecision
from bim2sim.kernel.element import SubElement
from bim2sim.project import PROJECT
from bim2sim.kernel.aggregation import Aggregated_ThermalZone
from teaser.project import Project
from teaser.logic.buildingobjects.building import Building
from teaser.logic.buildingobjects.thermalzone import ThermalZone
from teaser.logic.buildingobjects.useconditions import UseConditions
from teaser.logic.buildingobjects.buildingphysics.outerwall import OuterWall
from teaser.logic.buildingobjects.buildingphysics.floor import Floor
from teaser.logic.buildingobjects.buildingphysics.rooftop import Rooftop
from teaser.logic.buildingobjects.buildingphysics.groundfloor import GroundFloor
from teaser.logic.buildingobjects.buildingphysics.window import Window
from teaser.logic.buildingobjects.buildingphysics.innerwall import InnerWall
from teaser.logic.buildingobjects.buildingphysics.layer import Layer
from teaser.logic.buildingobjects.buildingphysics.material import Material
from teaser.logic.buildingobjects.buildingphysics.door import Door
from bim2sim.kernel.units import conversion, ureg



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
                         'OuterDoor': Door,
                         }

    @Task.log
    def run(self, workflow, instances, ifc):
        self.logger.info("Export to TEASER")
        prj = self._create_project(ifc.by_type('IfcProject')[0])
        bldg_instances = SubElement.get_class_instances('Building')
        for bldg_instance in bldg_instances:
            bldg = self._create_building(bldg_instance, prj)
            tz_instances = SubElement.get_class_instances('ThermalZone')
            for tz_instance in tz_instances:
                tz = self._create_thermal_zone(tz_instance, bldg)
                self._bind_instances_to_zone(tz, tz_instance, bldg)
                tz.calc_zone_parameters()
            bldg.calc_building_parameter()

        prj.export_aixlib(path=PROJECT.root / 'export' / 'TEASEROutput')

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
                    if type(aux) is ureg.Quantity:
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
                    aux = instance.get_material_properties(key)
                    if name_error not in cls.property_error:
                        cls.property_error[name_error] = {}
                    cls.property_error[name_error][key] = aux
        # set attr on teaser instance
        setattr(teaser_instance, key, aux)


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
    def _bind_instances_to_zone(cls, tz, tz_instance, bldg):
        """create and bind the instances of a given thermal zone to a teaser instance thermal zone"""
        for bound_element in tz_instance.bound_elements:
            cls._create_teaser_instance(bound_element, tz, bldg)

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
    def _instance_related(cls, teaser_instance, instance, bldg):
        """instance specific function, layers creation
        if layers not given, loads template"""
        # property getter if instance has materials/layers
        if isinstance(instance.layers, list) and len(instance.layers) > 0:
            for layer_instance in instance.layers:
                layer = Layer(parent=teaser_instance)
                cls._invalid_property_filter(layer, layer_instance, 'thickness', layer_instance.thickness.m)
                cls._material_related(layer, layer_instance, bldg)

    @classmethod
    def _material_related(cls, layer, layer_instance, bldg):
        """material instance specific functions, get properties of material and creates Material in teaser,
        if material or properties not given, loads material template"""
        material = Material(parent=layer)
        cls._teaser_property_getter(material, layer_instance, layer_instance.finder.templates)
