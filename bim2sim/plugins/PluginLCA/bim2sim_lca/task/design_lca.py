import matplotlib.pyplot as plt
import networkx as nx
from itertools import chain
import math
from bim2sim.elements.mapping.units import ureg
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_instances
from decimal import Decimal, ROUND_HALF_UP
from networkx.utils import not_implemented_for, pairwise

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

        visualisierung = True
        starting_point = [50, 0, 0]

        self.logger.info("Start design LCA")
        thermal_zones = filter_instances(instances, 'ThermalZone')
        thermal_zones = [tz for tz in thermal_zones if tz.ventilation_system == True]

        self.logger.info("Start calculating points of the ventilation outlet at the ceiling")
        # Hier werden die Mittelpunkte der einzelnen Räume aus dem IFC-Modell ausgelesen und im Anschluss um die
        # halbe Höhe des Raumes nach oben verschoben. Es wird also der Punkt an der UKRD (Unterkante Rohdecke)
        # in der Mitte des Raumes berechnet. Hier soll im weiteren Verlauf der Lüftungsauslass angeordnet werden
        center = self.center(thermal_zones, starting_point)
        self.logger.info("Finished calculating points of the ventilation outlet at the ceiling")

        self.logger.info("Getting Airflow Data")
        # Hier werden aus dem mit Daten angereicherten Modell die Daten ausgelesen. Die Daten enthalten den spezifischen
        # gesamten Luftbedarf pro Raum
        airflow_data = self.airflow_data(thermal_zones)


        self.logger.info("Calculating the Coordinates of the ceiling hights")
        # Hier werden die Koordinaten der Höhen an der UKRD berechnet und in ein Set
        # zusammengefasst, da diese Werte im weiterem Verlauf häufig benötigt werden, somit müssen diese nicht
        # immer wieder neu berechnet werden:
        z_coordinate_set = self.calculate_z_coordinate(center)


        self.logger.info("Calculating intersection points")
        # Hier werden die Schnittpunkte aller Punkte pro Geschoss berechnet. Es entsteht ein Raster im jeweiligen
        # Geschoss. Es wird als Verlegeraster für die Zuluft festgelegt. So werden die einzelnen Punkte der Lüftungs-
        # auslässe zwar nicht direkt verbunden, aber in der Praxis und nach Norm werden Lüftungskanäle nicht diagonal
        # durch ein Gebäude verlegt
        intersection_points = self.intersection_points(center,
                                                       z_coordinate_set
                                                       )

        self.logger.info("Visualising points on the ceiling for the ventilation outlet:")
        self.visualisierung(center,
                            airflow_data,
                            intersection_points
                            )


        # self.logger.info("Visualising intersectionpoints")
        # self.visualisierung_punkte_nach_ebene(center,
        #                                       intersection_points,
        #                                       z_coordinate_set)

        self.logger.info("Graph erstellen")
        self.graph_erstellen(center,
                             intersection_points,
                             z_coordinate_set,
                             visualisierung
                             )
        self.logger.info("Graph wurde erstellt")



    def runde_decimal(self, zahl, stellen):
        """Funktion legt fest wie gerundet wird

        Args:
            zahl: Zahl, welche gerundet werden soll
            stellen: Anzahl der Nachkommastellen
        Returns:
            gerundete Zahl als float
        """
        zahl_decimal = Decimal(zahl)
        rundungsregel = Decimal('1').scaleb(-stellen)  # Gibt die Anzahl der Dezimalstellen an
        return float(zahl_decimal.quantize(rundungsregel, rounding=ROUND_HALF_UP))

    def center(self, thermal_zones, starting_point):
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
        print(room_ceiling_ventilation_outlet)

        # Hier werden die Startpunkte (Schachtauslässe) je Ebene hinzugefügt und die gesamte Luftmenge an für die Ebene
        # berechnet. Diese wird für den Graphen gebraucht

        airflow_volume_per_storey = {}

        for sublist in room_ceiling_ventilation_outlet:
            z = sublist[2]  # Der dritte Eintrag (Index 2) ist 'z'
            a = sublist[3]  # Der vierte Eintrag (Index 3) ist 'a'
            if z in airflow_volume_per_storey:
                airflow_volume_per_storey[z] += a
            else:
                airflow_volume_per_storey[z] = a
        print(airflow_volume_per_storey)

        for z_coord in z_axis:
            room_ceiling_ventilation_outlet.append((starting_point[0],starting_point[1],z_coord,
                                                    airflow_volume_per_storey[z_coord]))

        print(room_ceiling_ventilation_outlet)

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

    # def grid_points(self):

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

    def graph_erstellen(self, ceiling_point, intersection_points, z_coordinate_set, visualisierung):
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

        def metric_closure(G, weight="weight"):
            """Return the metric closure of a graph.

            The metric closure of a graph *G* is the complete graph in which each edge
            is weighted by the shortest path distance between the nodes in *G* .

            Parameters
            ----------
            G : NetworkX graph

            Returns
            -------
            NetworkX graph
                Metric closure of the graph `G`.

            """
            M = nx.Graph()

            Gnodes = set(G)

            # check for connected graph while processing first node
            all_paths_iter = nx.all_pairs_dijkstra(G, weight=weight)
            u, (distance, path) = next(all_paths_iter)
            if Gnodes - set(distance):
                msg = "G is not a connected graph. metric_closure is not defined."
                raise nx.NetworkXError(msg)
            Gnodes.remove(u)
            for v in Gnodes:
                M.add_edge(u, v, distance=distance[v], path=path[v])

            # first node done -- now process the rest
            for u, (distance, path) in all_paths_iter:
                Gnodes.remove(u)
                for v in Gnodes:
                    M.add_edge(u, v, distance=distance[v], path=path[v])

            return M

        def steiner_tree(G, terminal_nodes, weight="weight"):
            """Return an approximation to the minimum Steiner tree of a graph.

            The minimum Steiner tree of `G` w.r.t a set of `terminal_nodes`
            is a tree within `G` that spans those nodes and has minimum size
            (sum of edge weights) among all such trees.

            The minimum Steiner tree can be approximated by computing the minimum
            spanning tree of the subgraph of the metric closure of *G* induced by the
            terminal nodes, where the metric closure of *G* is the complete graph in
            which each edge is weighted by the shortest path distance between the
            nodes in *G* .
            This algorithm produces a tree whose weight is within a (2 - (2 / t))
            factor of the weight of the optimal Steiner tree where *t* is number of
            terminal nodes.

            Parameters
            ----------
            G : NetworkX graph

            terminal_nodes : list
                 A list of terminal nodes for which minimum steiner tree is
                 to be found.

            Returns
            -------
            NetworkX graph
                Approximation to the minimum steiner tree of `G` induced by
                `terminal_nodes` .

            Notes
            -----
            For multigraphs, the edge between two nodes with minimum weight is the
            edge put into the Steiner tree.


            References
            ----------
            .. [1] Steiner_tree_problem on Wikipedia.
               https://en.wikipedia.org/wiki/Steiner_tree_problem
            """
            # H is the subgraph induced by terminal_nodes in the metric closure M of G.
            M = metric_closure(G, weight=weight)
            H = M.subgraph(terminal_nodes)
            # Use the 'distance' attribute of each edge provided by M.
            mst_edges = nx.minimum_spanning_edges(H, weight="distance", data=True)
            # Create an iterator over each edge in each shortest path; repeats are okay
            edges = chain.from_iterable(pairwise(d["path"]) for u, v, d in mst_edges)
            # For multigraph we should add the minimal weight edge keys
            if G.is_multigraph():
                edges = (
                    (u, v, min(G[u][v], key=lambda k: G[u][v][k][weight])) for u, v in edges
                )
            T = G.edge_subgraph(edges)
            return T



        # Hier wird ein leerer Graph erstellt. Dieser wird im weiteren Verlauf mit den Graphen der einzelnen Ebenen
        # angereichert
        three_dimensional_graph = nx.Graph()

        for z_value in z_coordinate_set:
            # Hier wird für jede Ebene ein einzelner Steinergraph erstellt.
            filtered_coords_ceiling_weight = [coord for coord in ceiling_point if coord[2] == z_value]
            filtered_coords_intersection = [coord for coord in intersection_points if coord[2] == z_value]

            ceiling_point_without_weight = [item[:3] for item in ceiling_point]
            filtered_coords_ceiling = [coord for coord in ceiling_point_without_weight if coord[2] == z_value]

            # Erstellt den Graphen
            G = nx.Graph()

            # Terminals:
            # Terminals sind die vordefinierten Knoten in einem Graphen, die in der Lösung des Steinerbaum-Problems
            # unbedingt miteinander verbunden werden müssen
            terminals = list()

            # Hinzufügen der Knoten für Lüftungsauslässe zu Terminals
            for x, y, z, a in filtered_coords_ceiling_weight:
                G.add_node((x, y, z), weight=int(a))
                if int(a) > 0:  # Bedingung, um Terminals zu bestimmen (z.B. Gewicht > 0)
                    terminals.append((x, y, z))


            coordinates = filtered_coords_ceiling + filtered_coords_intersection


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



            # Steinerbaum
            steiner_baum = steiner_tree(G, terminals, weight="weight")
            print(steiner_baum)

            # Nachden der Graph für die einzelne Ebene erstellt wurde, wird dieser hier zum 3D Graphen hinzugefügt
            three_dimensional_graph = nx.union(three_dimensional_graph, steiner_baum)

            if visualisierung == True:
                # Visualisierung
                plt.figure()
                plt.xlabel('X-Achse [m]')
                plt.ylabel('Y-Achse [m]')
                plt.title(f"Graph mit Kantengewichten und Knotengewichten, Z: {z_value}")
                plt.grid(False)
                # plt.subplots_adjust(right=0.7)

                # Positionen der Knoten festlegen
                pos = {coord: (coord[0], coord[1]) for coord in coordinates}

                # Knoten zeichnen
                nx.draw_networkx_nodes(steiner_baum, pos, nodelist=filtered_coords_ceiling, node_shape='D', node_color='blue',
                                       node_size=250)
                nx.draw_networkx_nodes(steiner_baum, pos, nodelist=filtered_coords_intersection, node_shape='o', node_color='red',
                                       node_size=100)

                # Kanten zeichnen
                nx.draw_networkx_edges(G, pos, width=1)
                nx.draw_networkx_edges(steiner_baum, pos, width=4, style="-.", edge_color="green")

                # Kantengewichte anzeigen
                edge_labels = nx.get_edge_attributes(steiner_baum, 'weight')
                nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=10, font_weight=10)
                # nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=5, font_weight=10)

                # Knotengewichte anzeigen
                node_labels = nx.get_node_attributes(steiner_baum, 'weight')
                nx.draw_networkx_labels(steiner_baum, pos, labels=node_labels, font_size=8, font_color="white")

                # Anzeigen des Graphens
                plt.show()

        print(three_dimensional_graph)

        # Darstellung des 3D-Graphens:
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')

        # Knotenpositionen in 3D
        pos = {coord: (coord[0], coord[1], coord[2]) for coord in list(three_dimensional_graph.nodes())}

        # Knoten zeichnen
        for node, (x, y, z) in pos.items():
            ax.scatter(x, y, z, color='blue', s=100)

        # Kanten zeichnen
        for edge in three_dimensional_graph.edges:
            x0, y0, z0 = pos[edge[0]]
            x1, y1, z1 = pos[edge[1]]
            ax.plot([x0, x1], [y0, y1], [z0, z1], color='black')

        # Achsenbeschriftungen und Titel
        ax.set_xlabel('X-Achse [m]')
        ax.set_ylabel('Y-Achse [m]')
        ax.set_zlabel('Z-Achse [m]')
        ax.set_title("3D Graph mit Kantengewichten und Knotengewichten")

        # Diagramm anzeigen
        plt.show()

