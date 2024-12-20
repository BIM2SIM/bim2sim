import tempfile
from pathlib import Path
import threading

import bim2sim
from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.tasks import common, bps
from bim2sim.utilities.common_functions import download_library
from bim2sim.utilities.types import IFCDomain, LOD, ZoningCriteria
from bim2sim.plugins.PluginTEASER.bim2sim_teaser import PluginTEASER, \
    LoadLibrariesTEASER
import bim2sim.plugins.PluginTEASER.bim2sim_teaser.task as teaser_task


def run_serialize_teaser_project_example(project_path, weather_file_path):
    """Serialize a TEASER Project for further use."""
    # Create the default logging to for quality log and bim2sim main log
    # (see logging documentation for more information)

    # Set the ifc path to use and define which domain the IFC belongs to
    ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/AC20-Institute-Var-2.ifc',
    }
    # Create a project including the folder structure for the project with
    # teaser as backend and no specified workflow (default workflow is taken)
    project = Project.create(project_path, ifc_paths, 'teaser')

    # specify simulation settings (please have a look at the documentation of
    # all under concepts/sim_settings
    # combine spaces to thermal zones based on their usage
    project.sim_settings.zoning_setup = LOD.medium
    project.sim_settings.zoning_criteria = ZoningCriteria.all_criteria
    project.sim_settings.setpoints_from_template = True

    # overwrite existing layer structures and materials based on templates
    project.sim_settings.layers_and_materials = LOD.low

    # specify templates for the layer and material overwrite
    project.sim_settings.construction_class_walls = "kfw_40"
    project.sim_settings.construction_class_windows = "Waermeschutzverglasung, dreifach"
    project.sim_settings.construction_class_doors = "kfw_40"

    # Activate Cooling and AHU
    project.sim_settings.heating = True
    project.sim_settings.cooling = True

    project.sim_settings.overwrite_ahu_by_settings = True
    project.sim_settings.deactivate_ahu = False
    project.sim_settings.ahu_heating = True
    project.sim_settings.ahu_cooling = True
    project.sim_settings.ahu_dehumidification = True
    project.sim_settings.ahu_humidification = True
    project.sim_settings.ahu_heat_recovery = True
    project.sim_settings.ahu_heat_recovery_efficiency = 0.8

    # Set Lock class
    project.sim_settings.lock = threading.Lock()

    # set weather file data
    project.sim_settings.weather_file_path = weather_file_path

    # Make sure that AixLib modelica library exist on machine by cloning it and
    #  setting the path of it as a sim_setting
    repo_url = "https://github.com/RWTH-EBC/AixLib.git"
    branch_name = "main"
    repo_name = "AixLib"
    path_aixlib = (
            Path(bim2sim.__file__).parent.parent / "local" / f"library_{repo_name}")
    # download_library(repo_url, branch_name, path_aixlib)
    project.sim_settings.path_aixlib = path_aixlib / repo_name / 'package.mo'

    project.sim_settings.prj_use_conditions = (Path(
        bim2sim.__file__).parent.parent /
                                               "bim2sim/assets/enrichment/usage/UseConditions.json")
    project.sim_settings.prj_custom_usages = (Path(
        bim2sim.__file__).parent.parent /
                                              "test/resources/arch/custom_usages/"
                                              "customUsagesAC20-Institute-Var-2_with_SB-1-0.json")


    # create plots based on the results after simulation
    project.sim_settings.create_plots = True
    project.plugin_cls.default_tasks = [
        common.LoadIFC,
        common.CreateElementsOnIfcTypes,
        bps.CreateSpaceBoundaries,
        bps.AddSpaceBoundaries2B,
        bps.CorrectSpaceBoundaries,
        common.CreateRelations,
        bps.DisaggregationCreationAndTypeCheck,
        bps.EnrichMaterial,
        bps.EnrichUseConditions,
        bps.CombineThermalZones,
        common.Weather,
        LoadLibrariesTEASER,
        teaser_task.CreateTEASER,
        teaser_task.SerializeTEASER,
        common.SerializeElements,
    ]
    answers = (2015,)
    handler = DebugDecisionHandler(answers)
    handler.handle(project.run())

    # return the export path and the path of the serialized project json file
    return (project.paths.export,
            project.paths.export /
            f"TEASER/serialized_teaser/{project.name}.json")


if __name__ == '__main__':
    run_serialize_teaser_project_example()
