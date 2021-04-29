from bim2sim.kernel.elements import Storage
from bim2sim.task.base import Task, ITask
from bim2sim.task.hvac.hvac import hvac_graph
from bim2sim.decision import Decision, BoolDecision

class ExpansionTanks(ITask):
    """Analyses graph network for expansion tanks and removes them"""

    reads = ('graph',)
    touches = ('graph',)

    @Task.log
    def run(self, workflow, graph, force=True):
        self.logger.info("Inspecting for dead ends")
        pot_tanks = self.identify_expansion_tanks(graph)
        self.logger.info(f"Found {pot_tanks} potential expansion tanks  in "
                         "network.")
        graph, n_removed = self.delete_expansion_tanks(graph, pot_tanks, force)
        self.logger.info(f"Removed {n_removed} elements because they were "
                         "expansion tanks.")
        return graph

    @staticmethod
    def identify_expansion_tanks(graph: {hvac_graph.HvacGraph}) -> set:
        """Identify potential expansion tanks in graph. Expansion tanks are all
        tanks with only one port."""
        element_graph = graph.element_graph
        pot_tanks = {node for node in element_graph.nodes if
                 (isinstance(node, Storage) and len(
                     node.neighbors) < 2)}
        return pot_tanks

    @staticmethod
    def delete_expansion_tanks(graph: hvac_graph.HvacGraph, pot_tanks,
                               force=True):
        """Delete the found expansions tanks, if force is false a decision will
        be called"""
        n_removed = 0
        if force:
            n_removed = len(pot_tanks)
            remove_ports = \
                [port for pot_tank in pot_tanks for port in pot_tank.ports]
            graph.remove_nodes_from(remove_ports)
        else:
            answers = {}
            decisions = []
            for tank in pot_tanks:
                cur_decision = BoolDecision(
                        f"Found {tank} which is a possible expansion tank and"
                        f" therefore should be deleted",
                        output=answers,
                        output_key=tank,
                        global_key="expansionTank.%s" % tank.guid,
                        allow_skip=True, allow_load=True, allow_save=True,
                        collect=True, quick_decide=False,
                        related={tank.guid},
                        )
                decisions.append(cur_decision)
                Decision.decide_collected(collection=decisions)
                for element, answer in answers.items():
                    if answer:
                        remove = element.ports
                        n_removed += len(remove)
                        graph.remove_nodes_from(remove)
                    else:
                        raise NotImplementedError()
                        # todo handle real storages
                        # maybe add ports to the storage and select the related
                        # dead end, with which the new storage port should be
                        # connected
        return graph, n_removed
