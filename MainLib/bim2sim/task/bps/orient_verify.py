from bim2sim.task.base import Task, ITask
from bim2sim.task.common.common_functions import angle_equivalent, vector_angle
from bim2sim.workflow import Workflow
from bim2sim.kernel.element import Element


class OrientationGetter(ITask):
    """Gets Instances Orientation based on the space boundaries"""

    reads = ('instances',)
    touches = ('oriented_instances',)

    def __init__(self):
        super().__init__()
        self.corrected = []
        pass

    @Task.log
    def run(self, workflow: Workflow, instances: dict):
        self.logger.info("setting verifications")

        for guid, ins in instances.items():
            new_orientation = self.orientation_verification(ins)
            if new_orientation is not None:
                ins.orientation = new_orientation
                self.corrected.append(ins)
        self.logger.info("Corrected %d instances", len(self.corrected))

        x1 = self.group_attribute(Element.instances['Window'].values(), 'orientation')
        x2 = self.group_attribute(Element.instances['OuterWall'].values(), 'orientation')

        return self.corrected,

    @staticmethod
    def orientation_verification(instance: Element):
        """gets new angle based on space boundaries and compares it with the geometric value"""
        vertical_instances = ['Window', 'OuterWall', 'OuterDoor', 'Wall', 'Door']
        horizontal_instances = ['Slab', 'Roof', 'Floor', 'GroundFloor']
        switcher = {'Slab': -1,
                    'Roof': -1,
                    'Floor': -2,
                    'GroundFloor': -2}
        instance_type = type(instance).__name__
        guid = instance.guid
        if instance_type in vertical_instances and len(instance.space_boundaries) > 0:
            # x = angle_equivalent(vector_angle(instance.space_boundaries[0].bound_normal.Coord()) + 180)
            # if abs(x - instance.orientation) > 0.2:
            #     print()
            new_angles = list(set([-space_boundary.orientation - space_boundary.thermal_zones[0].orientation
                                   for space_boundary in instance.space_boundaries
                                   if space_boundary.orientation != space_boundary.thermal_zones[0].orientation]))

            new_angles_alt = list(set([-space_boundary.orientation - space_boundary.thermal_zones[0].orientation
                                       for space_boundary in instance.space_boundaries]))
            if len(new_angles) > 1 or len(new_angles) == 0:
                return None

            # no true north necessary
            new_angle = angle_equivalent(new_angles[0])
            new_angle = angle_equivalent(vector_angle(instance.space_boundaries[0].bound_normal.Coord()) + 180)
            # new angle return
            if new_angle - instance.orientation > 0.1:
                return new_angle
        elif instance_type in horizontal_instances:
            return switcher[instance_type]
        return None

    @classmethod
    def group_attribute(cls, elements, attribute):
        """groups together a set of thermal zones, that have an attribute in common """
        groups = {}
        for ele in elements:
            value = cls.cardinal_direction(getattr(ele, attribute))
            if value not in groups:
                groups[value] = {}
            groups[value][ele.guid] = ele

        return groups

    @staticmethod
    def cardinal_direction(value):
        """groups together a set of thermal zones, that have common glass percentage in common """
        if 45 <= value < 135:
            value = 'E'
        elif 135 <= value < 225:
            value = 'S'
        elif 225 <= value < 315:
            value = 'W'
        else:
            value = 'N'
        return value
