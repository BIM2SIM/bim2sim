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
    def test_run_fzk_hause(self):
        """Run project with AC20-FZK-Haus.ifc"""
        ifc_names = {IFCDomain.arch: 'AC20-FZK-Haus.ifc'}
        project = self.create_project(ifc_names, PluginIFCCheck)

        # assign an IDS file, which is needed to check the ifc file by ifctester
        # TODO exchange to a more sophisticated ids file
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

        answers = ()
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    def test_run_fzk_hause_sb55(self):
        """Run project with AC20-FZK-Haus.ifc"""
        ifc_names = {IFCDomain.arch: 'AC20-FZK-Haus_with_SB55.ifc'}
        project = self.create_project(ifc_names, PluginIFCCheck)

        # assign an IDS file, which is needed to check the ifc file by ifctester
        # TODO exchange to a more sophisticated ids file
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

        answers = ('Other', 'Other')
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    def test_run_three_rooms_with_SB(self):
        """Run project with
        2024-04-23_3rooms_240317_Heater_AirTerminal_Table_with_SB.ifc"""

        ifc_3rooms_with_sb = Path(
            '/home/cudok/Documents/12_ifc_check_ids/03_ifc_veronika/2024-04-23_3rooms_240317_Heater_AirTerminal_Table_with_SB.ifc'
        )
        ifc_names = {IFCDomain.arch: ifc_3rooms_with_sb}
        project = self.create_project(ifc_names, PluginIFCCheck)

        # assign an IDS file, which is needed to check the ifc file by ifctester
        # TODO exchange to a more sophisticated ids file
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

        answers = ('Other', 'Other')
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    def test_run_three_rooms_with_SB_fail(self):
        """Run project with
        2024-04-23_3rooms_240317_Heater_AirTerminal_Table_with_SB.ifc"""

        ifc_3rooms_with_sb_fail = Path(
            '/home/cudok/Documents/12_ifc_check_ids/03_ifc_veronika/2024-04-23_3rooms_240317_Heater_AirTerminal_Table_with_SB_errors.ifc'
        )
        ifc_names = {IFCDomain.arch: ifc_3rooms_with_sb_fail}
        project = self.create_project(ifc_names, PluginIFCCheck)

        # assign an IDS file, which is needed to check the ifc file by ifctester
        # TODO exchange to a more sophisticated ids file
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

        answers = ('Other', 'Other')
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")
