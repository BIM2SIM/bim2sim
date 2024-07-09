import csv
from pathlib import Path
import ifcopenshell

from bim2sim.kernel.units import ureg
from bim2sim.task.base import ITask



class InterfaceToPluginTeaser(ITask):
    """Creates a heating circle out of an ifc model"""


    def __init__(self):
        super().__init__()



    def run(self, workflow, ifc, instances):
        self.logger.info("Creating heating circle")



    @staticmethod
    def ureg_to_str(value, unit, n_digits=3, ):
        """Transform pint unit to human readable value with given unit."""
        if value is not None and not isinstance(value, float):
            return round(value.to(unit).m, n_digits)
        elif value is None:
            return "-"
        else:
            return value
