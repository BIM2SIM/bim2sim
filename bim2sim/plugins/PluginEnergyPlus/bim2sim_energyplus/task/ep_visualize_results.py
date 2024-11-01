import logging

from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.utils\
    .utils_visualization import \
    VisualizationUtils
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements

logger = logging.getLogger(__name__)


class VisualizeResults(ITask):
    """
    Visualize results of the EnergyPlus simulation.

    See run function for more details.
    """

    reads = ('elements', 'sim_results_path')

    def run(self, elements, sim_results_path):
        """Run EnergyPlus specific visualization.

        This function is no longer maintained, please use the plot scripts
        based on the df_finals dataframe instead.
        This function creates images of a floor plan visualization and saves
        them as a .png file.

        Args:
            elements (dict): dictionary in the format dict[guid: element],
                holds preprocessed elements including space boundaries.
            sim_results_path (Path): Path to simulation results.
:
        """
        zone_list = filter_elements(elements, 'ThermalZone')
        zone_dict = {}
        for zone in zone_list:
            zone_dict[zone.guid] = zone
        VisualizationUtils.visualize_zones(zone_dict, sim_results_path /
                                           self.prj_name, self.paths)

