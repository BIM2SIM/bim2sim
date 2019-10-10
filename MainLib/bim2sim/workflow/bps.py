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
        for wall in walls:
            representation = Element.factory(wall)
            if representation.is_external is True:
                external_walls.append(wall)
                external_walls_rep.append(representation)

        x1 = float("inf")
        x2 = -float("inf")
        y1 = float("inf")
        y2 = -float("inf")

        for element in external_walls_rep:
            if element.position[0] < x1:
                x1 = element.position[0]
                p_x1 = element.position[1]
            if element.position[0] > x2:
                x2 = element.position[0]
                p_x2 = element.position[1]
            if element.position[1] < y1:
                y1 = element.position[1]
                p_y1 = element.position[0]
            if element.position[1] > y2:
                y2 = element.position[1]
                p_y2 = element.position[0]

        project_origin = ((x2 + x1) / 2, (y2 + y1) / 2)
        mh_1 = (y2 - p_x1) / (p_y2 - x1)
        mh_2 = (p_x2 - y1) / (x2 - p_y1)
        mv_1 = (y2 - p_x2) / (p_y2 - x2)
        mv_2 = (p_x1 - y1) / (x1 - p_y1)

        if abs(mh_2 - mh_1) < 1:
            project_slope = (mh_2 + mh_1) / 2
        elif abs(mv_2 - mv_1) < 1:
            project_slope = (mv_2 + mv_1) / 2

        if project_slope < 0:
            project_slope = abs(1/project_slope)

        project_origin_rad = math.atan(project_slope)

        # 1st quadrant: x+ , y+
        # 2nd quadrant: x- , y+
        # 3rd quadrant: x- , y-
        # 4th quadrant: x+ , y-


        for wall in external_walls:
            shape = ifcopenshell.geom.create_shape(settings, wall)
            i = 0
            vertices = []
            while i < len(shape.geometry.verts):
                vertices.append(shape.geometry.verts[i:i + 2])
                i += 3
            edges = [shape.geometry.edges[i: i + 2] for i in range(0, len(shape.geometry.edges), 2)]
            slopes = []
            for edge in edges:
                if (vertices[edge[1]][0] - vertices[edge[0]][0]) != 0:
                    slope = (vertices[edge[1]][1] - vertices[edge[0]][1]) / (
                                vertices[edge[1]][0] - vertices[edge[0]][0])
                else:
                    slope = 9999999999
                slopes.append(slope)
            slopes_groups = group_by_range(slopes, 0.1, "j")
            n_slope = 0
            for slope in slopes_groups:
                if len(slopes_groups[slope]) > n_slope:
                    n_slope = len(slopes_groups[slope])
                    wall_slope = slopes_groups[slope][0]
            wall_angle = math.degrees(math.atan(wall_slope))
            representation = Element.factory(wall)

            x = representation.position[0] - project_origin[0]
            y = representation.position[1] - project_origin[1]
            x_new = - y * math.sin(project_origin_rad) + x * math.cos(project_origin_rad)
            y_new = y * math.cos(project_origin_rad) + x * math.sin(project_origin_rad)

            if x_new > 0 and y_new > 0:
                if 45 < wall_angle < 90:
                    orientation = "NE"
                else:
                    orientation = "NW"
            elif x_new < 0 and y_new > 0:
                if 90+45 < wall_angle < 180:
                    orientation = "NW"
                else:
                    orientation = "SW"
            elif x_new < 0 and y_new < 0:
                if 180 < wall_angle < 180+45:
                    orientation = "SW"
                else:
                    orientation = "SE"
            elif x_new > 0 and y_new < 0:
                orientation = "SE -  NE"
                if 270 < wall_angle < 270+45:
                    orientation = "SE"
                else:
                    orientation = "NE"



            # if 67.5 < abs(wall_angle) < 90:
            #     orientation = "O-W"
            # elif 0 < abs(wall_angle) < 22.5:
            #     orientation = "N-S"
            # elif -2.4142 < wall_slope < -0.4142:
            #     orientation = "NO-SW"
            # elif 0.4142 < wall_slope < 2.4142:
            #     orientation = "SÖ-NW"
            wall.Representation.Description = orientation
            shapes.append(shape)

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
