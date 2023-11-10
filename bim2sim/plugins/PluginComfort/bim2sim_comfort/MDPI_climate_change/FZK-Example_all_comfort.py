import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.kernel.log import default_logging_setup
from bim2sim.utilities.types import IFCDomain, LOD

EXPORT_PATH = r'C:\Users\richter\sciebo\03-Paperdrafts' \
              r'\MDPI_SpecialIssue_Comfort_Climate\sim_results'

YEAR_OF_CONSTR = 2015
FLAG = ''#'_COOLING'#'_SHADING'
CITY = 'Cologne'


def run_heavy_2015():
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
    project_path = Path(EXPORT_PATH) / f'{CITY}' / f'Constr{YEAR_OF_CONSTR}'\
                   / f'heavy_2015{FLAG}'

    # Get path of the IFC Building model that is used for this example
    ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/AC20-FZK-Haus.ifc',
    }
    # Create a project including the folder structure for the project with
    # energyplus as backend and no specified workflow
    # (default workflow is taken)
    project = Project.create(project_path, ifc_paths, 'comfort')

    # specified settings for workflows can be changed later as well
    project.sim_settings.ep_install_path = 'C://EnergyPlusV9-4-0/'
    project.sim_settings.layers_and_materials = LOD.low
    project.sim_settings.construction_class_walls = 'heavy'
    project.sim_settings.construction_class_windows = \
        'Waermeschutzverglasung, dreifach'
    project.sim_settings.run_full_simulation = True
    project.sim_settings.setpoints_from_template = True
    #project.sim_settings.add_window_shading = 'Exterior'
    project.sim_settings.year_of_construction_overwrite = YEAR_OF_CONSTR
    project.sim_settings.prj_use_conditions = \
        Path(__file__).parent.parent / \
        'data/UseConditionsComfort_AC20-FZK-Haus.json'
    project.sim_settings.prj_custom_usages = \
        Path(__file__).parent.parent / \
        'data/customUsages_AC20-FZK-Haus.json'
    project.sim_settings.cooling = False
    # project.sim_settings.use_dynamic_clothing = True
    project.sim_settings.overwrite_weather = \
        r'C:\Users\richter\sciebo\03-Paperdrafts' \
        r'\MDPI_SpecialIssue_Comfort_Climate\weather\futureWeather' \
        r'\Koeln_07_21_EC-Earth3\DEU_NW_Koln.Bonn.AP.105130_TMYx.2007-2021.epw'
    answers = ('WC residential', 'Kitchen residential')
    # Run the project with the ConsoleDecisionHandler. This allows interactive
    # input to answer upcoming questions regarding the imported IFC.
    run_project(project, DebugDecisionHandler(answers))


def run_heavy_2050_SSP585():
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
    project_path = Path(EXPORT_PATH) / f'{CITY}'/ f'Constr{YEAR_OF_CONSTR}' / \
                   f'heavy_SSP585_2050{FLAG}'

    # Get path of the IFC Building model that is used for this example
    ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/AC20-FZK-Haus.ifc',
    }
    # Create a project including the folder structure for the project with
    # energyplus as backend and no specified workflow
    # (default workflow is taken)
    project = Project.create(project_path, ifc_paths, 'comfort')

    # specified settings for workflows can be changed later as well
    project.sim_settings.ep_install_path = 'C://EnergyPlusV9-4-0/'
    project.sim_settings.layers_and_materials = LOD.low
    project.sim_settings.construction_class_walls = 'heavy'
    project.sim_settings.construction_class_windows = \
        'Waermeschutzverglasung, dreifach'
    project.sim_settings.run_full_simulation = True
    project.sim_settings.setpoints_from_template = True
    #project.sim_settings.add_window_shading = 'Exterior'
    project.sim_settings.year_of_construction_overwrite = YEAR_OF_CONSTR
    project.sim_settings.prj_use_conditions = \
        Path(__file__).parent.parent / \
        'data/UseConditionsComfort_AC20-FZK-Haus.json'
    project.sim_settings.prj_custom_usages = \
        Path(__file__).parent.parent / \
        'data/customUsages_AC20-FZK-Haus.json'
    project.sim_settings.cooling = False
    # project.sim_settings.use_dynamic_clothing = True
    project.sim_settings.overwrite_weather = \
        r'C:\Users\richter\sciebo\03-Paperdrafts' \
        r'\MDPI_SpecialIssue_Comfort_Climate\weather\futureWeather' \
        r'\Koeln_07_21_EC-Earth3\DEU_NW_Koln.Bonn.AP_EC-Earth3_ssp585_2050.epw'

    # Run the project with the ConsoleDecisionHandler. This allows interactive
    # input to answer upcoming questions regarding the imported IFC.
    answers = ('WC residential', 'Kitchen residential')
    # Run the project with the ConsoleDecisionHandler. This allows interactive
    # input to answer upcoming questions regarding the imported IFC.
    run_project(project, DebugDecisionHandler(answers))


def run_heavy_2080_SSP585():
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
    project_path = Path(EXPORT_PATH) / f'{CITY}'/ f'Constr{YEAR_OF_CONSTR}' / \
                   f'heavy_SSP585_2080{FLAG}'

    # Get path of the IFC Building model that is used for this example
    ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/AC20-FZK-Haus.ifc',
    }
    # Create a project including the folder structure for the project with
    # energyplus as backend and no specified workflow
    # (default workflow is taken)
    project = Project.create(project_path, ifc_paths, 'comfort')

    # specified settings for workflows can be changed later as well
    project.sim_settings.ep_install_path = 'C://EnergyPlusV9-4-0/'
    project.sim_settings.layers_and_materials = LOD.low
    project.sim_settings.construction_class_walls = 'heavy'
    project.sim_settings.construction_class_windows = \
        'Waermeschutzverglasung, dreifach'
    project.sim_settings.run_full_simulation = True
    project.sim_settings.setpoints_from_template = True
    # project.sim_settings.add_window_shading = 'Exterior'
    project.sim_settings.year_of_construction_overwrite = YEAR_OF_CONSTR
    project.sim_settings.prj_use_conditions = \
        Path(__file__).parent.parent / \
        'data/UseConditionsComfort_AC20-FZK-Haus.json'
    project.sim_settings.prj_custom_usages = \
        Path(__file__).parent.parent / \
        'data/customUsages_AC20-FZK-Haus.json'
    project.sim_settings.cooling = False
    # project.sim_settings.use_dynamic_clothing = True
    project.sim_settings.overwrite_weather = \
        r'C:\Users\richter\sciebo\03-Paperdrafts' \
        r'\MDPI_SpecialIssue_Comfort_Climate\weather\futureWeather' \
        r'\Koeln_07_21_EC-Earth3\DEU_NW_Koln.Bonn.AP_EC-Earth3_ssp585_2080.epw'

    # Run the project with the ConsoleDecisionHandler. This allows interactive
    # input to answer upcoming questions regarding the imported IFC.
    answers = ('WC residential', 'Kitchen residential')
    # Run the project with the ConsoleDecisionHandler. This allows interactive
    # input to answer upcoming questions regarding the imported IFC.
    run_project(project, DebugDecisionHandler(answers))



def run_light_2015():
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
    project_path = Path(EXPORT_PATH) / f'{CITY}' / f'Constr{YEAR_OF_CONSTR}'\
                   / 'light_2015'

    # Get path of the IFC Building model that is used for this example
    ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/AC20-FZK-Haus.ifc',
    }
    # Create a project including the folder structure for the project with
    # energyplus as backend and no specified workflow
    # (default workflow is taken)
    project = Project.create(project_path, ifc_paths, 'comfort')

    # specified settings for workflows can be changed later as well
    project.sim_settings.ep_install_path = 'C://EnergyPlusV9-4-0/'
    project.sim_settings.layers_and_materials = LOD.low
    project.sim_settings.construction_class_walls = 'light'
    project.sim_settings.construction_class_windows = \
        'Waermeschutzverglasung, dreifach'
    project.sim_settings.run_full_simulation = True
    project.sim_settings.setpoints_from_template = True
    #project.sim_settings.add_window_shading = 'Exterior'
    project.sim_settings.year_of_construction_overwrite = YEAR_OF_CONSTR
    project.sim_settings.prj_use_conditions = \
        Path(__file__).parent.parent / \
        'data/UseConditionsComfort_AC20-FZK-Haus.json'
    project.sim_settings.prj_custom_usages = \
        Path(__file__).parent.parent / \
        'data/customUsages_AC20-FZK-Haus.json'
    project.sim_settings.cooling = False
    # project.sim_settings.use_dynamic_clothing = True
    project.sim_settings.overwrite_weather = \
        r'C:\Users\richter\sciebo\03-Paperdrafts' \
        r'\MDPI_SpecialIssue_Comfort_Climate\weather\futureWeather' \
        r'\Koeln_07_21_EC-Earth3\DEU_NW_Koln.Bonn.AP.105130_TMYx.2007-2021.epw'

    answers = ('WC residential', 'Kitchen residential')
    # Run the project with the ConsoleDecisionHandler. This allows interactive
    # input to answer upcoming questions regarding the imported IFC.
    run_project(project, DebugDecisionHandler(answers))


def run_light_2050_SSP585():
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
    project_path = Path(EXPORT_PATH) / f'{CITY}'/ f'Constr{YEAR_OF_CONSTR}' / \
                   'light_SSP585_2050'

    # Get path of the IFC Building model that is used for this example
    ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/AC20-FZK-Haus.ifc',
    }
    # Create a project including the folder structure for the project with
    # energyplus as backend and no specified workflow
    # (default workflow is taken)
    project = Project.create(project_path, ifc_paths, 'comfort')

    # specified settings for workflows can be changed later as well
    project.sim_settings.ep_install_path = 'C://EnergyPlusV9-4-0/'
    project.sim_settings.layers_and_materials = LOD.low
    project.sim_settings.construction_class_walls = 'light'
    project.sim_settings.construction_class_windows = \
        'Waermeschutzverglasung, dreifach'
    project.sim_settings.run_full_simulation = True
    project.sim_settings.setpoints_from_template = True
    #project.sim_settings.add_window_shading = 'Exterior'
    project.sim_settings.year_of_construction_overwrite = YEAR_OF_CONSTR
    project.sim_settings.prj_use_conditions = \
        Path(__file__).parent.parent / \
        'data/UseConditionsComfort_AC20-FZK-Haus.json'
    project.sim_settings.prj_custom_usages = \
        Path(__file__).parent.parent / \
        'data/customUsages_AC20-FZK-Haus.json'
    project.sim_settings.cooling = False
    # project.sim_settings.use_dynamic_clothing = True
    project.sim_settings.overwrite_weather = \
        r'C:\Users\richter\sciebo\03-Paperdrafts' \
        r'\MDPI_SpecialIssue_Comfort_Climate\weather\futureWeather' \
        r'\Koeln_07_21_EC-Earth3\DEU_NW_Koln.Bonn.AP_EC-Earth3_ssp585_2050.epw'

    answers = ('WC residential', 'Kitchen residential')
    # Run the project with the ConsoleDecisionHandler. This allows interactive
    # input to answer upcoming questions regarding the imported IFC.
    run_project(project, DebugDecisionHandler(answers))


def run_light_2080_SSP585():
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
    project_path = Path(EXPORT_PATH) / f'{CITY}'/ f'Constr{YEAR_OF_CONSTR}' / \
                   'light_SSP585_2080'

    # Get path of the IFC Building model that is used for this example
    ifc_paths = {
        IFCDomain.arch:
            Path(bim2sim.__file__).parent.parent /
            'test/resources/arch/ifc/AC20-FZK-Haus.ifc',
    }
    # Create a project including the folder structure for the project with
    # energyplus as backend and no specified workflow
    # (default workflow is taken)
    project = Project.create(project_path, ifc_paths, 'comfort')

    # specified settings for workflows can be changed later as well
    project.sim_settings.ep_install_path = 'C://EnergyPlusV9-4-0/'
    project.sim_settings.layers_and_materials = LOD.low
    project.sim_settings.construction_class_walls = 'light'
    project.sim_settings.construction_class_windows = \
        'Waermeschutzverglasung, dreifach'
    project.sim_settings.run_full_simulation = True
    project.sim_settings.setpoints_from_template = True
    #project.sim_settings.add_window_shading = 'Exterior'
    project.sim_settings.year_of_construction_overwrite = YEAR_OF_CONSTR
    project.sim_settings.prj_use_conditions = \
        Path(__file__).parent.parent / \
        'data/UseConditionsComfort_AC20-FZK-Haus.json'
    project.sim_settings.prj_custom_usages = \
        Path(__file__).parent.parent / \
        'data/customUsages_AC20-FZK-Haus.json'
    project.sim_settings.cooling = False
    # project.sim_settings.use_dynamic_clothing = True
    project.sim_settings.overwrite_weather = \
        r'C:\Users\richter\sciebo\03-Paperdrafts' \
        r'\MDPI_SpecialIssue_Comfort_Climate\weather\futureWeather' \
        r'\Koeln_07_21_EC-Earth3\DEU_NW_Koln.Bonn.AP_EC-Earth3_ssp585_2080.epw'

    answers = ('WC residential', 'Kitchen residential')
    # Run the project with the ConsoleDecisionHandler. This allows interactive
    # input to answer upcoming questions regarding the imported IFC.
    run_project(project, DebugDecisionHandler(answers))



if __name__ == '__main__':
    run_heavy_2015()
    run_heavy_2050_SSP585()
    run_heavy_2080_SSP585()
    # run_light_2015()
    # run_light_2050_SSP585()
    # run_light_2080_SSP585()