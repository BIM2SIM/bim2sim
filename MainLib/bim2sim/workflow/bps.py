"""This module holds elements related to bps_f workflow"""

import itertools
import json

from bim2sim.workflow import Workflow
from bim2sim.filter import TypeFilter
from bim2sim.ifc2python.element import Element, ElementEncoder, BasePort
from bim2sim.export import modelica
from bim2sim.decision import Decision
from bim2sim.project import PROJECT
from bim2sim.ifc2python import finder
from bim2sim.ifc2python import elements
from collections import defaultdict
from bim2sim.ifc2python.aggregation import group_by_range
import ifcopenshell
import ifcopenshell.geom
import math
from shapely.geometry.polygon import Polygon
from shapely.geometry import Point
import matplotlib.pyplot as plt
from bim2sim.workflow.bps_f import bps_functions


IFC_TYPES = (
    # 'IfcBuilding',
    'IfcWallElementedCase',
    'IfcWallStandardCase',
    'IfcWall',
    'IfcWindow',
    'IfcSpace'
    'ifcSlab',

    'IfcBuildingStorey',
    'IfcRoof',

    'IfcRoof',
    'IfcShadingDevice',
    'IfcPlate',
    'IfcCovering',
    'IfcDoor',
)


class Inspect(Workflow):
    """Analyses IFC, creates Element instances and connects them.

    elements are stored in .instances dict with guid as key"""

    def __init__(self):
        super().__init__()
        self.instances_bps = {}

    @Workflow.log
    def run(self, ifc, relevant_ifc_types):
        self.logger.info("Creates python representation of relevant ifc types")

        # Building and exterior orientations
        settings = ifcopenshell.geom.settings()
        walls = ifc.by_type('IfcWall')
        storeys_elements = {}
        tolerance = [[0.5, 0.5], [0.5, -0.5], [-0.5, -0.5], [-0.5, 0.5]]

        storeys = ifc.by_type('IfcBuildingStorey')
        for storey in storeys:
            externals = []
            spaces = {}
            # for ele in storey.ContainsElements[0].RelatedElements:
            #     if 'IfcWall' in str(ele):
            #         representation = Element.factory(ele)
            #         if representation.is_external is True:
            #             externals.append(ele)
            #         else:
            #             self.instances_bps[representation.guid] = representation
            #     elif 'IfcWindow' in str(ele):
            #         representation = Element.factory(ele)
            #         if representation.is_external is True:
            #             externals.append(ele)
            #         else:
            #             self.instances_bps[representation.guid] = representation
            if len(storey.IsDecomposedBy) != 0:
                for space in storey.IsDecomposedBy[0].RelatedObjects:
                    space_ = []
                    ps = bps_functions.get_polygon(space)
                    # plt.plot(*ps.exterior.xy)
                    # plt.show()
                    # for ele in externals:
                    #     pw = bps_functions.get_polygon(ele)
                    #     # plt.plot(*pw.xy, 'k')
                    #     if pw.intersects(ps) or ps.contains(pw):
                    #         space_.append(ele)
                    #         # plt.plot(*pw.xy)
                    # # plt.show()
                    # spaces[str(space)] = space_

            # storeys_elements[str(storey)] = spaces





        for space in spaces:
            # centroid = Point(representation.position[0:2])
            centroid = bps_functions.get_centroid(space)
            plt.plot(*centroid.xy, marker='x')
        # slabs = ifc.by_type('IfcSlab')

        # p1, p2, p3, p4, cardinal_direction = bps_functions.find_building_polygon(slabs)
        # building_envelope = bps_functions.find_building_envelope(p1, p2, p3, p4)

        for wall in walls:
            representation = Element.factory(wall)
            if representation.is_external is True:
                external_walls.append(wall)
            else:
                self.instances_bps[representation.guid] = representation

        for wall in external_walls:
            representation = Element.factory(wall)
            location = Point(representation.position[0:2])
            plt.plot(*location.xy, marker='x')
            space_elements = []
            elemets = wall.ContainedInStructure[0].RelatedElements
            for ele in elemets:
                if ('IfcWall' in str(ele)) or ('IfcWindow' in str(ele)):
                    representation = Element.factory(ele)
                    location = Point(representation.position[0:2])
                    plt.plot(*location.xy, marker='o')
            plt.show()



            # centroid = bps_functions.get_centroid(wall)
            # plt.plot(*centroid.xy, marker='o')
            # wall.Representation.Description = bps_functions.get_orientation\
            #     (building_envelope, centroid, cardinal_direction)
            self.instances_bps[representation.guid] = representation

        # plt.plot(*building_envelope[0].exterior.xy)
        # plt.plot(*building_envelope[1].exterior.xy)
        # plt.plot(*building_envelope[2].exterior.xy)
        # plt.plot(*building_envelope[3].exterior.xy)


        ######
        external_windows = []
        windows = ifc.by_type('IfcWindow')
        for window in windows:
            representation = Element.factory(window)
            if representation.is_external is True:
                external_windows.append(window)
            else:
                self.instances_bps[representation.guid] = representation

        for window in external_windows:
            representation = Element.factory(window)
            centroid = Point(representation.position[0:2])
            # plt.plot(*centroid.xy, marker='o')
            window.Tag = bps_functions.get_orientation(building_envelope, centroid, cardinal_direction)
            self.instances_bps[representation.guid] = representation

        # plt.plot(*building_envelope[0].exterior.xy)
        # plt.plot(*building_envelope[1].exterior.xy)
        # plt.plot(*building_envelope[2].exterior.xy)
        # plt.plot(*building_envelope[3].exterior.xy)
        # plt.show()

        storeys = ifc.by_type('IfcBuildingStorey')
        for storey in storeys:
            slabs = []
            exterior_slab = 0
            z_coordinate = float('inf')
            for element in storey.ContainsElements[0].RelatedElements:
                if 'IfcSlab' in str(element):
                    representation = Element.factory(element)
                    slabs.append(element)
                    if representation.position[2] < z_coordinate:
                        z_coordinate = representation.position[2]
                        exterior_slab = element
            slabs[slabs.index(exterior_slab)].Tag = 'True'
            for slab in slabs:
                representation = Element.factory(slab)
                self.instances_bps[representation.guid] = representation

        plates = ifc.by_type('IfcPlate')
        for plate in plates:
            bps_functions.get_natural_position(plate)

        # find and fills spaces
        spaces = ifc.by_type('IfcSpace')
        for space in spaces:
            representation = Element.factory(space)
            self.instances_bps[representation.guid] = representation

        for ifc_type in relevant_ifc_types[4:]:
            elements_ = ifc.by_type(ifc_type)
            for element in elements_:
                representation = Element.factory(element)
                self.instances_bps[representation.guid] = representation
        self.logger.info("Found %d relevant elements", len(self.instances_bps))
        # aggregate all elements from space

        # find zones

        # first_filter = group_by_range(instances_space, 2, "area")
        #
        # second_filter = {}
        # for group in first_filter:
        #     second_filter[group] = group_by_range(first_filter[group], 2, "specific_u_value")
        # x = dict(second_filter)
        # for group in x:
        #     if len(second_filter[str(group)]) < 2:
        #         del second_filter[str(group)]
        # zones = []
        # for group_1 in second_filter:
        #     for group_2 in second_filter[group_1]:
        #         zones.append(second_filter[group_1][group_2])
        # self.logger.info("Found %d possible zones", len(zones))

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
