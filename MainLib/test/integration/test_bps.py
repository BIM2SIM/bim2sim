import unittest

import bim2sim

from .base import IntegrationBase

# ------------------------------------------------------------------------------
# WARNING: run only one test per interpreter Instance.
# To use tests uncomment line below und run single test
# ------------------------------------------------------------------------------
# raise unittest.SkipTest("Integration tests not reliable for automated use")


class TestIntegrationTEASER(IntegrationBase, unittest.TestCase):

    def test_run_kitfzkhaus_test1(self):
        """Run project with AC20-FZK-Haus.ifc"""
        ifc = 'AC20-FZK-Haus.ifc'
        # todo add answers, in disaggreagtion branch
        # test -> spaces-low, layer-low
        answers = (True, True, 'Living', 'heavy', 'EnEv')
        with bim2sim.decision.Decision.debug_answer(answers, multi=True):
            return_code = self.run_project(ifc, 'TEASER')
        self.assertEqual(0, return_code, "Project did not finish successfully.")

    def test_run_kitfzkhaus_test2(self):
        """Run project with AC20-FZK-Haus.ifc"""
        ifc = 'AC20-FZK-Haus.ifc'
        # todo add answers, in disaggreagtion branch
        # test -> spaces-medium, layer-low
        answers = (True, True, 'Kitchen - preparations, storage', 'heavy', 'EnEv', False)
        # test -> spaces-medium, layer-full
        # answers = ()
        # test -> spaces-full, layer-full
        # answers = ()
        with bim2sim.decision.Decision.debug_answer(answers, multi=True):
            return_code = self.run_project(ifc, 'TEASER')
        self.assertEqual(0, return_code, "Project did not finish successfully.")

    def test_run_kitoffice_test1(self):
        """Run project with AC20-Institute-Var-2.ifc"""
        ifc = 'AC20-Institute-Var-2.ifc'
        # test -> spaces-low, layer-low
        answers = (True, True, 'Open-plan Office (7 or more employees)', 'heavy', 2015, 'EnEv')
        with bim2sim.decision.Decision.debug_answer(answers, multi=True):
            return_code = self.run_project(ifc, 'TEASER')
        self.assertEqual(0, return_code, "Project did not finish successfully.")

    def test_run_kitoffice_test2(self):
        """Run project with AC20-Institute-Var-2.ifc"""
        ifc = 'AC20-Institute-Var-2.ifc'
        # test -> spaces-medium, layer-low
        answers = (True, True, 'heavy', 2015, 'EnEv', False)
        # test -> spaces-medium, layer-full
        # answers = ()
        # test -> spaces-full, layer-full
        # answers = ()
        with bim2sim.decision.Decision.debug_answer(answers, multi=True):
            return_code = self.run_project(ifc, 'TEASER')
        self.assertEqual(0, return_code, "Project did not finish successfully.")


class TestIntegrationAixLib(unittest.TestCase):
    pass