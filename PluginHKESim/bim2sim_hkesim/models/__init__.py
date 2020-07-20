"""Package for Python representations of HKESim models"""

from bim2sim.export import modelica
from bim2sim.kernel import elements
from bim2sim.kernel.aggregation import PipeStrand, Consumer, ConsumerHeatingDistributorModule


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
    represents = [elements.SpaceHeater, Consumer]

    def get_params(self):
        self.register_param("rated_power", self.check_numeric(min_value=0), "Q_flow_nominal")
        self.params["T_nominal"] = (80, 60, 20)


class Pump(HKESim):
    path = "HKESim.Heating.Pumps.Pump"
    represents = [elements.Pump]

    def get_params(self):
        pass


class ConsumerHeatingDistributorModule(HKESim):
    path = "SystemModules.HeatingSystemModules.ConsumerHeatingDistributorModule"
    represents = [ConsumerHeatingDistributorModule]


    def get_params(self):
        self.params["Tconsumer"] = (80, 60)  # TODO: Werte aus dem Modell
        self.params["Medium"] = 'Modelica.Media.Water.ConstantPropertyLiquidWater'
        self.params["useHydraulicSeperator"] = True  # TODO: Werte aus dem Modell
        self.params["V"] = 5  # TODO: Werte aus dem Modell

        index = 0

        for consumer in self.element._consumer_cycles:
            index += 1
            for con in consumer:  # ToDo: darf nur ein Consumer sein
                # self.register_param("rated_power", self.check_numeric(min_value=0), "c{}Qflow_nom".format(index))
                # self.register_param("description", "c{}Name".format(index))
                self.params["c{}Qflow_nom".format(index)] = con.rated_power
                self.params["c{}Name".format(index)] = con.description
            self.params["c{}OpenEnd".format(index)] = False
            self.params["c{}TControl".format(index)] = False
            self.params["Tconsumer{}".format(index)] = (80, 60)  # TODO: Werte aus dem Modell
            if index > 1:
                self.params["isConsumer{}".format(index)] = True


