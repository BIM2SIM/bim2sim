from bim2sim.task.common import Weather


class WeatherEnergyPlus(Weather):
    """Specifies the base Weather class with EnergyPlus specific settings."""

    def __init__(self):
        super().__init__()

    def get_file_ending(self) -> str:
        return 'epw'
