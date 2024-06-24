import tempfile

from bim2sim import ConsoleDecisionHandler
from bim2sim.export.modelica import HeatTransferType
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler

from bim2sim.plugins.PluginAixLib.bim2sim_aixlib import LoadLibrariesAixLib
from bim2sim.elements.mapping.units import ureg
from test.unit.tasks.hvac.test_export import TestStandardLibraryExports
from test.unit.elements.aggregation.test_consumer import ConsumerHelper


class TestAixLibExport(TestStandardLibraryExports):

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        lib_aixlib = LoadLibrariesAixLib(cls.playground)
        cls.loaded_libs = lib_aixlib.run()[0]
        cls.export_task.prj_name = 'TestAixLibExport'

    def setUp(self) -> None:
        # Set export path to temporary path
        self.export_path = tempfile.TemporaryDirectory(prefix='bim2sim')
        self.export_task.paths.export = self.export_path.name

    def tearDown(self) -> None:
        self.helper.reset()

    def test_pump_export(self):
        graph = self.helper.get_pump()
        answers = ()

        modelica_model = DebugDecisionHandler(answers).handle(
            self.export_task.run(self.loaded_libs, graph))
        v_flow_expected = [
            0 * graph.elements[0].rated_volume_flow,
            graph.elements[0].rated_volume_flow,
            2 * graph.elements[0].rated_volume_flow
        ]
        dp_expected = [
            2 * graph.elements[0].rated_pressure_difference,
            graph.elements[0].rated_pressure_difference,
            0 * graph.elements[0].rated_pressure_difference
        ]
        pump_export_params_expected = {
            "per": {
                "pressure":
                    {
                        "V_flow": v_flow_expected,
                        "dp": dp_expected
                    }
            }
        }
        pump_export_params = {
            "per": modelica_model[0].elements[0].export_records["per"]
        }
        # TODO when export_unit problem is fixed for records, this can be
        #  simplified regarding the unit handling
        pump_modelica_params_expected = {
            "per": f'pressure(V_flow='
                   f'{[v_flow_i.to(ureg.m ** 3 / ureg.s).m for v_flow_i in v_flow_expected]},'
                   f'dp={[dp_i.m for dp_i in dp_expected]})'
            .replace(
                "[", "{").replace(
                "]", "}").replace(
                " ", "")
        }
        pump_modelica_params = {
            "per": modelica_model[0].elements[0].modelica_export_dict[
                'per'],
        }

        self.assertDictEqual(
            pump_export_params_expected, pump_export_params)
        self.assertDictEqual(
            pump_modelica_params_expected, pump_modelica_params)

    # TODO #624 Write tests for all components of AixLib

    def test_radiator_export_with_heat_ports(self):
        """Test export of two radiators, focus on correct heat port export."""
        graph = self.helper.get_two_radiators()
        answers = ()

        # export outer heat ports
        self.export_task.playground.sim_settings.outer_heat_ports = True

        modelica_model = DebugDecisionHandler(answers).handle(
            self.export_task.run(self.loaded_libs, graph))
        # ToDo: as elements are unsorted, testing with names is not robust
        # connections_heat_ports_conv_expected = [
        #     ('heatPortOuterCon[1]',
        #      'spaceheater_0000000000000000000001.heatPortCon'),
        #     ('heatPortOuterCon[2]',
        #      'spaceheater_0000000000000000000004.heatPortCon')]

        # connections_heat_ports_rad_expected = [
        #     ('heatPortOuterRad[1]',
        #      'spaceheater_0000000000000000000001.heatPortRad'),
        #     ('heatPortOuterRad[2]',
        #      'spaceheater_0000000000000000000004.heatPortRad')]

        # check existence of heat ports
        self.assertEqual(
            2, len(modelica_model[0].elements[0].heat_ports))
        self.assertEqual(
            2, len(modelica_model[0].elements[1].heat_ports))

        # check types of heat ports
        self.assertEqual(
            modelica_model[0].elements[0].heat_ports[0].heat_transfer_type,
            HeatTransferType.CONVECTIVE)
        self.assertEqual(
            modelica_model[0].elements[0].heat_ports[1].heat_transfer_type,
            HeatTransferType.RADIATIVE)
        self.assertEqual(
            modelica_model[0].elements[1].heat_ports[0].heat_transfer_type,
            HeatTransferType.CONVECTIVE)
        self.assertEqual(
            modelica_model[0].elements[1].heat_ports[1].heat_transfer_type,
            HeatTransferType.RADIATIVE)

        # check number of heat port connections
        self.assertEqual(
            2, len(modelica_model[0].connections_heat_ports_conv))
        self.assertEqual(
            2, len(modelica_model[0].connections_heat_ports_rad))
