import unittest
import tempfile
from pathlib import Path


from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.project import Project
from bim2sim.utilities.types import IFCDomain
from bim2sim.plugins import Plugin
from bim2sim.tasks import common, bps
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus.sim_settings import \
    EnergyPlusSimSettings
from bim2sim.plugins.PluginEnergyPlus.bim2sim_energyplus import \
    task as ep_tasks


class PluginHashDummyEP(Plugin):
    name = 'EnergyPlus'
    sim_settings = EnergyPlusSimSettings
    default_tasks = [
        common.LoadIFC,
        common.CheckIfc,
        common.CreateElementsOnIfcTypes,
        bps.CreateSpaceBoundaries,
        bps.AddSpaceBoundaries2B,
        bps.CorrectSpaceBoundaries,
        common.CreateRelations,
        bps.DisaggregationCreationAndTypeCheck,
        bps.EnrichMaterial,
        bps.EnrichUseConditions,
        common.Weather,
        ep_tasks.CreateIdf,
        # ep_tasks.IdfPostprocessing,
        # ep_tasks.ExportIdfForCfd,
        # common.SerializeElements,
    ]


test_rsrc_path = (Path(
    __file__).parent.parent.parent.parent.parent.parent.parent
                  / 'test/resources')


class TestHashFunction(unittest.TestCase):

    def tearDown(self):
        self.project.finalize(True)
        self.test_dir.cleanup()

    def test_idf_hash(self):
        """Tests the hash function to verify if the hash value is successfully
        generated and added to the IDF file."""

        self.test_dir = tempfile.TemporaryDirectory()

        ifc_paths = {
            IFCDomain.arch: test_rsrc_path / 'arch/ifc/AC20-FZK-Haus.ifc'}
        self.project = Project.create(self.test_dir.name, ifc_paths,
                                      plugin=PluginHashDummyEP)
        self.project.sim_settings.weather_file_path = (
                test_rsrc_path / 'weather_files/DEU_NW_Aachen.105010_TMYx.epw')
        # self.project.sim_settings.ep_install_path = 'C://EnergyPlusV9-4-0/'

        self.project.sim_settings.run_full_simulation = False
        self.project.sim_settings.add_hash = True

        handler = DebugDecisionHandler([])
        handler.handle(self.project.run(cleanup=False))

        ifc_file_path = ifc_paths[IFCDomain.arch]
        ifc_file_name = ifc_file_path.stem
        project_path = Path(self.test_dir.name)
        idf_path = project_path / "export" / "EnergyPlus" / "SimResults" / ifc_file_name / f"{ifc_file_name}.idf"

        with open(idf_path, "r") as f:
            first_line = f.readline()
            if "IFC_GEOMETRY_HASH" in first_line:
                print("IFC_GEOMETRY_HASH found in the first line of the file.")
                print("Hash line:", first_line)
            else:
                print("IFC_GEOMETRY_HASH not found in the first line of the file.")
            self.assertEqual("IFC_GEOMETRY_HASH" in first_line, True)


if __name__ == '__main__':
    unittest.main()
