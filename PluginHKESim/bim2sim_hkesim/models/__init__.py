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

    def get_port_name(self, port):
        try:
            index = self.element.ports.index(port)
        except ValueError:
            # unknown port
            index = -1
        if index == 0:
            return "port_a"
        elif index == 1:
            return "port_b"
        else:
            return super().get_port_name(port)  # ToDo: Gas connection


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

    def get_port_name(self, port):
        try:
            index = self.element.ports.index(port)
        except ValueError:
            # unknown port
            index = -1
        if index == 0:
            return "port_a"
        elif index == 1:
            return "port_b"
        else:
            return super().get_port_name(port)

class ConsumerHeatingDistributorModule(HKESim):
    path = "SystemModules.HeatingSystemModules.ConsumerHeatingDistributorModule"
    represents = [ConsumerHeatingDistributorModule]

    def __init__(self, element):
        self.check_temp_tupel = True #TODO: Checking System
        super().__init__(element)

    def get_params(self):
        # self.register_param("Tconsumer", self.check_temp_tupel, "Tconsumer")
        self.params["Tconsumer"] = (self.element.temperature_inlet, self.element.temperature_outlet)
        self.params["Medium_heating"] = 'Modelica.Media.Water.ConstantPropertyLiquidWater'
        self.register_param("useHydraulicSeparator", self.check_temp_tupel, "useHydraulicSeparator")
        self.register_param("hydraulicSeparatorVolume", self.check_temp_tupel, "V")

        index = 0

        for con in self.element.consumers:
            index += 1
            # self.register_param("rated_power", self.check_numeric(min_value=0), "c{}Qflow_nom".format(index))
            # self.register_param("description", "c{}Name".format(index))
            self.params["c{}Qflow_nom".format(index)] = con.rated_power
            self.params["c{}Name".format(index)] = '"{}"'.format(con.description)
            self.params["c{}OpenEnd".format(index)] = False
            self.params["c{}TControl".format(index)] = con.t_controll
            self.params["Tconsumer{}".format(index)] = (con.temperature_inlet, con.temperature_outlet)
            if index > 1:
                self.params["isConsumer{}".format(index)] = True

        if self.element.open_consumer_pairs:
            for pair in self.element.open_consumer_pairs:
                index += 1
                self.params["c{}Qflow_nom".format(index)] = 0
                self.params["c{}Name".format(index)] = '"Open End Consumer{}"'.format(index)
                self.params["c{}OpenEnd".format(index)] = True
                self.params["c{}TControl".format(index)] = False        # TODO: Werte aus dem Modell
                self.params["Tconsumer{}".format(index)] = (80 + 273.15, 60 + 273.15)  # TODO: Werte aus dem Modell
                if index > 1:
                    self.params["isConsumer{}".format(index)] = True

    def get_port_name(self, port):
        try:
            index = self.element.ports.index(port)
        except ValueError:
            # unknown port
            index = -1
        if index == 0:
            return "port_a_consumer"
        elif index == 1:
            return "port_b_consumer"
        elif (index % 2) == 0:
            return "port_a_consumer{}".format(len(self.element.consumers)+index-1)
        elif (index % 2) == 1:
            return "port_b_consumer{}".format(len(self.element.consumers)+index-2)
        else:
            return super().get_port_name(port)


