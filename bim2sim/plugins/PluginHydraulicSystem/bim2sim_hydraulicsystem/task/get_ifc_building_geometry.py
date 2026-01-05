import csv
import json
import numpy as np
import matplotlib.pyplot as plt
import math
from pathlib import Path
import ifcopenshell
import networkx as nx
from networkx.readwrite import json_graph
import threading

from bim2sim.tasks.base import ITask



class GetIFCBuildingGeometry(ITask):
    """Reads building geometry data out of an ifc model"""

    reads = ('ifc_files',)
    touches = ('floor_dict',)

    def run(self, ifc_files):

        self.lock = self.playground.sim_settings.lock

        self.hydraulic_system_directory = Path(self.paths.export / 'hydraulic system')
        self.hydraulic_system_directory.mkdir(parents=True, exist_ok=True)

        self.logger.info("Get building geometry")

        self.ifc_file = ifc_files[0].file
        if self.playground.sim_settings.generate_new_building_data:
            room = self.room_element_position()
            floor_dict = self.sort_room_floor(spaces_dict=room)
            self.write_json(data=floor_dict, filename=f"ifc_building_floor.json")
        else:
            floor_dict = self.load_json(filename=f"ifc_building_floor.json")

        return floor_dict,


    def write_json(self, data: dict, filename):
        export_path = self.hydraulic_system_directory / filename
        with self.lock:
            with open(export_path, "w") as f:
                json.dump(data, f, indent=4)

    def load_json(self, filename):
        import_path = Path(self.paths.root).parent / filename
        with self.lock:
            with open(import_path, "r") as f:
                file = json.load(f)
        return file

    def get_geometry(self):
        spaces = self.ifc_file.by_type("IfcSpace")
        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_PYTHON_OPENCASCADE, True)

        # Geometrieinformationen der Spaces und Fenster extrahieren
        for space in spaces:
            shape = ifcopenshell.geom.create_shape(settings, space).geometry
            representation = space.Representation
            if representation:
                shape_representation = representation.Representations[0]
                if shape_representation.is_a("IfcShapeRepresentation"):
                    # Abrufen der Geometrieinformationen
                    items = shape_representation.Items
                    for item in items:
                        if item.is_a("IfcFacetedBrep"):
                            for face in item.Outer.CfsFaces:
                                for bound in face.Bounds:
                                    if bound.is_a("IfcFaceOuterBound"):
                                        bound_geometry = bound.Bound
                                        if bound_geometry.is_a("IfcPolyLoop"):
                                            polygon = bound_geometry.Polygon
                                            vertices = [vertex_coords for vertex_coords in polygon]
                                            global_vertices = ifcopenshell.geom.create_shape(self.ifc_file,
                                                                                             vertices).geometry

    def sort_space_data(self, floor_elements, ref_point: tuple = (0, 0, 0)):
        """
        Args:
            floor_elements ():
            ref_point ():
        Returns:

        """
        element_dict = {}
        room_dict = {}
        start_dict = {}
        floor_dict = {}
        r_point = tuple
        for floor in floor_elements:
            _dict_floor = {}
            _dict_floor["type"] = floor_elements[floor]["type"]
            _dict_floor["height"] = floor_elements[floor]["height"]
            _dict_floor["heat_source"] = (ref_point[0], ref_point[1], floor_elements[floor]["height"])
            floor_dict[floor] = _dict_floor
            etage = floor_elements[floor]
            rooms = etage["rooms"]
            for room in rooms:
                _room_dict = {}
                _room_dict["type"] = rooms[room]["type"]
                _room_dict["global_corners"] = rooms[room]["global_corners"]
                _room_dict["belongs_to"] = rooms[room]["belongs_to"]
                room_dict[room] = _room_dict
                elements = rooms[room]["room_elements"]
                # room_points.extend(rooms[room]["global_corners"])
                # max_coords = np.amax(rooms[room]["global_corners"], axis=0)
                # min_coords = np.amin(rooms[room]["global_corners"], axis=0)
                # room_dict[room] =
                for element in elements:
                    _element_dict = {}
                    if elements[element]["type"] == "wall":
                        corner_points = elements[element]["global_corners"]
                    if elements[element]["type"] == "door":
                        corner_points = elements[element]["global_corners"]
                    if elements[element]["type"] == "window":
                        _element_dict["type"] = elements[element]["type"]
                        _element_dict["global_corners"] = elements[element]["global_corners"]
                        _element_dict["belongs_to"] = elements[element]["belongs_to"]
                        element_dict[element] = _element_dict

                        """corner_points = elements[element]["global_corners"]
                        end_point = tuple(np.mean(corner_points, axis=0))
                        p_rounded = tuple(round(coord, 2) for coord in end_point)
                        if p_rounded[0] > max_coords[0]:
                            x_window = max_coords[0]
                        elif p_rounded[0] < min_coords[0]:
                            x_window = min_coords[0]
                        else:
                            x_window = p_rounded[0]
                        if p_rounded[1] > max_coords[1]:
                            y_window = max_coords[1]
                        elif p_rounded[1] < min_coords[1]:
                            y_window = min_coords[1]
                        else:
                            y_window = p_rounded[1]
                        p_rounded = (x_window, y_window, etage["height"])

                        room_points.append(p_rounded)"""

        return floor_dict, room_dict, element_dict

    def occ_core_global_points(self, element, reduce_flag: bool = True):
        settings = ifcopenshell.geom.settings()
        settings.set(settings.USE_WORLD_COORDS, True)
        shape = ifcopenshell.geom.create_shape(settings, element)
        verts = shape.geometry.verts
        grouped_verts = [(round(verts[i], 2), round(verts[i + 1], 2), round(verts[i + 2], 2)) for i in
                         range(0, len(verts), 3)]
        """grouped_verts = [(verts[i], verts[i + 1], verts[i + 2]) for i in
                         range(0, len(verts), 3)]"""
        if reduce_flag is True and len(grouped_verts) > 8:
            grouped_verts = np.array(grouped_verts)
            x_min = np.min(grouped_verts[:, 0])
            x_max = np.max(grouped_verts[:, 0])
            y_min = np.min(grouped_verts[:, 1])
            y_max = np.max(grouped_verts[:, 1])
            z_min = np.min(grouped_verts[:, 2])
            z_max = np.max(grouped_verts[:, 2])
            grouped_verts = [(x_min, y_min, z_min), \
                             (x_max, y_min, z_min), \
                             (x_max, y_max, z_min), \
                             (x_min, y_max, z_min), \
                             (x_min, y_min, z_max), \
                             (x_max, y_min, z_max), \
                             (x_max, y_max, z_max), \
                             (x_min, y_max, z_max)]
        else:
            points = np.array(grouped_verts)
            z_min = np.min(points[:, 2])

        return grouped_verts, z_min

    def visualize_spaces(self):
        import OCC.Core.TopoDS
        settings_display = ifcopenshell.geom.settings()
        settings_display.set(settings_display.USE_PYTHON_OPENCASCADE, True)
        settings_display.set(settings_display.USE_WORLD_COORDS, True)
        settings_display.set(settings_display.EXCLUDE_SOLIDS_AND_SURFACES, False)
        settings_display.set(settings_display.INCLUDE_CURVES, True)

        spaces = self.ifc_file.by_type("IfcSpace")
        windows = self.ifc_file.by_type("ifcWindow")
        display, start_display, add_menu, add_function_to_menu = init_display()
        for tz in spaces:
            color = 'blue'
            if tz.LongName:
                if 'Buero' in tz.LongName:
                    color = 'red'
                elif 'Besprechungsraum' in tz.LongName:
                    color = 'green'
                elif 'Schlafzimmer' in tz.LongName:
                    color = 'yellow'
            shape = ifcopenshell.geom.create_shape(settings_display, tz).geometry
            display.DisplayShape(shape, update=True, color=color,
                                 transparency=0.7)

        for space in windows:
            shape = ifcopenshell.geom.create_shape(settings_display, space).geometry
            display.DisplayShape(shape, update=True, transparency=0.7)
        display.FitAll()
        start_display()

    def get_relative_matrix(self, relative_placement):
        # Definieren Sie die X-, Y- und Z-Achsen als 3x1 Spaltenvektoren.
        x_axis = np.array(relative_placement.RefDirection.DirectionRatios).reshape(3, 1)
        z_axis = np.array(relative_placement.Axis.DirectionRatios).reshape(3, 1)
        y_axis = np.cross(z_axis.T, x_axis.T).T

        # Kombinieren Sie die Achsen in eine 3x3 Rotationsmatrix.
        rotation_matrix = np.concatenate((x_axis, y_axis, z_axis), axis=1)
        # Erstellen Sie eine 4x4-Homogene Transformationsmatrix.
        relative_matrix = np.eye(4)
        relative_matrix[:3, :3] = rotation_matrix
        relative_matrix[:3, 3] = np.array(relative_placement.Location.Coordinates)
        return relative_matrix

    def get_global_matrix(self, element):
        if hasattr(element, 'ObjectPlacement'):
            if hasattr(element.ObjectPlacement.RelativePlacement.RefDirection, 'DirectionRatios'):
                matrix_chain = [self.get_relative_matrix(element.ObjectPlacement.RelativePlacement)]
                parent_placement = element.ObjectPlacement.PlacementRelTo
                if hasattr(parent_placement.RelativePlacement.RefDirection, 'DirectionRatios'):
                    while parent_placement is not None:
                        if parent_placement.RelativePlacement.RefDirection is None:
                            parent_placement = None
                        else:
                            parent_matrix = self.get_relative_matrix(parent_placement.RelativePlacement)
                            matrix_chain.insert(0, parent_matrix)
                            parent_placement = parent_placement.PlacementRelTo
                absolute_matrix = np.eye(4)
                for matrix in matrix_chain:
                    absolute_matrix = np.dot(absolute_matrix, matrix)

                return absolute_matrix
            else:
                absolute = np.array(element.ObjectPlacement.RelativePlacement.Location.Coordinates)
                placementrel = element.ObjectPlacement.PlacementRelTo
                while placementrel is not None:
                    absolute += np.array(placementrel.RelativePlacement.Location.Coordinates)
                    placementrel = placementrel.PlacementRelTo
                absolute_matrix = np.eye(4)
                absolute_matrix[:3, 3] = absolute
                return absolute_matrix

    def calc_global_position(self, element):
        if hasattr(element, 'ObjectPlacement'):
            absolute = np.array(element.ObjectPlacement.RelativePlacement.Location.Coordinates)
            placementrel = element.ObjectPlacement.PlacementRelTo
            while placementrel is not None:
                absolute += np.array(placementrel.RelativePlacement.Location.Coordinates)
                placementrel = placementrel.PlacementRelTo
        else:
            absolute = None
        return absolute

    def calc_bounding_box(self, element):
        from ifcopenshell.geom.occ_utils import get_bounding_box_center
        global_box = None
        for rep in element.Representation.Representations:
            if rep.RepresentationType == "BoundingBox":
                bound_box = rep.Items[0]
                box = bound_box.XDim, bound_box.YDim, bound_box.ZDim
                matrix = self.get_global_matrix(element=element)
                rot_matrix = matrix[:3, :3]
                global_box = np.dot(rot_matrix, box)[:3]
                break
            else:
                bbox = None
                if element.IsDefinedBy:
                    for rel in element.IsDefinedBy:

                        if rel.RelatingPropertyDefinition.is_a("IfcShapeAspect"):
                            shape_aspect = rel.RelatingPropertyDefinition
                            if shape_aspect.ShapeRepresentations:
                                for shape in shape_aspect.ShapeRepresentations:
                                    if shape.is_a("IfcProductDefinitionShape"):

                                        if shape.BoundingBox:
                                            bbox = shape.BoundingBox
                                            break
                if bbox:
                    return [
                        bbox.Corner[0].Coordinates[0],
                        bbox.Corner[0].Coordinates[1],
                        bbox.Corner[0].Coordinates[2],
                        bbox.Corner[1].Coordinates[0],
                        bbox.Corner[1].Coordinates[1],
                        bbox.Corner[1].Coordinates[2],
                    ]
        return global_box

    def ifc_path(self, element):
        path_elements = self.ifc_file.by_type("IfcPath")
        connected_paths = []
        # Durch alle IfcPath-Entitäten iterieren
        for path_element in path_elements:
            # if element.is_a("IfcWall"):
            """if element.GlobalId == path_element:
                relationship = path_element.RelatedFeatureElements[0]

                # Pfadelemente holen
                connected_path = relationship.RelatingElement.Name
                connected_paths.append(connected_path)
            # IfcRelConnectsPathElements-Beziehung abrufen
            relationship = path_element.RelatedFeatureElements[0]
            # Pfadelemente holen
            connected_path = relationship.RelatingElement.Name
            connected_paths.append(connected_path)"""

    def related_object_space(self, room):
        room_elements = []
        element_dict = {}
        for boundary_element in self.ifc_file.by_type("IfcRelSpaceBoundary"):
            if boundary_element.RelatingSpace == room:
                room_elements.append(boundary_element.RelatedBuildingElement)
        for element in room_elements:
            if element is not None:
                box = None
                if element.is_a("IfcWall"):
                    # global_corners, z_min = self.occ_core_global_points(element=element, reduce_flag=False)
                    global_corners, z_min = self.occ_core_global_points(element=element)
                    x_coords = [point[0] for point in global_corners]
                    y_coords = [point[1] for point in global_corners]
                    x_diff = np.max(x_coords) - np.min(x_coords)
                    y_diff = np.max(y_coords) - np.min(y_coords)
                    if x_diff > y_diff:
                        direction = "x"
                    else:
                        direction = "y"
                    connected_wall_ids = []
                    if element.ConnectedTo:
                        connected_wall_ids.extend([connected_wall.id() for connected_wall in element.ConnectedTo])
                    element_dict[element.GlobalId] = {"type": "wall",
                                                      "number": element.Name,
                                                      "id": element.id(),
                                                      # "transformation_matrix": matrix,
                                                      # "Position": absolute_position,
                                                      "height": z_min,
                                                      # "Bounding_box": global_box,
                                                      "global_corners": global_corners,
                                                      "belongs_to": room.GlobalId,
                                                      "direction": direction,
                                                      "connected_element": connected_wall_ids
                                                      }
                if element.is_a("IfcDoor"):
                    global_corners, z_min = self.occ_core_global_points(element=element)
                    x_coords = [point[0] for point in global_corners]
                    y_coords = [point[1] for point in global_corners]
                    x_diff = np.max(x_coords) - np.min(x_coords)
                    y_diff = np.max(y_coords) - np.min(y_coords)
                    if x_diff > y_diff:
                        direction = "x"
                    else:
                        direction = "y"
                    element_dict[element.GlobalId] = {"type": "door",
                                                      "number": element.Name,
                                                      "id": element.id(),
                                                      "height": z_min,
                                                      "global_corners": global_corners,
                                                      "belongs_to": room.GlobalId,
                                                      "direction": direction}
                if element.is_a("IfcWindow"):
                    global_corners, z_min = self.occ_core_global_points(element=element)
                    x_coords = [point[0] for point in global_corners]
                    y_coords = [point[1] for point in global_corners]
                    x_diff = np.max(x_coords) - np.min(x_coords)
                    y_diff = np.max(y_coords) - np.min(y_coords)
                    if x_diff > y_diff:
                        direction = "x"
                    else:
                        direction = "y"
                    element_dict[element.GlobalId] = {"type": "window",
                                                      "number": element.Name,
                                                      "id": element.id(),
                                                      "height": z_min,
                                                      "global_corners": global_corners,
                                                      "belongs_to": room.GlobalId,
                                                      "direction": direction}
        return element_dict

    def floor_heights_position(self):
        floor_heights = {}
        for floor in self.ifc_file.by_type("IfcBuildingStorey"):
            floor_heights[floor.GlobalId] = {"Name": floor.Name,
                                             "height": floor.Elevation,
                                             "rooms": []}
        return floor_heights

    def absolute_points_room(self, element, matrix):
        points = []
        for rep in element.Representation.Representations:
            if rep.RepresentationType == "BoundingBox":
                bound_box = rep.Items[0]
                length, width, height = bound_box.XDim, bound_box.YDim, bound_box.ZDim
                corners = np.array(
                    [(0, 0, 0, 1), (length, 0, 0, 1), (length, width, 0, 1), (0, width, 0, 1), (0, 0, height, 1),
                     (length, 0, height, 1), (length, width, height, 1), (0, width, height, 1)])
                global_corners = corners.dot(matrix.T)
                for corner in global_corners[:, :3]:
                    c_rounded = tuple(round(coord, 2) for coord in corner)
                    points.append(tuple(c_rounded))
                return points

    def room_element_position(self):
        spaces_dict = {}
        global_box = None
        global_corners = None
        for space in self.ifc_file.by_type("IfcSpace"):
            # absolute_position = self.calc_global_position(element=space)
            # absolute position room
            # matrix = self.get_global_matrix(element=space)
            # relative_point = np.array([0, 0, 0, 1])
            # absolute_position = np.dot(matrix, relative_point)[:3]
            # Bounding box
            # global_box = self.calc_bounding_box(space)

            # global_corners = self.absolute_points_room(element=space, matrix=matrix)
            global_corners, z_min = self.occ_core_global_points(element=space)
            x_coords = [point[0] for point in global_corners]
            y_coords = [point[1] for point in global_corners]
            x_diff = np.max(x_coords) - np.min(x_coords)
            y_diff = np.max(y_coords) - np.min(y_coords)
            if x_diff > y_diff:
                direction = "x"
            else:
                direction = "y"
            spaces_dict[space.GlobalId] = {"type": "space",
                                           "number": space.Name,
                                           "Name": space.LongName,
                                           "id": space.id(),
                                           "height": z_min,
                                           "direction": direction,
                                           # "transformation_matrix": matrix,
                                           # "Position": absolute_position,
                                           # "Bounding_box": global_box,
                                           "global_corners": global_corners,
                                           "room_elements": []
                                           }
            room_elements = self.related_object_space(room=space)
            spaces_dict[space.GlobalId]["room_elements"] = room_elements
        return spaces_dict

    def sort_room_floor(self, spaces_dict):
        floor_elements = {}
        spaces_dict_copy = spaces_dict.copy()
        for floor in self.ifc_file.by_type("IfcBuildingStorey"):
            floor_elements[floor.GlobalId] = {"type": "floor",
                                              "Name": floor.Name,
                                              "height": floor.Elevation,
                                              "rooms": []}
            rooms_on_floor = {}
            for room in spaces_dict_copy:
                # space_height = spaces_dict[room]["Position"][2]
                space_height = spaces_dict[room]["height"]
                if floor.Elevation == space_height:
                    spaces_dict[room]["belongs_to"] = floor.GlobalId
                    rooms_on_floor[room] = spaces_dict[room]
            floor_elements[floor.GlobalId]["rooms"] = rooms_on_floor
        return floor_elements

    def visualzation_grid_3D(self, G):
        node_xyz = np.array([v for v in sorted(G)])
        edge_xyz = np.array([(u, v) for u, v in G.edges()])
        fig = plt.figure()
        ax = fig.add_subplot(111, projection="3d")
        # ax.scatter(*node_xyz.T, s=100, ec="w")
        for vizedge in edge_xyz:
            ax.plot(*vizedge.T, color="tab:gray")
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.set_zlabel("z")
        fig.tight_layout()
        plt.show()
        plt.close()

    def visualzation_networkx_3D(self, G, minimum_tree, start_points, end_points):
        node_xyz = np.array([v for v in sorted(G)])
        edge_xyz = np.array([(u, v) for u, v in G.edges()])
        fig = plt.figure()
        ax = fig.add_subplot(111, projection="3d")
        # for i, coord in enumerate(points):
        #    t = tuple(round(p, 2) for p in coord)
        #    ax.text(coord[0], coord[1], coord[2], t, color='red')
        ax.scatter(*node_xyz.T, s=100, ec="w")
        for vizedge in edge_xyz:
            ax.plot(*vizedge.T, color="tab:gray")
        colors = ['r', 'g', 'b', 'y', 'm', 'c', 'w', 'r', 'g']
        for edge in minimum_tree.edges():
            xs = [edge[0][0], edge[1][0]]
            ys = [edge[0][1], edge[1][1]]
            zs = [edge[0][2], edge[1][2]]
            ax.plot(xs, ys, zs, color="red")
        for end in end_points:
            ax.scatter(*end, s=100, ec="w", color="black")
        # for start in start_points:
        #    ax.scatter(*start, s=100, ec="w", color="green")
        ax.scatter(*start_points, s=100, ec="w", color="green")
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.set_zlabel("z")
        fig.tight_layout()
        plt.show()
        plt.close()

    def visualzation_networkx_2D(self, G, short_edges, other_edges, start_ref, end_points):
        pos = nx.spring_layout(G)
        for edge in other_edges:
            nx.draw_networkx_edges(G, pos, edgelist=edge, edge_color='black')
        for edge in short_edges:
            nx.draw_networkx_edges(G, pos, edgelist=edge, edge_color='red')
        nx.draw_networkx_nodes(G, pos)
        nx.draw_networkx_labels(G, pos)
        nx.draw_networkx_nodes(G, pos, nodelist=[start_ref], node_color='g')
        for end in end_points:
            nx.draw_networkx_nodes(G, pos, nodelist=[end], node_color='r')

    def create_grid(self, graph: nx.DiGraph, points: list):
        # self.reduce_nodes(graph=graph)
        graph = self.create_edges(graph=graph, room_points=points)
        graph = self.limit_neighbors(graph)
        self.export_graph_json(graph)
        self.load_json_pipes(graph)
        return graph

    def load_json_pipes(self, graph):
        G = nx.Graph()
        G.add_edge(1, 2)
        G.add_edge(2, 3)
        net = pp.create_empty_network(name="MyNetwork")

        # Füge Knoten zum Netzwerk hinzu
        for node in G.nodes:
            pp.create_junction(net, node_name=str(node), pn_bar=1.0, tfluid_k=283.15)
        # Füge Kanten zum Netzwerk hinzu
        for edge in G.nodes:
            from_bus = str(edge[0])
            to_bus = str(edge[1])
            # Überprüfe, ob die Knoten existieren, bevor du eine Rohrleitung erstellst
            if from_bus in net.junction.index and to_bus in net.junction.index:
                pp.create_pipe_from_parameters(net, from_bus, to_bus, length_km=1, diameter_m=0.1)
            else:
                self.logger.info(
                    f"Warning: Pipe {from_bus}-{to_bus} tries to attach to non-existing junction(s) {from_bus} or {to_bus}.")

        # Prüfe, ob das Netzwerk korrekt erstellt wurde

    def export_graph_json(self, G):
        data = nx.readwrite.json_graph.node_link_data(G)
        with self.lock:
            with open("graph.json", "w") as f:
                json.dump(data, f)

    def limit_neighbors(self, graph: nx.DiGraph):
        for node in graph.nodes():
            neighbors = {}
            for neighbor in graph.neighbors(node):
                direction = tuple(
                    [(neighbor[i] - node[i]) // abs(neighbor[i] - node[i]) if neighbor[i] != node[i] else 0 for i in
                     range(3)])
                if direction in neighbors and neighbors[direction]:
                    neighbors[direction].add(neighbor)
            neighbor_count = 0
            for direction in neighbors:
                direction_neighbors = sorted(list(neighbors[direction]),
                                             key=lambda neighbor: abs(neighbor[0] - node[0]) + abs(
                                                 neighbor[1] - node[1]) + abs(neighbor[2] - node[2]))
                for neighbor in direction_neighbors:
                    if neighbor_count >= 6:
                        graph.remove_edge(node, neighbor)
                    else:
                        neighbor_count += 1
        return graph

    def spanning_tree(self, graph: nx.DiGraph(), start, end_points):
        # Finden des kürzesten Pfades mit dem Dijkstra-Algorithmus für jeden Endknoten
        shortest_paths = {}
        for end_node in end_points:
            shortest_path = nx.dijkstra_path(graph, start, end_node)
            shortest_paths[end_node] = shortest_path

        # Kombinieren der Kanten der kürzesten Pfade zu einem Baum
        T = nx.Graph()
        for end_node, shortest_path in shortest_paths.items():
            for i in range(len(shortest_path) - 1):
                edge = (shortest_path[i], shortest_path[i + 1])
                T.add_edge(*edge, length=graph.get_edge_data(*edge)['length'])
        # Ausgabe des Ergebnisses
        mst = nx.minimum_spanning_tree(T)
        lengths = [edge[2]['length'] for edge in mst.edges(data=True)]
        total_length = sum(lengths)
        if self.playground.sim_settings.export_graphs:
            self.visualzation_networkx_3D(G=graph, minimum_tree=mst, start_points=start, end_points=end_points)
        return graph, mst, start, end_points

    def shortest_path(self, graph: nx.DiGraph(), start, end_points):
        # todo: Gewichtung: Doppelte wege
        # todo: zusätzliche Gewichtung: Z-Richtung
        # todo: https://networkx.org/documentation/stable/reference/algorithms/shortest_paths.html
        # Erstelle einen Graphen mit den Punkten als Knoten
        _short_path_edges = []
        _other_path_edges = []
        # todo: doppelte kanten verhindern
        for end in end_points:
            path = nx.dijkstra_path(graph, start, end, length='length')
            distance = nx.dijkstra_path_length(graph, start, end, length='length')
            _short_path_edges.append(list(zip(path, path[1:])))
            _other_path_edges.append([edge for edge in graph.edges() if edge not in list(zip(path, path[1:]))])
            self.logger.info("Kürzester Pfad:", path)
            self.logger.info("Distanz:", distance)
        return graph, _short_path_edges, _other_path_edges, start, end_points

    def calc_pipe_coordinates(self, floors, ref_point):
        # todo: referenzpunkt einer eckpunkte des spaces zu ordnen: for d in distance(x_ref, poin
        # todo: Konten reduzieren
        # todo: path_lengths = nx.multi_source_dijkstra_path_length(G, [start_node], target=end_nodes, length='length')
        G = nx.DiGraph()
        _short_path = []
        _other_path = []
        _end_points = []
        _room_points = []
        _start_points = []
        for floor in floors:
            room_points = []
            etage = floors[floor]
            rooms = etage["rooms"]
            r_point = (ref_point[0], ref_point[1], etage["height"])
            _start_points.append(tuple(r_point))
            room_points.append(r_point)
            # rooms[room]["Position"]
            # rooms[room]["global_corners"]
            # rooms[room]["Bounding_box"]
            # rooms[room]["room_elements"]
            room_floor_end_points = []
            # room_points_floor = []
            for room in rooms:
                elements = rooms[room]["room_elements"]
                room_points.extend(rooms[room]["global_corners"])
                max_coords = np.amax(rooms[room]["global_corners"], axis=0)
                min_coords = np.amin(rooms[room]["global_corners"], axis=0)
                for element in elements:
                    if elements[element]["type"] == "wall":
                        corner_points = elements[element]["global_corners"]
                        # x_midpoint = np.mean(corner_points[:, 0])
                        # y_midpoint = np.mean(corner_points[:, 1])
                        # z_low = np.min(corner_points[:, 2])
                        # end_point = np.array([x_midpoint, y_midpoint, z_low])
                        # end_points.append(end_point)
                    if elements[element]["type"] == "door":
                        corner_points = elements[element]["global_corners"]
                        # x_midpoint = np.mean(corner_points[:, 0])
                        # y_midpoint = np.mean(corner_points[:, 1])
                        # z_low = np.min(corner_points[:, 2])
                        # end_point = np.array([x_midpoint, y_midpoint, z_low])
                        # end_points.append(end_point)
                    if elements[element]["type"] == "window":
                        corner_points = elements[element]["global_corners"]
                        end_point = tuple(np.mean(corner_points, axis=0))
                        p_rounded = tuple(round(coord, 2) for coord in end_point)
                        if p_rounded[0] > max_coords[0]:
                            x_window = max_coords[0]
                        elif p_rounded[0] < min_coords[0]:
                            x_window = min_coords[0]
                        else:
                            x_window = p_rounded[0]
                        if p_rounded[1] > max_coords[1]:
                            y_window = max_coords[1]
                        elif p_rounded[1] < min_coords[1]:
                            y_window = min_coords[1]
                        else:
                            y_window = p_rounded[1]
                        p_rounded = (x_window, y_window, etage["height"])
                        room_floor_end_points.append(p_rounded)
                        room_points.append(p_rounded)
            G = self.create_grid(G, room_points)
            # result = self.shortest_path(graph=G, start=r_point, end_points=room_floor_end_points)
            result = self.spanning_tree(graph=G, start=r_point, end_points=room_floor_end_points)
            G = result[0]


if __name__ == '__main__':

    working_path = r"D:\dja-jho\Testing\HydraulicSystem"

    ifc = Path(working_path, "AC20-Institute-Var-2.ifc")
    dym_json_file = Path(working_path, "tz_mapping.json")
    dym_mat_file = Path(working_path, "2010_heavy_Alu_Isolierverglasung_bearbeitet.mat")



    ifc_building_json = Path(working_path, "ifc_building.json")
    ifc_delivery_json = Path(working_path, "ifc_delivery.json")

    ifc = IfcBuildingsGeometry(ifc_file=ifc,
                               ifc_building_json=ifc_building_json,
                               ifc_delivery_json=ifc_delivery_json
                               )

    test = CreateHeatingCircle()

