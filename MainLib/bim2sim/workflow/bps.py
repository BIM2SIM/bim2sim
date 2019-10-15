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
from bim2sim.ifc2python import elements
from collections import defaultdict
from bim2sim.ifc2python.aggregation import group_by_range
import ifcopenshell
import ifcopenshell.geom
import math
from shapely.geometry.polygon import Polygon
from shapely.geometry import Point


IFC_TYPES = (
    # 'IfcBuilding',
    'IfcWall',
    'IfcWallElementedCase',
    'IfcWallStandardCase',
    'IfcRoof',
    'IfcShadingDevice',
    'ifcSlab',
    'IfcPlate',
    'IfcCovering',
    'IfcDoor',
    'IfcWindow',
    'IfcSpace'
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
        shapes = []
        external_walls = []
        external_walls_rep = []
        walls = ifc.by_type('IfcWall')
        slabs = ifc.by_type('IfcSlab')

        area_slab = 0
        slab_big = 0
        slab_rep = 0
        for slab in slabs:
            representation = Element.factory(slab)
            area_element = representation.area
            if area_element > area_slab:
                area_slab = area_element
                slab_big = slab
                slab_rep = representation

        shape = ifcopenshell.geom.create_shape(settings, slab_big)
        vertices = []
        i = 0
        while i < len(shape.geometry.verts):
            vertices.append(shape.geometry.verts[i:i + 2])
            i += 3

        x1 = [float("inf"), 0]
        x2 = [-float("inf"), 0]
        y1 = [0, float("inf")]
        y2 = [0, -float("inf")]

        for element in vertices:

            if element[0] < x1[0]:
                x1 = [element[0], element[1]]
            if element[0] > x2[0]:
                x2 = [element[0], element[1]]
            if element[1] < y1[1]:
                y1 = [element[0], element[1]]
            if element[1] > y2[1]:
                y2 = [element[0], element[1]]

        x1[0] = x1[0] + slab_rep.position[0]
        x2[0] = x2[0] + slab_rep.position[0]
        y1[0] = y1[0] + slab_rep.position[0]
        y2[0] = y2[0] + slab_rep.position[0]
        x1[1] = x1[1] + slab_rep.position[1]
        x2[1] = x2[1] + slab_rep.position[1]
        y1[1] = y1[1] + slab_rep.position[1]
        y2[1] = y2[1] + slab_rep.position[1]

        building_envelope = []
        tolerance = 1
        # slope =
        # tolerance_x = tolerance*math.sin(slope)
        # tolerance_y = tolerance*math.sin(slope)

        building_envelope.append(Polygon([(x1[0]-tolerance, x1[1]+tolerance),
                                         (y2[0]+tolerance, y2[1]+tolerance),
                                         (y2[0]+tolerance, y2[1]-tolerance),
                                         (x1[0]-tolerance, x1[1]-tolerance)]))
        building_envelope.append(Polygon([(x2[0]-tolerance, x2[1]-tolerance),
                                         (y2[0]-tolerance, y2[1]+tolerance),
                                         (y2[0]+tolerance, y2[1]+tolerance),
                                         (x2[0]+tolerance, x2[1]-tolerance)]))
        building_envelope.append(Polygon([(x2[0] + tolerance, x2[1] - tolerance),
                                          (y1[0] - tolerance, y1[1] - tolerance),
                                          (y1[0] - tolerance, y1[1] + tolerance),
                                          (x2[0] + tolerance, x2[1] + tolerance)]))
        building_envelope.append(Polygon([(x1[0] + tolerance, x1[1] + tolerance),
                                          (y1[0] + tolerance, y1[1] - tolerance),
                                          (y1[0] - tolerance, y1[1] - tolerance),
                                          (x1[0] - tolerance, x1[1] + tolerance)]))


        for wall in walls:
            representation = Element.factory(wall)
            if representation.is_external is True:
                external_walls.append(wall)

        wall_orientation = {}

        for wall in external_walls:
            representation = Element.factory(wall)
            centroid = Point(representation.position[0:2])
            orientation = "False"
            if building_envelope[0].contains(centroid):
                orientation = "NW"
            elif building_envelope[1].contains(centroid):
                orientation = "NE"
            elif building_envelope[2].contains(centroid):
                orientation = "SE"
            elif building_envelope[3].contains(centroid):
                orientation = "SW"

            wall.Representation.Description = orientation
            wall_orientation[wall.Name] = orientation, representation.Pset_WallCommon['Pset_Desite']['cpRevitLevel']

        for ifc_type in relevant_ifc_types:
            elements_ = ifc.by_type(ifc_type)
            for element in elements_:
                representation = Element.factory(element)
                self.instances_bps[representation.guid] = representation
        self.logger.info("Found %d relevant elements", len(self.instances_bps))

        # find and fills spaces
        spaces = ifc.by_type('IfcSpace')
        instances_space = []
        for space in spaces:
            representation = elements.ThermalSpace(space)
            instances_space.append(representation)
            self.instances_bps[representation.guid] = representation
        print("")

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
