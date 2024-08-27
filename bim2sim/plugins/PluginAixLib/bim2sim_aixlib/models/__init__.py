"""Package for Python representations of AixLib models"""
from bim2sim.elements.aggregation import hvac_aggregations
from bim2sim.export import modelica
from bim2sim.elements import hvac_elements as hvac
from bim2sim.elements.mapping.units import ureg
from bim2sim.export.modelica import check_numeric
from bim2sim.export.modelica import HeatPort

MEDIUM_WATER = 'AixLib.Media.Water'


# TODO get_port_name functions: use verbose_flow_direction instead index
class AixLib(modelica.ModelicaElement):
    library = "AixLib"


class Boiler(AixLib):
    # TODO: The model BoilerGeneric does not exist in AixLib
    path = "AixLib.Fluid.BoilerCHP.BoilerGeneric"
    represents = [hvac.Boiler]

    def __init__(self, element):
        super().__init__(element)
        self._set_parameter(name='redeclare package Medium',
                            unit=None,
                            required=False,
                            value=MEDIUM_WATER)
        self._set_parameter(name='dTWaterNom',
                            unit=ureg.kelvin,
                            required=True,
                            attributes=['dT_water'],
                            check=check_numeric(min_value=0 * ureg.kelvin))
        self._set_parameter(name='TRetNom',
                            unit=ureg.kelvin,
                            required=True,
                            attributes=['return_temperature'],
                            check=check_numeric(min_value=0 * ureg.kelvin))
        self._set_parameter(name='QNom',
                            unit=ureg.watt,
                            required=True,
                            attributes=['rated_power'],
                            check=check_numeric(min_value=0 * ureg.watt))
        self._set_parameter(name='PLRMin',
                            unit=ureg.dimensionless,
                            required=True,
                            attributes=['min_PLR'],
                            check=check_numeric(
                                min_value=0 * ureg.dimensionless))

    def get_port_name(self, port):
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
        self.heat_ports = [
            HeatPort(name='heatPortCon',
                     heat_transfer_type='convective',
                     parent=self),
            HeatPort(name='heatPortRad',
                     heat_transfer_type='radiative',
                      parent=self)
        ]
        self._set_parameter(name='redeclare package Medium',
                            unit=None,
                            required=False,
                            value=MEDIUM_WATER)
        self._set_parameter(name='Q_flow_nominal',
                            unit=ureg.watt,
                            required=True,
                            attributes=['rated_power'],
                            check=check_numeric(min_value=0 * ureg.watt))
        self._set_parameter(name='T_a_nominal',
                            unit=ureg.celsius,
                            required=True,
                            check=check_numeric(min_value=0 * ureg.celsius),
                            attributes=['flow_temperature'])
        self._set_parameter(name='T_b_nominal',
                            unit=ureg.celsius,
                            required=True,
                            check=check_numeric(min_value=0 * ureg.celsius),
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

    def __init__(self, element):
        super().__init__(element)
        self._set_parameter(name='redeclare package Medium',
                            unit=None,
                            required=False,
                            value=MEDIUM_WATER)
        self._set_parameter(name='V_flow',
                            unit=ureg.m ** 3 / ureg.s,
                            required=True,
                            export=False,
                            function=lambda rated_volume_flow:
                            [0 * rated_volume_flow,
                             1 * rated_volume_flow,
                             2 * rated_volume_flow])
        self._set_parameter(name='dp',
                            unit=ureg.pascal,
                            required=True,
                            export=False,
                            function=lambda rated_pressure_difference:
                            [2 * rated_pressure_difference,
                             1 * rated_pressure_difference,
                             0 * rated_pressure_difference])
        self._set_parameter(name='per',
                            unit=None,
                            required=False,
                            value={'pressure': {
                                'V_flow': self.parameters['V_flow'],
                                'dp': self.parameters['dp']}})

    def get_port_name(self, port):
        if port.verbose_flow_direction == 'SINK':
            return 'port_a'
        if port.verbose_flow_direction == 'SOURCE':
            return 'port_b'
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
        super().__init__(element)
        self._set_parameter(name='redeclare package Medium_con',
                            unit=None,
                            required=False,
                            value=MEDIUM_WATER)
        self._set_parameter(name='capacity',
                            unit=ureg.joule / ureg.kelvin,
                            required=False,
                            check=check_numeric(
                                min_value=0 * ureg.joule / ureg.kelvin),
                            attributes=['heat_capacity'])
        self._set_parameter(name='V',
                            unit=ureg.meter ** 3,
                            required=False,
                            check=check_numeric(min_value=0 * ureg.meter ** 3),
                            attributes=['volume'])
        self._set_parameter(name='Q_flow_fixed',
                            unit=ureg.watt,
                            required=False,
                            check=check_numeric(min_value=0 * ureg.watt),
                            attributes=['rated_power'])
        self._set_parameter(name='V_flow_nominal',
                            unit=ureg.meter ** 3 / ureg.s,
                            required=True,
                            export=False,
                            check=check_numeric(
                                min_value=0 * ureg.meter ** 3 / ureg.s),
                            attributes=['rated_volume_flow'])
        self._set_parameter(name='m_flow_nominal',
                            unit=ureg.kg / ureg.s,
                            required=False,
                            function=lambda:
                            (self.parameters['V_flow_nominal'].value * 998
                             * ureg.kg / ureg.meter ** 3))

    def get_port_name(self, port):
        if port.verbose_flow_direction == 'SINK':
            return 'port_a'
        if port.verbose_flow_direction == 'SOURCE':
            return 'port_b'
        else:
            return super().get_port_name(port)


class ConsumerHeatingDistributorModule(AixLib):
    # TODO: the model does not exists in AiLib
    path = ("AixLib.Systems.ModularEnergySystems.Modules.ModularConsumer."
            "ConsumerDistributorModule")
    represents = [hvac_aggregations.ConsumerHeatingDistributorModule]

    def __init__(self,
                 element: hvac_aggregations.ConsumerHeatingDistributorModule):
        super().__init__(element)
        n_consumers = len(element.whitelist_elements)
        self._set_parameter(name='redeclare package Medium_con',
                            unit=None,
                            required=False,
                            value=MEDIUM_WATER)
        self._set_parameter(name='T_start',
                            unit=ureg.kelvin,
                            required=False,
                            check=check_numeric(min_value=0 * ureg.kelvin),
                            attributes=['return_temperature'])
        self._set_parameter(name='n_consumers',
                            unit=ureg.dimensionless,
                            required=False,
                            value=n_consumers)
        self._set_parameter(name='functionality',
                            unit=None,
                            required=False,
                            value='Q_flow_fixed')
        self._set_parameter(name='demandType',
                            unit=None,
                            required=False,
                            attributes=['demand_type'])
        self._set_parameter(name='capacity',
                            unit=ureg.joule / ureg.kelvin,
                            required=False,
                            check=check_numeric(
                                min_value=0 * ureg.joule / ureg.kelvin),
                            attributes=['heat_capacity'])
        self._set_parameter(name='Q_flow_nom',
                            unit=ureg.watt,
                            required=False,
                            check=check_numeric(min_value=0 * ureg.watt),
                            attributes=['rated_power'])
        self._set_parameter(name='dT_nom',
                            unit=ureg.kelvin,
                            required=False,
                            check=check_numeric(min_value=0 * ureg.kelvin),
                            attributes=['dT_water'])
        self._set_parameter(name='hasFeedback',
                            unit=None,
                            required=False,
                            attributes=['t_control'])
        self._set_parameter(name='TInSetSou',
                            unit=None,
                            required=False,
                            value=("AixLib.Systems.ModularEnergySystems."
                                   "Modules.ModularConsumer.Types."
                                   "InputTypeConstant"))
        self._set_parameter(name='TInSet',
                            unit=ureg.kelvin,
                            required=False,
                            check=check_numeric(min_value=0 * ureg.kelvin),
                            attributes=['flow_temperature'])
        self._set_parameter(name='k_ControlConsumerValve',
                            unit=None,
                            required=False,
                            value=0.1 * n_consumers)
        self._set_parameter(name='Ti_ControlConsumerValve',
                            unit=None,
                            required=False,
                            value=10 * n_consumers)
        self._set_parameter(name='dp_Valve',
                            unit=ureg.pascal,
                            required=False,
                            value=1000 * n_consumers)
        self._set_parameter(name='hasPump',
                            unit=None,
                            required=False,
                            attributes=['has_pump'])
        self._set_parameter(name='TOutSet',
                            unit=ureg.kelvin,
                            required=False,
                            check=check_numeric(min_value=0 * ureg.kelvin),
                            attributes=['return_temperature'])
        self._set_parameter(name='TOutSetSou',
                            unit=None,
                            required=False,
                            value=("AixLib.Systems.ModularEnergySystems."
                                   "Modules.ModularConsumer.Types.InputType."
                                   "Constant"))
        self._set_parameter(name='k_ControlConsumerPump',
                            unit=None,
                            required=False,
                            value=0.1 * n_consumers)
        self._set_parameter(name='Ti_ControlConsumerPump',
                            unit=None,
                            required=False,
                            value=10 * n_consumers)
        self._set_parameter(name='dp_nominalConPump',
                            unit=ureg.pascal,
                            required=False,
                            value=10000 * n_consumers)

    def get_port_name(self, port):
        if port.verbose_flow_direction == 'SINK':
            return 'port_a'
        if port.verbose_flow_direction == 'SOURCE':
            return 'port_b'
        else:
            return super().get_port_name(port)


class BoilerAggregation(AixLib):
    # TODO: the model does not exists in AiLib
    """Modelica AixLib representation of the GeneratorOneFluid aggregation."""
    path = "AixLib.Systems.ModularEnergySystems.ModularBoiler.ModularBoiler"
    represents = [hvac_aggregations.GeneratorOneFluid]

    def __init__(self, element):
        super().__init__(element)
        self._set_parameter(name='redeclare package Medium',
                            unit=None,
                            required=False,
                            value=MEDIUM_WATER)
        self._set_parameter(name='hasPump',
                            unit=None,
                            required=False,
                            attributes=['has_pump'])
        self._set_parameter(name='hasFeedback',
                            unit=None,
                            required=False,
                            attributes=['has_bypass'])
        self._set_parameter(name='Q_flow_nominal',
                            unit=ureg.watt,
                            required=False,
                            check=check_numeric(min_value=0 * ureg.watt),
                            attributes=['rated_power'])
        self._set_parameter(name='FirRatMin',
                            unit=ureg.dimensionless,
                            required=False,
                            check=check_numeric(
                                min_value=0 * ureg.dimensionless),
                            attributes=['min_PLR'])
        self._set_parameter(name='TRet_nominal',
                            unit=ureg.kelvin,
                            required=False,
                            check=check_numeric(
                                min_value=0 * ureg.kelvin),
                            attributes=['return_temperature'])
        self._set_parameter(name='TSup_nominal',
                            unit=ureg.kelvin,
                            required=False,
                            check=check_numeric(
                                min_value=0 * ureg.kelvin),
                            attributes=['flow_temperature'])
        self._set_parameter(name='dT_nominal',
                            unit=ureg.kelvin,
                            required=False,
                            check=check_numeric(min_value=0 * ureg.kelvin),
                            attributes=['dT_water'])
        self._set_parameter(name='dp_Valve',
                            unit=ureg.pascal,
                            required=False,
                            value=10000)

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

    def __init__(self, element: hvac.Distributor):
        super().__init__(element)
        # n_ports = self.get_n_ports()
        self._set_parameter(name='redeclare package Medium',
                            unit=None,
                            required=False,
                            value=MEDIUM_WATER)
        # self._set_parameter(name='n',
        #                     unit=None,
        #                     required=False,
        #                     value=n_ports)
        self._set_parameter(name='m_flow_nominal',
                            unit=ureg.kg / ureg.s,
                            required=False,
                            check=check_numeric(min_value=0 * ureg.kg / ureg.s),
                            attributes=['rated_mass_flow'])

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
        self._set_parameter(name='redeclare package Medium_con',
                            unit=None,
                            required=False,
                            value=MEDIUM_WATER)
        self._set_parameter(name='m_flow_nominal',
                            unit=ureg.kg / ureg.s,
                            required=True,
                            check=check_numeric(
                                min_value=0 * ureg.kg / ureg.s),
                            attributes=['nominal_mass_flow_rate'])
        self._set_parameter(name='dpValve_nominal',
                            unit=ureg.pascal,
                            required=True,
                            check=check_numeric(min_value=0 * ureg.pascal),
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
        self._set_parameter(name='redeclare package Medium_con',
                            unit=None,
                            required=False,
                            value=MEDIUM_WATER)
        self._set_parameter(name='redeclare Medium_eva Medium_con',
                            unit=None,
                            required=False,
                            value=MEDIUM_WATER)
        self._set_parameter(name='Q_useNominal',
                            unit=ureg.watt,
                            required=False,
                            check=check_numeric(min_value=0 * ureg.watt),
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

    def __init__(self, element):
        super().__init__(element)
        self._set_parameter(name='redeclare package Medium_con',
                            unit=None,
                            required=False,
                            value=MEDIUM_WATER)
        self._set_parameter(name='redeclare Medium_eva Medium_con',
                            unit=None,
                            required=False,
                            value=MEDIUM_WATER)
        self._set_parameter(name='Q_useNominal',
                            unit=ureg.watt,
                            required=False,
                            check=check_numeric(min_value=0 * ureg.watt),
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

    def __init__(self, element):
        super().__init__(element)
        self._set_parameter(name='redeclare package Medium',
                            unit=None,
                            required=False,
                            value=MEDIUM_WATER)


class Storage(AixLib):
    path = "AixLib.Fluid.Storage.BufferStorage"
    represents = [hvac.Storage]

    def __init__(self, element):
        super().__init__(element)
        self._set_parameter(name='redeclare package Medium',
                            unit=None,
                            required=False,
                            value=MEDIUM_WATER)
        self._set_parameter(name='hTank',
                            unit=ureg.meter,
                            required=True,
                            export=False,
                            check=check_numeric(min_value=0 * ureg.meter),
                            attributes=['height'])
        self._set_parameter(name='dTank',
                            unit=ureg.meter,
                            required=True,
                            export=False,
                            check=check_numeric(min_value=0 * ureg.meter),
                            attributes=['diameter'])
        self._set_parameter(name='data',
                              unit=None,
                            required=False,
                            value={'hTank': self.parameters['hTank'],
                              "dTank": self.parameters['dTank']})

