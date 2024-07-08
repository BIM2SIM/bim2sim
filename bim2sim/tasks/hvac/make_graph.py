from bim2sim.elements.base_elements import Material
from bim2sim.elements.graphs.hvac_graph import HvacGraph
from bim2sim.tasks.base import ITask


class MakeGraph(ITask):
    """Instantiate HVACGraph"""

    reads = ('elements', )
    touches = ('graph', )

    def run(self, elements: dict):
        self.logger.info("Creating graph from IFC elements")
        not_mat_elements = \
            {k: v for k, v in elements.items() if not isinstance(v, Material)}
        graph = HvacGraph(not_mat_elements.values())
        return graph,
