"""Package for Python representations of AixLib models"""
from bim2sim.elements.aggregation import hvac_aggregations
from bim2sim.export import modelica
from bim2sim.elements import hvac_elements as hvac
from bim2sim.elements.mapping.units import ureg
from bim2sim.export.modelica import HeatPort


# TODO get_port_name functions: use verbose_flow_direction instead index
class AixLib(modelica.Instance):
    library = "AixLib"


class Boiler(AixLib):
    path = "AixLib.Fluid.BoilerCHP.BoilerGeneric"
    represents = [hvac.Boiler]

    def __init__(self, element):
        super().__init__(element)

    def request_params(self):

        self.export_params["redeclare package Medium"] = 'AixLib.Media.Water'
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
                           self.check_numeric(
                               min_value=0 * ureg.dimensionless),
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

    def __init__(self, element):
        super().__init__(element)
        self._add_heat_ports()

    def request_params(self):
        self.request_param("rated_power",
                           self.check_numeric(min_value=0 * ureg.kilowatt),
                           "Q_flow_nominal")
        # self.params["T_nominal"] = (80, 60, 20)

    def get_port_name(self, port):
        if port.verbose_flow_direction == 'SINK':
            return 'port_a'
        if port.verbose_flow_direction == 'SOURCE':
            return 'port_b'
        else:
            return super().get_port_name(port)

    def _add_heat_ports(self):
        self.heat_ports = [
            HeatPort(name='heatPortCon',
                     heat_transfer_type='convective',
                     parent=self),
           HeatPort(name='heatPortRad',
                    heat_transfer_type='radiative',
                    parent=self)]

    def get_heat_port_names(self):
        return [heat_port.name for heat_port in self.heat_ports]

class Pump(AixLib):
    path = "AixLib.Fluid.Movers.SpeedControlled_y"
    represents = [hvac.Pump]

    # TODO clarify difference in base modelica/__init__.py between
    #  parameter(modelica) and attribute (bim2sim)
    def request_params(self):
        self.export_params['redeclare package Medium'] = 'AixLib.Media.Water'
        self.request_param(
            "V_flow",
            # check=self.check_numeric(min_value=0 * ureg.m ** 3 / ureg.s),
            check=self.check_none(),
            export=False,
            needed_params=["rated_volume_flow"],
            function=lambda: [
                0 * self.stored_params["rated_volume_flow"],
                self.stored_params["rated_volume_flow"],
                2 * self.stored_params["rated_volume_flow"]
            ]
            # self._calc_v_flow
        )
        self.request_param(
            "dp",
            check=self.check_none(),
            # check=self.check_numeric(min_value=0 * ureg.newton / ureg.m ** 2),
            export=False,
            needed_params=["rated_pressure_difference"],
            function=lambda: [
                2 * self.stored_params["rated_pressure_difference"],
                self.stored_params["rated_pressure_difference"],
                0 * self.stored_params["rated_pressure_difference"]
            ]
        )
        self.request_param(
            name="per",
            check=self.check_none(),
            needed_params=[],
            export=True,
            function=lambda:
                {
                    "pressure":
                        {
                            "V_flow":
                                self.stored_params["V_flow"],
                            "dp":
                                self.stored_params["dp"]
                        }
                }
        )

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

    def get_heat_port_names(self):
        return {
            "con": "heatPortCon",
        }


class Consumer(AixLib):
    path = "AixLib.Systems.HydraulicModules.SimpleConsumer"
    represents = [hvac_aggregations.Consumer]

    def __init__(self, element):
        self.check_volume = self.check_numeric(min_value=0 * ureg.meter ** 3)
        super().__init__(element)

    def request_params(self):
        self.export_params['redeclare package Medium'] = 'AixLib.Media.Water'
        self.export_params["functionality"] = '\"Q_flow_fixed\"'
        if self.export_params["functionality"] == '\"Q_flow_fixed\"':
            self.export_params["Q_flow_fixed"] = self.element.rated_power
        self.export_params["demand_type"] = "1"

        # self.request_param("demand_type",
        #                    self.check_none(),
        #                    "demandType")

        self.export_params["hasFeedback"] = self.element.t_control
        if self.element.t_control:
            self.export_params["TInSetValue"] = self.element.flow_temperature
            self.export_params[
                "TInSetSou"] = "AixLib.Systems.ModularEnergySystems." \
                               "Modules.ModularConsumer.Types.InputType." \
                               "Constant"

        self.export_params["hasPump"] = self.element.has_pump
        if self.element.has_pump:
            self.export_params[
                "TOutSetValue"] = self.element.return_temperature
            self.export_params[
                "TOutSetSou"] = "AixLib.Systems.ModularEnergySystems." \
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
    represents = [hvac_aggregations.ConsumerHeatingDistributorModule]

    def __init__(self, element):
        self.check_volume = self.check_numeric(min_value=0 * ureg.meter ** 3)
        super().__init__(element)

    def request_params(self):
        n_consumers = len(self.element.whitelist_elements)
        # Parameters
        self.export_params["T_start"] = self.element.return_temperature
        self.export_params['redeclare package Medium'] = 'AixLib.Media.Water'
        # Consumer Design
        self.export_params['n_consumers'] = n_consumers
        self.export_params["functionality"] = "\"Q_flow_fixed\""
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
        self.export_params["Q_flow_nom"] = self.element.rated_power
        self.request_param("dT_water",
                           self.check_numeric(min_value=0 * ureg.kelvin),
                           "dT_nom")

        # Flow temperature control (Mixture Valve)
        self.export_params["hasFeedback"] = self.element.t_control
        self.export_params[
            "TInSetSou"] = "AixLib.Systems.ModularEnergySystems." \
                           "Modules.ModularConsumer.Types.InputType." \
                           "Constant"
        self.export_params["TInSet"] = self.element.flow_temperature
        self.export_params["k_ControlConsumerValve"] = [0.1] * n_consumers
        self.export_params["Ti_ControlConsumerValve"] = [10] * n_consumers
        self.export_params["dp_Valve"] = [1000] * n_consumers

        # Return temperature control (Pump)
        self.export_params["hasPump"] = self.element.has_pump
        self.export_params["TOutSet"] = self.element.return_temperature
        self.export_params[
            "TOutSetSou"] = "AixLib.Systems.ModularEnergySystems." \
                            "Modules.ModularConsumer.Types.InputType." \
                            "Constant"
        self.export_params["k_ControlConsumerPump"] = [0.1] * n_consumers
        self.export_params["Ti_ControlConsumerPump"] = [10] * n_consumers
        self.export_params["dp_nominalConPump"] = [10000] * n_consumers

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
    represents = [hvac_aggregations.GeneratorOneFluid]

    def __init__(self, element):
        super().__init__(element)

    def request_params(self):

        self.export_params["redeclare package Medium"] = 'AixLib.Media.Water'

        # System setup
        self.export_params["Pump"] = self.element.has_pump
        self.export_params["hasFeedback"] = self.element.has_bypass
        self.request_param("rated_power",
                           self.check_numeric(min_value=0 * ureg.kilowatt),
                           "QNom")
        self.request_param("min_PLR",
                           self.check_numeric(
                               min_value=0 * ureg.dimensionless),
                           "PLRMin")

        # Nominal condition
        self.request_param("return_temperature",
                           self.check_numeric(min_value=0 * ureg.celsius),
                           "TRetNom")
        self.request_param("dT_water",
                           self.check_numeric(min_value=0 * ureg.kelvin),
                           "dTWaterNom")

        # Feedback
        self.export_params[
            "dp_Valve"] = 10000  # Todo get from hydraulic circuit

    def get_port_name(self, port):
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
        self.export_params['redeclare package Medium'] = 'AixLib.Media.Water'
        self.export_params['n'] = self.get_n_ports()
        self.request_param("rated_mass_flow",
                           self.check_numeric(min_value=0 * ureg.kg / ureg.s),
                           "m_flow_nominal")

    def get_n_ports(self):
        ports = {port.guid: port for port in self.element.ports if
                 port.connection}
        return len(ports) / 2 - 1

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
        if type(other_inst.element) is hvac_aggregations.GeneratorOneFluid:
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
        self.export_params['redeclare package Medium'] = 'AixLib.Media.Water'

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
        self.export_params[
            'redeclare package Medium_con'] = 'AixLib.Media.Water'
        self.export_params[
            'redeclare package Medium_eva'] = 'AixLib.Media.Water'

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
        self.export_params[
            'redeclare package Medium_con'] = 'AixLib.Media.Water'
        self.export_params[
            'redeclare package Medium_eva'] = 'AixLib.Media.Water'

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
        self.export_params['redeclare package Medium'] = 'AixLib.Media.Water'


class Storage(AixLib):
    path = "AixLib.Fluid.Storage.BufferStorage"
    represents = [hvac.Storage]

    def request_params(self):
        self.export_params['redeclare package Medium'] = 'AixLib.Media.Water'
        self.export_params['n'] = 5  # default number of layers
        # TODO these values are currently not checked and not decision is
        #  triggered for them if they don't exist. Problem is documented in
        #  #542
        self.export_params["data"] = f"AixLib.DataBase.Storage.Generic_New_2000l(" \
                              f"hTank={self.element.height}," \
                              f" dTank={self.element.diameter})"

