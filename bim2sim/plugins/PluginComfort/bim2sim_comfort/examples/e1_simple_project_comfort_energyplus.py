import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.kernel.log import default_logging_setup
from bim2sim.utilities.types import IFCDomain, LOD


def run_example_1():
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
        prefix='bim2sim_comfort_e1').name)

    # Get path of the IFC Building model that is used for this example
    ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/AC20-FZK-Haus.ifc'
    }
    # Create a project including the folder structure for the project with
    # energyplus as backend and no specified workflow
    # (default workflow is taken)
    project = Project.create(project_path, ifc_paths, 'comfort')

    # set weather file data
    project.sim_settings.weather_file_path = (
            Path(bim2sim.__file__).parent.parent /
            'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.epw')

    # specified settings for workflows can be changed later as well
    project.sim_settings.ep_install_path = 'C://EnergyPlusV9-4-0/'
    project.sim_settings.layers_and_materials = LOD.low
    project.sim_settings.construction_class_walls = 'heavy'
    project.sim_settings.construction_class_windows = \
        'Waermeschutzverglasung, dreifach'
    project.sim_settings.run_full_simulation = True
    project.sim_settings.setpoints_from_template = True
    project.sim_settings.add_window_shading = 'Exterior'
    project.sim_settings.cooling = False
    project.sim_settings.rename_result_keys = True
    project.sim_settings.create_plots = True

    # Run the project with the ConsoleDecisionHandler. This allows interactive
    # input to answer upcoming questions regarding the imported IFC.
    run_project(project, ConsoleDecisionHandler())


if __name__ == '__main__':
    run_example_1()
