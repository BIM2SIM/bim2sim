from unittest import mock
from contextlib import contextmanager

from bim2sim.kernel.element import Element, Port, Root
from bim2sim.kernel import elements
from bim2sim.kernel.hvac.hvac_graph import HvacGraph


class SetupHelper:

    ifc = mock.Mock()
    ifc.Name = 'Test'
    ifc.HasAssignments = []
    type(ifc).GlobalId = mock.PropertyMock(side_effect=range(100000), name='GlobalId')

    def __init__(self):
        self._flags = None
        self.elements = []

        # self.setup, self.flags = self.get_setup()
        # self.setup.plot(r'c:\temp')

    def reset(self) -> None:
        for r in Root.objects.copy().values():
            r.discard()

        self.elements.clear()
        # self.setup = None
        # self.flags.clear()

    @contextmanager
    def flag_manager(self, flags):
        self._flags = flags
        yield
        self._flags = None

    @classmethod
    def fake_add_ports(cls, parent, n=2):
        new_ports = [Port(parent=parent, ifc=cls.ifc) for i in range(n)]
        parent.ports.extend(new_ports)
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
        with mock.patch.object(Element, '_add_ports', return_value=None):
            element = element_cls(self.ifc)
        self.elements.append(element)

        # set attributes
        for name, value in kwargs.items():
            if name not in element.attributes.names:
                raise AssertionError("Can't set attribute '%s' to %s. Choices are %s" %
                                     (name, element_cls.__name__, list(element.attributes.names)))
            setattr(element, name, value)

        # add ports
        self.fake_add_ports(element, n_ports)

        # assign flags
        if flags:
            if self._flags is None:
                raise AssertionError("Use contextmanager .flag_manager when setting flags")
            for flag in flags:
                self._flags.setdefault(flag, []).append(element)

        return element

    def get_setup_simple_boiler(self):
        """Simple generator system made of boiler, pump, expansion tank, distributor and pipes"""
        flags = {}
        with self.flag_manager(flags):
            # generator circuit
            boiler = self.element_generator(elements.Boiler, rated_power=200)
            gen_vl_a = [self.element_generator(elements.Pipe, length=100, diameter=40) for i in range(3)]
            h_pump = self.element_generator(elements.Pump, rated_power=2.2, rated_height=12, rated_volume_flow=8)
            gen_vl_b = [self.element_generator(elements.Pipe, flags=['strand1'], length=100, diameter=40) for i in range(5)]
            distributor = self.element_generator(elements.Distributor, flags=['distributor'])  # , volume=80
            gen_rl_a = [self.element_generator(elements.Pipe, length=100, diameter=40) for i in range(4)]
            fitting = self.element_generator(elements.PipeFitting, n_ports=3, diameter=40, length=60)
            gen_rl_b = [self.element_generator(elements.Pipe, length=100, diameter=40) for i in range(4)]
            gen_rl_c = [
                self.element_generator(elements.Pipe, flags=['strand2'], length=(1 + i) * 40, diameter=15)
                for i in range(3)
            ]
            tank = self.element_generator(elements.ExpansionTank, n_ports=1)

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
            if not isinstance(ele, Element):
                return False
        return True
