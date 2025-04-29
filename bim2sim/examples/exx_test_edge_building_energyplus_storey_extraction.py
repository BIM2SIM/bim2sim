import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.tasks import common, bps
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
    # Create a temp directory for the project, feel free to use a "normal"
    # directory
    project_path = Path(
        tempfile.TemporaryDirectory(prefix='bim2sim_example1').name)

    # Set the ifc path to use and define which domain the IFC belongs to
    # TODO
    # LOCAL CODE VERONIKA
    # ifc_paths = {
    #     IFCDomain.arch:
    #         Path(r'C:\Users\richter\Downloads\BIM-ESH-5A-BDS (EDITED)-IFC4 ('
    #         r'EDITED).ifc'),
    # }
    # ifc_paths = {
    #     IFCDomain.arch:
    #         Path(r'/home/veronika/Downloads/BIM-ESH-5A-BDS (EDITED)-IFC4.ifc'),
    # }
    # LOCAL CODE DAVID
    ifc_paths = {
        IFCDomain.arch:
            Path(r'D:\12_IFCs\BIM-ESH-5A-BDS (EDITED)-IFC4.ifc'),
            # Path(r'D:\12_IFCs\BIM-ESH-5A-BDS (EDITED) 00 EG _ OKFF +0,00 - 00 MZ _ OKFF +3,72 -IFC4.ifc'),
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
    # project.sim_settings.ep_install_path = 'C:/EnergyPlusV24-1-0'
    project.sim_settings.stories_to_load_guids = ['2YtJDdhvbA_ObcqqNobyw4']
    project.sim_settings.create_elements_from_sb = True
    project.sim_settings.handle_outer_walls_as_curtain_walls = True
    project.sim_settings.turn_horizontal_elements_internal = True
    project.sim_settings.set_wwr = 0.8
    project.sim_settings.ep_install_path = 'C:/EnergyPlusV9-4-0'
    project.sim_settings.ep_version = '9-4-0'
    project.plugin_cls.default_tasks = [
        common.LoadIFC,
        # common.CheckIfc,
        common.CreateElementsOnIfcTypes,
        bps.CreateSpaceBoundaries,
        bps.AddSpaceBoundaries2B,
        bps.CorrectSpaceBoundaries,
        common.CreateRelations,
        bps.CorrectInternalExternal,
        bps.CreateElementsFromSB,
        bps.DisaggregationCreationAndTypeCheck,
        bps.EnrichMaterial,
        bps.EnrichUseConditions,
        common.Weather,
        ep_tasks.CreateIdf,
        # ep_tasks.IdfPostprocessing,
        # ep_tasks.ExportIdfForCfd,
        # common.SerializeElements,
        ep_tasks.RunEnergyPlusSimulation,
        # ep_tasks.CreateResultDF,
        # ep_tasks.VisualizeResults,
        # bps.PlotBEPSResults,
    ]


    # 'BPS-Window' should be CurtainWall
    answers = (
        'ArchiCAD',
        'ArchiCAD',
        # validation decisions
        *(None,)*3,  # 3x wandhydrant

        # identification decisions
        None,  # Bodentank oder ähnliches
        None,  # Bodentank oder ähnliches
        None,  # Parkplatz
        'BPS-Wall',  # Vorhangfassade
        'BPS-Wall',  # Vorhangfassade
        'BPS-Wall',  # Vorhangfassade
        'BPS-Wall',  # Fertigbauwand Innen
        'BPS-Wall',  # Vorhangfassade Opak
        None,  # Geländer
        None,  # Wandhydrant
        'BPS-Wall',  # Innenschiebefenster
        'BPS-Wall',  # Vorhangfassade
        None,  # Geländer
        None,  # Eckpfosten im Gebäude
        None,  # Lampe
        None,  # Bodenablauf
        'BPS-Wall',  # Vorhangfassade Opak
        'BPS-Wall',  # Vorhangfassade Opak
        'BPS-Wall',  # Vorhangfassade (BA_FT2 Doppelt: BA_FT2 Doppelt) Wand oder Fenster?
        'BPS-Wall',  # Vorhangfassade Opak
        'BPS-Wall',  # Vorhangfassade Opak
        'BPS-InnerWall',  # Innenwand (Dämmung) IfcCovering
        None,  # Deckenrandverkleidung IfcCovering
        None,  # Pflanztrog IfcCovering
        None,  # Rankgerüst IfcCovering
        None,  # PR Fassade IfcCovering
        # year of construction
        2015,
        # usage decisions
        'Traffic area',  # Nutzfläche
        'Traffic area',  # Luftraum
        'Traffic area',  # Brutto-Grundfläche
    )
    # run_project(project, ConsoleDecisionHandler())
    run_project(project, DebugDecisionHandler(answers))


if __name__ == '__main__':
    run_example_simple_building()
