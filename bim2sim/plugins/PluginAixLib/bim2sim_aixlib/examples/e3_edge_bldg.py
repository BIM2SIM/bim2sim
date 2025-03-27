import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.utilities.types import IFCDomain


def run_example_edge_bldg():
    """Run an HVAC simulation with the AixLib backend with a complex IFC.

    First the project directory and location of the HVAC IFC file are specified.
    Then, we create a bim2sim project with the AixLib backend. Simulation type
    settings are set, in this case we set threshold of fuzzy search a bit lower,
    to reduce the amount of decisions. Afterwards the project is
    executed via the ConsoleDecisionHandler which takes answers for upcoming
    decisions via command line input.
    """

    # Create a temp directory for the project, feel free to use a "normal"
    # directory
    project_path = Path(
        tempfile.TemporaryDirectory(
            prefix='bim2sim_example_complex_aixlib').name)

    # Set path of ifc for hydraulic domain with the fresh downloaded test models
    ifc_paths = {
        IFCDomain.hydraulic:
            [Path("D:/12_IFCs\EDGE/ESH-8H-ROM-HZG-DT-U2-001-###.ifc"),
             Path("D:/12_IFCs\EDGE/ESH-8H-ROM-HZG-DT-U2-010-###.ifc"),
             Path("D:/12_IFCs\EDGE/ESH-8H-ROM-HZG-GR-U1-000-###.ifc"),
             Path("D:/12_IFCs\EDGE/ESH-8H-ROM-HZG-GR-U2-000-###.ifc")
             ]
    }
    # Create a project including the folder structure for the project with
    project = Project.create(project_path, ifc_paths, 'aixlib')

    # set weather file data
    project.sim_settings.weather_file_path = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.mos')

    # Set fuzzy threshold to 0.5 to reduce the number of decisions (this is
    # IFC-file specific and needs to be evaluated by the user
    project.sim_settings.fuzzy_threshold = 0.5

    # Run the project with the ConsoleDecisionHandler. This allows interactive
    # input to answer upcoming questions regarding the imported IFC.
    run_project(project, ConsoleDecisionHandler())



if __name__ == '__main__':
    run_example_edge_bldg()