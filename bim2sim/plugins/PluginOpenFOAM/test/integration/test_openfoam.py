import sys
import unittest
from shutil import copyfile, copytree, rmtree
from pathlib import Path

import os

from OCC.Core.gp import gp_Pnt

import bim2sim
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.tasks import common, bps
from bim2sim.plugins.PluginOpenFOAM.bim2sim_openfoam import task as of_tasks
from bim2sim.tasks import common, bps
from bim2sim.utilities.common_functions import filter_elements
from bim2sim.utilities.pyocc_tools import PyOCCTools
from bim2sim.utilities.test import IntegrationBase
from bim2sim.utilities.types import IFCDomain

# raise unittest.SkipTest("Integration tests not reliable for automated use")
sample_root = Path(__file__).parent.parent.parent / 'test/resources/arch/ifc'
DEBUG_CASE = True


class IntegrationBaseOF(IntegrationBase):
    # HACK: We have to remember stderr because eppy resets it currently.
    def setUp(self):
        self.old_stderr = sys.stderr
        self.working_dir = os.getcwd()
        super().setUp()

    def tearDown(self):
        os.chdir(self.working_dir)
        sys.stderr = self.old_stderr
        if not DEBUG_CASE:
            super().tearDown()

    def model_domain_path(self) -> str:
        return 'arch'

    def weather_file_path(self) -> Path:
        return (self.test_resources_path() /
                'weather_files/DEU_NW_Aachen.105010_TMYx.epw')


class TestOFIntegration(IntegrationBaseOF, unittest.TestCase):
    """
    Integration tests for multiple IFC example files.
    """

    # @unittest.skip("")

    def validate_positions(self, position_type, elements, openfoam_elements,
                           openfoam_case, valid_amount):
        positioned_objects = filter_elements(openfoam_elements, position_type)
        if positioned_objects:
            objs_bbox = PyOCCTools.simple_bounding_box_shape(
                [obj.tri_geom for obj in
                 positioned_objects])
            min_objs_bbox, max_objs_bbox = PyOCCTools.simple_bounding_box([
                obj.tri_geom for obj in
                positioned_objects])
            another_zone = None
            for tz in filter_elements(elements, 'ThermalZone'):
                if tz.guid != openfoam_case.current_zone.guid:
                    another_zone = tz
                    break
            with self.subTest("Center of Furniture Compound in Space Shape"):
                self.assertEqual(True, PyOCCTools.obj2_in_obj1(
                    openfoam_case.current_zone.space_shape, objs_bbox))
            with self.subTest("Center of Furniture Compound not in other "
                              "Space"):
                if another_zone is not None:
                    self.assertEqual(False, PyOCCTools.obj2_in_obj1(
                        another_zone.space_shape, objs_bbox))
                else:
                    self.assertEqual(True, False)
            with self.subTest("Min and Max of Bounding Box in Space Shape."):
                self.assertEqual(True, PyOCCTools.check_pnt_in_solid(
                    PyOCCTools.make_solid_from_shape(
                        PyOCCTools, openfoam_case.current_zone.space_shape),
                    gp_Pnt(*min_objs_bbox)))
                self.assertEqual(True, PyOCCTools.check_pnt_in_solid(
                    PyOCCTools.make_solid_from_shape(
                        PyOCCTools, openfoam_case.current_zone.space_shape),
                    gp_Pnt(*max_objs_bbox)))
        with self.subTest("Resulting number of positioned objects as "
                          "expected."):
            self.assertEqual(valid_amount, len(positioned_objects))

    def run_test_furniture_setup_with_people(self, project, space_guid,
                                             furniture_orientation,
                                             furniture_setting,
                                             furniture_amount=0,
                                             add_people=False,
                                             people_amount=1,
                                             people_setting='Seated',
                                             add_furniture=True,
                                             valid_number_furniture=0,
                                             valid_number_people=0):
        with self.subTest(f"Testing space_guid={space_guid}, "
                          f"setting={furniture_setting}, "
                          f"orientation={furniture_orientation}, add_people="
                          f"{add_people}, "
                          f"{f'people_amount={people_amount}, people_setting={people_setting}' if add_people else ''}"):
            if 'openfoam_case' in project.playground.state:
                openfoam_case = project.playground.state['openfoam_case']
                # remove openfoam directory from previous test
                if os.path.exists(openfoam_case.openfoam_dir):
                    rmtree(openfoam_case.openfoam_dir)

        ### redefine default tasks for OpenFOAM Plugin testing
        project.plugin_cls.default_tasks = [
            of_tasks.InitializeOpenFOAMSetup,
            of_tasks.CreateOpenFOAMGeometry,
        ]

        project.sim_settings.add_airterminals = False
        project.sim_settings.add_heating = False
        project.sim_settings.add_furniture = add_furniture
        project.sim_settings.furniture_amount = furniture_amount
        project.sim_settings.furniture_setting = furniture_setting
        project.sim_settings.furniture_orientation = furniture_orientation
        project.sim_settings.add_people = add_people
        project.sim_settings.people_setting = people_setting
        project.sim_settings.people_amount = people_amount
        project.sim_settings.select_space_guid = space_guid
        handler = DebugDecisionHandler(())
        handler.handle(project.run(cleanup=False))

        openfoam_case = project.playground.state['openfoam_case']
        openfoam_elements = project.playground.state['openfoam_elements']
        # todo: requires debugging, more than 48 should be possible here
        self.validate_positions('Furniture',
                                project.playground.elements,
                                openfoam_elements, openfoam_case,
                                valid_number_furniture)
        self.validate_positions('People',
                                project.playground.elements,
                                openfoam_elements, openfoam_case,
                                valid_number_people)
        self.assertEqual(0, handler.return_value)

    def test_furniture_setup(self):
        """Test Original IFC File from FZK-Haus (KIT)"""
        ifc_names = {IFCDomain.arch: 'AC20-FZK-Haus.ifc'}
        project = self.create_project(ifc_names, 'openfoam')

        project.plugin_cls.default_tasks = [
            common.LoadIFC,
            common.CreateElementsOnIfcTypes,
            bps.CreateSpaceBoundaries,
            bps.CorrectSpaceBoundaries,
            common.CreateRelations,
            of_tasks.InitializeOpenFOAMSetup,
            of_tasks.CreateOpenFOAMGeometry,
        ]
        project.sim_settings.add_airterminals = False
        project.sim_settings.add_heating = False
        project.sim_settings.add_furniture = True
        project.sim_settings.furniture_setting = 'Concert'
        project.sim_settings.furniture_orientation = 'long_side'
        project.sim_settings.furniture_amount = 50
        project.sim_settings.add_people = True
        project.sim_settings.people_amount = 1
        project.sim_settings.people_setting = 'Seated'
        project.sim_settings.ep_install_path = 'C://EnergyPlusV9-4-0/'
        project.sim_settings.select_space_guid = '2RSCzLOBz4FAK$_wE8VckM'
        answers = ()
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer

        self.assertEqual(0, handler.return_value)

    def test_furniture_setup_DH(self):
        """Test DigitalHub, IFC2SB Version, Furniture setups"""

        #### prepare for OpenFOAM Plugin (EnergyPlus is skipped here,
        # so no boundary conditions are available in this test)
        ifc_names = {IFCDomain.arch: 'FM_ARC_DigitalHub_with_SB89.ifc'}
        project = self.create_project(ifc_names, 'openfoam')
        project.plugin_cls.default_tasks = [
            common.LoadIFC,
            common.CreateElementsOnIfcTypes,
            bps.CreateSpaceBoundaries,
            bps.CorrectSpaceBoundaries,
            common.CreateRelations,
        ]
        project.sim_settings.ep_install_path = 'C://EnergyPlusV9-4-0/'
        answers = ('Autodesk Revit', 'Autodesk Revit', *(None,) * 12)
        handler = DebugDecisionHandler(answers)
        handler.handle(project.run(cleanup=False))
        self.run_test_furniture_setup_with_people(project,
                                                  '3GmoJyFk9FvAnea6mogixJ',
                                                  'west',
                                                  'Concert',
                                                  200,
                                                  valid_number_furniture=153)
        self.run_test_furniture_setup_with_people(project,
                                                  '3hiy47ppf5B8MyZqbpTfpc',
                                                  'door',
                                                  'Concert',
                                                  200,
                                                  valid_number_furniture=50)
        self.run_test_furniture_setup_with_people(project,
                                                  '2o3MylYZzAnR8q1ofuG3sg',
                                                  'window',
                                                  'Concert',
                                                  200,
                                                  valid_number_furniture=48)
        self.run_test_furniture_setup_with_people(project,
                                                  '2o3MylYZzAnR8q1ofuG3sg',
                                                  'south',
                                                  'Concert',
                                                  200,
                                                  valid_number_furniture=103)
        self.run_test_furniture_setup_with_people(project,
                                                  '2o3MylYZzAnR8q1ofuG3sg',
                                                  'door',
                                                  'Concert',
                                                  200,
                                                  valid_number_furniture=48)
        self.run_test_furniture_setup_with_people(project,
                                                  '2o3MylYZzAnR8q1ofuG3sg',
                                                  'door',
                                                  'Concert',
                                                  30,
                                                  add_people=True,
                                                  people_amount=2,
                                                  valid_number_furniture=30,
                                                  valid_number_people=2)


if __name__ == '__main__':
    unittest.main()
