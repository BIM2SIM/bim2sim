from bim2sim.kernel.decision import BoolDecision, DecisionBunch
from bim2sim.elements.graphs.hvac_graph import HvacGraph
from bim2sim.tasks.base import ITask
from bim2sim.tasks.base import Playground


class DeadEnds(ITask):

    reads = ('graph',)
    touches = ('graph',)

    def run(self, graph: HvacGraph) -> HvacGraph:
        """Analyses graph for dead ends and removes ports due to dead ends.

        This task performs the following steps:
        1. Identifies potential dead ends in the HVAC graph.
        2. Logs the number of identified potential dead ends.
        3. Prompts and yields decisions regarding the removal of dead ends and
        updates the graph accordingly.
        4. Logs the number of ports removed due to dead ends.
        5. Optionally, plots the HVAC graph in debug mode.

        Args:
            graph: HVAC graph containing elements and ports.

        Returns:
            Updated HVAC graph after handling dead ends.
        """
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
        """Identify potential dead ends in graph.

        This method identifies potential dead end ports in the HVAC graph by
        considering two cases:
        1. Ports that are not connected to any other port.
        2. Ports that are connected to only one other port.

        Args:
            graph: HVAC graph to be analysed.

        Returns:
            pot_dead_ends: List of potential dead ends.
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
        """Decide if potential dead ends are consumers or dead ends.

        This method evaluates potential dead end ports and prompts the user for
        decisions on removal. If force is True, dead ends are removed
        without confirmation. If playground is provided, the graph is updated
        and visualized during the process.

        Args:
            graph: HVAC graph to be analysed.
            pot_dead_ends: List of potential dead end ports to be evaluated.
            playground: BIM2SIM Playground instance. Defaults to None.
            force: If True, then all potential dead ends are removed without
                confirmation. Defaults to False.

        Yields:
            Decision bunch with BoolDecisions for confirming dead ends.

        Returns:
            Tuple containing the updated HVAC graph where dead ends are
            removed and the number of removed ports.
        """
        n_removed = 0
        remove_ports = {}
        for dead_end in pot_dead_ends:
            if len(dead_end.parent.ports) > 2:
                # dead end at > 2 ports -> remove port but keep element
                remove_ports[dead_end] = ([dead_end], [dead_end.parent])
                continue
            else:
                # TODO: how to handle devices where we might want to connect
                #  dead ends instead delete
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
            # TODO additional decision to decide if connections should be done or if the dead end just should be kept as it is
            answers = decisions.to_answer_dict()
            n_removed = 0

            connected = []
            for element, answer in answers.items():
                if answer:
                    remove = remove_ports[element][0]
                    n_removed += len(set(remove))
                    graph.remove_nodes_from(
                        [n for n in graph if n in set(remove)])
                    if playground:
                        playground.update_graph(graph)
                else:
                    # TODO continue here
                    con_decision = BoolDecision(
                        question=f"..."
                    )
                    pass
                    raise NotImplementedError()
                    # TODO connect elements that are open but not dead ends
                    #  (missing connections) #769
                    # TODO: handle consumers
                    # dead end identification with guid decision
                    #  (see issue97 add_gui_decision)
                    # build clusters with position for the rest of open ports
                    # decision to to group these open ports to consumers
                    # delete the rest of open ports afterwards
        return graph, n_removed
