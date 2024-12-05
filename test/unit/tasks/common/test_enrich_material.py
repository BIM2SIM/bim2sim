import tempfile
import unittest
from unittest import mock

from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.sim_settings import BuildingSimSettings
from bim2sim.tasks.bps import EnrichMaterial
from test.unit.elements.helper import SetupHelperBPS
from bim2sim.elements.mapping.units import ureg


class TestEnrichMaterial(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        # Set up playground, project and paths via mocks
        cls.playground = mock.Mock()
        project = mock.Mock()
        paths = mock.Mock()
        cls.playground.project = project
        cls.playground.sim_settings = BuildingSimSettings()

        # Load libraries as these are required for export
        # lib_msl = LoadLibrariesStandardLibrary(cls.playground)
        # cls.loaded_libs = lib_msl.run()[0]

        # Instantiate export task and set required values via mocks
        cls.enrich_task = EnrichMaterial(cls.playground)
        cls.enrich_task.prj_name = 'TestEnrichMaterial'
        cls.enrich_task.paths = paths

        cls.helper = SetupHelperBPS()

    def setUp(self) -> None:
        # Set export path to temporary path
        self.export_path = tempfile.TemporaryDirectory(prefix='bim2sim')
        self.enrich_task.paths.export = self.export_path.name

    def tearDown(self) -> None:
        self.helper.reset()

    def test_enrichment_LOD_low_iwu_heavy_window_dreifach_2010(self):
        """Tests layer and material enrichment for specified sim_settings."""
        self.playground.sim_settings.construction_class_walls = 'iwu_heavy'
        self.playground.sim_settings.construction_class_windows = \
            'Waermeschutzverglasung, dreifach'
        self.playground.sim_settings.year_of_construction = 2010
        elements = self.helper.get_setup_simple_house()
        test_res = DebugDecisionHandler(()).handle(
            self.enrich_task.run(elements, ))
        # OuterWall layer and material
        ow_layer_1_thickness_exp = 0.175 * ureg.m
        ow_layer_2_thickness_exp = 0.07 * ureg.m
        ow_layer_1_material_dens_exp = 2420 * ureg.kg / ureg.m ** 3
        ow_layer_1_material_cp_exp = 1.0 * ureg.kilojoule / (ureg.kg * ureg.K)
        ow_layer_1_material_thermal_conduc_exp = \
            2.1 * ureg.W / (ureg.m * ureg.K)
        ow_layer_2_material_dens_exp = 15 * ureg.kg / ureg.m ** 3
        ow_layer_2_material_cp_exp = 1.5 * ureg.kilojoule / (ureg.kg * ureg.K)
        ow_layer_2_material_thermal_conduc_exp = \
            0.04 * ureg.W / (ureg.m * ureg.K)

        # Window layer and material
        window_layer_thickness_exp = 0.024 * ureg.m
        window_inner_radiation_exp = 5.0 * ureg.W / (ureg.m ** 2 * ureg.K)
        window_inner_convection_exp = 2.7 * ureg.W / (ureg.m ** 2 * ureg.K)
        window_outer_radiation_exp = 5.0 * ureg.W / (ureg.m ** 2 * ureg.K)
        window_outer_convection_exp = 20.0 * ureg.W / (ureg.m ** 2 * ureg.K)
        window_g_value_exp = 0.5
        window_a_conv_exp = 0.07
        window_shading_g_total_exp = 1.0
        window_shading_max_irr_exp = 100.0

        # Outer wall test data
        ow_layer_1_thickness = elements[
            '0000000000000000000001'].layerset.layers[0].thickness
        ow_layer_2_thickness = elements[
            '0000000000000000000001'].layerset.layers[1].thickness
        ow_layer_1_material_dens = elements[
            '0000000000000000000001'].layerset.layers[0].material.density
        ow_layer_1_material_cp = elements[
            '0000000000000000000001'].layerset.layers[
            0].material.spec_heat_capacity
        ow_layer_1_material_thermal_conduc = elements[
            '0000000000000000000001'].layerset.layers[
            0].material.thermal_conduc
        ow_layer_2_material_dens = elements[
            '0000000000000000000001'].layerset.layers[1].material.density
        ow_layer_2_material_cp = elements[
            '0000000000000000000001'].layerset.layers[
            1].material.spec_heat_capacity
        ow_layer_2_material_thermal_conduc = elements[
            '0000000000000000000001'].layerset.layers[
            1].material.thermal_conduc

        # Window test data
        window_layer_thickness = elements[
            '0000000000000000000002'].layerset.layers[0].thickness
        window_inner_radiation = elements[
            '0000000000000000000002'].inner_radiation
        window_inner_convection = elements[
            '0000000000000000000002'].inner_convection
        window_outer_radiation = elements[
            '0000000000000000000002'].outer_radiation
        window_outer_convection = elements[
            '0000000000000000000002'].outer_convection
        window_g_value = elements[
            '0000000000000000000002'].g_value
        window_a_conv = elements[
            '0000000000000000000002'].a_conv
        window_shading_g_total = elements[
            '0000000000000000000002'].shading_g_total
        window_shading_max_irr = elements[
            '0000000000000000000002'].shading_max_irr

        # Assertions
        self.assertEqual(ow_layer_1_thickness_exp, ow_layer_1_thickness)
        self.assertEqual(ow_layer_2_thickness_exp, ow_layer_2_thickness)
        self.assertEqual(ow_layer_1_material_dens_exp,
                         ow_layer_1_material_dens)
        self.assertEqual(ow_layer_1_material_cp_exp, ow_layer_1_material_cp)
        self.assertEqual(ow_layer_1_material_thermal_conduc_exp,
                         ow_layer_1_material_thermal_conduc)
        self.assertEqual(ow_layer_2_material_dens_exp,
                         ow_layer_2_material_dens)
        self.assertEqual(ow_layer_2_material_cp_exp, ow_layer_2_material_cp)
        self.assertEqual(ow_layer_2_material_thermal_conduc_exp,
                         ow_layer_2_material_thermal_conduc)
        self.assertEqual(window_layer_thickness_exp, window_layer_thickness)
        self.assertEqual(window_inner_radiation_exp, window_inner_radiation)
        self.assertEqual(window_inner_convection_exp, window_inner_convection)
        self.assertEqual(window_outer_radiation_exp, window_outer_radiation)
        self.assertEqual(window_outer_convection_exp, window_outer_convection)
        self.assertEqual(window_g_value_exp, window_g_value)
        self.assertEqual(window_a_conv_exp, window_a_conv)
        self.assertEqual(window_shading_g_total_exp, window_shading_g_total)
        self.assertEqual(window_shading_max_irr_exp, window_shading_max_irr)

    def test_enrichment_LOD_low_kfw40_window_zweifach_2010(self):
        """Tests layer and material enrichment for specified sim_settings."""
        self.playground.sim_settings.construction_class_walls = 'kfw_40'
        self.playground.sim_settings.construction_class_windows = \
            'Alu- oder Stahlfenster, Waermeschutzverglasung, zweifach'
        self.playground.sim_settings.year_of_construction = 2010
        elements = self.helper.get_setup_simple_house()
        test_res = DebugDecisionHandler(()).handle(
            self.enrich_task.run(elements, ))

        # OuterWall layer and material expected values
        ow_layer_1_thickness_exp = 0.01 * ureg.m
        ow_layer_2_thickness_exp = 0.04 * ureg.m
        ow_layer_3_thickness_exp = 0.18 * ureg.m
        ow_layer_4_thickness_exp = 0.015 * ureg.m
        ow_layer_5_thickness_exp = 0.06 * ureg.m
        ow_layer_6_thickness_exp = 0.0125 * ureg.m

        # Window layer and material expected values
        window_layer_thickness_exp = 0.024 * ureg.m
        window_inner_radiation_exp = 5.0 * ureg.W / (ureg.m ** 2 * ureg.K)
        window_inner_convection_exp = 2.7 * ureg.W / (ureg.m ** 2 * ureg.K)
        window_outer_radiation_exp = 5.0 * ureg.W / (ureg.m ** 2 * ureg.K)
        window_outer_convection_exp = 20.0 * ureg.W / (ureg.m ** 2 * ureg.K)
        window_g_value_exp = 0.65
        window_a_conv_exp = 0.07
        window_shading_g_total_exp = 1.0
        window_shading_max_irr_exp = 100.0

        # Outer wall test data
        ow_layer_1_thickness = elements[
            '0000000000000000000001'].layerset.layers[0].thickness
        ow_layer_2_thickness = elements[
            '0000000000000000000001'].layerset.layers[1].thickness
        ow_layer_3_thickness = elements[
            '0000000000000000000001'].layerset.layers[2].thickness
        ow_layer_4_thickness = elements[
            '0000000000000000000001'].layerset.layers[3].thickness
        ow_layer_5_thickness = elements[
            '0000000000000000000001'].layerset.layers[4].thickness
        ow_layer_6_thickness = elements[
            '0000000000000000000001'].layerset.layers[5].thickness

        # Window test data
        window_layer_thickness = elements[
            '0000000000000000000002'].layerset.layers[0].thickness
        window_inner_radiation = elements[
            '0000000000000000000002'].inner_radiation
        window_inner_convection = elements[
            '0000000000000000000002'].inner_convection
        window_outer_radiation = elements[
            '0000000000000000000002'].outer_radiation
        window_outer_convection = elements[
            '0000000000000000000002'].outer_convection
        window_g_value = elements[
            '0000000000000000000002'].g_value
        window_a_conv = elements[
            '0000000000000000000002'].a_conv
        window_shading_g_total = elements[
            '0000000000000000000002'].shading_g_total
        window_shading_max_irr = elements[
            '0000000000000000000002'].shading_max_irr

        # Assertions for outer wall
        self.assertEqual(ow_layer_1_thickness_exp, ow_layer_1_thickness)
        self.assertEqual(ow_layer_2_thickness_exp, ow_layer_2_thickness)
        self.assertEqual(ow_layer_3_thickness_exp, ow_layer_3_thickness)
        self.assertEqual(ow_layer_4_thickness_exp, ow_layer_4_thickness)
        self.assertEqual(ow_layer_5_thickness_exp, ow_layer_5_thickness)
        self.assertEqual(ow_layer_6_thickness_exp, ow_layer_6_thickness)

        # Assertions for window
        self.assertEqual(window_layer_thickness_exp, window_layer_thickness)
        self.assertEqual(window_inner_radiation_exp, window_inner_radiation)
        self.assertEqual(window_inner_convection_exp, window_inner_convection)
        self.assertEqual(window_outer_radiation_exp, window_outer_radiation)
        self.assertEqual(window_outer_convection_exp, window_outer_convection)
        self.assertEqual(window_g_value_exp, window_g_value)
        self.assertEqual(window_a_conv_exp, window_a_conv)
        self.assertEqual(window_shading_g_total_exp, window_shading_g_total)
        self.assertEqual(window_shading_max_irr_exp, window_shading_max_irr)