"""This module holds elements related to bps workflow"""

import itertools
import json

from bim2sim.workflow import Workflow
from bim2sim.filter import TypeFilter
from bim2sim.ifc2python.element import Element, ElementEncoder, BasePort
# from bim2sim.ifc2python.bps import ...
from bim2sim.export import modelica
from bim2sim.decision import Decision
from bim2sim.project import PROJECT
from bim2sim.ifc2python import finder

IFC_TYPES = (
    'IfcWall',
    'IfcWallElementedCase',
    'IfcWallStandardCase',
    'IfcWindow',
    'IfcSpace'
)


class Inspect(Workflow):
    """Analyses IFC, creates Element instances and connects them.

    elements are stored in .instances dict with guid as key"""

    def __init__(self):
        super().__init__()
        self.instances = {}

    # @Workflow.log
    # def run(self, ifc, relevant_ifc_types):
    #     self.logger.info("Creates python representation of relevant ifc types")
    #     for ifc_type in relevant_ifc_types:
    #         elements = ifc.by_type(ifc_type)
    #         for element in elements:
    #             representation = Element.factory(element)
    #             self.instances[representation.guid] = representation
    #     self.logger.info("Found %d relevant elements", len(self.instances))
    #
    #     # connections
    #     self.logger.info("Connecting the relevant elements")
    #     self.logger.info(" - Connecting by relations ...")
    #     rel_connections = self.connections_by_relation(
    #         BasePort.objects.values())
    #     self.logger.info(" - Found %d potential connections.",
    #                      len(rel_connections))
    #
    #     self.logger.info(" - Checking positions of connections ...")
    #     confirmed, unconfirmed, rejected = \
    #         self.confirm_connections_position(rel_connections)
    #     self.logger.info(" - %d connections are confirmed and %d rejected. " \
    #         + "%d can't be confirmed.",
    #                      len(confirmed), len(rejected), len(unconfirmed))
    #     for port1, port2 in confirmed + unconfirmed:
    #         # unconfirmed have no position data and cant be connected by position
    #         port1.connect(port2)
    #
    #     unconected_ports = (port for port in BasePort.objects.values()
    #                         if not port.is_connected())
    #     self.logger.info(" - Connecting remaining ports by position ...")
    #     pos_connections = self.connections_by_position(unconected_ports)
    #     self.logger.info(" - Found %d additional connections.",
    #                      len(pos_connections))
    #     for port1, port2 in pos_connections:
    #         port1.connect(port2)
    #
    #     nr_total = len(BasePort.objects)
    #     nr_unconnected = sum(1 for port in BasePort.objects.values()
    #                          if not port.is_connected())
    #     nr_connected = nr_total - nr_unconnected
    #     self.logger.info("In total %d of %d ports are connected.",
    #                      nr_connected, nr_total)
    #     if nr_total > nr_connected:
    #         self.logger.warning("%d ports are not connected!", nr_unconnected)
#
#
# class Prepare(Workflow):
#     """Configurate""" #TODO: based on task
#
#     def __init__(self):
#         super().__init__()
#         self.filters = []
#
#     @Workflow.log
#     def run(self, relevant_ifc_types):
#         self.logger.info("Setting Filters")
#         Element.finder = finder.TemplateFinder()
#         Element.finder.load(PROJECT.finder)
#         self.filters.append(TypeFilter(relevant_ifc_types))


# class Reduce(Workflow):
#     """Reduce number of elements by aggregation"""
#
#     def __init__(self):
#         super().__init__()
#         self.reduced_instances = []
#         self.connections = []
#
#     @Workflow.log
#     def run(self, graph: hvac_graph.HvacGraph):
#         self.logger.info("Reducing elements by applying aggregations")
#         number_of_nodes_old = len(graph.element_graph.nodes)
#         number_ps = 0
#         chains = graph.get_type_chains(PipeStrand.aggregatable_elements)
#         for chain in chains:
#             number_ps += 1
#             pipestrand = PipeStrand("PipeStrand%d"%(number_ps), chain)
#             graph.merge(
#                 mapping=pipestrand.get_replacement_mapping(),
#                 inner_connections=pipestrand.get_inner_connections())
#         number_of_nodes_new = len(graph.element_graph.nodes)
#
#         self.logger.info(
#             "Applied %d aggregations which reduced"
#             + " number of elements from %d to %d.",
#             number_ps, number_of_nodes_old, number_of_nodes_new)
#         self.reduced_instances = graph.elements
#         self.connections = graph.get_connections()
#
#         if __debug__:
#             self.logger.info("Plotting graph ...")
#             graph.plot(PROJECT.export)

#
#
# class Export(Workflow):
#     """Export to Dymola/Modelica"""
#
#     def run(self, libraries, instances, connections):
#         self.logger.info("Export to Modelica code")
#         Decision.load(PROJECT.decisions)
#
#         modelica.Instance.init_factory(libraries)
#         export_instances = {inst: modelica.Instance.factory(inst) for inst in instances}
#
#         self.logger.info(Decision.summary())
#         Decision.decide_collected()
#         Decision.save(PROJECT.decisions)
#
#         connection_port_names = []
#         for connection in connections:
#             instance0 = export_instances[connection[0].parent]
#             port_name0 = instance0.get_full_port_name(connection[0])
#             instance1 = export_instances[connection[1].parent]
#             port_name1 = instance1.get_full_port_name(connection[1])
#             connection_port_names.append((port_name0, port_name1))
#
#         self.logger.info(
#             "Creating Modelica model with %d model instances and %d connections.",
#             len(export_instances), len(connection_port_names))
#
#         modelica_model = modelica.Model(
#             name="Test",
#             comment="testing",
#             instances=export_instances.values(),
#             connections=connection_port_names,
#         )
#         #print("-"*80)
#         #print(modelica_model.code())
#         #print("-"*80)
#         modelica_model.save(PROJECT.export)
