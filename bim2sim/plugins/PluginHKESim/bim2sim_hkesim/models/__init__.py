"""Package for Python representations of HKESim models"""

import bim2sim.elements.aggregation as aggregation
from bim2sim.elements.aggregation import hvac_aggregations
from bim2sim.elements.mapping import attribute
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
        self.export_parameters["redeclare package Medium"] \
            = 'Modelica.Media.Water.ConstantPropertyLiquidWater'
        self.request_param(name="rated_power",
                           check=self.check_numeric(
                               min_value=0 * ureg.kilowatt),
                           export_name="Q_nom",
                           export_unit=ureg.watt)
        self.request_param(name='return_temperature',
                           check=self.check_numeric(min_value=0 * ureg.celsius),
                           export_name='T_set',
                           export_unit=ureg.kelvin)

    def get_port_name(self, port):
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
        self.export_parameters["redeclare package Medium"] \
            = 'Modelica.Media.Water.ConstantPropertyLiquidWater'
        self.request_param(name='rated_power',
                           check=self.check_numeric(
                               min_value=0 * ureg.kilowatt),
                           export_name='Q_flow_nominal',
                           export_unit=ureg.watt)
        self.request_param(name='return_temperature',
                           check=self.check_numeric(min_value=0 * ureg.celsius),
                           export_name='Tout_max',
                           export_unit=ureg.kelvin)

    def get_port_name(self, port):
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
        self.export_parameters["redeclare package Medium"] = \
            'Modelica.Media.Water.ConstantPropertyLiquidWater'
        self.request_param(name="rated_height",
                           check=self.check_numeric(min_value=0 * ureg.meter),
                           export_name="head_set",
                           export_unit=ureg.meter)
        self.request_param(name="rated_volume_flow",
                           check=self.check_numeric(
                               min_value=0 * ureg['m**3/hour']),
                           export_name="Vflow_set",
                           export_unit='m**3/hour')
        self.request_param("rated_power",
                           self.check_numeric(min_value=0 * ureg.watt),
                           export_name="P_nom",
                           export_unit=ureg.watt)

    def get_port_name(self, port):
        if port.verbose_flow_direction == 'SINK':
            return 'port_a'
        if port.verbose_flow_direction == 'SOURCE':
            return 'port_b'
        else:
            return super().get_port_name(port)


class ThreeWayValve(HKESim):
    path = "HKESim.Heating.Hydraulics.Valves.ThreeWayValveControlled"
    represents = [hvac.ThreeWayValve]

    def request_params(self):
        self.export_parameters["redeclare package Medium"] = \
            'Modelica.Media.Water.ConstantPropertyLiquidWater'

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
            self.export_parameters["Tconsumer"] = (
                self.element.flow_temperature,
                self.element.return_temperature)
        self.export_parameters[
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
            self.export_parameters[
                "c{}Qflow_nom".format(index + 1)] = con.rated_power
            self.export_parameters["c{}Name".format(index + 1)] = '"{}"'.format(
                con.description)
            self.export_parameters["c{}OpenEnd".format(index + 1)] = False
            self.export_parameters["c{}TControl".format(index + 1)] = con.t_control
            if con.flow_temperature or con.return_temperature:
                self.export_parameters["Tconsumer{}".format(index + 1)] = (
                    con.flow_temperature, con.return_temperature)
            # TODO: this does not work, the parameter isConsumer1 in not
            #  known in Modelica model
            if len(self.element.consumers) > 1:
                self.export_parameters["isConsumer{}".format(index + 1)] = True

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
        self.export_parameters[
            "redeclare package Medium_heating"] = \
            'Modelica.Media.Water.ConstantPropertyLiquidWater'
        self.request_param(name="rated_power",
                           check=self.check_numeric(
                               min_value=0 * ureg.kilowatt),
                           export_name="Qflow_nom",
                           export_unit=ureg.watt)
        # TODO: Theating from flow_temperature and return_temperature, see #542
        # self.request_param(
        #     name="Theating",
        #     check=self.check_none(),
        #     export=False,
        #     needed_params=["flow_temperature", 'return_temperature'],
        #     function=lambda: [self.element.flow_temperature,
        #                       self.element.return_temperature]
        # )
        # self.export_params["Theating"] = [self.element.flow_temperature,
        #                                   self.element.return_temperature]
        # self.params["Theating"] = (300.15, 323.15)
        self.export_parameters["boilerPump"] = self.element.has_pump
        self.export_parameters["returnTempControl"] = self.element.has_bypass

    def get_port_name(self, port):
        if port.verbose_flow_direction == 'SINK':
            return 'port_a'
        if port.verbose_flow_direction == 'SOURCE':
            return 'port_b'
        else:
            return super().get_port_name(port)


class HeatPump(HKESim):
    path = 'HKESim.Heating.HeatPumps.HeatPump'
    represents = [hvac.HeatPump]

    def __init__(self, element):
        super().__init__(element)

    def request_params(self):
        self.export_parameters[
            'redeclare package Medium_con'] = \
            'Modelica.Media.Water.ConstantPropertyLiquidWater'
        self.export_parameters[
            'redeclare package Medium_ev'] = \
            'Modelica.Media.Water.ConstantPropertyLiquidWater'
        self.request_param(name='rated_power',
                           check=self.check_numeric(0 * ureg.kilowatt),
                           export_name='Qcon_nom',
                           export_unit=ureg.watt)

    def get_port_name(self, port):
        # TODO: heat pump might have 4 ports (if source is modeled in BIM)
        if port.verbose_flow_direction == 'SINK':
            return 'port_a_con'
        if port.verbose_flow_direction == 'SOURCE':
            return 'port_b_con'
        else:
            return super().get_port_name(port)


class Chiller(HKESim):
    path = 'HKESim.Heating.Chillers.CompressionChiller'
    represents = [hvac.Chiller]

    def __init__(self, element):
        super().__init__(element)

    def request_params(self):
        self.export_parameters[
            'redeclare package Medium_con'] = \
            'Modelica.Media.Water.ConstantPropertyLiquidWater'
        self.export_parameters[
            'redeclare package Medium_ev'] = \
            'Modelica.Media.Water.ConstantPropertyLiquidWater'
        self.request_param(name='nominal_COP',
                           check=self.check_numeric(0 * ureg.dimensionless),
                           export_name='EER_nom')
        self.request_param(name='rated_power',
                           check=self.check_numeric(0 * ureg.kilowatt),
                           export_name='Qev_nom',
                           export_unit=ureg.watt)

    def get_port_name(self, port):
        # TODO: chiller might have 4 ports (if source is modeled in BIM)
        if port.verbose_flow_direction == 'SINK':
            return 'port_a_con'
        if port.verbose_flow_direction == 'SOURCE':
            return 'port_b_con'
        else:
            return super().get_port_name(port)


class CHP(HKESim):
    path = "HKESim.Heating.CHPs.CHP"
    represents = [hvac.CHP]

    def request_params(self):
        self.export_parameters['redeclare package Medium'] = \
            'Modelica.Media.Water.ConstantPropertyLiquidWater'
        self.request_param(name='rated_power',
                           check=self.check_numeric(0 * ureg.kilowatt),
                           export_name='P_nom',
                           export_unit=ureg.watt)

    def get_port_name(self, port):
        if port.verbose_flow_direction == 'SINK':
            return 'port_a'
        if port.verbose_flow_direction == 'SOURCE':
            return 'port_b'
        else:
            return super().get_port_name(port)


class CoolingTower(HKESim):
    path = 'HKESim.Heating.CoolingTowers.CoolingTower'
    represents = [hvac.CoolingTower]

    def __init__(self, element):
        super().__init__(element)

    def request_params(self):
        self.export_parameters['redeclare package Medium'] = \
            'Modelica.Media.Water.ConstantPropertyLiquidWater'
        self.request_param(name='rated_power',
                           check=self.check_numeric(0 * ureg.kilowatt),
                           export_name='Qflow_nom',
                           export_unit=ureg.watt)

    def get_port_name(self, port):
        if port.verbose_flow_direction == 'SINK':
            return 'port_a'
        if port.verbose_flow_direction == 'SOURCE':
            return 'port_b'
        else:
            return super().get_port_name(port)
