"""Package for Python representations of HKESim models"""

import bim2sim.elements.aggregation as aggregation
from bim2sim.export import modelica
from bim2sim.elements import hvac_elements as hvac
from bim2sim.kernel.units import ureg


class HKESim(modelica.Instance):
    library = "HKESim"


class Boiler(HKESim):
    path = "HKESim.Heating.Boilers.Boiler"
    represents = [hvac.Boiler]

    def __init__(self, element):
        self.check_power = self.check_numeric(min_value=0 * ureg.kilowatt) #TODO: Checking System
        super().__init__(element)

    def request_params(self):
        self.request_param("rated_power", self.check_power, "nominal_power")

    def get_port_name(self, port):
        try:
            index = self.element.ports.index(port)
        except ValueError:
            # unknown port
            index = -1
        if port.verbose_flow_direction == 'SINK':
            return 'port_a'
        if port.verbose_flow_direction == 'SOURCE':
            return 'port_b'
        # if index == 0:
        #     return "port_a"
        # elif index == 1:
        #     return "port_b"
        else:
            return super().get_port_name(port)  # ToDo: Gas connection


class Radiator(HKESim):
    path = "HKESim.Heating.Consumers.Radiators.Radiator"
    represents = [hvac.SpaceHeater, aggregation.Consumer]

    def request_params(self):
        self.request_param("rated_power", self.check_numeric(min_value=0 * ureg.kilowatt), "Q_flow_nominal")
        # self.params["T_nominal"] = (80, 60, 20)


class Pump(HKESim):
    path = "HKESim.Heating.Pumps.Pump"
    represents = [hvac.Pump]

    def request_params(self):
        self.request_param("rated_height", self.check_numeric(min_value=0 * ureg.meter), "head_set")
        self.request_param("rated_volume_flow", self.check_numeric(min_value=0 * ureg['m**3/hour']), "Vflow_set", 'm**3/hour')
        self.request_param("rated_power", self.check_numeric(min_value=0 * ureg.watt), "P_norm")

    def get_port_name(self, port):
        try:
            index = self.element.ports.index(port)
        except ValueError:
            # unknown port
            index = -1
        if port.verbose_flow_direction == 'SINK':
            return 'port_a'
        if port.verbose_flow_direction == 'SOURCE':
            return 'port_b'
        # if index == 0:
        #     return "port_a"
        # elif index == 1:
        #     return "port_b"
        else:
            return super().get_port_name(port)


class ThreeWayValve(HKESim):
    path = "HKESim.Heating.Hydraulics.Valves.ThreeWayValveControlled"
    represents = [hvac.ThreeWayValve]

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
        elif index == 2:
            return "port_c"
        else:
            return super().get_port_name(port)


class ConsumerHeatingDistributorModule(HKESim):
    path = "SystemModules.HeatingSystemModules.ConsumerHeatingDistributorModule"
    represents = [aggregation.ConsumerHeatingDistributorModule]

    def __init__(self, element):
        self.check_volume = self.check_numeric(min_value=0 * ureg.meter ** 3)
        super().__init__(element)

    def request_params(self):
        if self.element.flow_temperature or self.element.return_temperature:
            self.params["Tconsumer"] = (self.element.flow_temperature, self.element.return_temperature)
        self.params["Medium_heating"] = 'Modelica.Media.Water.ConstantPropertyLiquidWater'
        self.request_param("use_hydraulic_separator", lambda value: True, "useHydraulicSeparator")
        self.request_param("hydraulic_separator_volume", self.check_volume, "V")

        index = 0

        for con in self.element.consumers:
            index += 1
            # self.register_param("rated_power", self.check_numeric(min_value=0 * ureg.kilowatt), "c{}Qflow_nom".format(index))
            # self.register_param("description", "c{}Name".format(index))
            self.params["c{}Qflow_nom".format(index)] = con.rated_power
            self.params["c{}Name".format(index)] = '"{}"'.format(con.description)
            self.params["c{}OpenEnd".format(index)] = False
            self.params["c{}TControl".format(index)] = con.t_control
            if con.flow_temperature or con.return_temperature:
                self.params["Tconsumer{}".format(index)] = (con.flow_temperature, con.return_temperature)
            if index > 1:
                self.params["isConsumer{}".format(index)] = True

        # TODO: this should be obsolete: consumers added to open ends from
        #  dead ends
        if self.element.open_consumer_pairs:
            for pair in self.element.open_consumer_pairs:
                index += 1
                self.params["c{}Qflow_nom".format(index)] = 0
                self.params["c{}Name".format(index)] = '"Open End Consumer{}"'.format(index)
                self.params["c{}OpenEnd".format(index)] = True
                self.params["c{}TControl".format(index)] = False        # TODO: Werte aus dem Modell
                # self.params["Tconsumer{}".format(index)] = (80 + 273.15, 60 + 273.15)  # TODO: Werte aus dem Modell
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


