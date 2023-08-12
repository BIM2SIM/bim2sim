from bim2sim.tasks.common import Weather


class WeatherEnergyPlus(Weather):
    """Specifies the base Weather class with EnergyPlus specific settings."""

    def run(self):
        self.logger.info("Setting weather file.")
        if self.playground.sim_settings.overwrite_weather:
            self.weather_file = self.playground.sim_settings.overwrite_weather
        else:
            self.logger.info("Setting weather file.")
            weatherfiles_path = self.paths.assets / 'weatherfiles'
            self.weather_file = yield from self.get_weatherfile_by_tool(
                weatherfiles_path)
        return self.weather_file,

    def get_file_ending(self) -> str:
        return 'epw'
