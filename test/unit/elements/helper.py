from contextlib import contextmanager
from unittest import mock

import networkx as nx

from bim2sim.elements import bps_elements as bps
from bim2sim.elements import hvac_elements as hvac
from bim2sim.elements.aggregation import hvac_aggregations
from bim2sim.elements.aggregation.hvac_aggregations import \
    ConsumerHeatingDistributorModule
from bim2sim.elements.hvac_elements import HVACPort
from bim2sim.elements.graphs.hvac_graph import HvacGraph
from bim2sim.elements.mapping.units import ureg


class SetupHelper:
    ifc = mock.Mock()
    ifc.Name = 'Test'
    ifc.HasAssignments = []
    type(ifc).GlobalId = mock.PropertyMock(side_effect=range(100000),
                                           name='GlobalId')

    def __init__(self):
        self._flags = None
        self.elements = []

        # self.setup, self.flags = self.get_setup()
        # self.setup.plot(r'c:\temp')

    def reset(self) -> None:
        self.elements.clear()

    @contextmanager
    def flag_manager(self, flags):
        self._flags = flags
        yield
        self._flags = None

    def element_generator(self):
        raise NotImplementedError


class SetupHelperHVAC(SetupHelper):

    @classmethod
    def fake_add_ports(cls, parent, n=2):
        new_ports = [HVACPort(parent=parent) for i in range(n)]
        parent.ports.extend(new_ports)
        if isinstance(parent, hvac.HVACProduct):
            parent.inner_connections.extend(parent.get_inner_connections())
        return new_ports

    @staticmethod
    def connect_strait(items):
        """Connects item[n].ports[0] with item[n+1].ports[1] for all items"""
        last = None
        for item in items:
            if last:
                last.ports[1].connect(item.ports[0])
            last = item

    def element_generator(self, element_cls, n_ports=2, flags=None, **kwargs):
        # instantiate
        with mock.patch.object(hvac.HVACProduct, 'get_ports', return_value=[]):
            element = element_cls(**kwargs)
        self.elements.append(element)
        # # set attributes
        # for name, value in kwargs.items():
        #     if name not in element.attributes.names:
        #         raise AssertionError("Can't set attribute '%s' to %s. Choices are %s" %
        #                              (name, element_cls.__name__, list(element.attributes.names)))
        #     setattr(element, name, value * getattr(element_cls, name).unit)

        # add ports
        self.fake_add_ports(element, n_ports)

        # assign flags
        if flags:
            if self._flags is None:
                raise AssertionError(
                    "Use contextmanager .flag_manager when setting flags")
            for flag in flags:
                self._flags.setdefault(flag, []).append(element)

        return element

    def get_simple_pipe(self):
        pipe = self.element_generator(
            hvac.Pipe,
            length=1 * ureg.m
        )
        pipe.ports[0].flow_direction = -1
        pipe.ports[1].flow_direction = 1
        return HvacGraph([pipe]), pipe

    def get_simple_junction(self):
        junction = self.element_generator(
            hvac.Junction,
            volume=1 * ureg.m ** 3)
        return HvacGraph([junction])

    def get_simple_valve(self):
        valve = self.element_generator(
            hvac.Valve,
            nominal_pressure_difference=100 * ureg.pascal
        )
        return HvacGraph([valve])

    def get_simple_pump(self):
        pump = self.element_generator(
            hvac.Pump,
            rated_volume_flow=1 * ureg.meter ** 3 / ureg.s,
            rated_pressure_difference=10000 * ureg.pascal,
            rated_height=10 * ureg.meter,
            rated_power=5 * ureg.kilowatt)
        return HvacGraph([pump]), pump

    def get_simple_radiator(self):
        radiator = self.element_generator(
            hvac.SpaceHeater,
            rated_power=20 * ureg.kilowatt,
            flow_temperature=70 * ureg.celsius,
            return_temperature=50 * ureg.celsius,
        )
        return HvacGraph([radiator])

    def get_simple_boiler(self):
        boiler = self.element_generator(
            hvac.Boiler,
            rated_power=100 * ureg.kilowatt,
            return_temperature=50 * ureg.celsius
        )
        return HvacGraph([boiler])

    def get_simple_consumer(self):
        consumer = self.element_generator(
            hvac_aggregations.Consumer,
            rated_power=20 * ureg.kilowatt,
            base_graph=nx.Graph(),
            match_graph=nx.Graph()
        )
        return HvacGraph([consumer]), consumer

    def get_simple_three_way_valve(self):
        three_way_valve = self.element_generator(
            hvac.ThreeWayValve,
            nominal_pressure_difference=100 * ureg.pascal
        )
        return HvacGraph([three_way_valve])

    def get_simple_heat_pump(self):
        heat_pump = self.element_generator(
            hvac.HeatPump,
            rated_power=100 * ureg.kilowatt
        )
        return HvacGraph([heat_pump])

    def get_simple_chiller(self):
        chiller = self.element_generator(
            hvac.Chiller,
            rated_power=100 * ureg.kilowatt,
            nominal_power_consumption=25,
            nominal_COP=4 * ureg.dimensionless
        )
        return HvacGraph([chiller])

    def get_simple_cooling_tower(self):
        cooling_tower = self.element_generator(
            hvac.CoolingTower,
            rated_power=100 * ureg.kilowatt,
        )
        return HvacGraph([cooling_tower])

    def get_simple_space_heater(self):
        space_heater = self.element_generator(
            hvac.SpaceHeater,
            rated_power=50 * ureg.kilowatt,
            flow_temperature=70 * ureg.celsius,
            return_temperature=50 * ureg.celsius,
        )
        space_heater.ports[0].flow_direction = -1
        space_heater.ports[1].flow_direction = 1
        return HvacGraph([space_heater]), space_heater

    def get_simple_storage(self):
        storage = self.element_generator(
            hvac.Storage,
            volume=1 * ureg.meter ** 3,
            height=1 * ureg.meter,
            diameter=1 * ureg.meter
        )
        return HvacGraph([storage])

    def get_simple_generator_one_fluid(self):
        generator_one_fluid = self.element_generator(
            hvac_aggregations.GeneratorOneFluid,
            rated_power=100 * ureg.kilowatt,
            return_temperature=50 * ureg.celsius,
            flow_temperature=70 * ureg.celsius,
            base_graph=nx.Graph(),
            match_graph=nx.Graph()
        )
        return HvacGraph([generator_one_fluid])

    def get_simple_chp(self):
        chp = self.element_generator(
            hvac.CHP,
            rated_power=100 * ureg.kilowatt
        )
        return HvacGraph([chp])

    def get_simple_distributor(self):
        distributor = self.element_generator(
            hvac.Distributor,
            n_ports=6,
        )
        distributor.ports[4].flow_direction = 1
        distributor.ports[5].flow_direction = -1
        return HvacGraph([distributor]), distributor

    def get_setup_simple_heating_distributor_module(self):
        _, space_heater1 = self.get_simple_space_heater()
        _, space_heater2 = self.get_simple_space_heater()
        _, distributor = self.get_simple_distributor()
        pipes = []
        for _ in range(6):
            _, pipe = self.get_simple_pipe()
            pipe.diameter = 0.2 * ureg.meter
            pipes.append(pipe)
        self.connect_strait([pipes[0], space_heater1, pipes[1]])
        self.connect_strait([pipes[2], space_heater2, pipes[3]])
        distributor.ports[0].connect(pipes[0].ports[0])
        distributor.ports[1].connect(pipes[1].ports[1])
        distributor.ports[2].connect(pipes[2].ports[0])
        distributor.ports[3].connect(pipes[3].ports[1])
        distributor.ports[4].connect(pipes[4].ports[0])
        distributor.ports[5].connect(pipes[5].ports[1])
        circuit = [*pipes[0:4], space_heater1, space_heater2,
                   distributor]
        return HvacGraph(circuit),

    def get_simple_consumer_heating_distributor_module(self):
        graph, = self.get_setup_simple_heating_distributor_module()
        matches, metas = hvac_aggregations.Consumer.find_matches(graph)
        # Merge Consumer
        for match, meta in zip(matches, metas):
            module = hvac_aggregations.Consumer(graph, match, **meta)
            graph.merge(
                mapping=module.get_replacement_mapping(),
                inner_connections=module.inner_connections
            )
        # Merge ConsumerHeatingDistributorModule
        matches, metas = (hvac_aggregations.ConsumerHeatingDistributorModule.
                          find_matches(graph))
        for match, meta in zip(matches, metas):
            module = hvac_aggregations.ConsumerHeatingDistributorModule(
                graph, match, **meta)
            graph.merge(
                mapping=module.get_replacement_mapping(),
                inner_connections=module.inner_connections
            )
        return graph

    def get_setup_simple_boiler(self):
        """Simple generator system made of boiler, pump, expansion tank,
        distributor and pipes"""

        flags = {}
        with self.flag_manager(flags):
            # generator circuit
            boiler = self.element_generator(hvac.Boiler, rated_power=200)
            gen_vl_a = [
                self.element_generator(hvac.Pipe, length=100, diameter=40) for i
                in range(3)]
            h_pump = self.element_generator(hvac.Pump, rated_power=2.2,
                                            rated_height=12,
                                            rated_volume_flow=8)
            gen_vl_b = [
                self.element_generator(hvac.Pipe, flags=['strand1'], length=100,
                                       diameter=40) for i in range(5)]
            distributor = self.element_generator(hvac.Distributor, flags=[
                'distributor'])  # , volume=80
            gen_rl_a = [
                self.element_generator(hvac.Pipe, length=100, diameter=40) for i
                in range(4)]
            fitting = self.element_generator(hvac.PipeFitting, n_ports=3,
                                             diameter=40, length=60)
            gen_rl_b = [
                self.element_generator(hvac.Pipe, length=100, diameter=40) for i
                in range(4)]
            gen_rl_c = [
                self.element_generator(hvac.Pipe, flags=['strand2'],
                                       length=(1 + i) * 40, diameter=15)
                for i in range(3)
            ]
            tank = self.element_generator(hvac.Storage, n_ports=1)

        # connect
        gen_vl = [boiler, *gen_vl_a, h_pump, *gen_vl_b, distributor]
        self.connect_strait(gen_vl)

        self.connect_strait([distributor, *gen_rl_a, fitting])
        self.connect_strait([fitting, *gen_rl_b, boiler])
        self.connect_strait([*gen_rl_c, tank])
        fitting.ports[2].connect(gen_rl_c[0].ports[0])

        # full system
        gen_circuit = [
            boiler, *gen_vl_a, h_pump, *gen_vl_b, distributor,
            *gen_rl_a, fitting, *gen_rl_b, *gen_rl_c, tank
        ]

        return HvacGraph(gen_circuit), flags

    # def test_port_mapping(self):
    #     self.assertTrue(self.test_aggregation)
    #
    #     mapping = self.test_aggregation.get_replacement_mapping()
    #
    #     self.assertIs(self.test_aggregation.ports[0], mapping[self.edge_ports[0]])
    #     self.assertIs(self.test_aggregation.ports[1], mapping[self.edge_ports[1]])

    @staticmethod
    def elements_in_agg(agg):
        if not agg:
            return False
        if not agg.elements:
            return False

        for ele in agg.elements:
            if not isinstance(ele, hvac.HVACProduct):
                return False
        return True


class SetupHelperBPS(SetupHelper):
    def element_generator(self, element_cls, flags=None, **kwargs):
        # with mock.patch.object(bps.BPSProduct, 'get_ports', return_value=[]):
        orient = kwargs.pop('orientation', None)  # TODO WORKAROUND,
        element = element_cls(**kwargs)
        element.orientation = orient
        return element

    def get_thermalzone(self, usage='Living'):
        tz = self.element_generator(
            bps.ThermalZone,
            net_area=100,
            gross_area=110,
            usage=usage)
        return tz

    def get_thermalzones_diff_usage(self, usages: list):
        """Returns a number of ThermalZones with different usage.

        The first ThermalZone has a usage that can be identified by regular
        expressions ('Living'). The second and third ThermalZone can't be
        identified due to random names, but the third one is similar to the
        first). The fourth ThermalZone can again be identified.

        Returns:
            list of the three ThermalZone elements
        """
        tz_elements = []
        for usage in usages:
            tz_elements.append(self.get_thermalzone(usage=usage))

        return tz_elements

    def get_setup_simple_house(self):
        out_wall_1 = self.element_generator(
            bps.OuterWall,
            net_area=20,
            gross_area=21,
            width=0.2,
            orientation=90
        )
        window_1 = self.element_generator(bps.Window, net_area=2, width=0.1)
        tz_1 = self.get_thermalzone()
        tz_1.bound_elements = [out_wall_1, window_1]
        build_1 = self.element_generator(bps.Building,
                                         bldg_name='simpleTestBuilding', year_of_construction=2010)
            # bps.ThermalZone, bound_elements=[out_wall_1])

        elements = {
            out_wall_1.guid : out_wall_1,
            window_1.guid:window_1,
            tz_1.guid: tz_1,
            build_1.guid: build_1
        }
        return elements
