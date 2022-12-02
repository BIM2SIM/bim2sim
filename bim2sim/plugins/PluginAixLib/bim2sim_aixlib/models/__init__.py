"""Package for Python representations of HKESim models"""
from bim2sim.kernel.elements import hvac
from bim2sim.export import modelica
from bim2sim.kernel import elements
from bim2sim.kernel.units import ureg
import bim2sim.kernel.aggregation as aggregation


class AixLib(modelica.Instance):
    library = "AixLib"


class Boiler(AixLib):
    path = "AixLib.Systems.ModularEnergySystems.Modules.ModularBoiler." \
           "ModularBoiler"
    represents = hvac.Boiler

    def __init__(self, element):
        super().__init__(element)

    def request_params(self):
        self.request_param("rated_power",
                           self.check_numeric(min_value=0 * ureg.kilowatt),
                           "QNom")

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
        # self.params["functionality"] = "\"T_fixed\""
        self.params["functionality"] = '\"Q_flow_fixed\"'
        # if self.params["functionality"] == '\"Q_flow_fixed\"':
        #     self.request_param("rated_power",
        #                        self.check_numeric(min_value=0 * ureg.kilowatt),
        #                        "Q_flow_fixed")
        self.request_param("demand_type",
                           self.check_none(),
                           "demandType")
        self.params["hasPump"] = self.element.has_pump
        self.request_param("rated_power",
                           self.check_numeric(min_value=0 * ureg.kilowatt),
                           "Q_flow_nom")
        self.request_param("dT_water",
                           self.check_numeric(min_value=0 * ureg.kelvin),
                           "dT_nom")
        self.request_param("heat_capacity",
                           self.check_numeric(
                               min_value=0 * ureg.joule / ureg.kelvin),
                           "capacity")

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
           "ModularConsumer"
    represents = [aggregation.ConsumerHeatingDistributorModule]

    def __init__(self, element):
        self.check_volume = self.check_numeric(min_value=0 * ureg.meter ** 3)
        super().__init__(element)

    def request_params(self):
        self.params['n_consumers'] = len(self.element.consumers)
        self.params['redeclare package Medium'] = 'AixLib.Media.Water'
        self.request_param("demand_type",
                           self.check_none(),
                           "demandType")
        self.params["hasPump"] = [con.has_pump for con in
                                  self.element.consumers]

        self.params["functionality"] = "\"Q_flow_fixed\""
        self.request_param("rated_power",
                           self.check_numeric(min_value=0 * ureg.kilowatt),
                           "Q_flow_nom")
        self.request_param("dT_water",
                           self.check_numeric(min_value=0 * ureg.kelvin),
                           "dT_nom")
        self.request_param("heat_capacity",
                           self.check_numeric(
                               min_value=0 * ureg.joule / ureg.kelvin),
                           "capacity")

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


class GeneratorOneFluid(AixLib):
    """Modelica AixLib representation of the GeneratorOneFluid aggregation."""
    path = "AixLib.Systems.ModularEnergySystems.Modules.ModularBoiler." \
           "ModularBoiler_multiport"
    represents = [aggregation.GeneratorOneFluid]

    def __init__(self, element):
        super().__init__(element)

    def request_params(self):
        self.params["redeclare package Medium"] = 'AixLib.Media.Water'
        self.params["Pump"] = self.element.has_pump
        self.params["k"] = 1
        self.params["use_advancedControl"] = True
        self.params["use_flowTControl"] = True
        self.params["manualTimeDelay"] = False

        self.request_param("flow_temperature",
                           self.check_numeric(min_value=0 * ureg.celsius),
                           "TColdNom")
        self.request_param("dT_water",
                           self.check_numeric(min_value=0 * ureg.kelvin),
                           "dTWaterNom")
        self.request_param("rated_power",
                           self.check_numeric(min_value=0 * ureg.kilowatt),
                           "QNom")
        self.request_param("min_PLR",
                           self.check_numeric(min_value=0 * ureg.dimensionless),
                           "PLRMin")
        self.params["hasFeedback"] = self.element.has_bypass
        # how can we append the number of circuits, m_flow_con, dp_con
        # (information from consumers)

    def get_port_name(self, port):
        try:
            index = self.element.ports.index(port)
        except ValueError:
            # unknown port
            index = -1
        if index == 0:
            return "port_a"
        elif index == 1:
            return "ports_b[1]"
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
    path = "AixLib.Fluid.Actuators.Valves.TwoWayEqualPercentage"
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
            return "port_a"
        elif index == 1:
            return "port_b"
        elif index == 2:
            return "port_c"
        else:
            return super().get_port_name(port)
