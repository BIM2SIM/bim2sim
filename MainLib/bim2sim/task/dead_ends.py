from bim2sim.task.base import Task, ITask


class Inspect(ITask):
    """Analyses graph network for dead ends"""

    reads = ('graph', )
    touches = ('instances', )

    @Task.log
    def run(self, workflow, graph):
        self.logger.info("Inspecting for dead ends")
        remove_list = []
        element_graph = graph.element_graph
        import os
        graph.plot(path=os.path.join('D:/testing'), ports=True)
        for node in element_graph.nodes:
            inner_edges = node.get_inner_connections()
            graph.remove_edges_from(inner_edges)

        direct_dead_ends = [v for v, d in graph.degree() if d == 0]
        print('test')

        graph.remove_nodes_from(remove_list)
        pass


class Reduce(ITask):
    """Removes dead ends from network"""
    reads = ('graph', )
    touches = ('instances', )