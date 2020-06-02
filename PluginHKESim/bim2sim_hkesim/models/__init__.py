"""Package for Python representations of HKESim models"""

from bim2sim.export import modelica
from bim2sim.kernel import elements
from bim2sim.kernel.aggregation import PipeStrand


class HKESim(modelica.Instance):
    library = "HKESim"


class Boiler(HKESim):
    path = "HKESim.Heating.Boilers.Boiler"
    represents = [elements.Boiler]

    def __init__(self, element):
        self.check_power = self.check_numeric(min_value=0) #TODO: Checking System
        super().__init__(element)

    def get_params(self):
        self.register_param("rated_power", self.check_power, "nominal_power")


class Radiator(HKESim):
    path = "HKESim.Heating.Consumers.Radiators.Radiator"
    represents = [elements.SpaceHeater, elements.Distributor]

    def get_params(self):
        self.register_param("nominal_power", self.check_numeric(min_value=0), "Q_flow_nominal")
        self.params["T_nominal"] = (80, 60, 20)


class Pump(HKESim):
    path = "HKESim.Heating.Pumps.Pump"
    represents = [elements.Pump]

    def get_params(self):
        pass
