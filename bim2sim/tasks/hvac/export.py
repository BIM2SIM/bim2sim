from datetime import datetime

from bim2sim.elements import hvac_elements as hvac
from bim2sim.elements.base_elements import ProductBased
from bim2sim.elements.graphs.hvac_graph import HvacGraph
from bim2sim.export import modelica
from bim2sim.tasks.base import ITask


class Export(ITask):
    """Export to Dymola/Modelica"""

    reads = ('libraries', 'graph')
    final = True

    def run(self, libraries: tuple, graph: HvacGraph):
        """Export HVAC graph to Modelica code.

        This method performs the following steps:
        1. Initializes the Modelica instance factory with the specified
        libraries.
        2. Creates Modelica instances for each HVAC element in the graph.
        3. Collects and exports parameters for each Modelica instance.
        4. Creates connections between Modelica instances based on the HVAC
        graph.
        5. Creates a Modelica model with the exported elements and connections.
        6. Saves the Modelica model to the specified export path.

        Args:
            libraries: Tuple of libraries to be used in Modelica.
            graph: The HVAC graph to be exported.
        """

        self.logger.info("Export to Modelica code")
        elements = graph.elements

        connections = graph.get_connections()

        modelica.Instance.init_factory(libraries)
        export_elements = {inst: modelica.Instance.factory(inst)
                            for inst in elements}

        # Perform decisions for requested but not existing attributes
        yield from ProductBased.get_pending_attribute_decisions(
            elements)

        # All parameters are checked against the specified check function and
        #  exported with the correct unit
        for instance in export_elements.values():
            instance.collect_params()

        connection_port_names = self.create_connections(graph, export_elements)

        self.logger.info(
            "Creating Modelica model with %d model elements "
            "and %d connections.",
            len(export_elements), len(connection_port_names))

        modelica_model = modelica.Model(
            name="bim2sim_"+self.prj_name,
            comment=f"Autogenerated by BIM2SIM on "
                    f"{datetime.now():%Y-%m-%d %H:%M:%S%z}",
            elements=list(export_elements.values()),
            connections=connection_port_names,
        )
        modelica_model.save(self.paths.export)

    @staticmethod
    def create_connections(graph: HvacGraph, export_elements: dict) -> list:
        """Creates a list of connections for the corresponding Modelica model.

        This method iterates over the edges of the HVAC graph and creates a
        list of connections for the corresponding Modelica model.
        It considers distributors and adjusts port names accordingly.

        Args:
            graph: the HVAC graph
            export_elements: the Modelica elements

        Returns:
           connection_port_names: list of tuple of port names that are
            connected.
        """
        connection_port_names = []
        distributors_n = {}
        distributors_ports = {}
        for port_a, port_b in graph.edges:
            if port_a.parent is port_b.parent:
                # ignore inner connections
                continue
            elements = {'a': export_elements[port_a.parent],
                        'b': export_elements[port_b.parent]}
            ports_name = {'a': elements['a'].get_full_port_name(port_a),
                          'b': elements['b'].get_full_port_name(port_b)}
            if any(isinstance(e.element, hvac.Distributor)
                   for e in elements.values()):
                for key, inst in elements.items():
                    if type(inst.element) is hvac.Distributor:
                        distributor = (key, inst)
                        distributor_port = ports_name[key]
                    else:
                        other_inst = inst
                        other_port = ports_name[key]

                ports_name[distributor[0]] = distributor[1].get_new_port_name(
                    distributor[1], other_inst, distributor_port, other_port,
                    distributors_n, distributors_ports)

            connection_port_names.append((ports_name['a'], ports_name['b']))

        for distributor in distributors_n:
            distributor.params['n'] = int(distributors_n[distributor] / 2 - 1)

        return connection_port_names
