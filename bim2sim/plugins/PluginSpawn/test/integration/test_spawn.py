import unittest
from pathlib import Path

from bim2sim import ConsoleDecisionHandler, run_project
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.export.modelica import ModelicaElement
from bim2sim.utilities.test import IntegrationWeatherBase
from bim2sim.utilities.types import IFCDomain
from bim2sim.tasks.hvac.export import Export


class IntegrationBaseSpawn(IntegrationWeatherBase):
    def tearDown(self):
        ModelicaElement.lookup = {}
        super().tearDown()

    def model_domain_path(self) -> str:
        return 'mixed'

    def set_test_weather_file(self):
        """Set the weather file path."""
        self.project.sim_settings.weather_file_path_modelica = (
                self.test_resources_path() /
                'weather_files/DEU_NW_Aachen.105010_TMYx.mos')

        self.project.sim_settings.weather_file_path_ep = (
                self.test_resources_path() /
                'weather_files/DEU_NW_Aachen.105010_TMYx.epw')

    @staticmethod
    def assertIsFile(path):
        if not Path(path).resolve().is_file():
            raise AssertionError("File does not exist: %s" % str(path))

class TestIntegrationAixLib(IntegrationBaseSpawn, unittest.TestCase):

    def test_mixed_ifc_spawn(self):
        """Run project with
        KM_DPM_Vereinshaus_Gruppe62_Heizung_with_pumps.ifc"""
        ifc_names = {IFCDomain.mixed:
                         'b03_heating_with_building_blenderBIM.ifc'}
        project = self.create_project(ifc_names, 'spawn')

        # HVAC/AixLib sim_settings
        # Generate outer heat ports for spawn HVAC sub model
        # Set other simulation settings, otherwise all settings are set to default
        project.sim_settings.aggregations = [
            'PipeStrand',
            'ParallelPump',
            'GeneratorOneFluid'
        ]
        project.sim_settings.group_unidentified = 'name'

        # EnergyPlus sim settings
        project.sim_settings.ep_install_path = Path(
            'C:/EnergyPlusV9-6-0/')
        project.sim_settings.ep_version = "9-6-0"
        answers = (
            'HVAC-PipeFitting',  # Identify PipeFitting
            'HVAC-Distributor',  # Identify Distributor
            'HVAC-ThreeWayValve',  # Identify ThreeWayValve
            2010,  # year of construction of building
            *(True,) * 7,  # 7 real dead ends found
            *(0.001,) * 13,  # volume of junctions
            2000, 175,
            # rated_pressure_difference + rated_volume_flow pump of 1st storey (big)
            4000, 200,
            # rated_pressure_difference + rated_volume_flow for 2nd storey
            *(70, 50,) * 7,  # flow and return temp for 7 space heaters
            0.056,  # nominal_mass_flow_rate 2nd storey TRV (kg/s),
            20,  # dT water of boiler
            70,  # nominal flow temperature of boiler
            0.3,  # minimal part load range of boiler
            8.5,  # nominal power of boiler (in kW)
            50,  # nominal return temperature of boiler
        )
        handler = DebugDecisionHandler(answers)
        for decision, answer in handler.decision_answer_mapping(project.run()):
            decision.value = answer

        self.assertEqual(355, len(self.project.playground.elements))
        # check temperature values of exported boiler
        self.assertEqual(70, project.playground.elements[
                             '01ZLkLzum6a4lxl_1XXMh0'].aggregation.flow_temperature.m)
        self.assertEqual(20, project.playground.elements[
                             '01ZLkLzum6a4lxl_1XXMh0'].aggregation.dT_water.m)
        # check number of thermal zones of building
        self.assertEqual(5, len(
            project.playground.elements[
                '0N8f6_N2WXb4$EWzeVdEh5'].thermal_zones))
        # check file structure
        file_names = [
            "BuildingModel.mo",
            "Hydraulic.mo",
            "package.mo",
            "package.order",
            "TotalModel.mo"
        ]
        for file_name in file_names:
            self.assertIsFile(project.paths.export / Export.get_package_name(
                self.project.name) / file_name)
