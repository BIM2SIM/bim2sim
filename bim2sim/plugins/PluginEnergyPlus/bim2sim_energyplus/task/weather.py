from bim2sim.task.common import Weather


class WeatherEnergyPlus(Weather):
    """Specifies the base Weather class with  TEASER plugin specific
    settings."""

    def get_file_ending(self) -> str:
        return 'epw'
