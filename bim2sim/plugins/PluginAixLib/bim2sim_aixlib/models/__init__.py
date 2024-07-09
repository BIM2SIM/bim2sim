"""Package for Python representations of AixLib models"""
from typing import Callable

import pint

from bim2sim.elements.aggregation import hvac_aggregations
from bim2sim.export import modelica
from bim2sim.elements import hvac_elements as hvac
from bim2sim.elements.mapping.units import ureg
from bim2sim.export.modelica import ModelicaParameter


class AixLib(modelica.Instance):
    library = "AixLib"


class Boiler(AixLib):
    # TODO: The model BoilerGeneric does not exist in AixLib
    path = "AixLib.Fluid.BoilerCHP.BoilerGeneric"
    represents = [hvac.Boiler]

    def __init__(self, element):
        super().__init__(element)

    def request_params(self):

        self.export_parameters[
            "redeclare package Medium"] = 'AixLib.Media.Water'
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

    def define_parameters(self):
        self.export_parameters[
            'redeclare package Medium'] = 'AixLib.Media.Water'
        self.parameter(name='Q_flow_nominal',
                       unit=ureg.watt,
                       required=True,
                       attributes=['rated_power'],
                       function=None)
        self.parameter(name='T_a_nominal',
                       unit=ureg.celsius,
                       required=True,
                       attributes=['flow_temperature'])
        self.parameter(name='T_b_nominal',
                       unit=ureg.celsius,
                       required=True,
                       attributes=['return_temperature'])

    def get_port_name(self, port):
        if port.verbose_flow_direction == 'SINK':
            return 'port_a'
        if port.verbose_flow_direction == 'SOURCE':
            return 'port_b'
        else:
            return super().get_port_name(port)


class Pump(AixLib):
    path = "AixLib.Fluid.Movers.SpeedControlled_y"
    represents = [hvac.Pump]

    def _performance_record(self, V_flow, dp):
        record_dict = {'pressure': {
            V_flow: self.non_export_parameters[V_flow],
            dp: self.non_export_parameters[dp]}}
        return record_dict

    def define_parameters(self):
        self.export_parameters[
            'redeclare package Medium'] = 'AixLib.Media.Water'
        self.parameter(name='V_flow',
                       unit=ureg.m ** 3 / ureg.s,
                       required=True,
                       export=False,
                       attributes=['rated_volume_flow'],
                       function=lambda rated_volume_flow:
                       [0 * rated_volume_flow,
                        1 * rated_volume_flow,
                        2 * rated_volume_flow])
        self.parameter(name='dp',
                       unit=ureg.pascal,
                       required=True,
                       export=False,
                       attributes=['rated_pressure_difference'],
                       function=lambda rated_pressure_difference:
                       [2 * rated_pressure_difference,
                        1 * rated_pressure_difference,
                        0 * rated_pressure_difference])
        self.parameter(name='per',
                       unit=None,
                       required=False,
                       required_parameters=['V_flow', 'dp'],
                       function=self._performance_record)
        # DRAFT: How can we generalize record definitions?
        # self.parameter(name='per',
        #                unit=[ureg.m **3 / s, ureg.pascal],
        #                required=True,
        #                attributes=['rated_volume_flow',
        #                            'rated_pressure_difference'],
        #                function=lambda rated_volume_flow,
        #                                rated_pressure_difference:
        #                {'pressure': {
        #                    'V_flow': [0 * rated_volume_flow,
        #                               1 * rated_volume_flow,
        #                               2 * rated_volume_flow],
        #                    'dp': [2 * rated_pressure_difference,
        #                           1 * rated_pressure_difference,
        #                           0 * rated_pressure_difference]}})

    def get_port_name(self, port):
        if port.verbose_flow_direction == 'SINK':
            return 'port_a'
        if port.verbose_flow_direction == 'SOURCE':
            return 'port_b'
        else:
            return super().get_port_name(port)


class Consumer(AixLib):
    path = "AixLib.Systems.HydraulicModules.SimpleConsumer"
    represents = [hvac_aggregations.Consumer]

    def _calc_m_flow_nominal(self, V_flow_nominal):
        return (self.non_export_parameters[V_flow_nominal]
                * 998 * ureg.kg / ureg.meter ** 3)

    def define_parameters(self):
        self.export_parameters[
            'redeclare package Medium'] = 'AixLib.Media.Water'
        self.parameter(name='capacity',
                       unit=ureg.joule / ureg.kelvin,
                       required=False,
                       attributes=['heat_capacity'])
        self.parameter(name='V',
                       unit=ureg.meter ** 3,
                       required=False,
                       attributes=['volume'])
        self.parameter(name='Q_flow_fixed',
                       unit=ureg.watt,
                       required=False,
                       attributes=['rated_power'])
        self.parameter(name='V_flow_nominal',
                       unit=ureg.meter ** 3 / ureg.s,
                       required=True,
                       export=False,
                       attributes=['rated_volume_flow'])
        self.parameter(name='m_flow_nominal',
                       unit=ureg.kg / ureg.s,
                       required=True,
                       required_parameters=['V_flow_nominal'],
                       function=self._calc_m_flow_nominal)

    def get_port_name(self, port):
        if port.verbose_flow_direction == 'SINK':
            return 'port_a'
        if port.verbose_flow_direction == 'SOURCE':
            return 'port_b'
        else:
            return super().get_port_name(port)


class ConsumerHeatingDistributorModule(AixLib):
    # TODO: the model does not exists in AiLib
    path = "AixLib.Systems.ModularEnergySystems.Modules.ModularConsumer." \
           "ConsumerDistributorModule"
    represents = [hvac_aggregations.ConsumerHeatingDistributorModule]

    def __init__(self, element):
        self.check_volume = self.check_numeric(min_value=0 * ureg.meter ** 3)
        super().__init__(element)

    def request_params(self):
        n_consumers = len(self.element.whitelist_elements)
        # Parameters
        self.export_parameters["T_start"] = self.element.return_temperature
        self.export_parameters[
            'redeclare package Medium'] = 'AixLib.Media.Water'
        # Consumer Design
        self.export_parameters['n_consumers'] = n_consumers
        self.export_parameters["functionality"] = "\"Q_flow_fixed\""
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
        self.export_parameters["Q_flow_nom"] = self.element.rated_power
        self.request_param("dT_water",
                           self.check_numeric(min_value=0 * ureg.kelvin),
                           "dT_nom")

        # Flow temperature control (Mixture Valve)
        self.export_parameters["hasFeedback"] = self.element.t_control
        self.export_parameters[
            "TInSetSou"] = "AixLib.Systems.ModularEnergySystems." \
                           "Modules.ModularConsumer.Types.InputType." \
                           "Constant"
        self.export_parameters["TInSet"] = self.element.flow_temperature
        self.export_parameters["k_ControlConsumerValve"] = [0.1] * n_consumers
        self.export_parameters["Ti_ControlConsumerValve"] = [10] * n_consumers
        self.export_parameters["dp_Valve"] = [1000] * n_consumers

        # Return temperature control (Pump)
        self.export_parameters["hasPump"] = self.element.has_pump
        self.export_parameters["TOutSet"] = self.element.return_temperature
        self.export_parameters[
            "TOutSetSou"] = "AixLib.Systems.ModularEnergySystems." \
                            "Modules.ModularConsumer.Types.InputType." \
                            "Constant"
        self.export_parameters["k_ControlConsumerPump"] = [0.1] * n_consumers
        self.export_parameters["Ti_ControlConsumerPump"] = [10] * n_consumers
        self.export_parameters["dp_nominalConPump"] = [10000] * n_consumers

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
    # TODO: the model does not exists in AiLib
    """Modelica AixLib representation of the GeneratorOneFluid aggregation."""
    path = "AixLib.Systems.ModularEnergySystems.Modules.ModularBoiler." \
           "ModularBoiler"
    represents = [hvac_aggregations.GeneratorOneFluid]

    def __init__(self, element):
        super().__init__(element)

    def define_parameters(self):
        self.export_parameters[
            "redeclare package Medium"] = 'AixLib.Media.Water'
        # System setup
        self.export_parameters["Pump"] = self.element.has_pump
        self.export_parameters["hasFeedback"] = self.element.has_bypass
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
        self.export_parameters[
            "dp_Valve"] = 10000  # Todo get from hydraulic circuit

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

    def define_parameters(self):
        self.export_parameters[
            'redeclare package Medium'] = 'AixLib.Media.Water'
        self.export_parameters['n'] = self.get_n_ports()
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

    def define_parameters(self):
        self.export_parameters[
            'redeclare package Medium'] = 'AixLib.Media.Water'
        self.parameter(name='nominal_mass_nominal',
                       unit=ureg.kg / ureg.s,
                       required=True,
                       attributes=['nominal_mass_flow_rate'])
        self.parameter(name='dpValve_nominal',
                       unit=ureg.pascal,
                       required=True,
                       attributes=['nominal_pressure_difference'])

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

    def define_parameters(self):
        self.export_parameters[
            'redeclare package Medium_con'] = 'AixLib.Media.Water'
        self.export_parameters[
            'redeclare package Medium_eva'] = 'AixLib.Media.Water'
        self.parameter(name='Q_useNominal',
                       unit=ureg.watt,
                       required=False,
                       attributes=['rated_power'])

    def get_port_name(self, port):
        # TODO: heat pumps might have 4 ports (if source is modeled in BIM)
        if port.verbose_flow_direction == 'SINK':
            return 'port_a'
        if port.verbose_flow_direction == 'SOURCE':
            return 'port_b'
        else:
            return super().get_port_name(port)


class Chiller(AixLib):
    path = "AixLib.Fluid.Chillers.Chiller"
    represents = [hvac.Chiller]

    def define_parameters(self):
        self.export_parameters[
            'redeclare package Medium_con'] = 'AixLib.Media.Water'
        self.export_parameters[
            'redeclare package Medium_eva'] = 'AixLib.Media.Water'
        self.parameter(name='Q_useNominal',
                       unit=ureg.watt,
                       required=False,
                       attributes=['rated_power'])

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

    def define_parameters(self):
        self.export_parameters[
            'redeclare package Medium'] = 'AixLib.Media.Water'


class Storage(AixLib):
    path = "AixLib.Fluid.Storage.BufferStorage"
    represents = [hvac.Storage]

    def define_parameters(self):
        self.export_parameters[
            'redeclare package Medium'] = 'AixLib.Media.Water'
        self.export_parameters['n'] = 5  # default number of layers
        self.parameter(name='height',
                       unit=ureg.meter,
                       required=True,
                       export=False,
                       attributes=['height'])
        self.parameter(name='diameter',
                       unit=ureg.meter,
                       required=True,
                       export=False,
                       attributes=['diameter'])
        self.parameter(name='data',
                       unit=None,
                       required=True,
                       required_parameters=['height', 'diameter'],
                       function=lambda height, diameter: {
                           "hTank": self.non_export_parameters['height'],
                           "dTank": self.non_export_parameters['diameter']})