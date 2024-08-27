import re
from datetime import datetime
from pathlib import Path

from mako.template import Template

from bim2sim.elements import hvac_elements as hvac
from bim2sim.elements.base_elements import ProductBased
from bim2sim.elements.graphs.hvac_graph import HvacGraph
from bim2sim.export import modelica
from bim2sim.export.modelica import HeatTransferType, ModelicaParameter
from bim2sim.tasks.base import ITask
from bim2sim.export.modelica import help_package, help_package_order


class CreateModelicaModel(ITask):
    """Export to Dymola/Modelica"""

    reads = ('libraries', 'graph')
    touches = ('modelica_model','connections', 'cons_heat_ports_conv',
               'cons_heat_ports_rad')
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

        modelica.ModelicaElement.init_factory(libraries)
        export_elements = {inst: modelica.ModelicaElement.factory(inst)
                           for inst in elements}
        connections = self.create_connections(graph, export_elements)

        # Perform decisions for requested but not existing attributes
        yield from ProductBased.get_pending_attribute_decisions(elements)
        # Perform decisions for required but not existing modelica parameters
        yield from ModelicaParameter.get_pending_parameter_decisions()

        # All parameters are checked against the specified check function and
        #  exported with the correct unit
        for instance in export_elements.values():
            instance.collect_params()

        inner_heat_port_cons_conv, inner_heat_port_cons_rad = (
            self.create_inner_heat_port_connections())

        if self.playground.sim_settings.outer_heat_ports:
            outer_heat_port_cons_conv, outer_heat_port_cons_rad = (
                self.create_outer_heat_port_connections(
                    list(export_elements.values())))
        else:
            outer_heat_port_cons_conv = []
            outer_heat_port_cons_rad = []
        cons_heat_ports_conv = (outer_heat_port_cons_conv +
                                inner_heat_port_cons_conv)
        cons_heat_ports_rad = (outer_heat_port_cons_rad +
                               inner_heat_port_cons_rad)

        # TODO #1 integrate heat ports in connections
        return (export_elements, connections,
                cons_heat_ports_conv, cons_heat_ports_rad)

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

    @staticmethod
    def create_outer_heat_port_connections(export_elements: list) -> \
            [list, list]:
        """Creates connections to an outer heat port for further connections"""
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

    reads = ('export_elements', 'connections','cons_heat_ports_conv',
             'cons_heat_ports_rad')
    touches = ('modelica_model',)
    final = True

    def run(self, export_elements: dict, connections: list,
            cons_heat_ports_conv: list, cons_heat_ports_rad: list):
        """Export modelica elements and connections to Modelica code.

        This method performs the following steps:
        1. Creates a Modelica model with the exported elements and connections.
        2. Saves the Modelica model to the specified export path.

        Args:
            export_elements:
            connections:
            cons_heat_ports_conv:
            cons_heat_ports_rad:

        Returns:
            modelica_model:
        """
        self.logger.info(
            "Creating Modelica model with %d model elements "
            "and %d connections.",
            len(export_elements), len(connections))
        regex = re.compile("[^a-zA-z0-9]")
        package_name = regex.sub(
            "", "bim2sim_aixlib_" + self.prj_name)
        # TODO
        # Check if regression is needed:
        if self.playground.sim_settings.regression_variables:
            regression = True
        else:
            regression = False
        model_name = 'Hydraulic'
        # TODO regression handling in template
        modelica_model = modelica.ModelicaModel(
            name=model_name,
            comment=f"Autogenerated by BIM2SIM on "
                    f"{datetime.now():%Y-%m-%d %H:%M:%S%z}",
            modelica_elements=list(export_elements.values()),
            connections=connections,
            connections_heat_ports_conv=cons_heat_ports_conv,
            connections_heat_ports_rad=cons_heat_ports_rad
        )
        # create base package structure
        export_pkg_path = self.paths.export / Path(package_name)
        Path.mkdir(export_pkg_path, exist_ok=True)
        help_package(
            path=export_pkg_path,
            name=export_pkg_path.stem,
            within="")
        help_package_order(path=export_pkg_path, package_list=[
            model_name,
            # 'building_model',
            # 'hvac_model'
        ])
        Path.mkdir(export_pkg_path / model_name, exist_ok=True)
        # export hydraulic model itself
        modelica_model.save_pkg(export_pkg_path / model_name)
        # Create folders for regression testing if needed
        if self.playground.sim_settings.regression_variables:
            dir_dymola = export_pkg_path / "Resources" / "Scripts" / "Dymola"
            dir_dymola.mkdir(parents=True, exist_ok=True)
            test_script_template = Template(
                filename=str(self.paths.assets /
                             'templates/modelica/modelicaTestScript'))
            regression_test_path = (
                    dir_dymola / model_name / f"{model_name}.mos")
            (dir_dymola / model_name).mkdir(exist_ok=True)
            with open(regression_test_path, 'w') as out_file:
                out_file.write(test_script_template.render_unicode(
                    package_name=package_name,
                    model_name=model_name,
                    stop_time=3600 * 24 * 365,
                    regression_variables=
                    self.playground.sim_settings.regression_variables,
                ))
            out_file.close()
        return modelica_model,
