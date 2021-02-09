from bim2sim.task.base import Task, ITask
from bim2sim.decision import Decision, ListDecision
from bim2sim.task.hvac import hvac_graph


class Reduce(ITask):
    """Analyses graph network for dead ends"""

    reads = ('graph', )
    touches = ('graph', )

    @Task.log
    def run(self, workflow, graph):
        self.logger.info("Inspecting for dead ends")
        dead_ends_fc = self.identify_deadends(graph)
        self.logger.info("Found %s possible dead ends in network." % len(dead_ends_fc))
        graph, n_removed = self.decide_deadends(graph, dead_ends_fc)
        self.logger.info("Removed %s ports due to found dead ends." % n_removed)
        return graph

    @staticmethod
    def identify_deadends(graph: hvac_graph.HvacGraph):

        uncoupled_graph = graph.copy()
        element_graph = uncoupled_graph.element_graph
        for node in element_graph.nodes:
            inner_edges = node.get_inner_connections()
            uncoupled_graph.remove_edges_from(inner_edges)

        # find first class dead ends (open ports)
        dead_ends_fc = [v for v, d in uncoupled_graph.degree() if d == 0]
        return dead_ends_fc

    @staticmethod
    def decide_deadends(graph: hvac_graph.HvacGraph, dead_ends_fc):
        # todo: what do we do with dead elements: no open ports but no usage (e.g. pressure expansion tanks)
        remove_ports = {}
        for dead_end in dead_ends_fc:
            if len(dead_end.parent.ports) > 2:
                # dead end at > 2 ports -> remove port but keep element
                remove_ports[dead_end] = [dead_end]
                continue
            else:
                remove_ports_strand = []
                # find if there are more elements in strand to be removed
                strand = hvac_graph.HvacGraph.get_path_without_junctions(graph, dead_end, include_edges=True)
                for port in strand:
                    remove_ports_strand.append(port)
                remove_ports[dead_end] = remove_ports_strand

        related_element_guids = set([port.parent.ifc.GlobalID for port in remove_ports if port.parent])
        answers = {}
        for dead_end, ports in remove_ports.items():
            ListDecision(
                "Found possible dead end at port %s with guid %s in system, "
                "please check if it is a dead end or one of the following:" % (dead_end, dead_end.guid),
                choices=['Consumer', 'Dead End'],
                output=answers,
                output_key=dead_end,
                global_key="deadEnd.%s" % dead_end.guid,
                allow_skip=True, allow_load=True, allow_save=True,
                collect=True, quick_decide=not True, related=related_element_guids, context=related_element_guids)

        Decision.decide_collected()
        n_removed = 0
        for element, answer in answers.items():
            if answer == "Dead End":
                remove = remove_ports[element]
                n_removed += len(set(remove))
                graph.remove_nodes_from([n for n in graph if n in set(remove)])
            else:
                # todo handle consumers
                pass

        return graph, n_removed
