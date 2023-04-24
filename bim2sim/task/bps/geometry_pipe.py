import ifcopenshell
import ifcopenshell.geom
import numpy as np
import math

import ifcopenshell.util.unit as unit
import ifcopenshell.util.element
import ifcopenshell.geom
import matplotlib.pyplot as plt
import networkx as nx
from mpl_toolkits.mplot3d import Axes3D
import gym
import tensorflow as tf
from gym import spaces
from tensorflow import keras
import itertools


class PipeGeometry():

    def __init__(self, ifc_file):
        print(ifc_file)
        self.model = ifcopenshell.open(ifc_file)

    def get_transformation_matrix(self, element):
        """Return the transformation matrix for an IfcAxis2Placement3D object."""
        # Get the location and axis vectors
        placement = element.ObjectPlacement.RelativePlacement
        # Erstellen der Transformationsmatrix
        """matrix = np.array([[placement.RefDirection.DirectionRatios[0], placement.RefDirection.DirectionRatios[1],
             placement.RefDirection.DirectionRatios[2], 0],
            [placement.Axis.DirectionRatios[0], placement.Axis.DirectionRatios[1], placement.Axis.DirectionRatios[2],
             0],
            [placement.Location.Coordinates[0], placement.Location.Coordinates[1], placement.Location.Coordinates[2],
             0],
            [0, 0, 0, 1]
        ])"""
        x_axis = np.array(placement.RefDirection.DirectionRatios).reshape(3, 1)
        y_axis = np.array(placement.Axis.DirectionRatios).reshape(3, 1)
        z_axis = np.cross(x_axis.T, y_axis.T).T
        # Kombinieren Sie die Achsen in eine 3x3 Rotationsmatrix.
        rotation_matrix = np.concatenate((x_axis, y_axis, z_axis), axis=1)

        # Erstellen Sie eine 4x4-Homogene Transformationsmatrix.
        relative_matrix = np.eye(4)
        relative_matrix[:3, :3] = rotation_matrix
        relative_matrix[:3, 3] = np.array(placement.Location.Coordinates)
        matrix = np.dot(relative_matrix, absolute_matrix)
        # Erstellen der globalen Koordinatenachsen
        x_axis = np.array([1, 0, 0, 1])
        y_axis = np.array([0, 1, 0, 1])
        z_axis = np.array([0, 0, 1, 1])
        return matrix

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
        global_box = None
        for rep in element.Representation.Representations:
            if rep.RepresentationType == "BoundingBox":
                bound_box = rep.Items[0]
                box = bound_box.XDim, bound_box.YDim, bound_box.ZDim
                matrix = self.get_global_matrix(element=element)
                rot_matrix = matrix[:3, :3]
                global_box = np.dot(rot_matrix, box)[:3]
                break
        return global_box

    def related_object_space(self, room):
        room_elements = []
        element_dict = {}
        for boundary_element in self.model.by_type("IfcRelSpaceBoundary"):
            if boundary_element.RelatingSpace == room:
                room_elements.append(boundary_element.RelatedBuildingElement)
        for element in room_elements:
            if element is not None:
                # wohl korrekt
                box = None
                if element.is_a("IfcWall"):
                    matrix = self.get_global_matrix(element)
                    relative_point = np.array([0, 0, 0, 1])
                    absolute_position = np.dot(matrix, relative_point)[:3]
                    global_box = self.calc_bounding_box(element)
                    global_corners = self.absolute_points_room(element=element, matrix=matrix)
                    element_dict[element.GlobalId] = {"type": "Wall",
                                                      "number": element.Name,
                                                      "id": element.id(),
                                                      # "transformation_matrix": matrix,
                                                      "Position": absolute_position,
                                                      # "Bounding_box": global_box,
                                                      "global_corners": global_corners
                                                      }
                if element.is_a("IfcDoor"):
                    matrix = self.get_global_matrix(element)
                    relative_point = np.array([0, 0, 0, 1])
                    absolute_position = np.dot(matrix, relative_point)[:3]
                    global_box = self.calc_bounding_box(element)
                    global_corners = self.absolute_points_room(element=element, matrix=matrix)
                    element_dict[element.GlobalId] = {"type": "Door",
                                                      "number": element.Name,
                                                      "id": element.id(),
                                                      # "transformation_matrix": matrix,
                                                      "Position": absolute_position,
                                                      # "Bounding_box": global_box,
                                                      "global_corners": global_corners}
                # todo: Fenster Koordianten noch nicht korrekt: die bounding box wird falsch addiert, allerdings scheint die Transformationsmatrix auch nicht korrekt zu sein.
                if element.is_a("IfcWindow"):
                    matrix = self.get_global_matrix(element)
                    relative_point = np.array([0, 0, 0, 1])
                    absolute_position = np.dot(matrix, relative_point)[:3]
                    global_box = self.calc_bounding_box(element)
                    global_corners = self.absolute_points_room(element=element, matrix=matrix)
                    element_dict[element.GlobalId] = {"type": "Window",
                                                      "number": element.Name,
                                                      "id": element.id(),
                                                      # "transformation_matrix": matrix,
                                                      "Position": absolute_position,
                                                      # "Bounding_box": global_box,
                                                      "global_corners": global_corners}
        return element_dict

    def transformation_matrix(self):
        element = self.model.by_type('IfcWindow')[4]
        print(element.Name)
        settings = ifcopenshell.geom.settings()
        shape = ifcopenshell.geom.create_shape(settings, element)
        absolute_matrix = self.get_global_matrix(element)
        print("Global Function: ", absolute_matrix)

        matrix = shape.transformation.matrix.data
        print("ifcopenopenshell shape function", matrix)
        matrix = self.calc_global_position(element)
        print("bim2sim", matrix)

        edges = shape.geometry.edges
        verts = shape.geometry.verts
        faces = shape.geometry.faces
        grouped_verts = [[verts[i], verts[i + 1], verts[i + 2]] for i in range(0, len(verts), 3)]
        grouped_edges = [[edges[i], edges[i + 1]] for i in range(0, len(edges), 2)]
        grouped_faces = [[faces[i], faces[i + 1], faces[i + 2]] for i in range(0, len(faces), 3)]
        # print(grouped_edges)

        pass

    def floor_heights_position(self):
        floor_heights = {}
        for floor in self.model.by_type("IfcBuildingStorey"):
            floor_heights[floor.GlobalId] = {"Name": floor.Name,
                                             "height": floor.Elevation,
                                             "rooms": []}
        return floor_heights

    def show_relative_coordinate_system(self, element):
        placement = element.ObjectPlacement.RelativePlacement

        # Erstellen der Transformationsmatrix
        matrix = np.array([
            [placement.RefDirection.DirectionRatios[0], placement.RefDirection.DirectionRatios[1],
             placement.RefDirection.DirectionRatios[2], 0],
            [placement.Axis.DirectionRatios[0], placement.Axis.DirectionRatios[1], placement.Axis.DirectionRatios[2],
             0],
            [placement.Location.Coordinates[0], placement.Location.Coordinates[1], placement.Location.Coordinates[2],
             0],
            [0, 0, 0, 1]
        ])
        print(matrix)
        # Erstellen der globalen Koordinatenachsen
        x_axis = np.array([1, 0, 0, 1])
        y_axis = np.array([0, 1, 0, 1])
        z_axis = np.array([0, 0, 1, 1])

        # Transformieren der globalen Koordinatenachsen
        x_axis_global = np.dot(matrix, x_axis)[:3]
        y_axis_global = np.dot(matrix, y_axis)[:3]
        z_axis_global = np.dot(matrix, z_axis)[:3]

        # Ausgabe der Ergebnisse
        print("Relative Koordinatensystem-Achsen:")
        print(f"x-Achse: {placement.RefDirection.DirectionRatios}")
        print(f"y-Achse: {placement.Axis.DirectionRatios}")
        print(f"z-Achse: {np.cross(placement.RefDirection.DirectionRatios, placement.Axis.DirectionRatios)}")

        print("Globale Koordinatensystem-Achsen:")
        print(f"x-Achse: {x_axis_global}")
        print(f"y-Achse: {y_axis_global}")
        print(f"z-Achse: {z_axis_global}")

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
        for space in self.model.by_type("IfcSpace"):
            # absolute_position = self.calc_global_position(element=space)
            # absolute position room
            matrix = self.get_global_matrix(element=space)
            relative_point = np.array([0, 0, 0, 1])
            absolute_position = np.dot(matrix, relative_point)[:3]
            print(space)
            print(absolute_position)
            # Bounding box
            global_box = self.calc_bounding_box(space)
            print(global_box)
            global_corners = self.absolute_points_room(element=space, matrix=matrix)
            spaces_dict[space.GlobalId] = {"type": "Space",
                                           "number": space.Name,
                                           "Name": space.LongName,
                                           "id": space.id(),
                                           # "transformation_matrix": matrix,
                                           "Position": absolute_position,
                                           # "Bounding_box": global_box,
                                           "global_corners": global_corners,
                                           "room_elements": []}
            room_elements = self.related_object_space(room=space)
            spaces_dict[space.GlobalId]["room_elements"] = room_elements
        return spaces_dict

    def read_pipe_segment(self):
        pass

    def write_pipe_segment(self):
        new_pipe = self.model.createIfcPipeSegment()
        # Weisen Sie dem neuen Rohr die relevanten Eigenschaften zu
        new_pipe.Name = "Your Pipe Name"
        new_pipe.ObjectPlacement = your_pipe_placement  # Platzierung des Rohrs in Ihrem Modell
        new_pipe.Representation = your_pipe_representation  # 3D-Repräsentation des Rohrs in Ihrem Modell
        new_pipe.Tag = "Your Pipe Tag"

        # Fügen Sie das Rohr dem Modell hinzu
        self.model.add(new_pipe)
        pass

    def calc_floor_height(self):
        pass

    def calc_pipe_floor_segment(self, room_coordinates: dict):
        x, y, z = 0, 0, 0
        reference_point = (x, y, z)
        for room in room_coordinates:
            print(room_coordinates[room])
            print(room, room_coordinates[room]["Position"])

        """for floor in your_floors:
            # Definieren Sie den Verteilerpunkt für diese Etage
            distribution_point = (x, y, z)"""

        pass

    def sort_room_floor(self, spaces_dict):
        floor_elements = {}
        for floor in self.model.by_type("IfcBuildingStorey"):
            floor_elements[floor.GlobalId] = {"type": "floor",
                                              "Name": floor.Name,
                                              "height": floor.Elevation,
                                              "rooms": []}
            rooms_on_floor = {}
            for room in spaces_dict:
                space_height = spaces_dict[room]["Position"][2]
                if floor.Elevation == space_height:
                    rooms_on_floor[room] = spaces_dict[room]
            floor_elements[floor.GlobalId]["rooms"] = rooms_on_floor
        return floor_elements

    def create_3_dim_grid(self):
        # Erstelle einen Graphen
        G = nx.Graph()

        # Füge Knoten hinzu
        G.add_node(1, pos=(0, 0, 0))
        G.add_node(2, pos=(1, 1, 1))
        G.add_node(3, pos=(2, 0, 0))

        # Füge Kanten hinzu
        G.add_edge(1, 2)
        G.add_edge(2, 3)
        G.add_edge(3, 1)

        # Erstelle eine 3D-Figur
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')

        # Rufe die Knotenpositionen ab
        pos = nx.get_node_attributes(G, 'pos')

        # Zeichne die Knoten und Kanten
        nx.draw_networkx_nodes(G, pos, ax=ax)
        nx.draw_networkx_edges(G, pos, ax=ax)

        # Zeige das Diagramm an
        plt.show()

    def distance(self, point1, point2):
        return math.sqrt((point2[0] - point1[0]) ** 2 + (point2[1] - point1[1]) ** 2 + (point2[2] - point1[2]) ** 2)

    def lay_pipe(self, point1, point2):
        pipe_length = self.distance(point1, point2)
        print("Pipe length:", pipe_length)
        # print("Pipe diameter:", pipe_diameter)
        return pipe_length

    def find_wall(self, direction, walls):
        direction_walls = [wall for wall in walls if wall[direction] == point[direction]]
        if not direction_walls:
            return None
        # Wand mit dem nächsten Abstand zum Punkt
        return min(direction_walls, key=lambda wall: distance(*point, *wall["start"]))
        pass

    def find_shortest_path(self, start, windows, walls, doors):
        current_point = start
        path = [current_point]
        while True:
            # Suche die nächstgelegene Wand in x-Richtung
            x_wall = find_wall(current_point, "x", walls)
            if not x_wall:
                break
            # Berechne den Abstand zum nächsten Fenster in der x-Richtung
            x_distance = min([distance(*x_wall["start"], *window) for window in windows])
            # Suche die nächstgelegene Wand in y-Richtung
            y_wall = find_wall(current_point, "y", walls)
            if not y_wall:
                break

    def generate_pipe_segments(self, start_point, end_point, walls, windows):
        """
        Generates pipe segments between the start point and end point,
        using walls as reference points for the pipe, and avoiding windows.
        """
        segments = []
        current_point = start_point
        while current_point != end_point:
            # Determine direction of pipe
            if end_point[0] > current_point[0]:
                dx = 1
            elif end_point[0] < current_point[0]:
                dx = -1
            else:
                dx = 0

            if end_point[1] > current_point[1]:
                dy = 1
            elif end_point[1] < current_point[1]:
                dy = -1
            else:
                dy = 0

            # Create new segment
            segment_start = current_point
            segment_end = None
            while segment_end is None:
                # Find next wall point
                next_point = (segment_start[0] + dx, segment_start[1] + dy)
                if next_point in walls:
                    segment_end = next_point
                elif next_point in windows:
                    # Skip window and continue in the same direction
                    segment_start = next_point
                else:
                    # Can't continue in this direction, try perpendicular direction
                    if dx != 0:
                        dx, dy = 0, 1
                    else:
                        dx, dy = 1, 0

            # Add segment to list
            segments.append((segment_start, segment_end))
            current_point = segment_end

        return segments

    def visualzation_networkx_3D(self, G, points, short_edges, other_edges, start_points, end_points):
        node_xyz = np.array([v for v in sorted(G)])
        edge_xyz = np.array([(u, v) for u, v in G.edges()])
        fig = plt.figure()
        ax = fig.add_subplot(111, projection="3d")
        #for i, coord in enumerate(points):
        #    t = tuple(round(p, 2) for p in coord)
        #    ax.text(coord[0], coord[1], coord[2], t, color='red')
        ax.scatter(*node_xyz.T, s=100, ec="w")
        for vizedge in edge_xyz:
            ax.plot(*vizedge.T, color="tab:gray")
        colors = ['r', 'g', 'b', 'y', 'm', 'c', 'w', 'r', 'g']
        for i, short in enumerate(short_edges):
            for start, end in short:
                xs = [start[0], end[0]]
                ys = [start[1], end[1]]
                zs = [start[2], end[2]]
                #ax.plot(xs, ys, zs, color=colors[i])
                ax.plot(xs, ys, zs, color="blue")
        for end in end_points:
            ax.scatter(*end, s=100, ec="w", color="red")

        for start in start_points:
            ax.scatter(*start, s=100, ec="w", color="green")
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.set_zlabel("z")
        fig.tight_layout()
        plt.show()

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
        graph = self.create_nodes(graph=graph, node_points=points)
        graph = self.create_edges(graph=graph, room_points=points)
        print(graph)
        graph = self.limit_neighbors(graph)
        print(graph)
        return graph


    def create_nodes(self, graph: nx.DiGraph, node_points: list):
        for point in node_points:
            p_rounded = tuple(round(coord, 2) for coord in point)
            graph.add_node(tuple(p_rounded))
        return graph

    def limit_neighbors(self, graph: nx.DiGraph):
        for node in graph.nodes():
            neighbors = {}
            print("test")
            print(node)
            for neighbor in graph.neighbors(node):
                direction = tuple(
                    [(neighbor[i] - node[i]) // abs(neighbor[i] - node[i]) if neighbor[i] != node[i] else 0 for i in
                     range(3)])
                if direction in neighbors and neighbors[direction]:
                    neighbors[direction].add(neighbor)
                print(neighbors)

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

    def create_edges(self, graph: nx.DiGraph, room_points):
        max_distance = np.linalg.norm(np.amax(room_points, axis=0) - np.amin(room_points, axis=0))
        tol_value = 0.0
        for p1 in graph.nodes():
            p1 = tuple(round(coord, 2) for coord in p1)
            edges = []
            for p2 in graph.nodes():
                p2 = tuple(round(coord, 2) for coord in p2)
                if p1 != p2 and np.linalg.norm(np.array(p1) - np.array(p2)) <= max_distance:
                    if abs(p1[0] - p2[0]) <= tol_value or abs(p1[1] - p2[1]) <= tol_value or abs(p1[2] - p2[2]) <= tol_value:
                        if abs(p1[0] - p2[0]) <= tol_value and abs(p1[1] - p2[1]) <= tol_value and p1[2] != p2[2]:
                            graph.add_edge(tuple(p1), tuple(p2), weight=abs(p1[2] - p2[2]))  # Gewicht 1 für Kanten in x-Richtung
                            #edges.append((p2, abs(p1[2] - p2[2])))
                        if abs(p1[0] - p2[0]) <= tol_value and p1[1] != p2[1] and abs(p1[2] - p2[2]) <= tol_value:
                            #edges.append((p2, abs(p1[1] - p2[1])))
                            graph.add_edge(tuple(p1), tuple(p2), weight=abs(p1[1] - p2[1]))  # Gewicht 2 für Kanten in anderen Richtungen
                        if p1[0] != p2[0] and abs(p1[1] - p2[1]) <= tol_value and abs(p1[2] - p2[2]) <= tol_value:
                            #edges.append((p2, abs(p1[0] - p2[0])))
                            graph.add_edge(tuple(p1), tuple(p2), weight=abs(p1[0] - p2[0]))  # Gewicht 2 für Kanten in anderen Richtungen
            #edges = sorted(edges, key=lambda x: x[1])
            #for edge in edges[:4]:
            #    graph.add_edge(tuple(p1), edge[0], weight=edge[1])
        return graph

    def shortest_path(self, graph: nx.DiGraph(), start, end_points):
        # todo: Gewichtung: Doppelte wege
        # todo: zusätzliche Gewichtung: Z-Richtung
        # Erstelle einen Graphen mit den Punkten als Knoten
        _short_path_edges = []
        _other_path_edges = []
        # todo: doppelte kanten verhindern
        for end in end_points:
            path = nx.dijkstra_path(graph, start, end, weight='weight')
            distance = nx.dijkstra_path_length(graph, start, end, weight='weight')
            _short_path_edges.append(list(zip(path, path[1:])))
            _other_path_edges.append([edge for edge in graph.edges() if edge not in list(zip(path, path[1:]))])
            print("Kürzester Pfad:", path)
            print("Distanz:", distance)
        return graph, _short_path_edges, _other_path_edges, start, end_points


    def calc_pipe_coordinates(self, floors, ref_point):
        # todo: referenzpunkt einer eckpunkte des spaces zu ordnen: for d in distance(x_ref, point)
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
            print(rooms)
            r_point = (ref_point[0], ref_point[1], etage["height"])
            _start_points.append(tuple(r_point))
            room_points.append(r_point)
            # rooms[room]["Position"]
            # rooms[room]["global_corners"]
            # rooms[room]["Bounding_box"]
            # rooms[room]["room_elements"]
            room_floor_end_points = []
            #room_points_floor = []
            for room in rooms:
                elements = rooms[room]["room_elements"]
                room_points.extend(rooms[room]["global_corners"])
                max_coords = np.amax(rooms[room]["global_corners"], axis=0)
                min_coords = np.amin(rooms[room]["global_corners"], axis=0)

                print(max_coords[0])

                for element in elements:
                    if elements[element]["type"] == "Wall":
                        corner_points = elements[element]["global_corners"]
                        # print(elements[element]["number"])
                        # print(corner_points)
                        # x_midpoint = np.mean(corner_points[:, 0])
                        # y_midpoint = np.mean(corner_points[:, 1])
                        # z_low = np.min(corner_points[:, 2])
                        # end_point = np.array([x_midpoint, y_midpoint, z_low])
                        # end_points.append(end_point)
                    if elements[element]["type"] == "Door":
                        corner_points = elements[element]["global_corners"]
                        # print(elements[element]["number"])
                        # print(corner_points)
                        # x_midpoint = np.mean(corner_points[:, 0])
                        # y_midpoint = np.mean(corner_points[:, 1])
                        # z_low = np.min(corner_points[:, 2])
                        # end_point = np.array([x_midpoint, y_midpoint, z_low])
                        # end_points.append(end_point)
                    if elements[element]["type"] == "Window":
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
            result = self.shortest_path(graph=G, start=r_point, end_points=room_floor_end_points)
            G = result[0]
            _short_path.extend(result[1])
            _other_path.extend(result[2])
            _end_points.extend(result[4])
            _room_points.extend(room_points)

        #self.visualzation_networkx_2D(G=G, short_edges=_short_path_edges, other_edges=_other_path_edges,
        #                              start_ref=start, end_points=end_points)
        self.visualzation_networkx_3D(G, _room_points, short_edges=_short_path, other_edges=_other_path,
                                      start_points=_start_points, end_points=_end_points)



    class SimpleEnv(gym.Env):
        def __init__(self):
            self.observation_space = spaces.Discrete(11)
            self.action_space = spaces.Discrete(2)
            self.state = 0

        def step(self, action):
            reward = 0
            if action == 0:
                self.state = max(0, self.state - 1)
            else:
                self.state = min(10, self.state + 1)

            if self.state == 10:
                reward = 1

            done = False
            return self.state, reward, done, {}

        def reset(self):
            self.state = 0
            return self.state

    class SimpleAgent:
        def __init__(self, obs_space, action_space):
            self.obs_space = obs_space
            self.action_space = action_space
            self.model = self.create_model()
            self.optimizer = tf.keras.optimizers.Adam()

        def create_model(self):
            model = keras.Sequential([
                keras.layers.Dense(16, activation='relu', input_shape=(self.obs_space.n,)),
                keras.layers.Dense(self.action_space.n, activation='softmax')
            ])
            model.compile(optimizer=self.optimizer, loss='mse')
            return model

        def get_action(self, state):
            q_values = self.model.predict(np.array([state]))[0]
            return np.argmax(q_values)


if __name__ == '__main__':
    ifc_path = "C:\\02_Masterarbeit\\08_BIMVision\\FZK-Haus.ifc"
    #ifc_path = "C:\\02_Masterarbeit\\08_BIMVision\\IFC_testfiles\\ERC_Mainbuilding_Arch.ifc"
    pipe = PipeGeometry(ifc_file=ifc_path)
    # pipe.transformation_matrix()
    spaces_dict = pipe.room_element_position()
    floor_elements = pipe.sort_room_floor(spaces_dict=spaces_dict)
    pipe.calc_pipe_coordinates(floors=floor_elements, ref_point=(4.04, 5.99, 0.00))
    # pipe.calc_pipe_coordinates(floor=floor_1, ref_point=(7.65, 4.25, 0.00))
    # pipe.create_3_dim_grid()
    # print(floor_elements)
    # pipe.rooms_on_floor()
#
#
# pipe.calc_pipe_floor_segment(room_coordinates=spaces_dict)
