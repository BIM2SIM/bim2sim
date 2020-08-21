from bim2sim.task.base import Task
from bim2sim.decision import BoolDecision
from bim2sim.kernel.element import Element, SubElement
from bim2sim.kernel.ifc2python import getElementType
from bim2sim.kernel.disaggregation import Disaggregation

from OCC.Display.SimpleGui import init_display



class Inspect(Task):
    """Analyses IFC, creates Element instances and connects them.

    elements are stored in .instances dict with guid as key"""

    def __init__(self, task, workflow):
        super().__init__()
        self.ifc = None
        self.instances = {}
        self.task = task
        self.workflow = workflow

    @Task.log
    def run(self, ifc):
        self.ifc = ifc
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

        self.recognize_space_boundaries(ifc)
        self.logger.info("Found %d space boundaries entities", len(self.instances))

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
        bound_instances = []
        for binding in thermalzone.ifc.BoundedBy:
            bound_element = binding.RelatedBuildingElement
            if bound_element is not None:# and binding.PhysicalOrVirtualBoundary is not 'VIRTUAL':
                bound_element_type = getElementType(bound_element)
            else:
                continue
            # if bound_element_type in relevant_ifc_types:
            bound_instance = thermalzone.get_object(bound_element.GlobalId)
            if bound_instance not in bound_instances and bound_instance is not None:
                bound_instances.append(bound_instance)
        for bound_instance in bound_instances:
            new_bound_instances = Disaggregation.based_on_thermal_zone(bound_instance, thermalzone)
            for inst in new_bound_instances:
                if inst not in thermalzone.bound_elements:
                    thermalzone.bound_elements.append(inst)
                if thermalzone not in inst.thermal_zones:
                    inst.thermal_zones.append(thermalzone)
            # disaggregation check:
            # if not Disaggregation.based_on_thermal_zone(bound_instance, thermalzone):
            #     if bound_instance not in thermalzone.bound_elements:
            #         thermalzone.bound_elements.append(bound_instance)
            #     if thermalzone not in bound_instance.thermal_zones:
            #         bound_instance.thermal_zones.append(thermalzone)

    def recognize_space_boundaries(self, ifc):
        """Recognizes space boundaries in ifc file by semantic detection for
        IfcRelSpaceBoundary entities"""
        self.logger.info("Create space boundaries by semantic detection")
        ifc_type = 'IfcRelSpaceBoundary'
        entities = ifc.by_type(ifc_type)
        for entity in entities:
            space_boundary = SubElement.factory(entity, ifc_type)
            self.instances[space_boundary.guid] = space_boundary
            self.bind_space_to_space_boundaries(space_boundary)


    def bind_space_to_space_boundaries(self, spaceboundary):
        """Binds the different spaces to the belonging zones"""
        bound_space = spaceboundary.thermal_zones[0]
        bound_instance = spaceboundary.bound_instance
        bound_space.space_boundaries.append(spaceboundary)
        if bound_instance is not None:
            bound_instance.space_boundaries.append(spaceboundary)




    def display_shape_of_space_boundaries(self):
        display, start_display, add_menu, add_function_to_menu = init_display()
        colors = ['blue', 'red', 'magenta', 'yellow', 'green', 'white', 'cyan']
        col = 0
        for inst in self.instances:
            if self.instances[inst].ifc_type == 'IfcSpace':
                col += 1
                zone = self.instances[inst]
                for bound in zone.space_boundaries:
                    try:
                        display.DisplayShape(bound.bound_shape, color=colors[(col - 1) % len(colors)])
                    except:
                        continue
        display.FitAll()
        start_display()

