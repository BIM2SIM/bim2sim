import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.kernel.log import default_logging_setup
from bim2sim.tasks import common, bps
from bim2sim.utilities.common_functions import download_test_resources
from bim2sim.utilities.types import IFCDomain, LOD, ZoningCriteria
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus import task as ep_tasks


def run_example_simple_building():
    """Run a building performance simulation with the EnergyPlus backend.

    This example runs a BPS with the EnergyPlus backend. Specifies project
    directory and location of the IFC file. Then, it creates a bim2sim
    project with the EnergyPlus backend. Workflow settings are specified (here,
    the zoning setup is specified to be with a medium level of detail),
    before the project is executed with the previously specified settings.
    """
    # Create the default logging to for quality log and bim2sim main log
    # (see logging documentation for more information)
    default_logging_setup()

    # Create a temp directory for the project, feel free to use a "normal"
    # directory
    project_path = Path(
        tempfile.TemporaryDirectory(prefix='bim2sim_example1').name)

    # download additional test resources for arch domain, you might want to set
    # force_new to True to update your test resources
    download_test_resources(IFCDomain.arch, force_new=False)
    # Set the ifc path to use and define which domain the IFC belongs to
    # TODO
    # LOCAL CODE VERONIKA
    # ifc_paths = {
    #     IFCDomain.arch:
    #         Path(r'C:\Users\richter\Downloads\BIM-ESH-5A-BDS (EDITED)-IFC4 ('
    #         r'EDITED).ifc'),
    # }
    # LOCAL CODE DAVID
    ifc_paths = {
        IFCDomain.arch:
            Path(r'D:\12_IFCs\BIM-ESH-5A-BDS (EDITED) 00 EG _ OKFF +0,00 - 00 MZ _ OKFF +3,72 -IFC4.ifc'),
    }
    # Create a project including the folder structure for the project with
    # teaser as backend and no specified workflow (default workflow is taken)
    project = Project.create(project_path, ifc_paths, 'energyplus')

    # set weather file data
    project.sim_settings.weather_file_path = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.epw')
    # Set the install path to your EnergyPlus installation according to your
    # system requirements
    project.sim_settings.cooling = True
    # overwrite existing layer structures and materials based on templates
    # Select results to output:
    project.sim_settings.sim_results = [
        "heat_demand_total", "cool_demand_total",
        "heat_demand_rooms", "cool_demand_rooms",
        "heat_energy_total", "cool_energy_total",
        "heat_energy_rooms", "cool_energy_rooms",
        "operative_temp_rooms", "air_temp_rooms", "air_temp_out"
    ]
    project.sim_settings.ep_install_path = 'C:/EnergyPlusV24-1-0'
    project.sim_settings.ep_version = '24-1-0'
    project.plugin_cls.default_tasks = [
        common.LoadIFC,
        # common.CheckIfc,
        common.CreateElements,
        bps.CreateSpaceBoundaries,
        bps.FilterTZ,
        bps.ProcessSlabsRoofs,
        common.BindStoreys,
        bps.EnrichUseConditions,
        bps.VerifyLayersMaterials,  # LOD.full
        bps.EnrichMaterial,  # LOD.full
        ep_tasks.EPGeomPreprocessing,
        ep_tasks.AddSpaceBoundaries2B,
        common.Weather,
        ep_tasks.CreateIdf,
        ep_tasks.IdfPostprocessing,
        ep_tasks.ExportIdfForCfd,
        ep_tasks.RunEnergyPlusSimulation,
        ep_tasks.CreateResultDF,
        # ep_tasks.VisualizeResults,
        bps.PlotBEPSResults,
    ]

    # Run the project with the ConsoleDecisionHandler. This allows interactive
    # input to answer upcoming questions regarding the imported IFC.
    answers = ('ArchiCAD', 'ArchiCAD',*(None,)*2, ('BPS-InnerWall',)*3,
               *(None,)*13, *('Traffic area',)*3, 2015)

    answers = ('ArchiCAD', 'ArchiCAD',*(None,)*3, *(None,)*23,
               *('Traffic area',)*3, 2015)
    run_project(project, ConsoleDecisionHandler())
    # run_project(project, DebugDecisionHandler(answers))


if __name__ == '__main__':
    run_example_simple_building()
