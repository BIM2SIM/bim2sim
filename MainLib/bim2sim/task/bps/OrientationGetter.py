from bim2sim.task.base import Task, ITask
from bim2sim.task.common.common_functions import angle_equivalent


class OrientationGetter(ITask):
    """Gets Instances Orientation based on the space boundaries"""

    reads = ('instances',)
    touches = ('instances',)

    def __init__(self):
        super().__init__()
        self.corrected = []
        pass

    @Task.log
    def run(self, workflow, instances):
        self.logger.info("setting verifications")

        for guid, ins in instances.items():
            new_orientation = self.orientation_verification(ins)
            if new_orientation is not None:
                ins.orientation = new_orientation
                self.corrected.append(ins)
        self.logger.info("Corrected %d instances", len(self.corrected))

        return instances,

    @staticmethod
    def orientation_verification(instance):
        supported_classes = {'Window', 'OuterWall', 'OuterDoor', 'Wall', 'Door'}
        instance_type = type(instance).__name__
        if instance_type in supported_classes and len(instance.space_boundaries) > 0:
            new_angles = list(set([space_boundary.orientation for space_boundary in instance.space_boundaries]))
            # new_angles = list(set([space_boundary.orientation - space_boundary.thermal_zones[0].orientation
            # for space_boundary in instance.space_boundaries]))
            if len(new_angles) > 1:
                return None
            # no true north necessary
            new_angle = angle_equivalent(new_angles[0])
            # new angle return
            if new_angle - instance.orientation > 0.1:
                return new_angle
