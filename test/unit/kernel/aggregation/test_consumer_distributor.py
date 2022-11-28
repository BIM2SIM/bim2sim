import unittest


from bim2sim.kernel.elements import hvac
from bim2sim.kernel.hvac.hvac_graph import HvacGraph
from bim2sim.kernel import aggregation
from test.unit.kernel.helper import SetupHelperHVAC

import networkx as nx


class ConsumerDistributorHelper(SetupHelperHVAC):

    def get_setup_con_dist(self):
        """Get a simple setup to test ConsumerHeatingDistributorModule.

        Setup includes the following components:
        * 1 Distributor with 4 ports
        * 1 Consumer connected with 3 pipe each (flow and return) to Distributor
        * 1 Boiler connected with 3 pipe each (flow and return) to Distributor
        """
        flags = {}
        with self.flag_manager(flags):
            # generator circuit
            con_vl = [self.element_generator(
                hvac.Pipe, length=100, diameter=30) for i in range(1)]
            con_rl = [self.element_generator(
                hvac.Pipe, length=100, diameter=30) for i in range(1)]
            consumer = self.element_generator(
                hvac.SpaceHeater, flags=['spaceheater'])
            boil_vl = [self.element_generator(
                hvac.Pipe, length=100, diameter=30) for i in range(1)]
            boil_rl = [self.element_generator(
                hvac.Pipe, length=100, diameter=30) for i in range(1)]
            boiler = self.element_generator(
                hvac.Boiler, n_ports=2, flags=['boiler'],)
            distributor = self.element_generator(
                hvac.Distributor, n_ports=4, flags=["distributor"])

        # connect elements
        self.connect_strait([*con_vl, consumer, *con_rl])
        self.connect_strait([*boil_rl, boiler, *boil_vl])
        # boiler.ports[0].connect(boiler.ports[1])

        boil_vl[-1].ports[-1].connect(distributor.ports[0])
        distributor.ports[1].connect(boil_rl[0].ports[0])
        distributor.ports[2].connect(con_vl[0].ports[0])
        distributor.ports[3].connect(con_rl[-1].ports[-1])

        circuit = [
            *con_vl, *con_rl, consumer, *boil_vl, *boil_rl, boiler, distributor]

        graph = HvacGraph(circuit)
        return graph, flags


class TestConsumerDistributorModule(unittest.TestCase):
    helper = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.helper = ConsumerDistributorHelper()

    def tearDown(self) -> None:
        self.helper.reset()

    def test_find_matches(self):
        """TODO"""
        # graph, flags = self.helper.get_setup_con_dist()
        graph2, flags2 = self.helper.get_setup_con_dist()
        # matches1, metas1 = \
        #     aggregation.ConsumerHeatingDistributorModule.find_matches(graph)
        matches2, metas2 = \
            aggregation.ConsumerHeatingDistributorModule.find_matches2(graph2)

        # edge_ports = aggregation.ConsumerHeatingDistributorModule.get_edge_ports2(graph2, matches2[0])
        module = aggregation.ConsumerHeatingDistributorModule(
            matches2[0].element_graph, **metas2[0])
        print('test')



