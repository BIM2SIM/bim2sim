from bim2sim.task import Task
from bim2sim.kernel import elements
from bim2sim.decision import DictDecision, ListDecision, RealDecision, BoolDecision
from bim2sim.kernel.element import Element
from bim2sim.kernel.ifc2python import getElementType
from bim2sim.kernel.disaggregation import Disaggregation, SubSlab, SubWall
from bim2sim.kernel import disaggregation as dis
from bim2sim.task.bps_f.bps_functions import get_boundaries, get_polygon
import copy

class Inspect(Task):
    """Analyses IFC, creates Element instances and connects them.

    elements are stored in .instances dict with guid as key"""

    def __init__(self, task):
        super().__init__()
        self.instances = {}
        self.task = task

    @Task.log
    def run(self, ifc):
        self.logger.info("Creates python representation for building spaces")
        self.recognize_zone_semantic(ifc)
        if len(self.instances) == 0:
            self.logger.warning("Found no spaces by semantic detection")
            decision = BoolDecision("Try to detect zones by geometrical?")
            use = decision.decide()
            if use:
                self.recognize_zone_geometrical()
            else:
                # todo abort program, because of missing zones/spaces
                raise NotImplementedError

        self.logger.info("Found %d space entities", len(self.instances))

    def recognize_zone_semantic(self, ifc):
        """Recognizes zones/spaces in ifc file by semantic detection for
        IfcSpace entities"""
        self.logger.info("Create zones by semantic detection")
        ifc_type = 'IfcSpace'
        entities = ifc.by_type(ifc_type)
        for entity in entities:
            thermal_zone = Element.factory(entity, ifc_type)
            self.instances[thermal_zone.guid] = thermal_zone
            self.bind_elements_to_zone(thermal_zone)

    def recognize_zone_geometrical(self):
        """Recognizes zones/spaces by geometric detection"""
        raise NotImplementedError

    def bind_elements_to_zone(self, thermalzone):
        """Binds the different elements to the belonging zones"""
        tn = thermalzone.get_true_north()
        relevant_ifc_types = self.task.workflow.relevant_ifc_types
        bound_instances = []

        for binding in thermalzone.ifc.BoundedBy:
            bound_element = binding.RelatedBuildingElement
            if bound_element is not None:
                bound_element_type = getElementType(bound_element)
            else:
                continue
            # todo virtual element crashs -> solve
            if bound_element_type in relevant_ifc_types:
                bound_instance = thermalzone.get_object(bound_element.GlobalId)
                if bound_instance not in bound_instances:
                    bound_instances.append(bound_instance)
        for bound_instance in bound_instances:
            # bound_instance = Disaggregation.based_on_thermal_zone("Sub_instance_%s" % bound_instance.name, bound_instance, thermalzone)
            disaggregation = 'Sub' + bound_instance.__class__.__name__
            try:
                bound_instance = getattr(dis, disaggregation).based_on_thermal_zone(disaggregation+bound_instance.name, bound_instance, thermalzone)
            except:
                pass
            # if bound_instance.ifc_type == 'IfcSlab':
            #     bound_instance = SubSlab.based_on_thermal_zone("Subslab_%s" % bound_instance.name, bound_instance, thermalzone)
            # if bound_instance.ifc_type == ['IfcWall', 'IfcWallStandardCase']:
            #     bound_instance = SubWall.based_on_thermal_zone("Subwall_%s" % bound_instance.name, bound_instance, thermalzone)
            if bound_instance not in thermalzone.bound_elements:
                thermalzone.bound_elements.append(bound_instance)
            if thermalzone not in bound_instance.thermal_zones:
                bound_instance.thermal_zones.append(thermalzone)


