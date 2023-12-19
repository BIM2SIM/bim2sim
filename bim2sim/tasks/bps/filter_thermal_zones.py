from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements


class FilterTZ(ITask):
    """Filters the thermal zones for later usage and stores them in state."""

    reads = ('elements',)
    touches = ('tz_elements',)

    def run(self, elements: dict):
        self.logger.info("Filtering thermal zones from all bim2sim elements.")
        thermal_zones = filter_elements(elements, 'ThermalZone')
        tz_elements = {inst.guid: inst for inst in thermal_zones}
        self.logger.info(f"Found {len(tz_elements)} thermal zones. "
                         f"Storing them in playground state.")
        return tz_elements,
