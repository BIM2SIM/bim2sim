from bim2sim.task.base import Task, ITask
from bim2sim.decision import BoolDecision
from bim2sim.kernel.element import ProductBased
from ifcopenshell.file import file
from bim2sim.workflow import Workflow


class TZInspect(ITask):
    """Analyses IFC, creates Element instances corresponding to thermal zones and connects them.
    elements are stored in .tz_instances dict with guid as key"""

    reads = ('instances', 'ifc',)
    touches = ('tz_instances',)

    def __init__(self):
        super().__init__()
        self.tz_instances = {}
        self.sb_instances = {}
        pass

    @Task.log
    def run(self, workflow: Workflow, ifc: file, instances: dict):
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

    def recognize_zone_semantic(self, ifc: file):
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
        """Bind thermal_zones and instances to each floor/storey"""
        storeys = SubElement.instances['Storey']
        for storey in storeys.values():
            storey.set_storey_instances()

    def recognize_space_boundaries(self, ifc: file):
        """Recognizes space boundaries in ifc file by semantic detection for
        IfcRelSpaceBoundary entities
        space boundaries are stored in .sb_instances dict with guid as key"""
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
    def bind_elements_to_zone(bound_instances: dict):
        """Binds the different elements to the belonging zones"""

        for bound_instance in bound_instances.values():
            for sb in bound_instance.space_boundaries:
                thermal_zone = sb.thermal_zones[0]
                if bound_instance not in thermal_zone.bound_elements:
                    thermal_zone.bound_elements.append(bound_instance)
                if thermal_zone not in bound_instance.thermal_zones:
                    bound_instance.thermal_zones.append(thermal_zone)

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
