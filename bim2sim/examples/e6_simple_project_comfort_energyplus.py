import tempfile
from pathlib import Path

from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.log import default_logging_setup
from bim2sim.utilities.types import IFCDomain


def run_example_6():
    """Run a thermal comfort analysis with EnergyPlus backend.

    This example runs a Thermal Comfort Analysis with the EnergyPlus backend.
    Specifies project directory and location of the IFC file. Then, it creates
    a bim2sim project with the Thermal Comfort backend that builds on the
    EnergyPlus backend. Workflow settings are specified (here, the zoning setup
    is specified to be with a full level of detail: each IfcSpace is
    represented by a single thermal Zone in EnergyPlus), before the project
    is executed with the previously specified settings.
    """
    # Create the default logging to for quality log and bim2sim main log (
    # see logging documentation for more information
    default_logging_setup()

    # Create a temp directory for the project, feel free to use a "normal"
    # directory
    project_path = Path(tempfile.TemporaryDirectory(
        prefix='bim2sim_example6').name)

    # Get path of the IFC Building model that is used for this example
    ifc_paths = {
        IFCDomain.arch: Path(__file__).parent.parent /
                        'assets/ifc_example_files/AC20-FZK-Haus.ifc'
                  }
    # Create a project including the folder structure for the project with
    # energyplus as backend and no specified workflow
    # (default workflow is taken)
    project = Project.create(project_path, ifc_paths, 'comfort')

    # specified settings for workflows can be changed later as well
    project.sim_settings.ep_install_path = 'C://EnergyPlusV9-4-0/'
    project.sim_settings.run_full_simulation = True
    project.sim_settings.cooling = True

    # Run the project with the ConsoleDecisionHandler. This allows interactive
    # input to answer upcoming questions regarding the imported IFC.
    run_project(project, ConsoleDecisionHandler())


if __name__ == '__main__':
    run_example_6()
