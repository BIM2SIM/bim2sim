import tempfile
from pathlib import Path

from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.log import default_logging_setup
from bim2sim.utilities.types import LOD, IFCDomain


def run_example_3():
    """Run a building performance simulation with the EnergyPlus backend.

    This example runs a BPS with the EnergyPlus backend. Specifies project
    directory and location of the IFC file. Then, it creates a bim2sim
    project with the EnergyPlus backend. Workflow settings are specified (here,
    the zoning setup is specified to be with a full level of detail: each
    IfcSpace is represented by a single thermal Zone in EnergyPlus),
    before the project is executed with the previously specified settings.
    """
    # Create the default logging to for quality log and bim2sim main log (
    # see logging documentation for more information
    default_logging_setup()

    # Create a temp directory for the project, feel free to use a "normal"
    # directory
    project_path = Path(tempfile.TemporaryDirectory(
        prefix='bim2sim_example3').name)

    # Get path of the IFC Building model that is used for this example
    ifc_paths = {
        IFCDomain.arch: Path(__file__).parent.parent
                        / 'assets/ifc_example_files/AC20-FZK-Haus.ifc',
    }
    # Create a project including the folder structure for the project with
    # energyplus as backend and no specified workflow
    # (default workflow is taken)
    project = Project.create(project_path, ifc_paths, 'energyplus')

    # specified settings for workflows can be changed later as well
    project.sim_settings.zoning_setup = LOD.full

    # Run the project with the ConsoleDecisionHandler. This allows interactive
    # input to answer upcoming questions regarding the imported IFC.
    run_project(project, ConsoleDecisionHandler())


if __name__ == '__main__':
    run_example_3()
