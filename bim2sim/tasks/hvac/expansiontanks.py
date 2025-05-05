from bim2sim.kernel.decision import BoolDecision, DecisionBunch
from bim2sim.elements.hvac_elements import Storage
from bim2sim.elements.graphs.hvac_graph import HvacGraph
from bim2sim.tasks.base import ITask
from bim2sim.tasks.base import Playground


class ExpansionTanks(ITask):

    reads = ('graph',)
    touches = ('graph',)

    def run(self, graph: HvacGraph, force: bool = False) -> HvacGraph:
        """Analyses graph network for expansion tanks and removes them.

        This task performs the following steps:
        1. Identifies potential expansion tanks in the HVAC graph.
        2. Logs the number of identified potential expansion tanks.
        3. Prompts and yields decisions regarding the removal of expansion
        tanks and updates  the graph accordingly.
        4. Logs the number of elements removed because they were identified as
        expansion tanks.

        Args:
            graph: The HVAC graph containing elements and ports.
            force: If True, forcefully remove expansion tanks without
                confirmation. Defaults to False.

        Returns:
            The updated HVAC graph after handling expansion tanks.
        """
        self.logger.info("Inspecting for expansion tanks")
        playground = self.playground
        potential_expansion_tanks = self.identify_expansion_tanks(graph)
        self.logger.info(
            f"Found {potential_expansion_tanks} "
            f"potential expansion tanks in network.")
        graph, n_removed = yield from self.decide_expansion_tanks(
            graph, potential_expansion_tanks, playground, force)
        self.logger.info(
            f"Removed {n_removed} elements because they were expansion tanks.")
        return graph,

    @staticmethod
    def identify_expansion_tanks(graph: HvacGraph) -> set:
        """Identify potential expansion tanks in the HVAC graph.

        Expansion tanks are all tanks with only one port.

        Args:
            graph: HVAC graph to be analysed.

        Returns:
            set of potential expansion tanks.
        """
        element_graph = graph.element_graph
        potential_expansion_tanks = {node for node in element_graph.nodes
                                     if (isinstance(node, Storage) and
                                         len(node.neighbors) < 2)}
        return potential_expansion_tanks

    @staticmethod
    def decide_expansion_tanks(
            graph: HvacGraph,
            potential_expansion_tanks: set,
            playground: Playground = None,
            force: bool = False) -> [HvacGraph, int]:
        """Decide and handle the removal of potential expansion tanks.

        This method evaluates potential expansion tanks and prompts the user
        for decisions on removal. If force is True, expansion tanks are
        removed without confirmation. If playground is provided, the graph is
        updated and visualized during the process.

        Args:
            graph: HVAC graph where the expansion tank should be removed.
            potential_expansion_tanks: set of potential expansion tank elements
                to be evaluated.
            playground: BIM2SIM Playground instance. Defaults to None.
            force: If True, forcefully remove expansion tanks without
                confirmation. Defaults to False.

        Yields:
            Decision bunch with BoolDecisions for confirming expansion tank
                removal.

        Returns:
            Tuple containing the updated HVAC graph where expansions tanks
            are removed and the number of removed expansion tanks.
        """
        if force:
            n_removed = len(potential_expansion_tanks)
            remove_ports = [
                port for pot_tank in potential_expansion_tanks
                for port in pot_tank.ports]
            graph.remove_nodes_from(remove_ports)
            if playground:
                playground.update_graph(graph)
        else:
            decisions = DecisionBunch()
            for tank in potential_expansion_tanks:
                cur_decision = BoolDecision(
                    f"Found {tank} which is a possible expansion tank and"
                    f" therefore should be deleted",
                    key=tank,
                    global_key="expansionTank.%s" % tank.guid,
                    allow_skip=True,
                    related=tank.guid,
                )
                decisions.append(cur_decision)
            yield decisions
            answers = decisions.to_answer_dict()
            n_removed = 0
            for element, answer in answers.items():
                if answer:
                    remove = element.ports
                    n_removed += 1
                    graph.remove_nodes_from(remove)
                    if playground:
                        playground.update_graph(graph)
                else:
                    raise NotImplementedError()
                    # TODO: handle real storages
                    # maybe add ports to the storage and select the related
                    # dead end, with which the new storage port should be
                    # connected
        return graph, n_removed
