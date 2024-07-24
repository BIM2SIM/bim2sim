"""Package for Python representations of HKESim models"""

from bim2sim.elements.aggregation import hvac_aggregations
from bim2sim.export import modelica
from bim2sim.elements import hvac_elements as hvac
from bim2sim.elements.mapping.units import ureg
from bim2sim.export.modelica import check_numeric

MEDIUM_WATER = 'Modelica.Media.Water.ConstantPropertyLiquidWater'


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
                            value=MEDIUM_WATER)
        self._set_parameter(name="Q_nom",
                            unit=ureg.watt,
                            required=True,
                            attributes=['rated_power'])
        self._set_parameter(name='T_set',
                            unit=ureg.kelvin,
                            required=True,
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
                            value=MEDIUM_WATER)
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
                            value=MEDIUM_WATER)
        self._set_parameter(name="head_set",
                            unit=ureg.meter,
                            required=True,
                            attributes=['rated_height'],
                            check=check_numeric(min_value=0 * ureg.meter))
        self._set_parameter(name="Vflow_set",
                            unit=ureg.meter ** 3 / ureg.hour,
                            required=True,
                            attributes=['rated_volume_flow'],
                            check=check_numeric(
                                min_value=0 * ureg.meter ** 3 / ureg.hour))
        self._set_parameter(name="P_nom",
                            unit=ureg.watt,
                            required=True,
                            attributes=['rated_power'],
                            check=check_numeric(min_value=0 * ureg.watt))

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
                            value=MEDIUM_WATER)

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
        super().__init__(element)
        self._set_parameter(name='redeclare package Medium_heating',
                            unit=None,
                            required=False,
                            value= MEDIUM_WATER)
        self._set_parameter(name='Tconsumer',
                            unit=ureg.kelvin,
                            required=False,
                            function=lambda flow_temperature,
                                            return_temperature:
                            (flow_temperature[0], return_temperature[0]))
        self._set_parameter(name='useHydraulicSeparator',
                            unit=None,
                            required=False,
                            attributes=['use_hydraulic_separator'])
        self._set_parameter(name='V',
                            unit=ureg.meter ** 3,
                            required=False,
                            attributes=['hydraulic_separator_volume'])
        for index, consumer in enumerate(self.element.consumers):
            self._set_parameter(name=f"c{index + 1}Qflow_nom",
                                unit=ureg.watt,
                                required=False,
                                value=getattr(consumer, 'rated_power'))
            self._set_parameter(name=f"Tconsumer{index + 1}",
                                unit=ureg.kelvin,
                                required=False,
                                value=(getattr(consumer, 'flow_temperature'),
                                       getattr(consumer, 'return_temperature')))
            self._set_parameter(name=f"c{index+1}OpenEnd",
                                unit=None,
                                required=False,
                                value=False)
            self._set_parameter(name=f"c{index + 1}TControl",
                                unit=None,
                                required=False,
                                value=getattr(consumer, 't_control'))
            if index > 0:
                self._set_parameter(name=f"isConsumer{index + 1}",
                                    unit=None,
                                    required=False,
                                    value=True)

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
                            value=MEDIUM_WATER)
        self._set_parameter(name='Qflow_nom',
                            unit=ureg.watt,
                            required=True,
                            check=check_numeric(min_value=0 * ureg.watt),
                            attributes=['rated_power'])
        self._set_parameter(name='Theating',
                            unit=ureg.kelvin,
                            required=True,
                            function=lambda flow_temperature,
                                            return_temperature:
                            (flow_temperature, return_temperature))
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
                            value=MEDIUM_WATER)
        self._set_parameter(name='redeclare package Medium_ev',
                            unit=None,
                            required=False,
                            value=MEDIUM_WATER)
        self._set_parameter(name='Qcon_nom',
                            unit=ureg.watt,
                            required=True,
                            check=check_numeric(min_value=0 * ureg.watt),
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
                            value= MEDIUM_WATER)
        self._set_parameter(name='redeclare package Medium_ev',
                            unit=None,
                            required=False,
                            value=MEDIUM_WATER)
        self._set_parameter(name='EER_nom',
                            unit=ureg.dimensionless,
                            check=check_numeric(
                                min_value=0 * ureg.dimensionless),
                            required=True,
                            attributes=['nominal_COP'])
        self._set_parameter(name='Qev_nom',
                            unit=ureg.watt,
                            required=True,
                            check=check_numeric(min_value=0 * ureg.watt),
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
                            value=MEDIUM_WATER)
        self._set_parameter(name='P_nom',
                            unit=ureg.watt,
                            required=True,
                            check=check_numeric(min_value=0 * ureg.watt),
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
                            value=MEDIUM_WATER)
        self._set_parameter(name='Qflow_nom',
                            unit=ureg.watt,
                            required=True,
                            check=check_numeric(min_value=0 * ureg.watt),
                            attributes=['rated_power'])

    def get_port_name(self, port):
        if port.verbose_flow_direction == 'SINK':
            return 'port_a'
        if port.verbose_flow_direction == 'SOURCE':
            return 'port_b'
        else:
            return super().get_port_name(port)
