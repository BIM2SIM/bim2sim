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
        matrix  = np.dot(relative_matrix, absolute_matrix)
        # Erstellen der globalen Koordinatenachsen
        x_axis = np.array([1, 0, 0, 1])
        y_axis = np.array([0, 1, 0, 1])
        z_axis = np.array([0, 0, 1, 1])

        return matrix

    def get_relative_matrix(self, relative_placement):
        # Definieren Sie die X-, Y- und Z-Achsen als 3x1 Spaltenvektoren.
        x_axis = np.array(relative_placement.RefDirection.DirectionRatios).reshape(3, 1)
        #y_axis = np.array(relative_placement.Axis.DirectionRatios).reshape(3, 1)
        #z_axis = np.cross(x_axis.T, y_axis.T).T
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
            matrix_chain = [self.get_relative_matrix(element.ObjectPlacement.RelativePlacement)]
            parent_placement = element.ObjectPlacement.PlacementRelTo
            while parent_placement is not None:
                parent_matrix = self.get_relative_matrix(parent_placement.RelativePlacement)
                matrix_chain.insert(0, parent_matrix)
                parent_placement = parent_placement.PlacementRelTo
            absolute_matrix = np.eye(4)
            for matrix in matrix_chain:
                absolute_matrix = np.dot(absolute_matrix, matrix)
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
                                                      #"transformation_matrix": matrix,
                                                      "Position": absolute_position,
                                                      #"Bounding_box": global_box,
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
                                                      #"transformation_matrix": matrix,
                                                      "Position": absolute_position,
                                                      #"Bounding_box": global_box,
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
                                                      #"transformation_matrix": matrix,
                                                      "Position": absolute_position,
                                                      #"Bounding_box": global_box,
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
        #print(grouped_edges)

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
        for rep in element.Representation.Representations:
            if rep.RepresentationType == "BoundingBox":
                bound_box = rep.Items[0]
                length, width, height = bound_box.XDim, bound_box.YDim, bound_box.ZDim
                corners = np.array([[0, 0, 0, 1], [length, 0, 0, 1], [length, width, 0, 1], [0, width, 0, 1], [0, 0, height, 1],
                            [length, 0, height, 1], [length, width, height, 1], [0, width, height, 1]])
                """corners = np.array([[position[0], position[1], position[2], 1], [length, 0, 0, 1], [length, width, 0, 1], [0, width, 0, 1], [0, 0, height, 1],
                            [length, 0, height, 1], [length, width, height, 1], [0, width, height, 1]])"""
                global_corners = corners.dot(matrix.T)
                return global_corners[:,:3]

    def room_element_position(self):
        spaces_dict = {}
        global_box = None
        global_corners = None
        for space in self.model.by_type("IfcSpace"):
            #absolute_position = self.calc_global_position(element=space)
            # absolute position room
            matrix = self.get_global_matrix(element=space)
            relative_point = np.array([0, 0, 0, 1])
            absolute_position = np.dot(matrix, relative_point)[:3]
            # Bounding box
            global_box = self.calc_bounding_box(space)
            global_corners = self.absolute_points_room(element=space, matrix=matrix)
            spaces_dict[space.GlobalId] = {"type": "Space",
                                           "number": space.Name,
                                           "Name": space.LongName,
                                           "id": space.id(),
                                           #"transformation_matrix": matrix,
                                           "Position": absolute_position,
                                           #"Bounding_box": global_box,
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
        #print("Pipe diameter:", pipe_diameter)
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

    def shortest_path(self, start, end, points):
        # Erstelle einen Graphen mit den Punkten als Knoten
        points = points.tolist()
        points.append(start)
        points.append(end)
        print(len(points))
        """# Punkte definieren
        points = [(0, 0, 0), (3, 0, 0), (3, 3, 0), (0, 3, 0), (0, 0, 3), (3, 0, 3), (3, 3, 3), (0, 3, 3), (3, 1.5, 0)]

        # Start- und Endpunkte definieren
        start = (0, 0, 0)
        end = (3, 1.5, 0)"""
        # Graphen erstellen
        G = nx.DiGraph()
        for p in points:
            print(p)
            p_rounded = tuple(round(coord, 2) for coord in p)
            G.add_node(tuple(p_rounded))
        # Kanten hinzufügen
        #max_distance = 10  # maximale Entfernung für Kanten
        max_distance = np.linalg.norm(np.amax(points, axis=0) - np.amin(points, axis=0))
        for p1 in points:
            p1 = tuple(round(coord, 2) for coord in p1)
            for p2 in points:
                p2 = tuple(round(coord, 2) for coord in p2)
                if p1 != p2 and np.linalg.norm(np.array(p1) - np.array(p2)) <= max_distance:
                    # nur Kanten in einer Richtung zulassen
                    if p1[0] == p2[0] or p1[1] == p2[1] or p1[2] == p2[2]:
                        # Kantenpriorisierung basierend auf der bevorzugten Richtung
                        if p1[0] == p2[0] and p1[1] == p2[1] and p1[2] != p2[2]:
                            G.add_edge(tuple(p1), tuple(p2), weight=1)  # Gewicht 1 für Kanten in x-Richtung
                        if p1[0] == p2[0] and p1[1] != p2[1] and p1[2] == p2[2]:
                            G.add_edge(tuple(p1), tuple(p2), weight=1)  # Gewicht 2 für Kanten in anderen Richtungen
                        if p1[0] != p2[0] and p1[1] == p2[1] and p1[2] == p2[2]:
                            G.add_edge(tuple(p1), tuple(p2), weight=1)  # Gewicht 2 für Kanten in anderen Richtungen
        print(G)
        path = nx.dijkstra_path(G, start, end, weight='weight')
        print(path)

        """max_distance = np.linalg.norm(np.amax(points, axis=0) - np.amin(points, axis=0))
        G = nx.Graph()
        for p1 in points:
            for p2 in points:
                if p1 != p2 and np.linalg.norm(np.array(p1) - np.array(p2)) <= max_distance:
                    #G.add_edge(p1, p2, weight=1)
                    G.add_edge(tuple(p1), tuple(p2), weight=np.linalg.norm(np.linalg.norm(np.array(p1) - np.array(p2))))
        # Finde den kürzesten Pfad zwischen Start- und Endpunkt
        print(G)
        path = nx.shortest_path(G, start, end)
        path_edges = []
        for i in range(len(path) - 1):
            edge = (path[i], path[i + 1])
            path_edges.append(edge)
        print(path)
        print(path_edges)"""
        pos = nx.spring_layout(G)
        nx.draw_networkx_nodes(G, pos)

        # Zeichne die Kanten
        nx.draw_networkx_edges(G, pos)

        # Zeichne die Labels
        nx.draw_networkx_labels(G, pos)
        plt.show()
        return path

    def point_element(self, element_points, point_ref, mh_distance: bool=True):
        d_list = []
        d_list = {np.sum(np.abs(point - point_ref)) if mh_distance else np.linalg.norm(point - point_ref) for point in
                  element_points}
        # Berechnen der Manhattan-Distanz zwischen Referenzpunkt und allen Ecken
        # Berechnen aller möglichen Kombinationen von Anfangs- und Endpunkten

        """combinations = list(itertools.product(element_points, repeat=2))
        print(combinations)

        # Berechnen der Distanz zwischen jedem Anfangs- und Endpunkt
        shortest_distance = np.inf
        for combination in combinations:
            start, end = combination
            distance = np.linalg.norm(end - start)
            if distance < shortest_distance:
                shortest_distance = distance
                shortest_combination = (start, end)

        # Ausgabe der Ergebnisse
        print("Kürzeste Distanz zwischen Anfangs- und Endpunkt:", shortest_distance)
        print("Anfangspunkt:", shortest_combination[0])
        print("Endpunkt:", shortest_combination[1])"""
        """ distances = np.sum(np.abs(element_points - point_ref), axis=1)

        # Sortieren der Distanzen und Speichern der sortierten Liste
        sorted_distances = np.argsort(distances)

        # Finden der Ecken mit der kürzesten Distanz
        shortest_distances = [element_points[i] for i in sorted_distances if distances[i] == distances[sorted_distances[0]]]

        # Ausgabe der Ergebnisse
        print(point_ref)
        print(shortest_distances)
        print("Ecken mit kürzester Manhattan-Distanz zum Referenzpunkt:")
        for corner in shortest_distances:
            print(corner)
        #print(d_list)"""
        # todo:
    def calc_pipe_coordinates(self, floor, ref_point):
        # todo: referenzpunkt einer eckpunkte des spaces zu ordnen: for d in distance(x_ref, point)
        #
        # todo:

        pipe_coords = []
        pipe_segments = []
        print(ref_point)
        rooms = floor["rooms"]
        # rooms[room]["Position"]
        # rooms[room]["global_corners"]
        # rooms[room]["Bounding_box"]
        # rooms[room]["room_elements"]
        for room in rooms:
            if room.find("347jFE2yX7IhCEIALmupEH") > -1:
                end_points = []
                print(rooms[room]["Name"])
                elements = rooms[room]["room_elements"]
                print(rooms[room]["global_corners"])
                #self.point_element(element_points=rooms[room]["global_corners"], point_ref=ref_point)
                self.shortest_path(start=(5.5, 9.7, 2.5), end=(7.65, 3.5, 0), points=rooms[room]["global_corners"] )
                for element in elements:
                    if elements[element]["type"] == "Wall":
                        corner_points = elements[element]["global_corners"]

                        #print(elements[element]["number"])
                        #print(corner_points)
                        x_midpoint = np.mean(corner_points[:, 0])
                        y_midpoint = np.mean(corner_points[:, 1])
                        #z_low = np.min(corner_points[:, 2])
                        #end_point = np.array([x_midpoint, y_midpoint, z_low])
                        #end_points.append(end_point)
                    if elements[element]["type"] == "Door":
                        corner_points = elements[element]["global_corners"]
                        #print(elements[element]["number"])
                        #print(corner_points)
                        #x_midpoint = np.mean(corner_points[:, 0])
                        #y_midpoint = np.mean(corner_points[:, 1])
                        #z_low = np.min(corner_points[:, 2])
                        #end_point = np.array([x_midpoint, y_midpoint, z_low])
                        #end_points.append(end_point)
                    if elements[element]["type"] == "Window":
                        window = elements[element]
                        corner_points = elements[element]["global_corners"]
                        x_midpoint = np.mean(corner_points[:, 0])
                        y_midpoint = np.mean(corner_points[:, 1])
                        z_low = np.min(corner_points[:, 2])
                        end_point = np.array([x_midpoint, y_midpoint, z_low])
                        end_points.append(end_point)

                for end_point in end_points:
                    pipe_length = self.lay_pipe(point1=end_point, point2=ref_point)
                    pipe_coords.append(pipe_length)

            """pipe_coords.append(ref_point + room_coordinates[room]["Position"])
            end_coords = []
            for window in room['windows']:
                end_coords.append((window[0], window[1], ref_point[2]))  # x, y, z

                # Wählen Sie das Fenster aus, das am nächsten zum Referenzpunkt liegt
            min_distance = math.inf
            chosen_coords = None
            for coords in end_coords:
                distance = math.sqrt((ref_point[0] - coords[0]) ** 2 + (ref_point[1] - coords[1]) ** 2)
                if distance < min_distance:
                    min_distance = distance
                    chosen_coords = coords"""

    class GraphNetwork:
        @staticmethod
        def create_grid():
            # Erstelle einen gerichteten Graphen
            G = nx.DiGraph()
            # Füge zwei Knoten hinzu
            G.add_node(1, pos=(0, 0))
            G.add_node(2, pos=(1, 1))
            # Füge eine Kante hinzu
            G.add_edge(1, 2)
            # Rufe nx.draw_networkx auf
            pos = nx.get_node_attributes(G, 'pos')
            nx.draw_networkx_nodes(G, pos, node_size=100)
            nx.draw_networkx_edges(G, pos, width=1)
            # Zeige das Diagramm an
            plt.axis('off')
            plt.show()

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
    ifc_path = "C:\\02_SvenArbeit\\Masterarbeit\\bim2sim\\test\\ifcmodell\\example.ifc"
    pipe = PipeGeometry(ifc_file=ifc_path)
    #pipe.transformation_matrix()
    spaces_dict = pipe.room_element_position()
    floor_elements = pipe.sort_room_floor(spaces_dict=spaces_dict)
    floor_1 = floor_elements["2eyxpyOx95m90jmsXLOuR0"]
    pipe.calc_pipe_coordinates(floor=floor_1, ref_point=(4.040, 5.990, 0.000))
    #pipe.create_3_dim_grid()



    #print(floor_elements)
    # pipe.create_grid()
    # pipe.rooms_on_floor()
#
#
# pipe.calc_pipe_floor_segment(room_coordinates=spaces_dict)
