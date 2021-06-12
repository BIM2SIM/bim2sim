from bim2sim.task.base import Task, ITask
from bim2sim.decision import BoolDecision
from bim2sim.workflow import Workflow
from bim2sim.utilities.common_functions import filter_instances
from bim2sim.kernel.elements.bps import Slab, GroundFloor, Floor, Roof


class Prepare(ITask):  # ToDo: change to prepare
    """Analyses IFC, creates Element instances corresponding to thermal zones and connects them.
    elements are stored in .tz_instances dict with guid as key"""

    reads = ('instances', 'space_boundaries',)
    touches = ('tz_instances',)

    def __init__(self):
        super().__init__()
        self.tz_instances = {}
        pass

    @Task.log
    def run(self, workflow: Workflow, instances: dict, space_boundaries: dict):
        self.prepare_thermal_zones(instances)
        self.prepare_instances(instances)

        return self.tz_instances,

    def prepare_thermal_zones(self, instances):
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
        """Bind thermal_zones and instances to each floor/storey"""
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

        gfs = filter_instances(instances, 'GroundFloor')
        for i in gfs:
            x = i.is_external

        for inst in instances.values():
            self.prepare_instance_class(inst)

        slabs = filter_instances(instances, 'Floor') + filter_instances(instances, 'GroundFloor') \
            + filter_instances(instances, 'Roof')
        g_slabs = {inst.guid: inst for inst in slabs}

        for sl in slabs:
            if sl.ifc.IsDecomposedBy:
                print()
            elif sl.ifc.Decomposes:
                print()

    @staticmethod
    def prepare_instance_class(instance):
        """do a recheck of selected classes if necessary, and changes it to a new class
        based on criteria and information of the space boundaries"""
        if type(instance).__bases__[0] is Slab:
            # GroundFloor recognition
            new_class = Floor
            if instance.is_external:
                new_class = Roof
                if instance.top_bottom:
                    if len(instance.top_bottom) == 1:
                        if instance.top_bottom[0] == 'TOP':
                            new_class = GroundFloor
                        # else:
                        #     new_class = Roof
            if new_class != type(instance):
                instance.__class__ = new_class
                # ToDo: More clean way to do this?
