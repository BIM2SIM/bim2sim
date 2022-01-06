from shutil import copyfile
from pathlib import Path

from bim2sim.task.base import ITask
from bim2sim.workflow import Workflow
from bim2sim.decision import ListDecision, DecisionBunch


class Weather(ITask):
    """Task to get the weatherfile for later simulation"""
    touches = ('weather_file',)

    def __init__(self):
        super().__init__()
        self.file_ending = 'mos'
        # self.file_ending = file_ending
        # TODO: use location of building or decision to get location
        self.location = "Aachen"
        self.weather_file = None

    def run(self, workflow: Workflow):
        self.logger.info("Setting weather file.")
        weatherfiles_path = self.paths.assets / 'weatherfiles'
        self.weather_file = yield from self.get_weatherfile_by_tool(
            weatherfiles_path)
        return self.weather_file,
        # weather_file = 'DEU_NW_Aachen.105010_TMYx.epw'
        # copyfile(SOURCE / weather_file,
        #          self.paths.resources / weather_file)

    def get_weatherfile_by_tool(self, weatherfiles_path) -> Path:
        """Returns the weatherfile"""
        search_str = "*" + self.location + "*" + '.' + self.file_ending
        possible_files = list(weatherfiles_path.glob(search_str))
        if not possible_files:
            self.logger.warning(f"No fitting weatherfile found for location "
                                f"{self.location}, using default file for "
                                f"Aachen.")
            filename = 'DEU_NW_Aachen.105010_TMYx' + '.' + self.file_ending
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
        # file_path = self.weatherfiles_path /

    # def get_file_ending(self) -> str:
    #     """Returns the needed file ending for the specific tool."""
    #     raise NotImplementedError

    # def utilize_file(self):
    #     """Further usage of the tool e.g. copy to tool specific folder or save
    #     in specific variable. Needs to be implemented by every tool."""
    #     raise NotImplementedError
