import logging

from bim2sim.elements.aggregation.hvac_aggregations import UnderfloorHeating, \
    Consumer, PipeStrand, ParallelPump, ConsumerHeatingDistributorModule, \
    GeneratorOneFluid
from bim2sim.elements.graphs.hvac_graph import HvacGraph
from bim2sim.kernel.decision import BoolDecision, DecisionBunch
from bim2sim.tasks.base import ITask


class Reduce(ITask):

    reads = ('graph',)
    touches = ('graph',)

    def run(self, graph: HvacGraph) -> (HvacGraph,):
        """Apply aggregations to reduce number of elements in the HVAC graph.

        This task applies aggregations to the HVAC graph based on the specified
        aggregation classes. It logs information about the number of elements
        before and after applying aggregations, as well as the statistics for
        each aggregation class. The task also updates the graph and logs
        relevant information. If the code is running in debug mode, it plots
        the graph using different options.

        Args:
            graph: The HVAC graph.

        Returns:
            The updated HVAC graph.
        """
        self.logger.info("Reducing elements by applying aggregations")

        aggregations_cls = {
            'UnderfloorHeating': UnderfloorHeating,
            'Consumer': Consumer,
            'PipeStrand': PipeStrand,
            'ParallelPump': ParallelPump,
            'ConsumerHeatingDistributorModule':
                ConsumerHeatingDistributorModule,
            'GeneratorOneFluid': GeneratorOneFluid,
        }
        aggregations = [aggregations_cls[agg] for agg in
                        self.playground.sim_settings.aggregations]

        statistics = {}
        number_of_elements_before = len(graph.elements)

        for agg_class in aggregations:
            name = agg_class.__name__
            self.logger.info(f"Aggregating {name} ...")
            matches, metas = agg_class.find_matches(graph)
            i = 0
            for match, meta in zip(matches, metas):
                try:
                    agg = agg_class(graph, match, **meta)
                except Exception as ex:
                    self.logger.exception("Instantiation of '%s' failed", name)
                else:
                    graph.merge(
                        mapping=agg.get_replacement_mapping(),
                        inner_connections=agg.inner_connections
                    )
                    i += 1
                    self.playground.update_graph(graph)
            statistics[name] = i
            if len(matches) > 0:
                self.logger.info(
                    f"Found {len(matches)} Aggregations of type "
                    f"{name} and was able to aggregate {i} of them.")
            else:
                self.logger.info(f"Found non Aggregations of type {name}")
        number_of_elements_after = len(graph.elements)

        log_str = "Aggregations reduced number of elements from %d to %d:" % \
                  (number_of_elements_before, number_of_elements_after)
        for aggregation, count in statistics.items():
            log_str += "\n  - %s: %d" % (aggregation, count)
        self.logger.info(log_str)

        if __debug__:
            self.logger.info("Plotting graph ...")
            graph.plot(self.paths.export)
            graph.plot(self.paths.export, ports=True)
            graph.plot(self.paths.export, ports=False, use_pyvis=True)

        return graph,

    @staticmethod
    def set_flow_sides(graph: HvacGraph):
        """ Set flow sides for ports in HVAC graph based on known flow sides.

        This function iteratively sets flow sides for ports in the HVAC graph.
        It uses a recursive method (`recurse_set_unknown_sides`) to determine
        the flow side for each unset port. The function may prompt the user
        for decisions in case of conflicts or unknown sides.

        Args:
             graph: The HVAC graph.

        Yields:
            DecisionBunch: A collection of decisions may be yielded during the
                task.
        """
        # TODO: needs testing!
        # TODO: at least one master element required
        accepted = []
        while True:
            unset_port = None
            for port in graph.get_nodes():
                if port.flow_side == 0 and graph.graph[port] \
                        and port not in accepted:
                    unset_port = port
                    break
            if unset_port:
                side, visited, masters = graph.recurse_set_unknown_sides(
                    unset_port)
                if side in (-1, 1):
                    # apply suggestions
                    for port in visited:
                        port.flow_side = side
                elif side == 0:
                    # TODO: ask user?
                    accepted.extend(visited)
                elif masters:
                    # ask user to fix conflicts (and retry in next while loop)
                    for port in masters:
                        decision = BoolDecision(
                            "Use %r as VL (y) or RL (n)?" % port)
                        yield DecisionBunch([decision])
                        use = decision.value
                        if use:
                            port.flow_side = 1
                        else:
                            port.flow_side = -1
                else:
                    # can not be solved (no conflicting masters)
                    # TODO: ask user?
                    accepted.extend(visited)
            else:
                # done
                logging.info("Flow_side set")
                break
