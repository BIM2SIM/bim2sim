import tempfile
import unittest
from pathlib import Path

import bim2sim.tasks.common.create_elements
from bim2sim.kernel.decision.decisionhandler import DebugDecisionHandler
from bim2sim.plugins import Plugin
from bim2sim.project import Project
from bim2sim.sim_settings import TEASERSimSettings, EnergyPlusSimSettings
from bim2sim.utilities.types import IFCDomain
from bim2sim.tasks.common import Weather


class PluginWeatherDummyTEASER(Plugin):
    name = 'TEASER'
    sim_settings = TEASERSimSettings
    default_tasks = [
        bim2sim.tasks.common.load_ifc.LoadIFC,
        bim2sim.tasks.common.create_elements.CreateElementsOnIfcTypes,
        Weather
    ]


class PluginWeatherDummyEP(Plugin):
    name = 'EnergyPlus'
    sim_settings = EnergyPlusSimSettings
    default_tasks = [
        bim2sim.tasks.common.load_ifc.LoadIFC,
        bim2sim.tasks.common.create_elements.CreateElementsOnIfcTypes,
        Weather
    ]


test_rsrc_path = Path(__file__).parent.parent.parent.parent / 'resources'


class TestWeather(unittest.TestCase):
    """Tests the weather task for loading weather files for simulations."""

    def tearDown(self):
        self.project.finalize(True)
        self.test_dir.cleanup()

    def test_weather_modelica(self):
        """Test if the weather file is correctly set for modelica."""
        self.test_dir = tempfile.TemporaryDirectory()
        ifc_paths = {
            IFCDomain.arch: test_rsrc_path / 'arch/ifc/AC20-FZK-Haus.ifc'}
        self.project = Project.create(self.test_dir.name, ifc_paths,
                                      plugin=PluginWeatherDummyTEASER)
        self.project.sim_settings.weather_file_path = (
                test_rsrc_path / 'weather_files/DEU_NW_Aachen.105010_TMYx.mos')
        handler = DebugDecisionHandler([])
        handler.handle(self.project.run(cleanup=False))
        try:
            weather_file = self.project.playground.state['weather_file']
        except Exception:
            raise ValueError(f"No weather file set through Weather task. An"
                             f"error occurred.")
        self.assertEquals(weather_file,
                          self.project.sim_settings.weather_file_path)

    def test_weather_energyplus(self):
        """Test if the weather file is correctly set for energyplus."""
        self.test_dir = tempfile.TemporaryDirectory()
        ifc_paths = {
            IFCDomain.arch: test_rsrc_path / 'arch/ifc/AC20-FZK-Haus.ifc'}
        self.project = Project.create(self.test_dir.name, ifc_paths,
                                      plugin=PluginWeatherDummyEP)
        self.project.sim_settings.weather_file_path = (
                test_rsrc_path / 'weather_files/DEU_NW_Aachen.105010_TMYx.epw')
        handler = DebugDecisionHandler([])
        handler.handle(self.project.run(cleanup=False))
        try:
            weather_file = self.project.playground.state['weather_file']
        except Exception:
            raise ValueError(f"No weather file set through Weather task. An"
                             f"error occurred.")
        self.assertEquals(weather_file,
                          self.project.sim_settings.weather_file_path)
