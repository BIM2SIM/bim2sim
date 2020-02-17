import unittest
from unittest import mock

from bim2sim.kernel.element import Element, Port, Root


class TestAggregation(unittest.TestCase):
    __test__ = False

    ifc = mock.Mock()
    ifc.Name = 'Test'
    ifc.HasAssignments = []
    type(ifc).GlobalId = mock.PropertyMock(side_effect=range(1000), name='GlobalId')

    @classmethod
    def fake_add_ports(cls, parent, n=2):
        for i in range(n):
            parent.ports.append(Port(parent=parent, ifc=cls.ifc))

    @classmethod
    def tearDownClass(cls) -> None:
        for r in Root.objects.copy().values():
            r.discard()

    def tearDown(self) -> None:
        for port in Port.objects.copy().values():
            port.disconnect()

    @staticmethod
    def connect_strait(items):
        last = None
        for item in items:
            if last:
                last.ports[1].connect(item.ports[0])
            last = item
