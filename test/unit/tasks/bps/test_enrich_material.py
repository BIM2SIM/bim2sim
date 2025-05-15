from bim2sim.elements.mapping.units import ureg
from bim2sim.sim_settings import BuildingSimSettings
from bim2sim.tasks.bps import EnrichMaterial
from test.unit.elements.helper import SetupHelperBPS
from test.unit.tasks import TestTask


class TestEnrichMaterial(TestTask):

    @classmethod
    def simSettingsClass(cls):
        return BuildingSimSettings()

    @classmethod
    def testTask(cls):
        return EnrichMaterial(cls.playground)

    @classmethod
    def helper(cls):
        return SetupHelperBPS()

    def test_enrichment_LOD_low_iwu_heavy_window_dreifach_2010(self):
        """Tests layer and material enrichment for specified sim_settings."""
        self.playground.sim_settings.construction_class_walls = 'iwu_heavy'
        self.playground.sim_settings.construction_class_windows = \
            'Waermeschutzverglasung, dreifach'
        self.playground.sim_settings.year_of_construction = 2010
        elements = self.helper.get_setup_simple_house()
        answers = ()
        reads = (elements, )
        test_res = self.run_task(answers, reads)
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
            'outerWall001'].layerset.layers[0].thickness
        ow_layer_2_thickness = elements[
            'outerWall001'].layerset.layers[1].thickness
        ow_layer_1_material_dens = elements[
            'outerWall001'].layerset.layers[0].material.density
        ow_layer_1_material_cp = elements[
            'outerWall001'].layerset.layers[
            0].material.spec_heat_capacity
        ow_layer_1_material_thermal_conduc = elements[
            'outerWall001'].layerset.layers[
            0].material.thermal_conduc
        ow_layer_2_material_dens = elements[
            'outerWall001'].layerset.layers[1].material.density
        ow_layer_2_material_cp = elements[
            'outerWall001'].layerset.layers[
            1].material.spec_heat_capacity
        ow_layer_2_material_thermal_conduc = elements[
            'outerWall001'].layerset.layers[
            1].material.thermal_conduc

        # Window test data
        window_layer_thickness = elements[
            'window001'].layerset.layers[0].thickness
        window_inner_radiation = elements[
            'window001'].inner_radiation
        window_inner_convection = elements[
            'window001'].inner_convection
        window_outer_radiation = elements[
            'window001'].outer_radiation
        window_outer_convection = elements[
            'window001'].outer_convection
        window_g_value = elements[
            'window001'].g_value
        window_a_conv = elements[
            'window001'].a_conv
        window_shading_g_total = elements[
            'window001'].shading_g_total
        window_shading_max_irr = elements[
            'window001'].shading_max_irr

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
        answers = ()
        reads = (elements, )
        test_res = self.run_task(answers, reads)

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
            'outerWall001'].layerset.layers[0].thickness
        ow_layer_2_thickness = elements[
            'outerWall001'].layerset.layers[1].thickness
        ow_layer_3_thickness = elements[
            'outerWall001'].layerset.layers[2].thickness
        ow_layer_4_thickness = elements[
            'outerWall001'].layerset.layers[3].thickness
        ow_layer_5_thickness = elements[
            'outerWall001'].layerset.layers[4].thickness
        ow_layer_6_thickness = elements[
            'outerWall001'].layerset.layers[5].thickness

        # Window test data
        window_layer_thickness = elements[
            'window001'].layerset.layers[0].thickness
        window_inner_radiation = elements[
            'window001'].inner_radiation
        window_inner_convection = elements[
            'window001'].inner_convection
        window_outer_radiation = elements[
            'window001'].outer_radiation
        window_outer_convection = elements[
            'window001'].outer_convection
        window_g_value = elements[
            'window001'].g_value
        window_a_conv = elements[
            'window001'].a_conv
        window_shading_g_total = elements[
            'window001'].shading_g_total
        window_shading_max_irr = elements[
            'window001'].shading_max_irr

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
