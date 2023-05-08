from pathlib import Path

from bim2sim.decision import ListDecision, DecisionBunch
from bim2sim.task.base import ITask
from bim2sim.simulation_type import SimType


class Weather(ITask):
    """Task to get the weatherfile for later simulation"""
    touches = ('weather_file',)

    def __init__(self, playground):
        super().__init__(playground)
        # TODO: use location of building or decision to get location
        self.location = "Aachen"
        self.weather_file = None

    def run(self):
        self.logger.info("Setting weather file.")
        weatherfiles_path = self.paths.assets / 'weatherfiles'
        self.weather_file = yield from self.get_weatherfile_by_tool(
            weatherfiles_path)
        return self.weather_file,

    def get_weatherfile_by_tool(self, weatherfiles_path) -> Path:
        """Returns the weatherfile"""
        file_ending = self.get_file_ending()
        search_str = "*" + self.location + "*" + '.' + file_ending
        possible_files = list(weatherfiles_path.glob(search_str))
        if not possible_files:
            self.logger.warning(f"No fitting weatherfile found for location "
                                f"{self.location}, using default file for "
                                f"Aachen.")
            filename = 'DEU_NW_Aachen.105010_TMYx' + file_ending
            file = weatherfiles_path / filename
        elif len(possible_files) == 1:
            file = possible_files[0]
        else:
            weather_decision = ListDecision(
                "Multiple weatherfiles found for location %s."
                " Please select one." % self.location,
                choices=possible_files,
                global_key='weatherfile_dec'
            )
            yield DecisionBunch([weather_decision])
            file = weather_decision.value
        return file

    def get_file_ending(self) -> str:
        """Returns the needed file ending for the specific tool."""
        raise NotImplementedError
