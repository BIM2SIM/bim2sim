import unittest

from test.kernel.helper import SetupHelper
from bim2sim.kernel import elements
from bim2sim.kernel.hvac.hvac_graph import HvacGraph
from bim2sim.kernel.aggregation import PipeStrand, DeadEnd
from bim2sim.decision import ListDecision

class DeadEndHelper(SetupHelper):

    def get_simple_circuit(self):
        """get a simple circuit with a 4 port pipefitting with open ports,
         some connected pipes and dead ends"""
        flags = {}
        with self.flag_manager(flags):
            fitting_4port = self.element_generator(elements.PipeFitting, flags=['fitting_4port'], n_ports=4, name="fit4")
            fitting_3port_1 = self.element_generator(elements.PipeFitting, flags=['fitting_3port_1'], n_ports=3, name="fit3_1")
            fitting_3port_2 = self.element_generator(elements.PipeFitting, flags=['fitting_3port_2'], n_ports=3, name="fit3_2")
            # fitting_1port = self.element_generator(elements.PipeFitting, flags=['fitting_1port'], n_ports=1, name="fit1")
            pipestrand1 = [self.element_generator(elements.Pipe, length=100, diameter=30, name="ps1") for i in range(1)]
            pipestrand2 = [self.element_generator(elements.Pipe, length=100, diameter=30, name="ps2") for i in range(1)]
            pipestrand3 = [self.element_generator(elements.Pipe, length=100, diameter=30, name="ps3") for i in range(1)]
            pipestrand4 = [self.element_generator(elements.Pipe, length=100, diameter=30, name="ps4") for i in range(1)]
            pipestrand5 = [self.element_generator(elements.Pipe, length=100, diameter=30, name="ps5") for i in range(1)]
            pipestrand6 = [self.element_generator(elements.Pipe, length=100, diameter=30, name="ps6") for i in range(1)]

            self.connect_strait([*pipestrand1])
            self.connect_strait([*pipestrand2])
            self.connect_strait([*pipestrand3])
            self.connect_strait([*pipestrand4])
            self.connect_strait([*pipestrand5])
            self.connect_strait([*pipestrand6])
            fitting_4port.ports[0].connect(pipestrand1[0].ports[0])
            fitting_4port.ports[1].connect(pipestrand2[0].ports[0])
            fitting_4port.ports[2].connect(pipestrand3[0].ports[0])
            # fitting_1port.ports[0].connect(pipestrand1[-1].ports[-1])
            pipestrand2[-1].ports[-1].connect(fitting_3port_1.ports[0])
            fitting_3port_1.ports[1].connect(pipestrand4[0].ports[0])
            fitting_3port_1.ports[2].connect(pipestrand5[0].ports[0])
            fitting_3port_2.ports[0].connect(pipestrand4[-1].ports[-1])
            fitting_3port_2.ports[1].connect(pipestrand5[-1].ports[-1])
            fitting_3port_2.ports[2].connect(pipestrand6[0].ports[0])





            circuit = [*pipestrand1, *pipestrand2, *pipestrand3, *pipestrand4, *pipestrand5, *pipestrand6,
                       fitting_4port, fitting_3port_1, fitting_3port_2]
            # circuit = [*pipestrand1, *pipestrand2, *pipestrand3, *pipestrand4, *pipestrand5, *pipestrand6,
            #            fitting_4port, fitting_3port_1, fitting_3port_2, fitting_1port]

            graph = HvacGraph(circuit)
            return graph, flags

class TestParallelPumps(unittest.TestCase):
    helper = None

    @classmethod
    def setUpClass(cls):
        cls.helper = DeadEndHelper()

    def tearDown(self) -> None:
        self.helper.reset()

    def test_dead_end_identification(self):
        graph, flags = self.helper.get_simple_circuit()
        # graph.plot('D:/testing/')
        # graph.plot('D:/10_ProgramTesting/before', ports=True)

        uncoupled_graph = graph.copy()
        element_graph = uncoupled_graph.element_graph
        for node in element_graph.nodes:
            inner_edges = node.get_inner_connections()
            uncoupled_graph.remove_edges_from(inner_edges)

        # find first class dead ends (open ports)
        dead_ends_fc = [v for v, d in uncoupled_graph.degree() if d == 0]
        # todo: what do we do with dead elements: no open ports but no usage (e.g. pressure expansion tanks)
        remove_ports = []
        for dead_end in dead_ends_fc:
            if len(dead_end.parent.ports) > 2:
                # dead end at > 2 ports -> remove port but keep element
                # todo add collectable decision here for single element
                remove_ports.append([dead_end])
                continue
            else:
                remove_ports_strand = []
                # find if there are more elements in strand to be removed
                strand = HvacGraph.get_path_without_junctions(graph, dead_end, include_edges=True)
                for port in strand:
                    remove_ports_strand.append(port)
                remove_ports.append(remove_ports_strand)

        for rm_list in remove_ports:
            ListDecision(
                "Found possible Dead End:",
                choices=[[cls.ifc_type, "Match: '" + ",".join(cls.filter_for_text_fracments(k)) + "' in " + " or ".join(
                    ["'%s'" % txt for txt in [k.Name, k.Description] if txt])] for cls in v],
                output=answers,
                output_key=k,
                global_key="%s.%s" % (k.is_a(), k.GlobalId),
                allow_skip=True, allow_load=True, allow_save=True,
                collect=True, quick_decide=not True)

        # flat remove list
        remove_ports = [rm_port for rm_list in remove_ports for rm_port in rm_list]
        for rm_port in remove_ports:
                print("dead end port: %s - parent: %s" % (rm_port, rm_port.parent.name))
        print(remove_ports)
        print('finished')
        graph.remove_nodes_from([n for n in graph if n in set(remove_ports)])
        graph.plot('D:/10_ProgramTesting/after', ports=True)

        # create subgraph with only remove list

