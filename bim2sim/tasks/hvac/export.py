import re
from datetime import datetime
from pathlib import Path
from typing import Tuple, List, Dict

from bim2sim.elements import hvac_elements as hvac
from bim2sim.elements.base_elements import ProductBased
from bim2sim.elements.graphs.hvac_graph import HvacGraph
from bim2sim.elements.hvac_elements import HVACProduct
from bim2sim.export import modelica
from bim2sim.export.modelica import HeatTransferType, ModelicaParameter, \
    ModelicaElement
from bim2sim.export.modelica import help_package, help_package_order
from bim2sim.tasks.base import ITask


class CreateModelicaModel(ITask):
    """Export to Dymola/Modelica"""

    reads = ('libraries', 'graph')
    touches = ('export_elements', 'connections', 'cons_heat_ports_conv',
               'cons_heat_ports_rad')

    def run(self, libraries: tuple, graph: HvacGraph):
        """Export HVAC graph to Modelica code.

        This method performs the following steps:
        1. Initializes the Modelica instance factory with the specified
        libraries.
        2. Creates Modelica instances for each HVAC element in the graph.
        3. Collects and exports parameters for each Modelica instance.
        4. Creates connections between Modelica instances based on the HVAC
        graph.
        5. Creates heat port connections (both inner and outer).
        6. Returning the created elements and connections.

        Args:
            libraries: Tuple of libraries to be used in Modelica.
            graph: The HVAC graph to be exported.

        Returns:
            export_elements: A mapping of HVAC elements to their corresponding
                Modelica instances.
            connections: A list of connections between the Modelica instances.
            cons_heat_ports_conv: A list of convective heat port connections.
            cons_heat_ports_rad: A list of radiative heat port connections.
        """
        # Initialize Modelica factory and create Modelica instances
        self.logger.info("Exporting HVAC graph to Modelica code")
        elements = sorted(graph.elements, key=lambda x: x.guid)
        modelica.ModelicaElement.init_factory(libraries)
        export_elements = self._create_export_elements(elements)

        # Create connections based on HVAC graph
        connections = self._create_connections(graph, export_elements)

        # Handle pending attribute and parameter decisions
        yield from self._handle_pending_decisions(elements)

        # Collect parameters for each Modelica instance
        self._collect_parameters(export_elements)

        # Create heat port connections
        cons_heat_ports_conv, cons_heat_ports_rad = (
            self._create_heat_port_connections(export_elements))

        # # TODO #1 integrate heat ports in connections
        # connections.extend(cons_heat_ports_conv)
        # connections.extend(cons_heat_ports_rad)
        return (export_elements, connections,
                cons_heat_ports_conv, cons_heat_ports_rad)

    @staticmethod
    def _create_export_elements(elements: List[HVACProduct]
                                ) -> Dict[HVACProduct, ModelicaElement]:
        """Create Modelica instances for each HVAC element."""
        return {inst: modelica.ModelicaElement.factory(inst)
                for inst in elements}

    @staticmethod
    def _handle_pending_decisions(elements: List[HVACProduct]):
        """Handle pending attribute and parameter decisions."""
        yield from ProductBased.get_pending_attribute_decisions(elements)
        yield from ModelicaParameter.get_pending_parameter_decisions()

    @staticmethod
    def _collect_parameters(
            export_elements: Dict[HVACProduct, ModelicaElement]):
        """Collect and export parameters for each Modelica instance."""
        for instance in export_elements.values():
            instance.collect_params()

    @staticmethod
    def _create_connections(graph: HvacGraph,
                            export_elements: Dict[HVACProduct, ModelicaElement]
                            ) -> List[Tuple[str, str]]:
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
                   for e in
                   elements.values()):
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

        # for distributor in distributors_n:
        #     distributor.parameters['n'] = int(
        #         distributors_n[distributor] / 2 - 1)

        return connection_port_names

    def _create_heat_port_connections(
            self, export_elements: Dict[HVACProduct, ModelicaElement]
    ) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
        """Create inner and outer heat port connections."""
        inner_heat_port_cons_conv, inner_heat_port_cons_rad = (
            self.create_inner_heat_port_connections())

        if self.playground.sim_settings.outer_heat_ports:
            outer_heat_port_cons_conv, outer_heat_port_cons_rad = (
                self.create_outer_heat_port_connections(
                    list(export_elements.values())))
        else:
            outer_heat_port_cons_conv, outer_heat_port_cons_rad = [], []

        cons_heat_ports_conv = (outer_heat_port_cons_conv +
                                inner_heat_port_cons_conv)
        cons_heat_ports_rad = (outer_heat_port_cons_rad +
                               inner_heat_port_cons_rad)

        return cons_heat_ports_conv, cons_heat_ports_rad

    @staticmethod
    def create_outer_heat_port_connections(
            export_elements: List[ModelicaElement]
    ) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
        """Creates connections to an outer heat port for further connections

            Connects heat ports of the export elements to outer heat ports
            (convective and radiative). Returns two lists containing these
            connections.

        Returns:
            Two lists containing convective and radiative heat port connections.
        """
        # ToDo only connect heat ports that might not be connected already by
        #  create_inner_heat_port_connections() function

        # ToDo annotations/placements are missing. Those needs to be added to
        #  visualize connections
        convective_heat_port_connections = []
        radiative_heat_port_connections = []
        convective_ports_index = 1
        radiative_ports_index = 1

        for ele in export_elements:
            for heat_port in ele.heat_ports:
                if heat_port.heat_transfer_type == HeatTransferType.CONVECTIVE:
                    convective_heat_port_connections.append(
                        (f"heatPortOuterCon[{convective_ports_index}]",
                         heat_port.get_full_name()))
                    convective_ports_index += 1
                if heat_port.heat_transfer_type == HeatTransferType.RADIATIVE:
                    radiative_heat_port_connections.append(
                        (f"heatPortOuterRad[{radiative_ports_index}]",
                         heat_port.get_full_name()))
                    radiative_ports_index += 1

        return (convective_heat_port_connections,
                radiative_heat_port_connections)

    def create_inner_heat_port_connections(self) -> [list, list]:
        # TODO if this is needed
        return [], []


class Export(ITask):
    """Export to Dymola/Modelica"""

    reads = ('export_elements', 'connections', 'cons_heat_ports_conv',
             'cons_heat_ports_rad')
    touches = ('modelica_model', 'package_name', 'model_name_hydraulic')

    def run(self, export_elements: dict, connections: list,
            cons_heat_ports_conv: list, cons_heat_ports_rad: list):
        """Export Modelica elements and connections to Modelica code.

        This method creates a Modelica model, organizes the package structure,
        and saves the model to the specified path.

        Args:
            export_elements: Dictionary containing elements to export.
            connections: List of fluid port connections.
            cons_heat_ports_conv: List of convective heat port connections.
            cons_heat_ports_rad: List of radiative heat port connections.

        Returns:
            modelica_model: The modelica model as string.
            package_name: The name of the package (i.e. the folder where the
                modelica model is stored.)
            model_name_hydraulic: The name of the model.
        """
        self.logger.info("Creating Modelica model with %d model elements and %d"
                         " connections.", len(export_elements),
                         len(connections))
        model_name_hydraulic = 'Hydraulic'
        package_name = self.get_package_name(self.prj_name)

        # Setup package directory structure
        export_package_path = self._setup_package_structure(
            package_name, model_name_hydraulic
        )

        # Save the Modelica model
        modelica_model = save_modelica_model(
            model_name=model_name_hydraulic,
            package_path=export_package_path,
            export_elements=list(export_elements.values()),
            connections=connections,
            cons_heat_ports_conv=cons_heat_ports_conv,
            cons_heat_ports_rad=cons_heat_ports_rad
        )
        return modelica_model, package_name, model_name_hydraulic

    @staticmethod
    def get_package_name(prj_name) -> str:
        """Generate a valid package name based on the project name.

        Returns:
            str: The valid package name.
        """
        regex = re.compile("[^a-zA-z0-9]")
        return regex.sub("", prj_name)

    def _setup_package_structure(self, package_name: str,
                                 model_name_hydraulic: str) -> Path:
        """Set up the package directory structure for exporting Modelica models.

        Args:
            package_name: The name of the package.
            model_name_hydraulic: The name of the hydraulic model.

        Returns:
            Path: The path to the export package directory.
        """
        export_package_path = self.paths.export / Path(package_name)

        # Helper functions to structure the Modelica package
        help_package(path=export_package_path, name=export_package_path.stem,
                     within="")
        help_package_order(path=export_package_path,
                           package_list=[model_name_hydraulic])

        return export_package_path


def save_modelica_model(model_name: str, package_path: Path,
                        export_elements, connections, cons_heat_ports_conv,
                        cons_heat_ports_rad):
    """Saves the Modelica model file.

    Args:
        model_name: The name of the model.
        package_path: The directory/package path where the model will be saved.
        export_elements: List of elements to export.
        connections: List of connections data.
        cons_heat_ports_conv: List of convective heat port connections.
        cons_heat_ports_rad: List of radiative heat port connections.
    """
    modelica_model = modelica.ModelicaModel(
        name=model_name,
        comment=f"Autogenerated by BIM2SIM on "
                f"{datetime.now():%Y-%m-%d %H:%M:%S%z}",
        modelica_elements=export_elements,
        connections=connections,
        connections_heat_ports_conv=cons_heat_ports_conv,
        connections_heat_ports_rad=cons_heat_ports_rad
    )
    modelica_model.save(package_path / f"{model_name}.mo")
    return modelica_model
