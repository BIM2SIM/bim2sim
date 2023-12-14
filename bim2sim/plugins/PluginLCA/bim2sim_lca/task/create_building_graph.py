from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_instances


class CreateBuildingGraph(ITask):
    """short docs.

    longs docs.

    Args:
        ...
    Returns:
        ...
    """

    reads = ('ifc_files', 'instances')
    touches = ('...', )
    final = True

    def run(self, ifc_files, instances):
        all_tz  = filter_instances(instances, 'ThermalZone')

        a = ''
        return a,
