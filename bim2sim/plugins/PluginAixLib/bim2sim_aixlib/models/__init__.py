"""Package for Python representations of HKESim models"""
import bim2sim.elements.aggregation as aggregation
from bim2sim.export import modelica
from bim2sim.elements import hvac_elements as hvac
from bim2sim.elements.mapping.units import ureg


class AixLib(modelica.Instance):
    library = "AixLib"


class Boiler(AixLib):
    path = "AixLib.Fluid.BoilerCHP.BoilerGeneric"
    represents = [hvac.Boiler]

    def __init__(self, element):
        super().__init__(element)

    def request_params(self):

        self.params["redeclare package Medium"] = 'AixLib.Media.Water'
        self.request_param("dT_water",
                           self.check_numeric(min_value=0 * ureg.kelvin),
                           "dTWaterNom")
        self.request_param("return_temperature",
                           self.check_numeric(min_value=0 * ureg.celsius),
                           "TRetNom")
        self.request_param("rated_power",
                           self.check_numeric(min_value=0 * ureg.kilowatt),
                           "QNom")
        self.request_param("min_PLR",
                           self.check_numeric(min_value=0 * ureg.dimensionless),
                           "PLRMin")

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
            return super().get_port_name(port)  # ToDo: Gas connection


class Radiator(AixLib):
    path = "AixLib.Fluid.HeatExchangers.Radiators.RadiatorEN442_2"
    represents = [hvac.SpaceHeater]

    def request_params(self):
        self.request_param("rated_power",
                           self.check_numeric(min_value=0 * ureg.kilowatt),
                           "Q_flow_nominal")
        # self.params["T_nominal"] = (80, 60, 20)


class Pump(AixLib):
    path = "AixLib.Fluid.Movers.SpeedControlled_y"
    represents = [hvac.Pump]

    def request_params(self):
        self.params['redeclare package Medium'] = 'AixLib.Media.Water'
        self.request_param(
            "rated_mass_flow",
            self.check_numeric(min_value=0 * ureg['kg/second']))
        self.request_param(
            "rated_pressure_difference",
            self.check_numeric(min_value=0 * ureg['newton/m**2']))
        # generic pump operation curve
        # todo renders as "V_flow" only in Modelica
        self.params["per.pressure"] =\
            f"V_flow={{0," \
            f" {self.element.rated_mass_flow}/1000," \
            f" {self.element.rated_mass_flow} /1000/0.7}}," \
            f" dp={{ {self.element.rated_pressure_difference} / 0.7," \
            f" {self.element.rated_pressure_difference}," \
            f"0}}"

        # ToDo remove decisions from tests if not asking this anymore
        # self.request_param("rated_height",
        #                    self.check_numeric(min_value=0 * ureg.meter),
        #                    "head_set")
        # self.request_param("rated_volume_flow",
        #                    self.check_numeric(min_value=0 * ureg['m**3/hour']),
        #                    "Vflow_set", 'm**3/hour')
        # self.request_param("rated_power",
        #                    self.check_numeric(min_value=0 * ureg.watt),
        #                    "P_norm")

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


class Consumer(AixLib):
    path = "AixLib.Systems.HydraulicModules.SimpleConsumer"
    represents = [aggregation.Consumer]

    def __init__(self, element):
        self.check_volume = self.check_numeric(min_value=0 * ureg.meter ** 3)
        super().__init__(element)

    def request_params(self):
        self.params['redeclare package Medium'] = 'AixLib.Media.Water'
        self.params["functionality"] = '\"Q_flow_fixed\"'
        if self.params["functionality"] == '\"Q_flow_fixed\"':
            self.params["Q_flow_fixed"] = self.element.rated_power
        self.params["demand_type"] = "1"

        # self.request_param("demand_type",
        #                    self.check_none(),
        #                    "demandType")

        self.params["hasFeedback"] = self.element.t_control
        if self.element.t_control:
            self.params["TInSetValue"] = self.element.flow_temperature
            self.params["TInSetSou"] = "AixLib.Systems.ModularEnergySystems." \
                                   "Modules.ModularConsumer.Types.InputType." \
                                   "Constant"

        self.params["hasPump"] = self.element.has_pump
        if self.element.has_pump:
            self.params["TOutSetValue"] = self.element.return_temperature
            self.params["TOutSetSou"] = "AixLib.Systems.ModularEnergySystems." \
                                   "Modules.ModularConsumer.Types.InputType." \
                                   "Constant"
        # self.params["dT_nom"] = self.element.dT_water
        # self.params["capacity"] = self.element.heat_capacity
        # self.request_param("rated_power",
        #                    self.check_numeric(min_value=0 * ureg.kilowatt),
        #                    "Q_flow_nom")
        # self.request_param("dT_water",
        #                    self.check_numeric(min_value=0 * ureg.kelvin),
        #                    "dT_nom")
        # self.request_param("heat_capacity",
        #                    self.check_numeric(
        #                        min_value=0 * ureg.joule / ureg.kelvin),
        #                    "capacity")

    def get_port_name(self, port):
        try:
            index = self.element.ports.index(port)
        except ValueError:
            # unknown port
            index = -1
        if index == 1:
            return "port_a"
        elif index == 0:
            return "port_b"
        else:
            return super().get_port_name(port)


class ConsumerHeatingDistributorModule(AixLib):
    path = "AixLib.Systems.ModularEnergySystems.Modules.ModularConsumer." \
           "ConsumerDistributorModule"
    represents = [aggregation.ConsumerHeatingDistributorModule]

    def __init__(self, element):
        self.check_volume = self.check_numeric(min_value=0 * ureg.meter ** 3)
        super().__init__(element)

    def request_params(self):
        n_consumers = len(self.element.whitelist_elements)
        # Parameters
        self.params["T_start"] = self.element.return_temperature
        self.params['redeclare package Medium'] = 'AixLib.Media.Water'
        # Consumer Design
        self.params['n_consumers'] = n_consumers
        self.params["functionality"] = "\"Q_flow_fixed\""
        self.request_param("demand_type",
                           self.check_none(),
                           "demandType")
        self.request_param("heat_capacity",
                           self.check_numeric(
                               min_value=0 * ureg.joule / ureg.kelvin),
                           "capacity")

        # Nominal Conditions
        # todo q_flow_fixed is just dummy value as Modelica model
        #  needs it for any reason, check on Modelica side
        self.request_param("rated_power",
                           self.check_numeric(min_value=0 * ureg.kilowatt),
                           "Q_flow_fixed")
        self.params["Q_flow_nom"] = self.element.rated_power
        self.request_param("dT_water",
                           self.check_numeric(min_value=0 * ureg.kelvin),
                           "dT_nom")

        # Flow temperature control (Mixture Valve)
        self.params["hasFeedback"] = self.element.t_control
        self.params["TInSetSou"] = "AixLib.Systems.ModularEnergySystems." \
                                   "Modules.ModularConsumer.Types.InputType." \
                                   "Constant"
        self.params["TInSet"] = self.element.flow_temperature
        self.params["k_ControlConsumerValve"] = [0.1] * n_consumers
        self.params["Ti_ControlConsumerValve"] = [10] * n_consumers
        self.params["dp_Valve"] = [1000] * n_consumers

        # Return temperature control (Pump)
        self.params["hasPump"] = self.element.has_pump
        self.params["TOutSet"] = self.element.return_temperature
        self.params["TOutSetSou"] = "AixLib.Systems.ModularEnergySystems." \
                                   "Modules.ModularConsumer.Types.InputType." \
                                   "Constant"
        self.params["k_ControlConsumerPump"] = [0.1] * n_consumers
        self.params["Ti_ControlConsumerPump"] = [10] * n_consumers
        self.params["dp_nominalConPump"] = [10000] * n_consumers

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


class BoilerAggregation(AixLib):
    """Modelica AixLib representation of the GeneratorOneFluid aggregation."""
    path = "AixLib.Systems.ModularEnergySystems.Modules.ModularBoiler." \
           "ModularBoiler"
    represents = [aggregation.GeneratorOneFluid]

    def __init__(self, element):
        super().__init__(element)

    def request_params(self):

        self.params["redeclare package Medium"] = 'AixLib.Media.Water'

        # System setup
        self.params["Pump"] = self.element.has_pump
        self.params["hasFeedback"] = self.element.has_bypass
        self.request_param("rated_power",
                           self.check_numeric(min_value=0 * ureg.kilowatt),
                           "QNom")
        self.request_param("min_PLR",
                           self.check_numeric(min_value=0 * ureg.dimensionless),
                           "PLRMin")

        # Nominal condition
        self.request_param("return_temperature",
                           self.check_numeric(min_value=0 * ureg.celsius),
                           "TRetNom")
        self.request_param("dT_water",
                           self.check_numeric(min_value=0 * ureg.kelvin),
                           "dTWaterNom")

        # Feedback
        self.params["dp_Valve"] = 10000  # Todo get from hydraulic circuit

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


class Distributor(AixLib):
    path = "AixLib.Fluid.HeatExchangers.ActiveWalls.Distributor"
    represents = [hvac.Distributor]

    def __init__(self, element):
        super().__init__(element)

    def request_params(self):
        self.params['redeclare package Medium'] = 'AixLib.Media.Water'
        self.params['n'] = self.get_n_ports()
        self.request_param("rated_mass_flow",
                           self.check_numeric(min_value=0 * ureg.kg / ureg.s),
                           "m_flow_nominal")

    def get_n_ports(self):
        ports = {port.guid: port for port in self.element.ports if
                 port.connection}
        return len(ports)/2 - 1

    def get_port_name(self, port):
        try:
            index = self.element.ports.index(port)
        except ValueError:
            # unknown port
            index = -1
        if (index % 2) == 0:
            return "port_a_consumer"
        elif (index % 2) == 1:
            return "port_b_consumer"
        else:
            return super().get_port_name(port)

    @staticmethod
    def get_new_port_name(distributor, other_inst, distributor_port,
                          other_port, distributors_n, distributors_ports):
        if distributor not in distributors_n:
            distributors_n[distributor] = 0
            distributors_ports[distributor] = {}
        distributors_n[distributor] += 1
        if type(other_inst.element) is aggregation.GeneratorOneFluid:
            list_name = distributor_port.split('.')[:-1] + \
                        ['mainReturn' if 'port_a' in other_port
                         else 'mainFlow']
        else:
            port_key = other_port.split('.')[-1]
            if port_key not in distributors_ports[distributor]:
                distributors_ports[distributor][port_key] = 0
            distributors_ports[distributor][port_key] += 1
            n = distributors_ports[distributor][port_key]
            list_name = distributor_port.split('.')[:-1] + \
                        ['flowPorts[%d]' % n if 'port_a' in other_port
                         else 'returnPorts[%d]' % n]
        return '.'.join(list_name)


class ThreeWayValve(AixLib):
    path = "AixLib.Fluid.Actuators.Valves.ThreeWayEqualPercentageLinear"
    represents = [hvac.ThreeWayValve]

    def __init__(self, element):
        super().__init__(element)

    def request_params(self):
        self.params['redeclare package Medium'] = 'AixLib.Media.Water'

    def get_port_name(self, port):
        try:
            index = self.element.ports.index(port)
        except ValueError:
            # unknown port
            index = -1
        if index == 0:
            return "port_1"
        elif index == 1:
            return "port_2"
        elif index == 2:
            return "port_3"
        else:
            return super().get_port_name(port)


class Heatpump(AixLib):
    path = "AixLib.Fluid.HeatPumps.HeatPump"
    represents = [hvac.HeatPump]

    def __init__(self, element):
        super().__init__(element)

    def request_params(self):
        self.params['redeclare package Medium_con'] = 'AixLib.Media.Water'
        self.params['redeclare package Medium_eva'] = 'AixLib.Media.Water'

    def get_port_name(self, port):
        # TODO heat pumps might have 4 ports (if source is modeld in BIM)
        if port.verbose_flow_direction == 'SINK':
            return 'port_a'
        if port.verbose_flow_direction == 'SOURCE':
            return 'port_b'
        else:
            return super().get_port_name(port)


class Chiller(AixLib):
    path = "AixLib.Fluid.Chillers.Chiller"
    represents = [hvac.Chiller]

    def request_params(self):
        self.params['redeclare package Medium_con'] = 'AixLib.Media.Water'
        self.params['redeclare package Medium_eva'] = 'AixLib.Media.Water'

    def get_port_name(self, port):
        # TODO heat pumps might have 4 ports (if source is modeld in BIM)
        if port.verbose_flow_direction == 'SINK':
            return 'port_a'
        if port.verbose_flow_direction == 'SOURCE':
            return 'port_b'
        else:
            return super().get_port_name(port)


class CHP(AixLib):
    path = "AixLib.Fluid.BoilerCHP.CHPNoControl"
    represents = [hvac.CHP]

    def request_params(self):
        self.params['redeclare package Medium'] = 'AixLib.Media.Water'


class Storage(AixLib):
    path = "AixLib.Fluid.Storage.BufferStorage"
    represents = [hvac.Storage]

    def request_params(self):
        self.params['redeclare package Medium'] = 'AixLib.Media.Water'
        self.params['n'] = 5  # default number of layers
        # TODO these values are currently not checked and not decision is
        #  triggered for them if they don't exist. Problem is documented in #542
        self.params["data"] = f"AixLib.DataBase.Storage.Generic_New_2000l(" \
                              f"hTank={self.element.height}," \
                              f" dTank={self.element.diameter})"