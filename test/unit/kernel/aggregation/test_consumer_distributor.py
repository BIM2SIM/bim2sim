import unittest

from bim2sim.kernel import aggregation
from bim2sim.kernel.elements import hvac
from bim2sim.kernel.hvac.hvac_graph import HvacGraph
from test.unit.kernel.helper import SetupHelperHVAC


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
                hvac.Pipe, length=100, diameter=30, flags=['PipeCon'])
                for i in range(1)]
            con_rl = [self.element_generator(
                hvac.Pipe, length=100, diameter=30, flags=['PipeCon'])
                for i in range(1)]
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
        """Test the old find matches method, new one in #167 (below)"""
        graph, flags = self.helper.get_setup_con_dist()
        matches, metas = \
            aggregation.ConsumerHeatingDistributorModule.find_matches(graph)
        self.assertEqual(
            len(matches), 1,
            "There is 1 case for ConsumerDistrubtorModule Cycles but "
            "'find_matches' returned %d" % len(matches)
        )

        module = aggregation.ConsumerHeatingDistributorModule(
            matches[0], **metas[0])
        module_elements = \
            [item for item in
             flags['spaceheater']+flags['distributor']+flags['PipeCon']]
        self.assertCountEqual(module.elements, module_elements)

    @unittest.skip("This is WIP")
    def test_find_matches_branch167(self):
        """TODO"""
        graph, flags = self.helper.get_setup_con_dist()
        matches, metas = \
            aggregation.ConsumerHeatingDistributorModule.find_matches2(graph)

        module = aggregation.ConsumerHeatingDistributorModule(
            matches[0].element_graph, **metas[0])
        print('test')

    # @unittest.skip("This is WIP")
    def test_compare_original_vs_167(self):
        graph, flags = self.helper.get_setup_con_dist()
        matches, metas = \
            aggregation.ConsumerHeatingDistributorModule.find_matches(graph)

        module1 = aggregation.ConsumerHeatingDistributorModule(
            matches[0], **metas[0])

        graph, flags = self.helper.get_setup_con_dist()
        matches2, metas2 = \
            aggregation.ConsumerHeatingDistributorModule.find_matches2(graph)
        for match2, meta2 in zip(matches2, metas2):
            edge_ports = \
                aggregation.ConsumerHeatingDistributorModule.get_edge_ports2(
                    graph, match2)

        # module2 = aggregation.ConsumerHeatingDistributorModule(
        #     matches2[0].element_graph, edge_ports)
        print('test')

