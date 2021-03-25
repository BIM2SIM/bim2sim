import unittest
import networkx as nx

from test.kernel.helper import SetupHelper
from bim2sim.kernel import aggregation
from bim2sim.kernel import elements
from bim2sim.kernel.hvac.hvac_graph import HvacGraph
from bim2sim.kernel.units import ureg
from bim2sim import decision
from bim2sim.decision.console import ConsoleFrontEnd as FrontEnd


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
            distributor = self.element_generator(elements.Distributor,
                                                 flags=[
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
            pipe_outer_vl_distr = [self.element_generator(elements.Pipe, flags=['outer_vl'], length=100, diameter=40)
                for i in range(2)]
            pipe_outer_rl_distr = [self.element_generator(elements.Pipe, flags=['outer_rl'],length=100, diameter=40)
                for i in range(2)]

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
        self.connect_strait([*pipe_outer_rl_distr])
        self.connect_strait([*pipe_outer_vl_distr])
        pipe_outer_vl_distr[-1].ports[-1].connect(pipe_outer_rl_distr[0].ports[0])
        distributor.ports[2].connect(pipe_outer_vl_distr[0].ports[0])
        distributor.ports[3].connect(pipe_outer_rl_distr[-1].ports[-1])
        fitting.ports[2].connect(gen_rl_c[0].ports[0])
        fitting_bp_1.ports[2].connect(bypass[0].ports[0])
        fitting_bp_2.ports[2].connect(bypass[-1].ports[-1])

        # full system
        gen_circuit = [
            boiler, *gen_vl_a, h_pump, *gen_vl_b1, *gen_vl_b2,  distributor,
            *gen_rl_a, fitting, fitting_bp_1, fitting_bp_2, *bypass, *gen_rl_b1,
            *gen_rl_b2, *gen_rl_c, tank, *pipe_outer_vl_distr, *pipe_outer_rl_distr
        ]

        return HvacGraph(gen_circuit), flags


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


    def setup_get_two_parallel_boilers(self):
        """Generator system made of two boilers, two pumps,  1 bypass, expansion
        tank, distributor and pipes.

        .. image: two_parallel_boilers_test.png
        """
        flags = {}
        with self.flag_manager(flags):
            # generator circuit
            boiler1 = self.element_generator(elements.Boiler, rated_power=200)
            boiler2 = self.element_generator(elements.Boiler, rated_power=400)
            h_pump1 = self.element_generator(elements.Pump, rated_power=2.2,
                                            rated_height=12,
                                            rated_volume_flow=8)
            h_pump2 = self.element_generator(elements.Pump, rated_power=2.2,
                                            rated_height=12,
                                            rated_volume_flow=8)
            gen_strand1 = [self.element_generator(elements.Pipe, flags=[
                'strand1'], length=100, diameter=40) for i in range(2)]
            gen_strand2 = [self.element_generator(elements.Pipe, flags=[
                'strand2'], length=100, diameter=40) for i in range(3)]
            gen_strand3 = [self.element_generator(elements.Pipe, flags=[
                'strand3'], length=100, diameter=40) for i in range(2)]
            gen_strand4 = [self.element_generator(elements.Pipe, flags=[
                'strand4'], length=100, diameter=40) for i in range(3)]
            gen_strand5 = [self.element_generator(elements.Pipe, flags=[
                'strand5'], length=100, diameter=40) for i in range(2)]
            gen_strand6 = [self.element_generator(elements.Pipe, flags=[
                'strand6'], length=100, diameter=40) for i in range(1)]
            gen_strand7 = [self.element_generator(elements.Pipe, flags=[
                'strand7'], length=100, diameter=40) for i in range(1)]
            gen_strand8 = [self.element_generator(elements.Pipe, flags=[
                'strand8'], length=100, diameter=40) for i in range(1)]
            gen_strand9 = [self.element_generator(elements.Pipe, flags=[
                'strand9'], length=100, diameter=40) for i in range(1)]
            gen_strand10 = [self.element_generator(elements.Pipe, flags=[
                'strand10'], length=100, diameter=40) for i in range(1)]
            gen_strand11 = [self.element_generator(elements.Pipe, flags=[
                'strand11'], length=100, diameter=40) for i in range(3)]
            distributor = self.element_generator(
                elements.Distributor, flags=['distributor'], n_ports=4)
            fitting1 = self.element_generator(elements.PipeFitting, n_ports=3,
                                             diameter=40, length=60)
            fitting2 = self.element_generator(elements.PipeFitting, n_ports=3,
                                             diameter=40, length=60)
            fitting3 = self.element_generator(elements.PipeFitting, n_ports=3,
                                             diameter=40, length=60)
            fitting4 = self.element_generator(elements.PipeFitting, n_ports=3,
                                             diameter=40, length=60)
            pipe_outer_vl_distr = [self.element_generator(elements.Pipe, flags=['outer_vl'], length=100, diameter=40)
                for i in range(2)]
            pipe_outer_rl_distr = [self.element_generator(elements.Pipe, flags=['outer_rl'],length=100, diameter=40)
                for i in range(2)]
            # todo tank = self.element_generator(elements.Storage, n_ports=1)

        # connect
        gen_dis = [*gen_strand1, distributor, *gen_strand2]
        gen_boi1 = [
            *gen_strand3, h_pump2, *gen_strand4, boiler2, *gen_strand5]
        gen_boi2_rl = [*gen_strand6, h_pump1, *gen_strand7]
        gen_boi2 = [*gen_strand8, boiler1, *gen_strand9]
        self.connect_strait(gen_dis)
        self.connect_strait(gen_boi1)
        self.connect_strait(gen_boi2_rl)
        self.connect_strait(gen_boi2)
        self.connect_strait([*gen_strand10])
        self.connect_strait([*gen_strand11])
        self.connect_strait([*pipe_outer_vl_distr, *pipe_outer_rl_distr])
        fitting1.ports[0].connect(gen_strand1[0].ports[0])
        gen_strand2[-1].ports[-1].connect(fitting2.ports[0])
        fitting2.ports[1].connect(gen_strand3[0].ports[0])
        gen_strand5[-1].ports[-1].connect(fitting1.ports[1])
        fitting2.ports[2].connect(gen_strand6[0].ports[0])
        gen_strand7[-1].ports[-1].connect(fitting3.ports[0])
        fitting3.ports[1].connect(gen_strand8[0].ports[0])
        gen_strand9[-1].ports[-1].connect(fitting4.ports[0])
        fitting4.ports[1].connect(gen_strand10[0].ports[0])
        gen_strand10[-1].ports[-1].connect(fitting1.ports[2])
        fitting3.ports[2].connect(gen_strand11[0].ports[0])
        gen_strand11[-1].ports[-1].connect(fitting4.ports[2])
        distributor.ports[2].connect(pipe_outer_vl_distr[0].ports[0])
        distributor.ports[3].connect(pipe_outer_rl_distr[-1].ports[-1])
        # full system
        gen_circuit = [
            distributor, *gen_strand1, *gen_strand2, *gen_strand3, *gen_strand4,
            *gen_strand5, *gen_strand6, *gen_strand7, *gen_strand8,
            *gen_strand9, *gen_strand10, *gen_strand11, boiler1, boiler2,
            fitting1, fitting2, fitting3, fitting4, h_pump1, h_pump2,
            *pipe_outer_vl_distr, *pipe_outer_rl_distr
        ]

        return HvacGraph(gen_circuit), flags


class TestGeneratorAggregation(unittest.TestCase):
    frontend = FrontEnd()
    helper = None
    _backup = None

    @classmethod
    def setUpClass(cls):
        cls._backup = decision.Decision.frontend
        decision.Decision.set_frontend(cls.frontend)
        cls.helper = GeneratorHelper()

    @classmethod
    def tearDownClass(cls):
        decision.Decision.set_frontend(cls._backup)

    def tearDown(self):
        decision.Decision.all.clear()
        decision.Decision.stored_decisions.clear()
        self.helper.reset()

    def test_simple_boiler_with_bypass(self):
        graph, flags = self.helper.get_setup_boiler_with_bypass()
        # todo remove before merge
        graph.plot(r'D:/10_ProgramTesting/before')
        matches, metas = aggregation.Generator_One_Fluid.find_matches(graph)
        self.assertEqual(
            len(matches), 1,
            "There is 1 case for generation cycles but 'find_matches' "
            "returned %d" % len(matches)
        )
        agg_generator = aggregation.Generator_One_Fluid(
            "Test", matches[0], **metas[0])
        print(agg_generator.rated_power)
        self.assertEqual(agg_generator.rated_power, 200 * ureg.kilowatt)
        self.assertTrue(agg_generator.has_pump,
                        "No pump was found in generator cycle but there should"
                        " be one existing")
        with decision.Decision.debug_answer(True):
            self.assertTrue(agg_generator.has_bypass,
                            "No bypass was found in generator cycle but there should"
                            " be one existing")
        graph.merge(
            mapping=agg_generator.get_replacement_mapping(),
            inner_connections=agg_generator.get_inner_connections(),
        )
        # todo remove before merge
        graph.plot(r'D:/10_ProgramTesting/after')

    # todo finish
    def test_two_simple_boiler_with_bypass(self):
        graph, flags = self.helper.get_setup_two_seperate_boilers()
        graph.plot(r'D:/10_ProgramTesting/before')
        matches, meta = aggregation.Generator_One_Fluid.find_matches(graph)

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
        graph.plot(r'D:/10_ProgramTesting/after')
        print('test')

    # todo
    def test_two_parallel_boilers_with_bypass(self):
        graph, flags = self.helper.setup_get_two_parallel_boilers()
        graph.plot(r'D:/10_ProgramTesting/before')
        matches, metas = aggregation.Generator_One_Fluid.find_matches(graph)
        self.assertEqual(
            len(matches), 2,
            "There are 2 generation cycles but 'find_matches' "
            "returned %d" % len(matches)
        )
        name_builder = '{} {}'
        i = 0
        agg_generators = []
        for match, meta in zip(matches, metas):
            agg_generator = aggregation.Generator_One_Fluid(
                name_builder.format('generator', i+1), match, **meta)
            i += 1
            agg_generators.append(agg_generator)
        # todo fix
        print(agg_generator.rated_power)
        # self.assertEqual(agg_generator.rated_power, 200 * ureg.kilowatt)
        # self.assertTrue(agg_generator.has_pump,
        #                 "No pump was found in generator cycle but there should"
        #                 " be one existing")
        # with decision.Decision.debug_answer(True):
        #     self.assertTrue(agg_generator.has_bypass,
        #                     "No bypass was found in generator cycle but there should"
        #                     " be one existing")
        for agg_generator in agg_generators:
            graph.merge(
                mapping=agg_generator.get_replacement_mapping(),
                inner_connections=agg_generator.get_inner_connections(),
            )
            graph.plot(r'D:/10_ProgramTesting/after')
        # # todo remove before merge
        # graph.plot(r'D:/10_ProgramTesting/after')

# test cases:
# normal
# bypass
# distributor
# storage




if __name__ == '__main__':
    unittest.main()
