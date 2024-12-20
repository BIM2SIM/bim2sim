import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.tasks import common, bps
from bim2sim.utilities.common_functions import download_library
from bim2sim.utilities.types import IFCDomain, LOD, ZoningCriteria
from bim2sim.plugins.PluginTEASER.bim2sim_teaser import PluginTEASER, \
    LoadLibrariesTEASER
import bim2sim.plugins.PluginTEASER.bim2sim_teaser.task as teaser_task


def run_serialize_teaser_project_example():
    """Serialize a TEASER Project for further use."""
    # Create the default logging to for quality log and bim2sim main log
    # (see logging documentation for more information)
    project_path = Path(
        tempfile.TemporaryDirectory(prefix='bim2sim_example1').name)

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



    project.sim_settings.zoning_criteria = ZoningCriteria.usage
    # use cooling
    project.sim_settings.cooling_tz_overwrite = False
    project.sim_settings.setpoints_from_template = True

    project.sim_settings.ahu_heating_overwrite = True
    project.sim_settings.ahu_cooling_overwrite = True
    project.sim_settings.ahu_heat_recovery_overwrite = True

    # overwrite existing layer structures and materials based on templates
    project.sim_settings.layers_and_materials = LOD.low
    # specify templates for the layer and material overwrite
    project.sim_settings.construction_class_walls = 'heavy'
    project.sim_settings.construction_class_windows = \
        'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach'

    # set weather file data
    project.sim_settings.weather_file_path = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.mos')
    # Run a simulation directly with dymola after model creation
    project.sim_settings.dymola_simulation = True
    # Make sure that AixLib modelica library exist on machine by cloning it and
    #  setting the path of it as a sim_setting
    repo_url = "https://github.com/RWTH-EBC/AixLib.git"
    branch_name = "main"
    repo_name = "AixLib"
    path_aixlib = (
            Path(bim2sim.__file__).parent.parent / "local" / f"library_{repo_name}")
    download_library(repo_url, branch_name, path_aixlib)
    project.sim_settings.path_aixlib = path_aixlib / repo_name / 'package.mo'

    # Select results to output:
    project.sim_settings.sim_results = [
        "heat_demand_total", "cool_demand_total",
        "heat_demand_rooms", "cool_demand_rooms",
        "heat_energy_total", "cool_energy_total",
        "heat_energy_rooms", "cool_energy_rooms",
        "operative_temp_rooms", "air_temp_rooms", "air_temp_out",
        "internal_gains_machines_rooms", "internal_gains_persons_rooms",
        "internal_gains_lights_rooms",
        "heat_set_rooms",
        "cool_set_rooms"
    ]
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
