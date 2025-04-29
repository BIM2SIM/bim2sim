from collections import defaultdict

from bim2sim.elements.aggregation.bps_aggregations import AggregatedThermalZone
from bim2sim.elements.hvac_elements import AirTerminal
from bim2sim.elements.bps_elements import ThermalZone
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements
from bim2sim.utilities.types import ZoningCriteria
from typing import Callable
from bim2sim.utilities.pyocc_tools import PyOCCTools

class VentilationIdentification(ITask):
    reads = ('elements',)

    def run(self, elements):
        air_terminals = filter_elements(elements, AirTerminal)
        tz_elements = filter_elements(elements, ThermalZone)

        zone_to_air_terminals = defaultdict(list)
        for tz in tz_elements:
            for air_terminal in air_terminals:
                if PyOCCTools.obj2_in_obj1(
                        obj1=tz.space_shape, obj2=air_terminal.shape):
                    zone_to_air_terminals[tz.guid].append(air_terminal.guid)
        return zone_to_air_terminals

