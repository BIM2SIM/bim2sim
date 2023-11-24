import matplotlib.pyplot as plt
import networkx as nx
import matplotlib.lines as mlines
import numpy as np
import math
from bim2sim.elements.mapping.units import ureg
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_instances
from decimal import Decimal, ROUND_HALF_UP

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
        self.logger.info("Start design LCA")
        thermal_zones = filter_instances(instances, 'ThermalZone')
        thermal_zones = [tz for tz in thermal_zones if tz.ventilation_system == True]

        self.logger.info("Start calculating points of the ventilation outlet at the ceiling")
        # Hier werden die Mittelpunkte der einzelnen Räume aus dem IFC-Modell ausgelesen und im Anschluss um die
        # halbe Höhe des Raumes nach oben verschoben. Es wird also der Punkt an der UKRD (Unterkante Rohdecke)
        # in der Mitte des Raumes berechnet. Hier soll im weiteren Verlauf der Lüftungsauslass angeordnet werden
        self.center(thermal_zones)
        self.logger.info("Finished calculating points of the ventilation outlet at the ceiling")

        self.logger.info("Getting Airflow Data")
        # Hier werden aus dem mit Daten angereicherten Modell die Daten ausgelesen. Die Daten enthalten den spezifischen
        # gesamten Luftbedarf pro Raum
        self.airflow_data(thermal_zones)


        self.logger.info("Calculating the Coordinates of the ceiling hights")
        # Hier werden die Koordinaten der Höhen an der UKRD berechnet und in ein Set
        # zusammengefasst, da diese Werte im weiterem Verlauf häufig benötigt werden, somit müssen diese nicht
        # immer wieder neu berechnet werden:
        z_coordinate_set = self.calculate_z_coordinate(self.center(thermal_zones))


        self.logger.info("Calculating intersection points")
        # Hier werden die Schnittpunkte aller Punkte pro Geschoss berechnet. Es entsteht ein Raster im jeweiligen
        # Geschoss. Es wird als Verlegeraster für die Zuluft festgelegt. So werden die einzelnen Punkte der Lüftungs-
        # auslässe zwar nicht direkt verbunden, aber in der Praxis und nach Norm werden Lüftungskanäle nicht diagonal
        # durch ein Gebäude verlegt
        self.intersection_points(self.center(thermal_zones),
                                 z_coordinate_set
                                 )

        self.logger.info("Visualising points on the ceiling for the ventilation outlet:")
        self.visualisierung(self.center(thermal_zones),
                            self.airflow_data(thermal_zones),
                            self.intersection_points(self.center(thermal_zones),
                                                     z_coordinate_set
                                                     )
                            )


        self.logger.info("Visualising intersectionpoints")
        # self.visualisierung_punkte_nach_ebene(self.center(thermal_zones),
        #                                       self.intersection_points(self.center(thermal_zones),
        #                                                                z_coordinate_set
        #                                                                ),
        #                                       z_coordinate_set)

        self.logger.info("Graph erstellen")
        self.graph_erstellen(thermal_zones,
                             self.center(thermal_zones),
                             self.intersection_points(self.center(thermal_zones),
                                                      z_coordinate_set
                                                      ),
                             z_coordinate_set
                             )

    def runde_decimal(self, zahl, stellen):
        zahl_decimal = Decimal(zahl)
        rundungsregel = Decimal('1').scaleb(-stellen)  # Gibt die Anzahl der Dezimalstellen an
        return float(zahl_decimal.quantize(rundungsregel, rounding=ROUND_HALF_UP))

    def center(self, thermal_zones):
        """Function calculates position of the outlet of the LVA

        Args:
            tz: thermal_zones bim2sim element
        Returns:
            center of the room at the ceiling
        """
        # Listen:
        room_ceiling_ventilation_outlet = []
        room_type = []

        for tz in thermal_zones:
            room_ceiling_ventilation_outlet.append([self.runde_decimal(tz.space_center.X(), 1),
                                                    self.runde_decimal(tz.space_center.Y(), 1),
                                                    self.runde_decimal(tz.space_center.Z() + tz.height.magnitude / 2, 2),
                                                    self.runde_decimal(tz.air_flow.magnitude,0)])
            room_type.append(tz.usage)



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
        for x, y, z, a in room_ceiling_ventilation_outlet:
            if z not in grouped_coordinates_x:
                grouped_coordinates_x[z] = []
            grouped_coordinates_x[z].append((x, y, z, a))

        # Anpassen der Koordinaten in x-Koordinate
        adjusted_coords_x = []
        for z_coord in z_axis:
            sort = sorted(grouped_coordinates_x[z_coord], key=lambda coord: (coord[0], coord[1]))

            i = 0
            while i < len(sort):
                x1, y1, z1,a1 = sort[i]
                total_x = x1
                count = 1

                j = i + 1
                while j < len(sort) and sort[j][0] - x1 <= 0.75:
                    total_x += sort[j][0]
                    count += 1
                    j += 1

                x_avg = total_x / count
                for _ in range(i, j):
                    _, y, z, a = sort[i]
                    adjusted_coords_x.append((self.runde_decimal(x_avg,1), y, z, a))
                    i += 1


        # Erstellt ein Dictonary sortiert nach Z-Koorinaten
        grouped_coordinates_y = {}
        for x, y, z, a in adjusted_coords_x:
            if z not in grouped_coordinates_y:
                grouped_coordinates_y[z] = []
            grouped_coordinates_y[z].append((x, y, z, a))

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
                    x, _, z, a = room_ceiling_ventilation_outlet[k]
                    adjusted_coords_y.append((x, self.runde_decimal(average_y,1), z, a))

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

    def calculate_z_coordinate(self, center):
        z_coordinate_set = set()
        for i in range(len(center)):
            z_coordinate_set.add(center[i][2])
        return z_coordinate_set

    def intersection_points(self, ceiling_point, z_coordinate_set):
        intersection_points_list = []

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
        ceiling_point = [item[:3] for item in ceiling_point]
        intersection_points_list = [item for item in intersection_points_list if item not in ceiling_point] # Entfernt
        # die Schnittpunkte, welche ein Lüftungsauslass sind

        return intersection_points_list

    def visualisierung(self, room_ceiling_ventilation_outlet, air_flow_building, intersection):
        """The function visualizes the points in a diagram

        Args:
            room_ceiling_ventilation_outlet: Point at the ceiling in the middle of the room
            air_flow_building:
        Returns:
            3D diagramm
        """

        # 3D-Diagramm erstellen
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')

        # Anpassen des Layouts für die Legende
        plt.subplots_adjust(right=0.75)

        # Punkte hinzufügen
        coordinates1 = room_ceiling_ventilation_outlet # Punkte für Auslässe
        coordinates2 = intersection # Schnittpunkte

        # Extrahieren der x, y und z Koordinaten aus den beiden Listen
        x1, y1, z1, a1 = zip(*coordinates1)
        x2, y2, z2 = zip(*coordinates2)

        # Plotten der zweiten Liste von Koordinaten in Rot
        ax.scatter(x2, y2, z2, c='red', marker='x', label='Schnittpunkte')

        # Plotten der ersten Liste von Koordinaten in Blau
        ax.scatter(x1, y1, z1, c='blue', marker='D', label='Lüftungsauslässe')

        # Achsenbeschriftungen
        ax.set_xlabel('X-Achse [m]')
        ax.set_ylabel('Y-Achse [m]')
        ax.set_zlabel('Z-Achse [m]')

        # Legende hinzufügen
        ax.legend(loc="center left", bbox_to_anchor=(1, 0))

        # Diagramm anzeigen
        plt.show()


    def visualisierung_punkte_nach_ebene(self,center, intersection, z_coordinate_set):
        """The function visualizes the points in a diagram
        Args:
           intersection points: intersection points at the ceiling
        Returns:
           2D diagramm for each ceiling
       """
        for z_value in z_coordinate_set:
            x_values = [x for x, y, z in intersection if z == z_value]
            y_values = [y for x, y, z in intersection if z == z_value]
            x_values_center = [x for x, y, z in center if z == z_value]
            y_values_center = [y for x, y, z in center if z == z_value]

            plt.figure(num=f"Grundriss: {z_value}")
            plt.scatter(x_values, y_values, color="r", marker='x',label="Schnittpunkte")
            plt.scatter(x_values_center, y_values_center, color="b", marker='D', label="Lüftungsauslässe")
            plt.title(f'Höhe: {z_value}')
            plt.subplots_adjust(right=0.7)
            plt.legend(loc="center left", bbox_to_anchor=(1, 0.5))
            plt.xlabel('X-Achse [m]')
            plt.ylabel('Y-Achse [m]')

        plt.show()

    def graph_erstellen(self, thermal_zones, ceiling_point, intersection_points, z_coordinate_set):
        """The function creates a connected graph for each floor
        Args:
           ceiling_point: Point at the ceiling in the middle of the room
           intersection points: intersection points at the ceiling
        Returns:
           connected graph for each floor
       """

        def euklidische_distanz(punkt1, punkt2):
            """
            Calculating the distance between point1 and 2
            :param punkt1:
            :param punkt2:
            :return: Distance between punkt1 and punkt2
            """
            return round(math.sqrt((punkt2[0] - punkt1[0]) ** 2 + (punkt2[1] - punkt1[1]) ** 2 + (punkt2[2] - punkt1[2]) ** 2),2)

        for z_value in z_coordinate_set:
            filtered_coords_ceiling_weight = [coord for coord in ceiling_point if coord[2] == z_value]
            filtered_coords_intersection = [coord for coord in intersection_points if coord[2] == z_value]

            ceiling_point_without_weight = [item[:3] for item in ceiling_point]
            filtered_coords_ceiling = [coord for coord in ceiling_point_without_weight if coord[2] == z_value]

            # Erstellt den Graphen
            G = nx.Graph()

            # Hinzufügen der Knoten für Lüftungsauslässe
            for x, y, z, a in filtered_coords_ceiling_weight:
                G.add_node((x, y, z), weight=int(a))


            coordinates = filtered_coords_ceiling + filtered_coords_intersection
            for coord in filtered_coords_intersection:
                G.add_node((coord[0], coord[1], coord[2]), weight=0)


            # Kanten entlang der X-Achse hinzufügen
            unique_coords = set(coord[0] for coord in coordinates)
            for u in unique_coords:
                nodes_on_same_axis = sorted([coord for coord in coordinates if coord[0] == u],
                                            key=lambda c: c[1 - 0])
                for i in range(len(nodes_on_same_axis) - 1):
                    gewicht_kante_y = euklidische_distanz(nodes_on_same_axis[i], nodes_on_same_axis[i + 1])
                    G.add_edge(nodes_on_same_axis[i], nodes_on_same_axis[i + 1], weight=gewicht_kante_y)

            # Kanten entlang der Y-Achse hinzufügen
            unique_coords = set(coord[1] for coord in coordinates)
            for u in unique_coords:
                nodes_on_same_axis = sorted([coord for coord in coordinates if coord[1] == u],
                                            key=lambda c: c[1 - 1])
                for i in range(len(nodes_on_same_axis) - 1):
                    gewicht_kante_x = euklidische_distanz(nodes_on_same_axis[i], nodes_on_same_axis[i + 1])
                    G.add_edge(nodes_on_same_axis[i], nodes_on_same_axis[i + 1], weight=gewicht_kante_x)

            # Visualisierung
            plt.figure(figsize=(15, 10))
            plt.xlabel('X-Achse [m]')
            plt.ylabel('Y-Achse [m]')
            plt.title(f"Graph mit Kantengewichten und Knotengewichten, Z: {z_value}")
            plt.grid(True)
            plt.subplots_adjust(right=0.7)

            # Positionen der Knoten festlegen
            pos = {coord: (coord[0], coord[1]) for coord in coordinates}

            # Knoten zeichnen
            nx.draw_networkx_nodes(G, pos, nodelist=filtered_coords_ceiling, node_shape='D', node_color='blue',
                                   node_size=250)
            nx.draw_networkx_nodes(G, pos, nodelist=filtered_coords_intersection, node_shape='o', node_color='red',
                                   node_size=100)

            # Kanten zeichnen
            nx.draw_networkx_edges(G, pos)

            # Kantengewichte anzeigen
            edge_labels = nx.get_edge_attributes(G, 'weight')
            nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=5)

            # Knotengewichte anzeigen
            node_labels = nx.get_node_attributes(G, 'weight')
            nx.draw_networkx_labels(G, pos, labels=node_labels, font_size=8, font_color="white")

            # Anzeigen des Graphens
            plt.show()
