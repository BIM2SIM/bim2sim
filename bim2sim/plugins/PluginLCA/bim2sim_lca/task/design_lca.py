import matplotlib.pyplot as plt
from collections import defaultdict
from bim2sim.elements.mapping.units import ureg
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_instances
import matplotlib.pyplot as plt
import networkx as nx
import math
import copy


class DesignLCA(ITask):
    """Design of the LCA

    Annahmen:
    Inputs: IFC Modell, Räume,

    Args:
        instances: bim2sim elements
    Returns:
        instances: bim2sim elements enriched with needed air flows
    """
    reads = ('instances',)
    touches = ()

    a = "test"

    def run(self, instances):
        thermal_zones = filter_instances(instances, 'ThermalZone')

        self.logger.info("Start design LCA")

        self.logger.info("Start calculating points of the ventilation outlet at the ceiling")
        self.center(thermal_zones)
        self.logger.info("Finished calculating points of the ventilation outlet at the ceiling")

        self.logger.info("Getting Airflow Data")
        self.airflow_data(thermal_zones)

        self.logger.info("Calculating intersection points")
        self.intersection_points(thermal_zones, self.center(thermal_zones))

        self.logger.info("Visualising points on the ceiling for the ventilation outlet:")
        self.visualisierung(
            self.center(thermal_zones),
            self.airflow_data(thermal_zones),
            self.intersection_points(thermal_zones, self.center(thermal_zones))
        )

        self.logger.info("Visualising intersectionpoints")
        self.visualisierung_schnittpunkte_nach_ebene(self.intersection_points(thermal_zones, self.center(thermal_zones)))

        self.logger.info("Graph erstellen")
        self.graph_erstellen(self.center(thermal_zones),
                             self.intersection_points(thermal_zones, self.center(thermal_zones))
                             )

    def center(self, thermal_zones):
        """Function calculates position of the outlet of the LVA

        Args:
            tz: thermal_zones bim2sim element
        Returns:
            center of the room at the ceiling
        """
        # Listen:
        room_ceiling_ventilation_outlet = []

        for tz in thermal_zones:
            room_ceiling_ventilation_outlet.append([round(tz.space_center.X(), 1), round(tz.space_center.Y(), 1),
                                                    round(tz.space_center.Z() + tz.height.magnitude / 2, 2)])

        # Da die Punkte nicht exakt auf einer Linie liegen, obwohl die Räume eigentlich nebeneinander liegen,
        # einige Räume allerdings leicht unterschiedlich tief sind, müssen die Koordinaten angepasst werden.
        # Eine kleine Verschiebung des Lüftungsauslasses wird in der Realität keine große Änderung hervorrufen,
        # da die Lüftungsauslässe entweder mit einem Flexschlauch angebunden werden, oder direkt aus dem Hauptkanal.

        # Z-Achsen
        z_axis = set()
        for i in range(len(room_ceiling_ventilation_outlet)):
            z_axis.add(room_ceiling_ventilation_outlet[i][2])


        # Erstellt ein Dictonary sortiert nach Z-Koorinaten
        grouped_coordinates_x = {}
        for x, y, z in room_ceiling_ventilation_outlet:
            if z not in grouped_coordinates_x:
                grouped_coordinates_x[z] = []
            grouped_coordinates_x[z].append((x, y, z))

        # Anpassen der Koordinaten in x-Koordinate
        adjusted_coords_x = []
        for z_coord in z_axis:
            sort = sorted(grouped_coordinates_x[z_coord], key=lambda coord: (coord[0], coord[1]))

            i = 0
            while i < len(sort):
                x1, y1, z1 = sort[i]
                total_x = x1
                count = 1

                j = i + 1
                while j < len(sort) and sort[j][0] - x1 <= 0.75:
                    total_x += sort[j][0]
                    count += 1
                    j += 1

                x_avg = total_x / count
                for _ in range(i, j):
                    _, y, z = sort[i]
                    adjusted_coords_x.append((round(x_avg,1), y, z))
                    i += 1


        # Erstellt ein Dictonary sortiert nach Z-Koorinaten
        grouped_coordinates_y = {}
        for x, y, z in adjusted_coords_x:
            if z not in grouped_coordinates_y:
                grouped_coordinates_y[z] = []
            grouped_coordinates_y[z].append((x, y, z))

        # Neue Liste für die verschobenen Koordinaten erstellen
        adjusted_coords_y = []

        # Anpassen der Koordinaten in y-Koordinate
        for z_coord in z_axis:
            room_ceiling_ventilation_outlet = grouped_coordinates_y[z_coord]

            # Sortiere die Koordinaten nach der y-Koordinate
            room_ceiling_ventilation_outlet.sort(key=lambda coord: coord[1])

            # Schleife durch die sortierten Koordinaten
            i = 0
            while i < len(room_ceiling_ventilation_outlet):
                current_coord = room_ceiling_ventilation_outlet[i]
                sum_y = current_coord[1]
                count = 1

                # Überprüfen, ob die nächsten Koordinaten innerhalb von 0,5 Einheiten der aktuellen y-Koordinate liegen
                j = i + 1
                while j < len(room_ceiling_ventilation_outlet) and room_ceiling_ventilation_outlet[j][1] - current_coord[1] < 0.5:
                    sum_y += room_ceiling_ventilation_outlet[j][1]
                    count += 1
                    j += 1

                # Berechne den Durchschnitt der y-Koordinaten
                average_y = sum_y / count

                # Füge die Koordinaten mit dem Durchschnitt der y-Koordinaten zur neuen Liste hinzu
                for k in range(i, j):
                    x, _, z = room_ceiling_ventilation_outlet[k]
                    adjusted_coords_y.append((x, round(average_y,1), z))

                # Aktualisiere die äußere Schleifenvariable i auf den nächsten nicht verarbeiteten Index
                i = j

        room_ceiling_ventilation_outlet = adjusted_coords_y

        return room_ceiling_ventilation_outlet

    def airflow_data(self, thermal_zones):
        """Function getting the airflow data of each room from the IFC File

        Args:
            tz: ThermalZone bim2sim elemnt
        Returns:
            a list of the airflow of each room
        """
        airflow_list = []
        for tz in thermal_zones:
            airflow_list.append(round(tz.air_flow * (3600 * ureg.second) / (1 * ureg.hour), 3))
        return airflow_list

    def intersection_points(self, thermal_zones, ceiling_point):
        z_coordinate_set = set()
        intersection_points_list = []

        for i in range(len(ceiling_point)):
            z_coordinate_set.add(ceiling_point[i][2])

        for i in z_coordinate_set:
            filtered_coordinates_list = [coord for coord in ceiling_point if coord[2] == i]

            ebene_liste = list(set(filtered_coordinates_list))

            for i in range(len(filtered_coordinates_list)):
                for j in range(i + 1, len(filtered_coordinates_list)):
                    p1 = filtered_coordinates_list[i]
                    p2 = filtered_coordinates_list[j]
                    # Schnittpunkte entlang der X- und Y-Achsen
                    intersection_points_list.append((p2[0], p1[1], p1[
                        2]))  # Schnittpunkt auf der Linie parallel zur X-Achse von p1 und zur Y-Achse von p2
                    intersection_points_list.append((p1[0], p2[1], p2[
                        2]))  # Schnittpunkt auf der Linie parallel zur Y-Achse von p1 und zur X-Achse von p2

        intersection_points_list = list(set(intersection_points_list))  # Doppelte Punkte entfernen

        return intersection_points_list

    def visualisierung(self, room_ceiling_ventilation_outlet, air_flow_building, intersection):
        """The function visualizes the points in a diagram

        Args:
            room_ceiling_ventilation_outlet: Point at the ceiling in the middle of the room
            air_flow_building:
        Returns:
            3D diagramm
        """
        print("Outlet:")
        print(room_ceiling_ventilation_outlet)

        print("Intersection:")
        print(intersection)


        labels = air_flow_building

        # 3D-Diagramm erstellen
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')

        # Punkte hinzufügen
        coordinates1 = room_ceiling_ventilation_outlet # Punkte für Auslässe
        coordinates2 = intersection # Schnittpunkte

        # Extrahieren der x, y und z Koordinaten aus den beiden Listen
        x1, y1, z1 = zip(*coordinates1)
        x2, y2, z2 = zip(*coordinates2)

        # Plotten der ersten Liste von Koordinaten in Blau
        ax.scatter(x1, y1, z1, c='blue', label='List 1')

        # Plotten der zweiten Liste von Koordinaten in Rot
        ax.scatter(x2, y2, z2, c='red', label='List 2')

        # Achsenbeschriftungen
        ax.set_xlabel('X-Achse')
        ax.set_ylabel('Y-Achse')
        ax.set_zlabel('Z-Achse')

        # Diagramm anzeigen
        plt.show()


    def visualisierung_schnittpunkte_nach_ebene(self, intersection):
        for z_value in set(z for x, y, z in intersection):
            x_values = [x for x, y, z in intersection if z == z_value]
            y_values = [y for x, y, z in intersection if z == z_value]

            plt.figure()
            plt.scatter(x_values, y_values, color="r")
            plt.title(f'Z-Koordinate: {z_value}')
            plt.xlabel('X-Achse')
            plt.ylabel('Y-Achse')

        plt.show()

    def graph_erstellen(self, ceiling_point, intersection_points):

        z_coordinate_set = set()
        for i in range(len(ceiling_point)):
            z_coordinate_set.add(ceiling_point[i][2])

        # Koordinaten
        list1 = ceiling_point
        list2 = intersection_points

        filtered_coordinates_list1 = [coord for coord in list1 if coord[2] == -0.3]
        filtered_coordinates_list2 = [coord for coord in list2 if coord[2] == -0.3]

        for i in z_coordinate_set:
            filtered_coordinates_list1 = [coord for coord in list1 if coord[2] == i]
            filtered_coordinates_list2 = [coord for coord in list2 if coord[2] == i]

            coordinates = list(set(filtered_coordinates_list1 + filtered_coordinates_list2))

            G = nx.Graph()
            for coord in coordinates:
                G.add_node(coord)

            # Gruppierung der Knoten nach Y-Koordinaten und Verbindung der Knoten auf der X-Achse
            unique_y_coords = set(y for x, y, z in coordinates)
            for y in unique_y_coords:
                # Knoten für diese spezifische Y-Koordinate filtern und nach X-Koordinaten sortieren
                nodes_on_same_y = sorted([coord for coord in coordinates if coord[1] == y], key=lambda c: c[0])

                # Verbinde jeden Knoten mit seinem Nachbarn auf der X-Achse
                for i in range(len(nodes_on_same_y) - 1):
                    G.add_edge(nodes_on_same_y[i], nodes_on_same_y[i + 1])

            # Gruppierung der Knoten nach X-Koordinaten und Verbindung der Knoten auf der Y-Achse
            unique_x_coords = set(x for x, y, z in coordinates)
            for x in unique_x_coords:
                # Knoten für diese spezifische X-Koordinate filtern und nach Y-Koordinaten sortieren
                nodes_on_same_x = sorted([coord for coord in coordinates if coord[0] == x], key=lambda c: c[1])

                # Verbinde jeden Knoten mit seinem Nachbarn auf der Y-Achse
                for i in range(len(nodes_on_same_x) - 1):
                    G.add_edge(nodes_on_same_x[i], nodes_on_same_x[i + 1])

            # Zeichnen des Graphen
            pos = {coord: (coord[0], coord[1]) for coord in coordinates}
            nx.draw(G, pos, with_labels=False, node_color='lightblue', node_size=500)
            plt.show()
