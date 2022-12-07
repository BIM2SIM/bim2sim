import tempfile
from pathlib import Path

from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.log import default_logging_setup


def run_example_4():
    # Create the default logging to for quality log and bim2sim main log (
    # see logging documentation for more information
    default_logging_setup()

    # Create a temp directory for the project, feel free to use a "normal"
    # directory
    project_path = Path(
        tempfile.TemporaryDirectory(prefix='bim2sim_example1').name)

    # Get path of the IFC Building model that is used for this example
    ifc_path = Path(
        __file__).parent.parent / 'assets/ifc_example_files/hvac_heating.ifc'

    # Create a project including the folder structure for the project with
    # teaser as backend and no specified workflow (default workflow is taken)
    project = Project.create(project_path, ifc_path, 'aixlib')

    # specified settings for workflows can be changed later as well
    project.workflow.aggregations = [
        'UnderfloorHeating',
        'Consumer',
        'PipeStrand',
        'ParallelPump',
        'ConsumerHeatingDistributorModule',
        'GeneratorOneFluid'
    ]

    # Run the project with the ConsoleDecisionHandler. This allows interactive
    # input to answer upcoming questions regarding the imported IFC.
    run_project(project, ConsoleDecisionHandler())


# 'HVAC-Distributor',
# 'HVAC-ThreeWayValve'*2,
# 'HVAC-PipeFitting'*14',
# None*2,
# True *4,
# True * 4
# efficiency: 0.95
# flow_temperature: 70
# nominal_power_consumption: 200
# return_temperature: 50
# following multiple
# return_temperature: 50
# (body_mass: 15, heat_capacity: 10) * 7

if __name__ == '__main__':
    run_example_4()
