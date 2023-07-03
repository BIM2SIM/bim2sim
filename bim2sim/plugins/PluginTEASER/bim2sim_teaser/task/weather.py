from bim2sim.tasks.common import Weather


class WeatherTEASER(Weather):
    """Specifies the base Weather class with  TEASER plugin specific
    settings."""

    def get_file_ending(self) -> str:
        return 'mos'
