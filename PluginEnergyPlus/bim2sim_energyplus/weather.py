from pathlib import Path
from shutil import copyfile

from bim2sim.task.base import ITask
from bim2sim.decision import BoolDecision, DecisionBunch
from bim2sim.workflow import Workflow

import bim2sim_energyplus
SOURCE = Path(bim2sim_energyplus.__file__).parent.parent / 'data'


class Weather(ITask):
    """Set weather file for EP."""

    def run(self, workflow: Workflow):
        self.logger.info("Setting weather file.")
        # TODO: make this flexible
        weather_file = 'DEU_NW_Aachen.105010_TMYx.epw'
        copyfile(SOURCE / weather_file,
                 self.paths.resources / weather_file)
