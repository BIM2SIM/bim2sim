from bim2sim.task.base import Task, ITask
from bim2sim.decision import BoolDecision
from bim2sim.kernel.element import Element, SubElement


class TZInspect(ITask):
    """Analyses IFC, creates Element instances and connects them.
    elements are stored in .instances dict with guid as key"""

    reads = ('instances', 'ifc',)
    touches = ('tz_instances',)

    def __init__(self):
        super().__init__()
        self.tz_instances = {}
        self.sb_instances = {}
        pass

    @Task.log
    def run(self, workflow, ifc, instances):
        self.logger.info("Creates python representation for building spaces")
        self.recognize_zone_semantic(ifc)
        if len(self.tz_instances) == 0:
            self.logger.warning("Found no spaces by semantic detection")
            decision = BoolDecision("Try to detect zones by geometrical?")
            use = decision.decide()
            if use:
                self.recognize_zone_geometrical()
            else:
                # todo abort program, because of missing zones/spaces
                raise NotImplementedError

        self.bind_elements_to_storey()
        self.recognize_space_boundaries(ifc)
        self.bind_elements_to_zone(instances)
        self.set_space_properties()

        self.logger.info("Found %d space entities", len(self.tz_instances))
        self.logger.info("Found %d space boundaries entities", len(self.sb_instances))

        instances.update(self.tz_instances)
        return self.tz_instances,

    def recognize_zone_semantic(self, ifc):
        """Recognizes zones/spaces in ifc file by semantic detection for
        IfcSpace entities"""
        self.logger.info("Create zones by semantic detection")
        ifc_type = 'IfcSpace'
        entities = ifc.by_type(ifc_type)
        for entity in entities:
            thermal_zone = Element.factory(entity, ifc_type)
            self.tz_instances[thermal_zone.guid] = thermal_zone

    @staticmethod
    def bind_elements_to_storey():
        storeys = SubElement.get_class_instances('Storey')
        for storey in storeys:
            storey.set_storey_instances()

    def recognize_space_boundaries(self, ifc):
        """Recognizes space boundaries in ifc file by semantic detection for
        IfcRelSpaceBoundary entities"""
        entities = ifc.by_type('IfcRelSpaceBoundary')

        ifc_type = 'IfcRelSpaceBoundary'
        for entity in entities:
            if entity.RelatedBuildingElement is not None:
                related_element = Element.get_object(entity.RelatedBuildingElement.GlobalId)
                if not entity.RelatingSpace.is_a('IfcSpace'):
                    continue
                if related_element is not None:
                    space_boundary = SubElement.factory(entity, ifc_type)
                    self.sb_instances[space_boundary.guid] = space_boundary

        self.logger.info("Create space boundaries by semantic detection")

    @staticmethod
    def bind_elements_to_zone(bound_instances):
        """Binds the different elements to the belonging zones"""

        for bound_instance in bound_instances.values():
            for sb in bound_instance.space_boundaries:
                thermal_zone = sb.thermal_zones[0]
                if bound_instance not in thermal_zone.bound_elements:
                    thermal_zone.bound_elements.append(bound_instance)
                if thermal_zone not in bound_instance.thermal_zones:
                    bound_instance.thermal_zones.append(thermal_zone)

    def set_space_properties(self):
        cooling_decision = BoolDecision(question="Do you want for all the thermal zones to be cooled? - "
                                                 "with cooling",
                                        global_key='Thermal_Zones.Cooling',
                                        allow_skip=True, allow_load=True, allow_save=True,
                                        collect=False, quick_decide=not True)
        cooling_decision.decide()
        heating_decision = BoolDecision(question="Do you want for all the thermal zones to be heated? - "
                                                 "with heating",
                                        global_key='Thermal_Zones.Heating',
                                        allow_skip=True, allow_load=True, allow_save=True,
                                        collect=False, quick_decide=not True)
        heating_decision.decide()

        for k, tz in self.tz_instances.items():
            if cooling_decision.value is True:
                tz.with_cooling = True
            if heating_decision.value is True:
                tz.with_heating = True

    def recognize_zone_geometrical(self):
        """Recognizes zones/spaces by geometric detection"""
        raise NotImplementedError
