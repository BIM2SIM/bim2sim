import threading
import unittest

from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.utilities.test import IntegrationBase
from bim2sim.utilities.types import IFCDomain, LCACalculationBuilding

lock = threading.Lock()


class IntegrationBaseLCA(IntegrationBase):
    def model_domain_path(self) -> str:
        return 'arch'


class TestIntegrationLCA(IntegrationBaseLCA, unittest.TestCase):
    def test_run_kitinstitute_lca(self):
        """Run project with AC20-Institute-Var-2..ifc"""
        ifc_names = {IFCDomain.arch: 'AC20-Institute-Var-2.ifc'}
        project = self.create_project(ifc_names, 'LCA')
        project.sim_settings.update_emission_parameter_from_oekobdauat = True
        project.sim_settings.calculate_lca_building = (LCACalculationBuilding.
                                                       granular)
        project.sim_settings.calculate_lca_hydraulic_system = False
        project.sim_settings.calculate_lca_ventilation_system = False
        # TODO #176 is a quite dirty implementation for multi processing
        #  at the moment, check if this is still needed and if yes, find a
        #  cleaner way. Check all code for project.sim_settings.lock = lock
        project.sim_settings.lock = lock
        answers = (2005,)
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")

    def test_run_ERC_lca(self):
        """Run project with AC20-FZK-Haus.ifc"""
        ifc_names = {IFCDomain.arch: 'ERC_Mainbuilding_Arch.ifc'}
        project = self.create_project(ifc_names, 'LCA')
        project.sim_settings.update_emission_parameter_from_oekobdauat = True
        project.sim_settings.calculate_lca_building = (LCACalculationBuilding.
                                                       granular)
        project.sim_settings.calculate_lca_hydraulic_system = False
        project.sim_settings.calculate_lca_ventilation_system = False
        project.sim_settings.lock = lock
        answers = ()
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer
        self.assertEqual(0, handler.return_value,
                         "Project did not finish successfully.")
