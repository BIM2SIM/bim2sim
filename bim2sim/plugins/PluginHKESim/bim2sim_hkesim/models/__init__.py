"""Package for Python representations of HKESim models"""

import bim2sim.elements.aggregation as aggregation
from bim2sim.elements.aggregation import hvac_aggregations
from bim2sim.export import modelica
from bim2sim.elements import hvac_elements as hvac
from bim2sim.elements.mapping.units import ureg


class HKESim(modelica.Instance):
    library = "HKESim"


class Boiler(HKESim):
    path = "HKESim.Heating.Boilers.Boiler"
    represents = [hvac.Boiler]

    def __init__(self, element):
        super().__init__(element)

    def request_params(self):
        self.export_params["redeclare package Medium"] \
            = 'Modelica.Media.Water.ConstantPropertyLiquidWater'
        self.request_param("rated_power",
                           self.check_numeric(min_value=0 * ureg.kilowatt),
                           "Q_nom")
        self.request_param('return_temperature',
                           self.check_numeric(min_value=0 * ureg.celsius),
                           'T_set')

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
        else:
            return super().get_port_name(port)
        # TODO: Gas and electric connection


class Radiator(HKESim):
    path = "HKESim.Heating.Consumers.Consumer"
    represents = [hvac.SpaceHeater, hvac_aggregations.Consumer]

    def __init__(self, element):
        super().__init__(element)

    def request_params(self):
        self.export_params["redeclare package Medium"] \
            = 'Modelica.Media.Water.ConstantPropertyLiquidWater'
        self.request_param('rated_power',
                           self.check_numeric(min_value=0 * ureg.kilowatt),
                           'Q_flow_nominal')
        self.request_param('return_temperature',
                           self.check_numeric(min_value=0 * ureg.celsius),
                           'Tout_max')

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
        else:
            return super().get_port_name(port)


class Pump(HKESim):
    path = "HKESim.Heating.Pumps.Pump"
    represents = [hvac.Pump]

    def request_params(self):
        self.request_param("rated_height",
                           self.check_numeric(min_value=0 * ureg.meter),
                           "head_set")
        self.request_param("rated_volume_flow",
                           self.check_numeric(min_value=0 * ureg['m**3/hour']),
                           "Vflow_set", 'm**3/hour')
        self.request_param("rated_power",
                           self.check_numeric(min_value=0 * ureg.watt),
                           "P_norm")

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
    path = "SystemModules.HeatingSystemModules" \
           ".ConsumerHeatingDistributorModule"
    represents = [hvac_aggregations.ConsumerHeatingDistributorModule]

    def __init__(self, element):
        self.check_volume = self.check_numeric(min_value=0 * ureg.meter ** 3)
        super().__init__(element)

    def request_params(self):
        # TODO: flow_temperature and return_temperature has multiple,
        #  but very close values
        if self.element.flow_temperature or self.element.return_temperature:
            self.export_params["Tconsumer"] = (
                self.element.flow_temperature,
                self.element.return_temperature)
        self.export_params[
            "redeclare package Medium_heating"] = \
            'Modelica.Media.Water.ConstantPropertyLiquidWater'
        # TODO: this does not work, parameter is not set to True in Modelica
        #  model
        self.request_param("use_hydraulic_separator", lambda value: True,
                           "useHydraulicSeparator")

        # TODO: this does not work, parameter V is not known in Modelica model
        self.request_param("hydraulic_separator_volume", self.check_volume,
                           "V")

        for index, con in enumerate(self.element.consumers):
            self.export_params["c{}Qflow_nom".format(index + 1)] = con.rated_power
            self.export_params["c{}Name".format(index + 1)] = '"{}"'.format(
                con.description)
            self.export_params["c{}OpenEnd".format(index + 1)] = False
            self.export_params["c{}TControl".format(index + 1)] = con.t_control
            if con.flow_temperature or con.return_temperature:
                self.export_params["Tconsumer{}".format(index + 1)] = (
                con.flow_temperature, con.return_temperature)
            # TODO: this does not work, the parameter isConsumer1 in not
            #  known in Modelica model
            if len(self.element.consumers) > 1:
                self.export_params["isConsumer{}".format(index + 1)] = True

        # TODO: this should be obsolete: consumers added to open ends from
        #  dead ends;
        # TODO: not clear what is meant by the above comment; what happens
        #  if the there are more than 4 consumers?
        # if self.element.open_consumer_pairs:
        #     for index, pair in enumerate(self.element.open_consumer_pairs):
        #         self.params["c{}Qflow_nom".format(index+1)] = 0
        #         self.params["c{}Name".format(index+1)] = '"Open End
        #         Consumer{}"'.format(index)
        #         self.params["c{}OpenEnd".format(index+1)] = True
        #         self.params["c{}TControl".format(index+1)] = False
        # TODO: Werte aus dem Modell
        #         # self.params["Tconsumer{}".format(index)] = (80 + 273.15,
        #         60 + 273.15)  # TODO: Werte aus dem Modell
        #         if len(self.element.open_consumer_pairs) > 1:
        #         # if index > 1:
        #             self.params["isConsumer{}".format(index+1)] = True

    def get_port_name(self, port):
        try:
            index = self.element.ports.index(port)
        except ValueError:
            # unknown port
            index = -1
        if port.verbose_flow_direction == 'SINK':
            return "port_a_consumer"
        elif port.verbose_flow_direction == 'SOURCE':
            return "port_b_consumer"
        elif (index % 2) == 0:
            return "port_a_consumer{}".format(
                len(self.element.consumers) + index - 1)
        elif (index % 2) == 1:
            return "port_b_consumer{}".format(
                len(self.element.consumers) + index - 2)
        else:
            return super().get_port_name(port)


class BoilerModule(HKESim):
    path = "SystemModules.HeatingSystemModules.BoilerModule"
    represents = [hvac_aggregations.GeneratorOneFluid]

    def __init__(self, element):
        super().__init__(element)

    def request_params(self):
        self.export_params[
            "redeclare package Medium_heating"] = \
            'Modelica.Media.Water.ConstantPropertyLiquidWater'
        self.request_param("rated_power",
                           self.check_numeric(min_value=0 * ureg.kilowatt),
                           "Qflow_nom")
        # TODO: Theating from flow_temperature and return_temperature, see #542
        # self.params["Theating"] = (300.15, 323.15)
        self.export_params["boilerPump"] = self.element.has_pump
        self.export_params["returnTempControl"] = self.element.has_bypass

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
        else:
            return super().get_port_name(port)
