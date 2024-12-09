import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project
from bim2sim.elements.aggregation.bps_aggregations import AggregatedThermalZone
from bim2sim.elements.bps_elements import ThermalZone
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.kernel.log import default_logging_setup
from bim2sim.tasks import common, bps
from bim2sim.utilities.common_functions import filter_elements
from bim2sim.utilities.types import IFCDomain, LOD, ZoningCriteria
from bim2sim.utilities.visualize_spaces import visualize_zones


def visualize_zoning_of_complex_building():
    """Visualize the ThermalZone element entities of a bim2sim run.

    ...
    """
    # The following is the same as in the example e2, look their if you want to
    # know what happens here
    project_path = Path(
        tempfile.TemporaryDirectory(prefix='bim2sim_example1').name)
    ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/FM_ARC_DigitalHub_with_SB89.ifc',
    }
    project = Project.create(project_path, ifc_paths, 'teaser')

    # specify simulation settings (especially for zoning)

    # we use LOD.medium that means that zones are merged based on
    # zoning_criteria sim_setting
    project.sim_settings.zoning_setup = LOD.medium

    # We don't need a full bim2sim run with simulation to demonstrate this, so
    # we will just run the needed tasks:
    project.plugin_cls.default_tasks = [
        common.LoadIFC,
        # common.CheckIfc,
        common.CreateElementsOnIfcTypes,
        bps.CreateSpaceBoundaries,
        bps.AddSpaceBoundaries2B,
        bps.CorrectSpaceBoundaries,
        common.CreateRelations,
        bps.DisaggregationCreationAndTypeCheck,
        bps.EnrichUseConditions,
        bps.CombineThermalZones,
    ]
    # We get the use conditions and usages from predefined templates, look at
    # example e2 to get more information how this works
    project.sim_settings.prj_use_conditions = (Path(
        bim2sim.__file__).parent.parent /
            "test/resources/arch/custom_usages/"
            "UseConditionsFM_ARC_DigitalHub.json")
    project.sim_settings.prj_custom_usages = (Path(
        bim2sim.__file__).parent.parent /
            "test/resources/arch/custom_usages/"
            "customUsagesFM_ARC_DigitalHub_with_SB89.json")

    # set weather file data
    project.sim_settings.weather_file_path = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.mos')
    # Run a simulation directly with dymola after model creation
    # Run the project with the ConsoleDecisionHandler. This allows interactive
    space_boundary_genenerator = 'Other'
    handle_proxies = (*(None,) * 12,)
    answers = (space_boundary_genenerator,
               *handle_proxies)
    # Create one run of bim2sim for each zoning criteria and store the
    # resulting visualizations.
    for zoning_criteria in list(ZoningCriteria):

        project.sim_settings.zoning_criteria = zoning_criteria

        handler = DebugDecisionHandler(answers)

        # run the project for each criteria selection
        handler.handle(project.run())
        # get the resulting elements
        elements = project.playground.state['elements']
        thermal_zones = filter_elements(elements, ThermalZone)
        aggregated_thermal_zones = filter_elements(
            elements, AggregatedThermalZone)
        all_zones = thermal_zones + aggregated_thermal_zones
        visualize_zones(
            all_zones, project.paths.export,
            f"zoning_{zoning_criteria.name}.png")

        # Reset project before the next run
        project.reset()


if __name__ == '__main__':
    visualize_zoning_of_complex_building()
