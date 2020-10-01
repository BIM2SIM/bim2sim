import unittest

from bim2sim.kernel import aggregation
from bim2sim.kernel import elements
from bim2sim.kernel.hvac.hvac_graph import HvacGraph

from bim2sim.kernel.units import ureg

from test.kernel.helper import SetupHelper

import networkx as nx


class GeneratorHelper(SetupHelper):

    def get_setup_boiler_with_bypass(self):
        """Simple generator system made of boiler, pump, bypass, expansion
        tank, distributor and pipes"""
        flags = {}
        with self.flag_manager(flags):
            # generator circuit
            boiler = self.element_generator(elements.Boiler, rated_power=200)
            gen_vl_a = [
                self.element_generator(elements.Pipe, length=100, diameter=40)
                for i in range(3)]
            h_pump = self.element_generator(elements.Pump, rated_power=2.2,
                                            rated_height=12,
                                            rated_volume_flow=8)
            gen_vl_b1 = [self.element_generator(elements.Pipe, flags=[
                'strand1'],
                                               length=100, diameter=40) for i in
                        range(2)]
            gen_vl_b2 = [self.element_generator(elements.Pipe, flags=[
                'strand1'],
                                               length=100, diameter=40) for i in
                        range(3)]
            distributor = self.element_generator(elements.Distributor, flags=[
                'distributor'], n_ports=3)  # , volume=80
            gen_rl_a = [
                self.element_generator(elements.Pipe, length=100, diameter=40)
                for i in range(4)]
            fitting = self.element_generator(elements.PipeFitting, n_ports=3,
                                             diameter=40, length=60)
            fitting_bp_1 = self.element_generator(elements.PipeFitting, n_ports=3,
                                             diameter=40, length=60)
            fitting_bp_2 = self.element_generator(elements.PipeFitting, n_ports=3,
                                             diameter=40, length=60)
            gen_rl_b1 = [
                self.element_generator(elements.Pipe, length=100, diameter=40)
                for i in range(2)]
            gen_rl_b2 = [
                self.element_generator(elements.Pipe, length=100, diameter=40)
                for i in range(2)]
            gen_rl_c = [
                self.element_generator(elements.Pipe, flags=['strand2'],
                                       length=(1 + i) * 40, diameter=15)
                for i in range(3)
            ]
            tank = self.element_generator(elements.Storage, n_ports=1)
            bypass = [self.element_generator(
                elements.Pipe, flags=['bypass'], length=60, diameter=30) for
                i in range(3)]
        # connect
        gen_vl = [boiler, *gen_vl_a, h_pump]
        self.connect_strait(gen_vl)
        self.connect_strait([h_pump, *gen_rl_b1, fitting_bp_1])
        self.connect_strait([fitting_bp_1, *gen_rl_b2, distributor])
        self.connect_strait([distributor, *gen_rl_a, fitting])
        self.connect_strait([fitting, *gen_vl_b1, fitting_bp_2])
        self.connect_strait([fitting_bp_2, *gen_vl_b2, boiler])
        self.connect_strait([*gen_rl_c, tank])
        self.connect_strait([*bypass])
        fitting.ports[2].connect(gen_rl_c[0].ports[0])
        fitting_bp_1.ports[2].connect(bypass[0].ports[0])
        fitting_bp_2.ports[2].connect(bypass[-1].ports[-1])

        # full system
        gen_circuit = [
            boiler, *gen_vl_a, h_pump, *gen_vl_b1, *gen_vl_b2,  distributor,
            *gen_rl_a, fitting, fitting_bp_1, fitting_bp_2, *bypass, *gen_rl_b1,
            *gen_rl_b2, *gen_rl_c, tank
        ]

        return HvacGraph(gen_circuit), flags

    # todo
    def get_setup_two_seperate_boilers(self):
        """Simple generator system made of boiler, pump, bypass, expansion
        tank, distributor and pipes, bufferstorage"""
        flags = {}
        with self.flag_manager(flags):
            # generator circuit 1
            boiler = self.element_generator(elements.Boiler, rated_power=200)
            gen_vl_a = [
                self.element_generator(elements.Pipe, length=100, diameter=40)
                for i in range(3)]
            h_pump = self.element_generator(elements.Pump, rated_power=2.2,
                                            rated_height=12,
                                            rated_volume_flow=8)
            gen_vl_b1 = [self.element_generator(elements.Pipe, flags=[
                'strand1'],
                                               length=100, diameter=40) for i in
                        range(2)]
            gen_vl_b2 = [self.element_generator(elements.Pipe, flags=[
                'strand1'],
                                               length=100, diameter=40) for i in
                        range(3)]
            distributor = self.element_generator(elements.Distributor, flags=[
                'distributor'], n_ports=4)  # , volume=80
            gen_rl_a = [
                self.element_generator(elements.Pipe, length=100, diameter=40)
                for i in range(4)]
            fitting = self.element_generator(elements.PipeFitting, n_ports=3,
                                             diameter=40, length=60)
            fitting_bp_1 = self.element_generator(elements.PipeFitting, n_ports=3,
                                             diameter=40, length=60)
            fitting_bp_2 = self.element_generator(elements.PipeFitting, n_ports=3,
                                             diameter=40, length=60)
            gen_rl_b1 = [
                self.element_generator(elements.Pipe, length=100, diameter=40)
                for i in range(2)]
            gen_rl_b2 = [
                self.element_generator(elements.Pipe, length=100, diameter=40)
                for i in range(2)]
            gen_rl_c = [
                self.element_generator(elements.Pipe, flags=['strand2'],
                                       length=(1 + i) * 40, diameter=15)
                for i in range(3)
            ]
            tank = self.element_generator(elements.Storage, n_ports=1)
            bypass = [self.element_generator(
                elements.Pipe, flags=['bypass'], length=60, diameter=30) for
                i in range(3)]
        # connect
        gen_vl = [boiler, *gen_vl_a, h_pump]
        self.connect_strait(gen_vl)
        self.connect_strait([h_pump, *gen_rl_b1, fitting_bp_1])
        self.connect_strait([fitting_bp_1, *gen_rl_b2, distributor])
        self.connect_strait([distributor, *gen_rl_a, fitting])
        self.connect_strait([fitting, *gen_vl_b1, fitting_bp_2])
        self.connect_strait([fitting_bp_2, *gen_vl_b2, boiler])
        self.connect_strait([*gen_rl_c, tank])
        self.connect_strait([*bypass])
        fitting.ports[2].connect(gen_rl_c[0].ports[0])
        fitting_bp_1.ports[2].connect(bypass[0].ports[0])
        fitting_bp_2.ports[2].connect(bypass[-1].ports[-1])

        # generator circuit 2
        with self.flag_manager(flags):
            boiler2 = self.element_generator(elements.Boiler, rated_power=200)
            gen_vl_a2 = [
                self.element_generator(elements.Pipe, length=100, diameter=40)
                for i in range(3)]
            h_pump2 = self.element_generator(elements.Pump, rated_power=2.2,
                                            rated_height=12,
                                            rated_volume_flow=8)
            gen_vl_b12 = [self.element_generator(elements.Pipe, flags=[
                'strand12'],
                                                length=100, diameter=40) for i in
                         range(2)]
            gen_vl_b22 = [self.element_generator(elements.Pipe, flags=[
                'strand12'],
                                                length=100, diameter=40) for i in
                         range(3)]
            distributor2 = self.element_generator(elements.Distributor, flags=[
                'distributor2'], n_ports=4)  # , volume=80
            gen_rl_a2 = [
                self.element_generator(elements.Pipe, length=100, diameter=40)
                for i in range(4)]
            fitting2 = self.element_generator(elements.PipeFitting, n_ports=3,
                                             diameter=40, length=60)
            fitting_bp_12 = self.element_generator(elements.PipeFitting, n_ports=3,
                                                  diameter=40, length=60)
            fitting_bp_22 = self.element_generator(elements.PipeFitting, n_ports=3,
                                                  diameter=40, length=60)
            gen_rl_b12 = [
                self.element_generator(elements.Pipe, length=100, diameter=40)
                for i in range(2)]
            gen_rl_b22 = [
                self.element_generator(elements.Pipe, length=100, diameter=40)
                for i in range(2)]
            gen_rl_c2 = [
                self.element_generator(elements.Pipe, flags=['strand22'],
                                       length=(1 + i) * 40, diameter=15)
                for i in range(3)
            ]
            tank2 = self.element_generator(elements.Storage, n_ports=1)
            bypass2 = [self.element_generator(
                elements.Pipe, flags=['bypass2'], length=60, diameter=30) for
                i in range(3)]
        # connect

        gen_vl2 = [boiler2, *gen_vl_a2, h_pump2]
        self.connect_strait(gen_vl2)
        self.connect_strait([h_pump2, *gen_rl_b12, fitting_bp_12])
        self.connect_strait([fitting_bp_12, *gen_rl_b22, distributor2])
        self.connect_strait([distributor2, *gen_rl_a2, fitting2])
        self.connect_strait([fitting2, *gen_vl_b12, fitting_bp_22])
        self.connect_strait([fitting_bp_22, *gen_vl_b22, boiler2])
        self.connect_strait([*gen_rl_c2, tank2])
        self.connect_strait([*bypass2])
        fitting2.ports[2].connect(gen_rl_c2[0].ports[0])
        fitting_bp_12.ports[2].connect(bypass2[0].ports[0])
        fitting_bp_22.ports[2].connect(bypass2[-1].ports[-1])

        # connection between two systems
        with self.flag_manager(flags):
            con_sys_1_vl = [
                self.element_generator(elements.Pipe, length=100, diameter=40)
                for i in range(2)]
            con_sys_2_vl = [
                self.element_generator(elements.Pipe, length=100, diameter=40)
                for i in range(2)]
            con_sys_1_rl = [
                self.element_generator(elements.Pipe, length=100, diameter=40)
                for i in range(2)]
            con_sys_2_rl = [
                self.element_generator(elements.Pipe, length=100, diameter=40)
                for i in range(2)]
            con_fitting_vl = self.element_generator(elements.PipeFitting,
                                                 n_ports=3,
                                             diameter=40, length=60)
            con_fitting_rl = self.element_generator(elements.PipeFitting,
                                                 n_ports=3,
                                             diameter=40, length=60)
            dead_end_vl = [
                self.element_generator(elements.Pipe, length=100, diameter=40)
                for i in range(2)]
            dead_end_rl = [
                self.element_generator(elements.Pipe, length=100, diameter=40)
                for i in range(2)]
        self.connect_strait([*con_sys_1_vl])
        self.connect_strait([*con_sys_2_vl])
        self.connect_strait([*con_sys_1_rl])
        self.connect_strait([*con_sys_2_rl])
        self.connect_strait([*dead_end_vl])
        self.connect_strait([*dead_end_rl])
        con_fitting_vl.ports[0].connect(con_sys_1_vl[-1].ports[-1])
        con_fitting_vl.ports[1].connect(con_sys_2_vl[-1].ports[-1])
        con_fitting_vl.ports[2].connect(dead_end_vl[0].ports[0])
        con_fitting_rl.ports[0].connect(dead_end_rl[-1].ports[-1])
        con_fitting_rl.ports[1].connect(con_sys_1_rl[0].ports[0])
        con_fitting_rl.ports[2].connect(con_sys_2_rl[0].ports[0])
        distributor.ports[2].connect(con_sys_1_vl[0].ports[0])
        distributor.ports[3].connect(con_sys_1_rl[-1].ports[-1])
        distributor2.ports[2].connect(con_sys_2_vl[0].ports[0])
        distributor2.ports[3].connect(con_sys_2_rl[-1].ports[-1])


        # full system
        gen_circuit = [
            boiler, *gen_vl_a, h_pump, *gen_vl_b1, *gen_vl_b2,  distributor,
            *gen_rl_a, fitting, fitting_bp_1, fitting_bp_2, *bypass, *gen_rl_b1,
            *gen_rl_b2, *gen_rl_c, tank,
            boiler2, *gen_vl_a2, h_pump2, *gen_vl_b12, *gen_vl_b22,
            distributor2,
            *gen_rl_a2, fitting2, fitting_bp_12, fitting_bp_22, *bypass2,
            *gen_rl_b12,
            *gen_rl_b22, *gen_rl_c2, tank2, *con_sys_1_vl, *con_sys_2_vl,
            *con_sys_1_rl, *con_sys_2_rl, *dead_end_vl, *dead_end_rl,
            con_fitting_vl, con_fitting_rl,

        ]

        return HvacGraph(gen_circuit), flags

class TestGeneratorAggregation(unittest.TestCase):
    helper = None

    @classmethod
    def setUpClass(cls):
        cls.helper = GeneratorHelper()

    def tearDown(self) -> None:
        self.helper.reset()

    def test_detection_simple_boiler(self):
        graph, flags = self.helper.get_setup_simple_boiler()
        # graph.plot()
        # import matplotlib.pyplot as plt
        # plt.show()
        matches, meta = aggregation.Generator_One_Fluid.find_matches(graph)

    def test_detection_boiler_with_bypass(self):
        graph, flags = self.helper.get_setup_boiler_with_bypass()
        graph.plot(r'c:/temp')
        matches, meta = aggregation.Generator_One_Fluid.find_matches(graph)

    def test_simple_boiler(self):
        graph, flags = self.helper.get_setup_simple_boiler()
        graph.plot(r'c:/temp/')
        matches, meta = aggregation.Generator_One_Fluid.find_matches(graph)
        self.assertEqual(len(matches), 1)
        agg_generator = aggregation.Generator_One_Fluid(
            "Test", matches[0], **meta[0])
        mapping = agg_generator.get_replacement_mapping()
        graph.merge(
            mapping=agg_generator.get_replacement_mapping(),
            inner_connections=agg_generator.get_inner_connections(),
        )
        graph.plot(r'c:/temp/')

    def test_two_simple_boiler_with_bypass(self):
        graph, flags = self.helper.get_setup_two_seperate_boilers()
        graph.plot(r'c:/temp/')
        matches, meta = aggregation.Generator_One_Fluid.find_matches(graph)
el
        agg_generators = []
        self.assertEqual(len(matches), 2)
        for e, match in enumerate(matches):
            agg_generator = aggregation.Generator_One_Fluid(
                "Test basics", matches[e], **meta[e])
            agg_generators.append(agg_generator)
        if len(agg_generators) == 0:
            self.assertTrue(False, 'Kein Generator Kreis idendifiziert!')

        mappings = []
        for agg_generator in agg_generators[::-1]:
            mapping = agg_generator.get_replacement_mapping()
            mappings.append(mapping)
            graph.merge(
                mapping=agg_generator.get_replacement_mapping(),
                inner_connections=agg_generator.get_inner_connections(),
            )
        graph.plot(r'c:/temp/')
        print('test')


# test cases:
# normal
# bypass
# distributor
# storage




if __name__ == '__main__':
    unittest.main()
