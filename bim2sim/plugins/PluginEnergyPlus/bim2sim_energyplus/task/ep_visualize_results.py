import logging

from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.utils\
    .utils_visualization import \
    VisualizationUtils
from bim2sim.task.base import ITask
from bim2sim.utilities.common_functions import filter_instances

logger = logging.getLogger(__name__)


class VisualizeResults(ITask):
    """
    Visualize results of the EnergyPlus simulation.
    """

    reads = ('instances', )

    def __init__(self):
        super().__init__()

    def run(self, workflow, instances):
        zone_list = filter_instances(instances, 'ThermalZone')
        zone_dict = {}
        for zone in zone_list:
            zone_dict[zone.guid] = zone
        VisualizationUtils.visualize_zones(zone_dict, self.paths)

