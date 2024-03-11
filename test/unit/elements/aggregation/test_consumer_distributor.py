import unittest

import bim2sim.elements.aggregation.hvac_aggregations
from bim2sim.elements import aggregation
from bim2sim.elements import hvac_elements as hvac
from bim2sim.elements.graphs.hvac_graph import HvacGraph
from test.unit.elements.helper import SetupHelperHVAC


class ConsumerDistributorHelper(SetupHelperHVAC):

    def get_setup_con_dist1(self):
        """ Get a simple setup to test ConsumerHeatingDistributorModule.

        The setup includes the following components:
        * 1 Distributor with 4 ports
        * 1 Consumer connected with 3 pipe each (flow and return) to
            Distributor
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
        boil_vl[-1].ports[-1].connect(distributor.ports[0])
        distributor.ports[1].connect(boil_rl[0].ports[0])
        distributor.ports[2].connect(con_vl[0].ports[0])
        distributor.ports[3].connect(con_rl[-1].ports[-1])

        flags['edge_ports'] = [distributor.ports[0], distributor.ports[1]]

        circuit = [
            *con_vl, *con_rl, consumer, *boil_vl, *boil_rl, boiler, distributor]

        graph = HvacGraph(circuit)
        return graph, flags

    def get_setup_con_dist2(self):
        """ Get a simple setup to test ConsumerHeatingDistributorModule with
            undefined consumer ports.

        The setup includes the following components:
        * 1 Distributor with 6 ports, 2 of them unconnected
        * 1 Consumer connected with 3 pipe each (flow and return) to
            Distributor
        * 1 Boiler connected with 3 pipe each (flow and return) to Distributor
        """
        flags = {}
        with self.flag_manager(flags):
            # generator circuit
            boil_vl = [self.element_generator(
                hvac.Pipe, length=100, diameter=30) for i in range(1)]
            boil_rl = [self.element_generator(
                hvac.Pipe, length=100, diameter=30) for i in range(1)]
            boiler = self.element_generator(
                hvac.Boiler, n_ports=2, flags=['boiler'], )
            # consumer circuit
            con_vl = [self.element_generator(
                hvac.Pipe, length=100, diameter=30, flags=['PipeCon'])
                for i in range(1)]
            con_rl = [self.element_generator(
                hvac.Pipe, length=100, diameter=30, flags=['PipeCon'])
                for i in range(1)]
            consumer = self.element_generator(
                hvac.SpaceHeater, flags=['spaceheater'])
            distributor = self.element_generator(
                hvac.Distributor, n_ports=6, flags=["distributor"])
            # undefined circuit
            undef_vl = [self.element_generator(
                hvac.Pipe, length=100, diameter=30) for i in range(1)]
            undef_rl = [self.element_generator(
                hvac.Pipe, length=100, diameter=30) for i in range(1)]

        # connect elements
        self.connect_strait([*con_vl, consumer, *con_rl])
        self.connect_strait([*boil_rl, boiler, *boil_vl])
        boil_vl[-1].ports[-1].connect(distributor.ports[0])
        distributor.ports[1].connect(boil_rl[0].ports[0])
        distributor.ports[2].connect(con_vl[0].ports[0])
        distributor.ports[3].connect(con_rl[-1].ports[-1])
        distributor.ports[4].connect(undef_vl[0].ports[0])
        distributor.ports[5].connect(undef_rl[-1].ports[-1])

        flags['edge_ports'] = [distributor.ports[0], distributor.ports[1]]
        flags['undefined_consumer_ports'] = [distributor.ports[4],
                                             distributor.ports[5]]

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
        """ Test the find matches method."""
        graph, flags = self.helper.get_setup_con_dist1()
        con_heat_dist_mod = bim2sim.elements.aggregation.hvac_aggregations.ConsumerHeatingDistributorModule
        matches, metas = con_heat_dist_mod.find_matches(graph)
        self.assertEqual(
            len(matches), 1,
            "There is 1 case for ConsumerDistrubtorModule Cycles but "
            "'find_matches' returned %d" % len(matches)
        )

        module = bim2sim.elements.aggregation.hvac_aggregations.ConsumerHeatingDistributorModule(
            graph, matches[0], **metas[0])
        module_elements = [item for item in flags['spaceheater']
                           + flags['distributor'] + flags['PipeCon']]
        edge_ports_originals = [
            edge_port.originals for edge_port in module.get_ports()]
        self.assertNotEqual(edge_ports_originals, flags['edge_ports'])
        self.assertCountEqual(module.elements, module_elements)

    def test_aggregation(self):
        """ Test the aggregation of consumer heating distribution module."""
        graph, flags = self.helper.get_setup_con_dist1()
        con_heat_dist_mod = bim2sim.elements.aggregation.hvac_aggregations.ConsumerHeatingDistributorModule
        matches, metas = con_heat_dist_mod.find_matches(graph)
        for match, meta in zip(matches, metas):
            module = bim2sim.elements.aggregation.hvac_aggregations.ConsumerHeatingDistributorModule(
                graph, match, **meta)
            edge_ports = [edge_port.originals[0] for edge_port in
                          module.get_ports()]
            self.assertEqual(set(edge_ports), set(flags['edge_ports']))
            graph.merge(
                mapping=module.get_replacement_mapping(),
                inner_connections=module.inner_connections
            )

        aggregated_con_heat_dis_mod = [
            ele for ele in graph.elements
            if ele.__class__.__name__ == 'ConsumerHeatingDistributorModule']
        self.assertEqual(len(aggregated_con_heat_dis_mod), 1)

    def test_aggregation2(self):
        """ Test the aggregation of consumer heating distribution module and
            detection of undefined consumer ports."""
        graph, flags = self.helper.get_setup_con_dist2()
        con_heat_dist_mod = bim2sim.elements.aggregation.hvac_aggregations.ConsumerHeatingDistributorModule
        matches, metas = con_heat_dist_mod.find_matches(graph)
        for match, meta in zip(matches, metas):
            module = bim2sim.elements.aggregation.hvac_aggregations.ConsumerHeatingDistributorModule(
                graph, match, **meta)
            graph.merge(
                mapping=module.get_replacement_mapping(),
                inner_connections=module.inner_connections
            )

        aggregated_con_heat_dis_mod = [
            ele for ele in graph.elements
            if ele.__class__.__name__ == 'ConsumerHeatingDistributorModule']
        self.assertEqual(len(aggregated_con_heat_dis_mod), 1)
        self.assertEqual(flags['undefined_consumer_ports'],
                         metas[0]['undefined_consumer_ports'])


if __name__ == '__main__':
    unittest.main()
