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
        self._set_parameter(name='redeclare package Medium',
                            unit=None,
                            required=False,
                            value=
                            'Modelica.Media.Water.ConstantPropertyLiquidWater')
        self._set_parameter(name="Q_nom",
                            unit=ureg.watt,
                            required=False,
                            attributes=['rated_power'])
        self._set_parameter(name='T_set',
                            unit=ureg.kelvin,
                            required=False,
                            attributes=['return_temperature'])

    def get_port_name(self, port):
        if port.verbose_flow_direction == 'SINK':
            return 'port_a'
        if port.verbose_flow_direction == 'SOURCE':
            return 'port_b'
        else:
            return super().get_port_name(port)
        # TODO: Gas and electric connection see
        #  https://github.com/BIM2SIM/bim2sim/issues/80


class Radiator(HKESim):
    path = "HKESim.Heating.Consumers.Consumer"
    represents = [hvac.SpaceHeater, hvac_aggregations.Consumer]

    def __init__(self, element):
        super().__init__(element)
        self._set_parameter(name='redeclare package Medium',
                            unit=None,
                            required=False,
                            value=
                            'Modelica.Media.Water.ConstantPropertyLiquidWater')
        self._set_parameter(name="Q_flow_nominal",
                            unit=ureg.watt,
                            required=False,
                            attributes=['rated_power'])
        self._set_parameter(name="Tout_max",
                            unit=ureg.kelvin,
                            required=False,
                            attributes=['return_temperature'])

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

    def __init__(self, element):
        super().__init__(element)
        self._set_parameter(name='redeclare package Medium',
                            unit=None,
                            required=False,
                            value=
                            'Modelica.Media.Water.ConstantPropertyLiquidWater')
        self._set_parameter(name="head_set",
                            unit=ureg.meter,
                            required=False,
                            attributes=['rated_height'])
        self._set_parameter(name="Vflow_set",
                            unit=ureg.meter ** 3 / ureg.hour,
                            required=False,
                            attributes=['rated_volume_flow'])
        self._set_parameter(name="P_nom",
                            unit=ureg.watt,
                            required=False,
                            attributes=['rated_power'])

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

    def __init__(self, element):
        super().__init__(element)
        self._set_parameter(name='redeclare package Medium',
                            unit=None,
                            required=False,
                            value=
                            'Modelica.Media.Water.ConstantPropertyLiquidWater')

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
    represents = [hvac_aggregations.ConsumerHeatingDistributorModule]

    def __init__(self, element):
        self.check_volume = self.check_numeric(min_value=0 * ureg.meter ** 3)
        super().__init__(element)
        self._set_parameter(name='redeclare package Medium_heating',
                            unit=None,
                            required=False,
                            value=
                            'Modelica.Media.Water.ConstantPropertyLiquidWater')
        self._set_parameter(name='Tconsumer',
                            unit=ureg.kelvin,
                            required=False,
                            function=lambda T_flow, T_return:
                            (T_flow, T_return),
                            function_inputs={'T_flow': 'flow_temperature',
                                             'T_return': 'return_temperature'})
        self._set_parameter(name='useHydraulicSeparator',
                            unit=None,
                            required=False,
                            attributes=['use_hydraulic_separator'])
        self._set_parameter(name='V',
                            unit=ureg.meter ** 3,
                            required=False,
                            attributes=['hydraulic_separator_volume'])
        # TODO: This does not work yet
        for index, consumer in enumerate(self.element.consumers, 1):
            self._set_parameter(name=f"c{index}Name",
                                unit=None,
                                required=False,
                                attributes=['description'])

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
        self._set_parameter(name='redeclare package Medium_heating',
                            unit=None,
                            required=False,
                            value=
                            'Modelica.Media.Water.ConstantPropertyLiquidWater')
        self._set_parameter(name='Qflow_nom',
                            unit=ureg.watt,
                            required=False,
                            attributes=['rated_power'])
        self._set_parameter(name='Theating',
                            unit=ureg.kelvin,
                            required=False,
                            function=lambda T_flow, T_return:
                            (T_flow, T_return),
                            function_inputs={'T_flow': 'return_temperature',
                                             'T_return': 'flow_temperature'})
        self._set_parameter(name='boilerPump',
                            unit=None,
                            required=False,
                            attributes=['has_pump'])
        self._set_parameter(name='returnTempControl',
                            unit=None,
                            required=False,
                            attributes=['has_bypass'])

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
        self._set_parameter(name='redeclare package Medium_con',
                            unit=None,
                            required=False,
                            value=
                            'Modelica.Media.Water.ConstantPropertyLiquidWater')
        self._set_parameter(name='redeclare package Medium_ev',
                            unit=None,
                            required=False,
                            value=
                            'Modelica.Media.Water.ConstantPropertyLiquidWater')
        self._set_parameter(name='Qcon_nom',
                            unit=ureg.watt,
                            required=False,
                            attributes=['rated_power'])

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
        self._set_parameter(name='redeclare package Medium_con',
                            unit=None,
                            required=False,
                            value=
                            'Modelica.Media.Water.ConstantPropertyLiquidWater')
        self._set_parameter(name='redeclare package Medium_ev',
                            unit=None,
                            required=False,
                            value=
                            'Modelica.Media.Water.ConstantPropertyLiquidWater')
        self._set_parameter(name='EER_nom',
                            unit=ureg.dimensionless,
                            required=False,
                            attributes=['nominal_COP'])
        self._set_parameter(name='Qev_nom',
                            unit=ureg.watt,
                            required=False,
                            attributes=['rated_power'])

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

    def __init__(self, element):
        super().__init__(element)
        self._set_parameter(name='redeclare package Medium',
                            unit=None,
                            required=False,
                            value=
                            'Modelica.Media.Water.ConstantPropertyLiquidWater')
        self._set_parameter(name='P_nom',
                            unit=ureg.watt,
                            required=False,
                            attributes=['rated_power'])

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
        self._set_parameter(name='redeclare package Medium',
                            unit=None,
                            required=False,
                            value=
                            'Modelica.Media.Water.ConstantPropertyLiquidWater')
        self._set_parameter(name='Qflow_nom',
                            unit=ureg.watt,
                            required=False,
                            attributes=['rated_power'])

    def get_port_name(self, port):
        if port.verbose_flow_direction == 'SINK':
            return 'port_a'
        if port.verbose_flow_direction == 'SOURCE':
            return 'port_b'
        else:
            return super().get_port_name(port)
