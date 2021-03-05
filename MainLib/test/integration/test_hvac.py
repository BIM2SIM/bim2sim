import unittest
from pathlib import Path
import tempfile
import logging

import bim2sim
import bim2sim.decision
import bim2sim.kernel.element

# ------------------------------------------------------------------------------
# WARNING: run only one test per interpreter Instance.
# To use tests uncomment line below und run single test
# ------------------------------------------------------------------------------
raise unittest.SkipTest("Integration tests not reliable for automated use")


class IntegrationBase:
    """Base class mixin for Integration tests"""

    def setUp(self):
        # importlib.reload(bim2sim)
        self.temp_dir = tempfile.TemporaryDirectory(prefix='bim2sim_')

    def tearDown(self):
        # manually close file handlers which would block temp dir deletion
        # TODO: this does not always work. log file somtijmes still blocked
        # TODO: Projekt noch properly reset. Run only one test per Interpreter instance as workaround
        root = logging.getLogger()
        for handler in root.handlers:
            if isinstance(handler, logging.FileHandler):
                handler.stream.flush()
                handler.stream.close()
            root.removeHandler(handler)
        for filt in root.filters:
            root.removeFilter(filt)

        # reset project
        self.reset_project()

        # delete temp dir
        self.temp_dir.cleanup()

    def reset_project(self):
        """clean bim2sim lib"""
        # decisions
        bim2sim.decision.Decision.reset_decisions()
        bim2sim.decision.Decision.stored_decisions.clear()
        # element.objects
        for item in list(bim2sim.kernel.element.Root.objects.values()):
            item.discard()

    def run_project(self, ifc_file: str, backend: str):
        """Create example project and copy ifc if necessary
        :param backend: Project backend e.g. 'hkesim', 'aixlib', ...
        :param ifc_file: name of ifc file located in dir TestModels
        :return: return code of main()
        """

        project_path = Path(self.temp_dir.name)
        path_ifc = Path(__file__).parent.parent / 'TestModels' / ifc_file

        if not bim2sim.PROJECT.is_project_folder(project_path):
            bim2sim.PROJECT.create(project_path, path_ifc, target=backend)
        return_code = bim2sim.main(project_path)
        return return_code


class TestIntegrationHKESIM(IntegrationBase, unittest.TestCase):

    def test_run_vereinshaus1(self):
        """Run project with KM_DPM_Vereinshaus_Gruppe62_Heizung_with_pumps.ifc"""
        ifc = 'KM_DPM_Vereinshaus_Gruppe62_Heizung_with_pumps.ifc'
        answers = (True, True, *(True,)*14, 50)
        with bim2sim.decision.Decision.debug_answer(answers, multi=True):
            return_code = self.run_project(ifc, 'hkesim')
        self.assertEqual(0, return_code, "Project did not finish successfully.")

    def test_run_vereinshaus2(self):
        """Run project with KM_DPM_Vereinshaus_Gruppe62_Heizung_DTV_all_elements.ifc"""
        ifc = 'KM_DPM_Vereinshaus_Gruppe62_Heizung_DTV_all_elements.ifc'
        answers = (True, *(True,)*16, 200)
        with bim2sim.decision.Decision.debug_answer(answers, multi=True):
            return_code = self.run_project(ifc, 'hkesim')
        self.assertEqual(0, return_code, "Project did not finish successfully.")


class TestIntegrationAixLib(unittest.TestCase):

    pass