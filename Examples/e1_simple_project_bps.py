import tempfile
from pathlib import Path

from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.log import default_logging_setup
from bim2sim.workflow import LOD


# Create the default logging to for quality log and bim2sim main log (
# see logging documentation for more information
default_logging_setup()

# Create a temp directory for the project, feel free to use a "normal" directory
project_path = Path(tempfile.TemporaryDirectory(prefix='bim2sim_example1').name)

# Get path of the IFC Building model that is used for this example
ifc_path = Path(__file__).parent.parent / 'test/TestModels/AC20-FZK-Haus.ifc'

# Create a project including the folder structure for the project with teaser as
# backend and no specified workflow (default workflow is taken)
# with open_conf the default created config file will be opened and can be
# adjusted by the user and saved afterwards.
project = Project.create(
    project_path, ifc_path, 'teaser', open_conf=True)

# specified settings for workflows can be changed later as well
project.workflow.layers_and_materials = LOD.full

# Run the project with the ConsoleDecisionHandler. This allows interactive input
# to answer upcoming questions regarding the imported IFC. If you are using the
# default config without any changes you won't have to answer any decisions.
# run_project(project, ConsoleDecisionHandler())
handler = ConsoleDecisionHandler()
ConsoleDecisionHandler().handle(project.run(
    interactive=True), project.loaded_decisions)
#
# for decision, answer in handler.decision_answer_mapping(project.run()):
#     decision.value = answer