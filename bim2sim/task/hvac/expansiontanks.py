from bim2sim.kernel.elements.hvac import Storage
from bim2sim.task.base import ITask
from bim2sim.kernel.hvac.hvac_graph import HvacGraph
from bim2sim.decision import BoolDecision, DecisionBunch
from bim2sim.workflow import Workflow


class ExpansionTanks(ITask):
    """Analyses graph network for expansion tanks and removes them."""

    reads = ('graph',)
    touches = ('graph',)

    def run(self, workflow: Workflow, graph: HvacGraph, force: bool = False) -> HvacGraph:
        self.logger.info("Inspecting for expansion tanks")
        potential_expansion_tanks = self.identify_expansion_tanks(graph)
        self.logger.info(f"Found {potential_expansion_tanks} potential expansion tanks in network.")
        graph, n_removed = yield from self.decide_expansion_tanks(graph, potential_expansion_tanks, force)
        self.logger.info(f"Removed {n_removed} elements because they were expansion tanks.")
        return graph,

    @staticmethod
    def identify_expansion_tanks(graph: HvacGraph) -> set:
        """Identify potential expansion tanks in graph. Expansion tanks are all tanks with only one port.

        Args:
            graph: HVAC graph to be investigated

        Returns:
            set of potential expansion tanks
        """
        element_graph = graph.element_graph
        potential_expansion_tanks = {node for node in element_graph.nodes
                                     if (isinstance(node, Storage) and len(node.neighbors) < 2)}
        return potential_expansion_tanks

    @staticmethod
    def decide_expansion_tanks(graph: HvacGraph, potential_expansion_tanks: set, force: bool = False) \
            -> [HvacGraph, int]:
        """Delete the found expansions tanks. If force is false a decision will be called

        Args:
            graph: HVAC graph where the expansion tank should be removed
            potential_expansion_tanks: set of potential expansion tanks
            force: if false, a decision will be called

        Returns:
            HvacGraph: the HVAC graph where expansions tanks are removed
            n_removed: number of removed expansion tanks
        """
        if force:
            n_removed = len(potential_expansion_tanks)
            remove_ports = [port for pot_tank in potential_expansion_tanks for port in pot_tank.ports]
            graph.remove_nodes_from(remove_ports)
        else:
            decisions = DecisionBunch()
            for tank in potential_expansion_tanks:
                cur_decision = BoolDecision(
                    f"Found {tank} which is a possible expansion tank and therefore should be deleted",
                    key=tank,
                    global_key="expansionTank.%s" % tank.guid,
                    allow_skip=True,
                    related={tank.guid},
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
                else:
                    raise NotImplementedError()
                    # TODO: handle real storages
                    # maybe add ports to the storage and select the related
                    # dead end, with which the new storage port should be
                    # connected
        return graph, n_removed
