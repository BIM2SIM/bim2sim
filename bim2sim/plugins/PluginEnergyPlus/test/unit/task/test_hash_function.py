import unittest
import tempfile
from pathlib import Path

import bim2sim
from bim2sim import Project, run_project, ConsoleDecisionHandler
from bim2sim.utilities.types import IFCDomain



class Test_Hash_Function(unittest.TestCase):
    """Tests the hash function to verify if the hash value is successfully generated and added to the IDF file."""

    def test_idf_hash(self):
        # Create a temporary directory for the project
        temp_dir = tempfile.TemporaryDirectory(prefix='bim2sim_example1')
        project_path = Path(temp_dir.name)

        # The temporary directory is cleaned up after the test
        self.addCleanup(temp_dir.cleanup)

        # Set the ifc path to use and define which domain the IFC belongs to
        ifc_paths = {
            IFCDomain.arch:
                Path(bim2sim.__file__).parent.parent /
                'test/resources/arch/ifc/AC20-FZK-Haus.ifc',
        }
        ifc_file_path = ifc_paths[IFCDomain.arch]
        ifc_file_name = ifc_file_path.stem
        # Create a project including the folder structure for the project
        project = Project.create(project_path, ifc_paths, 'energyplus')

        # set weather file data
        project.sim_settings.weather_file_path = (
                Path(bim2sim.__file__).parent.parent /
                'test/resources/weather_files/DEU_NW_Aachen.105010_TMYx.epw')
        # project.sim_settings.ep_install_path = 'C://EnergyPlusV9-4-0/'
        project.sim_settings.run_full_simulation = False
        project.sim_settings.reset_guids = True

        # Run the project
        run_project(project, ConsoleDecisionHandler())

        idf_path = project_path / "export" / "EnergyPlus" / "SimResults" / ifc_file_name / f"{ifc_file_name}.idf"

        with open(idf_path, "r") as f:
            first_line = f.readline()
            if "IFC_GEOMETRY_HASH" in first_line:
                print("IFC_GEOMETRY_HASH found in the first line of the file.")
                print("Hashline:", first_line)
            else:
                print("IFC_GEOMETRY_HASH not found in the first line of the file.")
            self.assertEqual("IFC_GEOMETRY_HASH" in first_line, True)


if __name__ == '__main__':
    unittest.main()
