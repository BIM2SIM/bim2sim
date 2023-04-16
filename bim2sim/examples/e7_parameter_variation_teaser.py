import tempfile
from pathlib import Path
import copy

from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.log import default_logging_setup
from bim2sim.workflow import LOD


def run_example_1():
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
        tempfile.TemporaryDirectory(prefix='bim2sim_example1').name)

    # Get path of the IFC Building model that is used for this example
    ifc_path = Path(
        __file__).parent.parent / 'assets/ifc_example_files/AC20-FZK-Haus.ifc'

    # Create a project including the folder structure for the project with
    # teaser as backend and no specified workflow (default workflow is taken)
    project = Project.create(project_path, ifc_path, 'teaser')

    # specified settings for workflows can be changed later as well
    project.workflow.zoning_setup = LOD.medium

    # Run the project with the ConsoleDecisionHandler. This allows interactive
    # input to answer upcoming questions regarding the imported IFC.

    run_project(project, ConsoleDecisionHandler())

    # Todo solve folder problem (names shouldn't be the same for both projects)
    teaser_prj_base = project.playground.state['teaser_prj']
    teaser_prj_base.export_aixlib(
        path=Path("D:/b2s_workshop/results/teaser_parameter_variation/option1"),
        use_postprocessing_calc=True)
    teaser_prj_variation = copy.copy(teaser_prj_base)
    teaser_bldg_variation = teaser_prj_variation.buildings[0]
    for tz in teaser_bldg_variation.thermal_zones:
        for outer_wall in tz.outer_walls:
            outer_wall.load_type_element(
                year=1984,
                construction='light'
            )
    teaser_prj_variation.calc_all_buildings()
    teaser_prj_variation.export_aixlib(
        path=Path("D:/b2s_workshop/results/teaser_parameter_variation/option2"),
        use_postprocessing_calc=True)


if __name__ == '__main__':
    run_example_1()
