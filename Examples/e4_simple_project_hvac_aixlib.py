import tempfile
from pathlib import Path

from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.log import default_logging_setup
from bim2sim.workflow import LOD


def run_example_4():
    # Create the default logging to for quality log and bim2sim main log (
    # see logging documentation for more information
    default_logging_setup()

    # Create a temp directory for the project, feel free to use a "normal" directory
    project_path = Path(tempfile.TemporaryDirectory(prefix='bim2sim_example1').name)

    # Get path of the IFC Building model that is used for this example
    ifc_path = Path(__file__).parent.parent / 'test/TestModels/2022_11_21_B03_Heating_ownCells.ifc'

    # Create a project including the folder structure for the project with teaser as
    # backend and no specified workflow (default workflow is taken)
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

    # Run the project with the ConsoleDecisionHandler. This allows interactive input
    # to answer upcoming questions regarding the imported IFC.
    run_project(project, ConsoleDecisionHandler())

# 'HVAC-Distributor',
# 'HVAC-Boiler'
# 'HVAC-PipeFitting'*14',
# ' 16dMYEqBD0ha5FH1ji7tae'
# '3ApjErtphPlKeFnrwh0yL0'
# True * 4
# efficiency: 0.95
# flow_temperature: 70
# nominal_power_consumption: 200

# following multiple
# return_temperature: 50
# body_mass: 15
# heat_capacity: 10
# return_temperature = 50

if __name__ == '__main__':
    run_example_4()
