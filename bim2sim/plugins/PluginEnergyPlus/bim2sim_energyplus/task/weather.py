from bim2sim.tasks.common import Weather


class WeatherEnergyPlus(Weather):
    """Specifies the base Weather class with EnergyPlus specific settings."""

    def get_file_ending(self) -> str:
        return 'epw'
