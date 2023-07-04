from bim2sim.kernel.decision import BoolDecision, DecisionBunch
from bim2sim.elements.graphs.hvac_graph import HvacGraph
from bim2sim.tasks.base import ITask
from bim2sim.tasks.base import Playground


class DeadEnds(ITask):
    """Analyses graph network for dead ends and removes ports due to dead ends."""

    reads = ('graph',)
    touches = ('graph',)

    def run(self, graph: HvacGraph) -> HvacGraph:
        self.logger.info("Inspecting for dead ends")
        pot_dead_ends = self.identify_dead_ends(graph)
        self.logger.info("Found %s possible dead ends in network."
                         % len(pot_dead_ends))
        graph, n_removed = yield from self.decide_dead_ends(
            graph, pot_dead_ends, False)
        self.logger.info("Removed %s ports due to found dead ends." % n_removed)
        if __debug__:
            self.logger.info("Plotting graph ...")
            graph.plot(self.paths.export)
            graph.plot(self.paths.export, ports=True)
        return graph,

    @staticmethod
    def identify_dead_ends(graph: HvacGraph) -> list:
        """ Identify dead ends in graph. Dead ends are all ports of elements
            which are not connected with another port.

        Args:
            graph: HVAC graph being analysed

        Returns:
            pot_dead_ends: List of potential dead ends
        """

        uncoupled_graph = graph.copy()
        element_graph = uncoupled_graph.element_graph
        for node in element_graph.nodes:
            inner_edges = node.inner_connections
            uncoupled_graph.remove_edges_from(inner_edges)
        # find first class dead ends (ports which are not connected to any other
        # port)
        pot_dead_ends_1 = [v for v, d in uncoupled_graph.degree() if d == 0]
        # find second class dead ends (ports which are connected to one side
        # only)
        pot_dead_ends_2 = [v for v, d in graph.degree() if d == 1]
        pot_dead_ends = list(set(pot_dead_ends_1 + pot_dead_ends_2))
        return pot_dead_ends

    @staticmethod
    def decide_dead_ends(graph: HvacGraph, pot_dead_ends: list,
                         playground: Playground = None,
                         force: bool = False) -> [{HvacGraph}, int]:
        """Decides for all dead ends whether they are consumers or dead ends.

        Args:
            graph: HVAC graph being analysed
            pot_dead_ends: List of potential dead ends
            playground: bim2sim Playground instance
            force: If True, then all potential dead ends are removed

        Returns:
            graph: HVAC graph where dead ends are removed
            n_removed: Number of removed ports due to dead ends
        """
        n_removed = 0
        remove_ports = {}
        for dead_end in pot_dead_ends:
            if len(dead_end.parent.ports) > 2:
                # dead end at > 2 ports -> remove port but keep element
                remove_ports[dead_end] = ([dead_end], [dead_end.parent])
                continue
            else:
                # TODO: how to handle devices where we might want to connect dead ends instead delete
                remove_ports_strand = []
                remove_elements_strand = []
                # find if there are more elements in strand to be removed
                strand_ports = HvacGraph.get_path_without_junctions(
                    graph, dead_end, include_edges=True)
                strand = graph.subgraph(strand_ports).element_graph
                for port in strand_ports:
                    remove_ports_strand.append(port)
                for element in strand:
                    remove_elements_strand.append(element)
                remove_ports[dead_end] = (remove_ports_strand,
                                          remove_elements_strand)

        if force:
            for dead_end in pot_dead_ends:
                remove = remove_ports[dead_end][0]
                n_removed += len(set(remove))
                graph.remove_nodes_from([n for n in graph if n in set(remove)])

        else:
            decisions = DecisionBunch()
            for dead_end, (port_strand, element_strand) in remove_ports.items():
                dead_end_port = dead_end
                if hasattr(dead_end_port, "originals"):
                    while hasattr(dead_end_port, "originals"):
                        related_guid = dead_end_port.originals[0].parent.guid
                        dead_end_port = dead_end_port.originals[0]
                else:
                    related_guid = dead_end.parent.guid
                cur_decision = BoolDecision(
                    question="Found possible dead end at port %s in system, "
                    "please check if it is a dead end" % dead_end,
                    console_identifier="GUID: %s" % dead_end.guid,
                    key=dead_end,
                    global_key="deadEnd.%s" % dead_end.guid,
                    allow_skip=False,
                    related={related_guid}, context=set(
                        element.guid for element in element_strand))
                decisions.append(cur_decision)
            yield decisions
            answers = decisions.to_answer_dict()
            n_removed = 0
            for element, answer in answers.items():
                if answer:
                    remove = remove_ports[element][0]
                    n_removed += len(set(remove))
                    graph.remove_nodes_from(
                        [n for n in graph if n in set(remove)])
                    if playground:
                        playground.update_graph(graph)
                else:
                    raise NotImplementedError()
                    # TODO: handle consumers
                    # dead end identification with guid decision (see issue97 add_gui_decision)
                    # build clusters with position for the rest of open ports
                    # decision to to group these open ports to consumers
                    # delete the rest of open ports afterwards
        return graph, n_removed
