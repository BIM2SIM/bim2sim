from bim2sim.task.base import Task, ITask
from bim2sim.decision import BoolDecision
from bim2sim.workflow import Workflow
from bim2sim.utilities.common_functions import filter_instances
from bim2sim.kernel.elements.bps import Slab, GroundFloor, Floor, Roof


class Prepare(ITask):
    """Analyses IFC, creates Element instances corresponding to thermal zones and connects them.
    elements are stored in .tz_instances dict with guid as key"""

    reads = ('instances', 'space_boundaries',)
    touches = ('tz_instances', 'instances',)

    def __init__(self):
        super().__init__()
        self.tz_instances = {}
        self.reduced_instances = {}
        pass

    @Task.log
    def run(self, workflow: Workflow, instances: dict, space_boundaries: dict):
        self.reduced_instances = dict(instances)
        self.prepare_thermal_zones(instances)
        self.prepare_instances(instances)

        return self.tz_instances, self.reduced_instances

    def prepare_thermal_zones(self, instances):
        """prepare the thermal zones by:
        * binding the elements to a storey, and storeys to the elements
        * setting space properties, with cooling and heating"""

        thermal_zones = filter_instances(instances, 'ThermalZone')
        self.tz_instances = {inst.guid: inst for inst in thermal_zones}

        if len(self.tz_instances) == 0:  # ToDo: Geometric Method before SB creation
            self.logger.warning("Found no spaces by semantic detection")
            decision = BoolDecision("Try to detect zones by geometrical?")
            use = decision.decide()
            if use:
                self.recognize_zone_geometrical()
            else:
                # todo abort program, because of missing zones/spaces
                raise NotImplementedError

        self.bind_elements_to_storey(instances)
        self.set_space_properties()

        self.logger.info("Found %d space entities", len(self.tz_instances))

    @staticmethod
    def bind_elements_to_storey(instances):
        """Bind thermal_zones and instances to each floor/storey and vice versa"""
        storeys = filter_instances(instances, 'Storey')
        for storey in storeys:
            storey_instances = []
            for ifc_structure in storey.ifc.ContainsElements:
                for ifc_element in ifc_structure.RelatedElements:
                    instance = instances.get(ifc_element.GlobalId, None)
                    if instance is not None:
                        storey_instances.append(instance)
                        if storey not in instance.storeys:
                            instance.storeys.append(storey)
            storey_spaces = []
            for ifc_aggregates in storey.ifc.IsDecomposedBy:
                for ifc_element in ifc_aggregates.RelatedObjects:
                    instance = instances.get(ifc_element.GlobalId, None)
                    if instance is not None:
                        storey_spaces.append(instance)
                        if storey not in instance.storeys:
                            instance.storeys.append(storey)

            storey.storey_instances = storey_instances
            storey.thermal_zones = storey_spaces

    def set_space_properties(self):
        """set cooling and heating values based on general question for all building"""

        cooling_decision = self.tz_property_decision('cool')
        heating_decision = self.tz_property_decision('heat')

        for k, tz in self.tz_instances.items():
            if cooling_decision is True:
                tz.with_cooling = True
            if heating_decision is True:
                tz.with_heating = True

    @staticmethod
    def tz_property_decision(property_name: str):
        """thermal zone property decision corresponding cooling and heating for building"""
        decision = BoolDecision(question="Do you want for all the thermal zones to be %sed? - "
                                         "with %sing" % (property_name, property_name),
                                global_key='Thermal_Zones.%sing' % property_name,
                                allow_skip=True, allow_load=True, allow_save=True,
                                collect=False, quick_decide=not True)
        decision.decide()
        return decision.value

    def recognize_zone_geometrical(self):
        """Recognizes zones/spaces by geometric detection"""
        raise NotImplementedError

    def prepare_instances(self, instances):
        """prepare instances based on recheck, can change classes"""
        for inst in instances.values():
            self.prepare_instance_class(inst, instances)

    def prepare_instance_class(self, instance, instances):
        """prepare instances based on different functions:
        * slabs class recheck
        * recognize decomposed roofs"""

        if type(instance).__bases__[0] is Slab or type(instance) is Slab:
            self.better_slab_class(instance)
            self.recognize_decomposed_roofs(instance, instances)

    @staticmethod
    def better_slab_class(instance):
        """do a recheck of selected classes if necessary, and changes it to a new class
        based on criteria and information of the space boundaries"""
        if len(instance.space_boundaries) > 0:
            # TODO Is Floor the most correct here? We might create a new class for such elements
            new_class = Floor
            if instance.is_external is True:
                new_class = Roof
                if instance.top_bottom:
                    if len(instance.top_bottom) == 1:
                        if instance.top_bottom[0] == 'TOP':
                            new_class = GroundFloor
            if new_class != type(instance):
                instance.__class__ = new_class
                # ToDo: More clean way to do this?

    def recognize_decomposed_roofs(self, instance, instances):
        """recognize the roofs that are decomposed on another slabs, and after that:
        * set decompositions on decomposed instance
        * set decomposition properties on decomposed instance"""
        if instance.ifc.IsDecomposedBy:
            for decomp in instance.ifc.IsDecomposedBy:
                for inst_ifc in decomp.RelatedObjects:
                    inst = instances.get(inst_ifc.GlobalId, None)
                    if inst:
                        self.set_decompositions(instance, inst)
                        self.set_decomposition_properties(instance, inst)
                        del self.reduced_instances[inst.guid]

    @staticmethod
    def set_decompositions(instance, d_instance):
        """set decompositions of a decomposed slab and vice versa as list in the instance"""
        if not hasattr(instance, 'decomposed_by'):
            instance.decomposed_by = []
        instance.decomposed_by.append(d_instance)
        if not hasattr(d_instance, 'decomposes'):
            d_instance.decomposes = []
        d_instance.decomposes.append(instance)

    @staticmethod
    def set_decomposition_properties(instance, d_instance):
        """set attributes of decomposes instance, if attribute of decomposed instance not available or invalid"""
        # when decomposed,decomposes instance has attributes of the decomposed instance
        for attr, (value, available) in instance.attributes.items():
            if not value and hasattr(d_instance, attr):
                if getattr(d_instance, attr):
                    setattr(instance, attr, getattr(d_instance, attr))