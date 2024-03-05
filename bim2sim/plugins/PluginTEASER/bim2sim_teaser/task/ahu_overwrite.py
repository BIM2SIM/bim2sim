from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements


class OverwriteAHU(ITask):
    reads = ('elements',)

    def run(self, elements):
        tz_list = filter_elements(elements, 'ThermalZone')
        # read your csv
        for tz in tz_list:
            # e.g. set AHU to True for all zones
            tz.central_ahu = True
