import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.kernel.log import default_logging_setup
from bim2sim.tasks import bps, common
from bim2sim.utilities.common_functions import download_test_resources
from bim2sim.utilities.types import IFCDomain, LOD, ZoningCriteria
import bim2sim.plugins.PluginTEASER.bim2sim_teaser.task as teaser_task


def run_example_loadExistingProject():
    """Run a building performance simulation with the TEASER backend.

    This example runs a BPS with the TEASER backend. Specifies project
    directory and location of the IFC file. Then, it creates a bim2sim
    project with the TEASER backend. Workflow settings are specified (here,
    the zoning setup is specified to be with a medium level of detail),
    before the project is executed with the previously specified settings.
    """
    # Create the default logging to for quality log and bim2sim main log
    # (see logging documentation for more information)
    default_logging_setup()

    # Create a temp directory for the project, feel free to use a "normal"
    # directory
    project_path = Path(
        "D:/01_Kurzablage/compare_EP_TEASER_DH/bim2sim_project_teaser")

    # download additional test resources for arch domain, you might want to set
    # force_new to True to update your test resources
    download_test_resources(IFCDomain.arch, force_new=False)

    # Create a project including the folder structure for the project with
    # teaser as backend and no specified workflow (default workflow is taken)
    project = Project.create(project_path, plugin='teaser')

    project.sim_settings.prj_use_conditions = (Path(
        bim2sim.__file__).parent.parent /
           "test/resources/arch/custom_usages/"
           "UseConditionsFM_ARC_DigitalHub_with_SB89.json")
    project.sim_settings.prj_custom_usages = (Path(
        bim2sim.__file__).parent.parent /
            "test/resources/arch/custom_usages/"
            "customUsagesFM_ARC_DigitalHub_with_SB89.json")

    # # specify simulation settings (please have a look at the documentation of
    # # all under concepts/sim_settings
    # # combine spaces to thermal zones based on their usage
    # project.sim_settings.zoning_setup = LOD.low
    # project.sim_settings.zoning_criteria = ZoningCriteria.usage
    # # use cooling
    #
    # project.sim_settings.setpoints_from_template = True
    # project.sim_settings.cooling = True
    # # overwrite existing layer structures and materials based on templates
    # project.sim_settings.layers_and_materials = LOD.low
    # # specify templates for the layer and material overwrite
    # project.sim_settings.construction_class_walls = 'heavy'
    # project.sim_settings.construction_class_windows = \
    #     'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach'

    # TODO those 2 are not used but are needed currently as otherwise the
    #  plotting tasks will be executed and weather file is mandatory
    # set weather file data
    project.sim_settings.weather_file_path = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.mos')
    # Run a simulation directly with dymola after model creation
    project.sim_settings.dymola_simulation = True
    # Select results to output:
    project.sim_settings.sim_results = [
        "heat_demand_total", "cool_demand_total",
        "heat_demand_rooms", "cool_demand_rooms",
        "heat_energy_total", "cool_energy_total",
        "heat_energy_rooms", "cool_energy_rooms",
        "operative_temp_rooms", "air_temp_rooms", "air_temp_out"
    ]

    project.plugin_cls.default_tasks = [
        common.LoadIFC,
        teaser_task.LoadModelicaResults,
        teaser_task.CreateResultDF,
        bps.PlotBEPSResults,
    ]
    # Run the project with the ConsoleDecisionHandler. This allows interactive
    # input to answer upcoming questions regarding the imported IFC.
    run_project(project, ConsoleDecisionHandler())


if __name__ == '__main__':
    run_example_loadExistingProject()
