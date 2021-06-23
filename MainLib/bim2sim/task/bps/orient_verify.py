from bim2sim.task.base import ITask
from bim2sim.utilities.common_functions import angle_equivalent, vector_angle
from bim2sim.workflow import Workflow
from bim2sim.kernel.element import ProductBased
from bim2sim.kernel.elements import bps


class OrientationGetter(ITask):
    """Gets Instances Orientation based on the space boundaries"""

    reads = ('instances',)
    touches = ('oriented_instances',)

    def __init__(self):
        super().__init__()
        self.corrected = []
        pass

    def run(self, workflow: Workflow, instances: dict):
        self.logger.info("setting verifications")

        for guid, ins in instances.items():
            new_orientation = self.orientation_verification(ins)
            if new_orientation is not None:
                ins.orientation = new_orientation
                self.corrected.append(ins)
        self.logger.info("Corrected %d instances", len(self.corrected))

        return self.corrected,

    @staticmethod
    def orientation_verification(instance: ProductBased):
        """gets new angle based on space boundaries and compares it with the
        geometric value"""
        vertical_instances = [bps.Window, bps.OuterWall, bps.OuterDoor]
        horizontal_instances = [bps.Slab, bps.Roof, bps.Floor, bps.GroundFloor]
        switcher = {'Slab': -1,
                    'Roof': -1,
                    'Floor': -2,
                    'GroundFloor': -2}
        if type(instance) in vertical_instances and \
                hasattr(instance, 'space_boundaries'):
            if len(instance.space_boundaries) > 0:
                new_angles = list(set([vector_angle(
                    space_boundary.bound_normal.Coord())
                    for space_boundary in instance.space_boundaries]))
                if len(new_angles) > 1 or len(new_angles) == 0:
                    return None
                # no true north necessary
                new_angle = angle_equivalent(new_angles[0])
                # new_angle = angle_equivalent(new_angles[0] + 180)  # no sb55.
                # eg: FZK Buildings
                # new angle return
                if new_angle - instance.orientation > 0.1:
                    return new_angle

        elif type(instance) in horizontal_instances:
            return switcher[type(instance).__name__]
        return None

    @classmethod
    def group_attribute(cls, elements, attribute):
        """groups together a set of thermal zones, that have an attribute in
        common """
        groups = {}
        for ele in elements:
            value = cls.cardinal_direction(getattr(ele, attribute))
            if value not in groups:
                groups[value] = {}
            groups[value][ele.guid] = ele

        return groups

    @staticmethod
    def cardinal_direction(value):
        """groups together a set of thermal zones, that have common glass
        percentage in common """
        if 45 <= value < 135:
            value = 'E'
        elif 135 <= value < 225:
            value = 'S'
        elif 225 <= value < 315:
            value = 'W'
        else:
            value = 'N'
        return value
