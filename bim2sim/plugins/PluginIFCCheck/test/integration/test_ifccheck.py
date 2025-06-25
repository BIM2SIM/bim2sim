import unittest
from pathlib import Path

import bim2sim
from bim2sim.kernel.decision.console import ConsoleDecisionHandler
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.utilities.test import IntegrationBase
from bim2sim.utilities.types import LOD, IFCDomain, ZoningCriteria
from bim2sim.plugins.PluginIFCCheck.bim2sim_ifccheck import PluginIFCCheck

class IntegrationBaseIFCCheck(IntegrationBase):
    def model_domain_path(self) -> str:
        return 'arch'


class TestIntegrationIFCCheck(IntegrationBaseIFCCheck, unittest.TestCase):
    def test_run_kitinstitute_lca(self):
        """Run project with AC20-FZK-Haus.ifc"""
        ifc_names = {IFCDomain.arch: 'AC20-FZK-Haus.ifc'}
        project = self.create_project(ifc_names, PluginIFCCheck)

        # assign an IDS file, which is needed to check the ifc file by ifctester
        project.sim_settings.ids_file_path = (
                Path(bim2sim.__file__).parent.parent /
                'test/resources/ids/fail-a_minimal_ids_can_check_a_minimal_ifc_1_2.ids'
        )

        # In the next step we assign this file to the project by setting:
        project.sim_settings.prj_custom_usages = (Path(
            bim2sim.__file__).parent.parent / "test/resources/arch/custom_usages/"
                "customUsagesAC20-FZK-Haus.json")

        project.sim_settings.prj_use_conditions = (Path(
            bim2sim.__file__).parent.parent / "test/resources/arch/custom_usages/"
                "UseConditionsAC20-FZK-Haus.json")

        project.sim_settings.setpoints_from_template = True

        # run_project(project, ConsoleDecisionHandler())

        answers = ()
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")
