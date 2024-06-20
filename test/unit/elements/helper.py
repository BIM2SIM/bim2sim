from contextlib import contextmanager
from unittest import mock

from bim2sim.elements import bps_elements as bps
from bim2sim.elements import hvac_elements as hvac
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

    def get_setup_simple_boiler(self):
        """Simple generator system made of boiler, pump, expansion tank, distributor and pipes"""
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

    def get_pipe(self):
        pipe = self.element_generator(
            hvac.Pipe,
            diameter=0.02 * ureg.m,
            length=1 * ureg.m
        )
        return HvacGraph([pipe])

    def get_pump(self):
        pump = self.element_generator(
            hvac.Pump,
            rated_volume_flow=1 * ureg.m ** 3 / ureg.s,
            rated_pressure_difference=10000 * ureg.N / (ureg.m ** 2))
        return HvacGraph([pump])

    def get_Boiler(self):
        self.element_generator(hvac.Boiler, ...)

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
        elements = [out_wall_1, window_1, tz_1, build_1]
        return elements
