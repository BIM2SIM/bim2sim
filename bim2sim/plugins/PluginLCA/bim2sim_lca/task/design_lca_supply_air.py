import bim2sim
import matplotlib.pyplot as plt
import networkx as nx
from itertools import chain
import math
import pandas as pd
import pandapipes as pp
from pathlib import Path
from bim2sim.elements.mapping.units import ureg
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_instances
from decimal import Decimal, ROUND_HALF_UP
from networkx.utils import pairwise
from copy import deepcopy
import pandapipes.plotting as plot


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

        export_graphen = False
        starting_point = [50, 0, -2]
        position_rlt = [25, starting_point[1], starting_point[2]]
        # y-Achse von Schacht und RLT müssen identisch sein
        querschnittsart = "optimal"  # Wähle zwischen rund, eckig und optimal
        zwischendeckenraum = 200  # Hier wird die verfügbare Höhe (in [mmm]) in der Zwischendecke angegeben! Diese
        # entspricht dem verfügbaren Abstand zwischen UKRD (Unterkante Rohdecke) und OKFD (Oberkante Fertigdecke),
        # siehe https://www.ctb.de/_wiki/swb/Massbezuege.php

        self.logger.info("Start design LCA")
        thermal_zones = filter_instances(instances, 'ThermalZone')
        thermal_zones = [tz for tz in thermal_zones if tz.ventilation_system == True]

        self.logger.info("Start calculating points of the ventilation outlet at the ceiling")
        # Hier werden die Mittelpunkte der einzelnen Räume aus dem IFC-Modell ausgelesen und im Anschluss um die
        # halbe Höhe des Raumes nach oben verschoben. Es wird also der Punkt an der UKRD (Unterkante Rohdecke)
        # in der Mitte des Raumes berechnet. Hier soll im weiteren Verlauf der Lüftungsauslass angeordnet werden
        center, airflow_volume_per_storey = self.center(thermal_zones, starting_point)
        self.logger.info("Finished calculating points of the ventilation outlet at the ceiling")

        self.logger.info("Getting Airflow Data")
        # Hier werden aus dem mit Daten angereicherten Modell die Daten ausgelesen. Die Daten enthalten den spezifischen
        # gesamten Luftbedarf pro Raum
        airflow_data = self.airflow_data(thermal_zones)
        self.logger.info("Getting Airflow Data successful")

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
        self.logger.info("Calculating intersection points successful")

        # self.logger.info("Visualising points on the ceiling for the ventilation outlet:")
        # self.visualisierung(center,
        #                     airflow_data,
        #                     intersection_points
        #                     )
        #
        #
        # self.logger.info("Visualising intersectionpoints")
        # self.visualisierung_punkte_nach_ebene(center,
        #                                       intersection_points,
        #                                       z_coordinate_set)

        self.logger.info("Graph für jedes Geschoss erstellen")
        (dict_steinerbaum_mit_leitungslaenge,
         dict_steinerbaum_mit_kanalquerschnitt,
         dict_steinerbaum_mit_luftmengen,
         dict_steinerbaum_mit_mantelflaeche,
         dict_steinerbaum_mit_rechnerischem_querschnitt) = self.graph_erstellen(center,
                                                                                intersection_points,
                                                                                z_coordinate_set,
                                                                                starting_point,
                                                                                querschnittsart,
                                                                                zwischendeckenraum,
                                                                                export_graphen
                                                                                )
        self.logger.info("Graph für jedes Geschoss wurde erstellt")

        self.logger.info("Schacht und RLT verbinden")
        (dict_steinerbaum_mit_leitungslaenge,
         dict_steinerbaum_mit_kanalquerschnitt,
         dict_steinerbaum_mit_luftmengen,
         dict_steinerbaum_mit_mantelflaeche,
         dict_steinerbaum_mit_rechnerischem_querschnitt) = self.rlt_schacht(z_coordinate_set,
                                                                            starting_point,
                                                                            airflow_volume_per_storey,
                                                                            position_rlt,
                                                                            dict_steinerbaum_mit_leitungslaenge,
                                                                            dict_steinerbaum_mit_kanalquerschnitt,
                                                                            dict_steinerbaum_mit_luftmengen,
                                                                            dict_steinerbaum_mit_mantelflaeche,
                                                                            dict_steinerbaum_mit_rechnerischem_querschnitt,
                                                                            export_graphen
                                                                            )
        self.logger.info("Schacht und RLT verbunden")

        self.logger.info("3D-Graph erstellen")
        (graph_leitungslaenge,
         graph_luftmengen,
         graph_kanalquerschnitt,
         graph_mantelflaeche,
         graph_rechnerischer_durchmesser) = self.drei_dimensionaler_graph(dict_steinerbaum_mit_leitungslaenge,
                                                                          dict_steinerbaum_mit_kanalquerschnitt,
                                                                          dict_steinerbaum_mit_luftmengen,
                                                                          dict_steinerbaum_mit_mantelflaeche,
                                                                          dict_steinerbaum_mit_rechnerischem_querschnitt)
        self.logger.info("3D-Graph erstellt")

        self.logger.info("Starte Druckverlustberechnung")
        self.druckverlust(z_coordinate_set,
                          position_rlt,
                          graph_leitungslaenge,
                          graph_luftmengen,
                          graph_kanalquerschnitt,
                          graph_mantelflaeche,
                          graph_rechnerischer_durchmesser
                          )

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
            thermal_zones: thermal_zones bim2sim element
            starting_point: Schachtkoordinate
        Returns:
            center of the room at the ceiling
        """
        # Listen:
        room_ceiling_ventilation_outlet = []
        room_type = []

        for tz in thermal_zones:
            room_ceiling_ventilation_outlet.append([self.runde_decimal(tz.space_center.X(), 1),
                                                    self.runde_decimal(tz.space_center.Y(), 1),
                                                    self.runde_decimal(tz.space_center.Z() + tz.height.magnitude / 2,
                                                                       2),
                                                    self.runde_decimal(tz.air_flow.magnitude, 0)])
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
                x1, y1, z1, a1 = sort[i]
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
                    adjusted_coords_x.append((self.runde_decimal(x_avg, 1), y, z, a))
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
                while j < len(room_ceiling_ventilation_outlet) and room_ceiling_ventilation_outlet[j][1] - \
                        current_coord[1] < 0.5:
                    sum_y += room_ceiling_ventilation_outlet[j][1]
                    count += 1
                    j += 1

                # Berechne den Durchschnitt der y-Koordinaten
                average_y = sum_y / count

                # Füge die Koordinaten mit dem Durchschnitt der y-Koordinaten zur neuen Liste hinzu
                for k in range(i, j):
                    x, _, z, a = room_ceiling_ventilation_outlet[k]
                    adjusted_coords_y.append((x, self.runde_decimal(average_y, 1), z, a))

                # Aktualisiere die äußere Schleifenvariable i auf den nächsten nicht verarbeiteten Index
                i = j

        room_ceiling_ventilation_outlet = adjusted_coords_y

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

        for z_coord in z_axis:
            room_ceiling_ventilation_outlet.append((starting_point[0], starting_point[1], z_coord,
                                                    airflow_volume_per_storey[z_coord]))

        return room_ceiling_ventilation_outlet, airflow_volume_per_storey

    def airflow_data(self, thermal_zones):
        """Function getting the airflow data of each room from the IFC File

        Args:
            thermal_zones: ThermalZone bim2sim element
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
        # Liste der Schnittpunkte
        intersection_points_list = []

        # # Raster
        #
        # for z_value in z_coordinate_set:
        #
        #     for x in range(50):  #
        #         for y in range(20):  #
        #             intersection_points_list.append((x, y, z_value, 0))

        # Schnittpunkte
        for z_value in z_coordinate_set:
            filtered_coordinates_list = [coord for coord in ceiling_point if coord[2] == z_value]

            for z_value in range(len(filtered_coordinates_list)):
                for j in range(z_value + 1, len(filtered_coordinates_list)):
                    p1 = filtered_coordinates_list[z_value]
                    p2 = filtered_coordinates_list[j]
                    # Schnittpunkte entlang der X- und Y-Achsen
                    intersection_points_list.append((p2[0], p1[1], p1[2], 0))  # Schnittpunkt auf der Linie parallel zur
                    # X-Achse von p1 und zur Y-Achse von p2
                    intersection_points_list.append((p1[0], p2[1], p2[2], 0))  # Schnittpunkt auf der Linie parallel zur
                    # Y-Achse von p1 und zur X-Achse von p2

        intersection_points_list = list(set(intersection_points_list))  # Doppelte Punkte entfernen

        # Erstelle eine neue Liste, um die gefilterten Punkte zu speichern
        filtered_intersection_points = []

        # Überprüfe für jeden Punkt in intersection_points, ob er in ceiling_points existiert
        for ip in intersection_points_list:
            if not any(cp[:3] == ip[:3] for cp in ceiling_point):
                filtered_intersection_points.append(ip)

        return filtered_intersection_points

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
        coordinates1 = room_ceiling_ventilation_outlet  # Punkte für Auslässe
        coordinates2 = intersection  # Schnittpunkte

        # Extrahieren der x, y und z Koordinaten aus den beiden Listen
        x1, y1, z1, a1 = zip(*coordinates1)
        x2, y2, z2, a2 = zip(*coordinates2)

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

    def visualisierung_punkte_nach_ebene(self, center, intersection, z_coordinate_set):
        """The function visualizes the points in a diagram
        Args:
            center: Mittelpunkt es Raumes an der Decke
            intersection: intersection points at the ceiling
            z_coordinate_set: Z-Koordinaten für jedes Geschoss an der Decke
        Returns:
           2D diagramm for each ceiling
       """
        for z_value in z_coordinate_set:
            x_values = [x for x, y, z, a in intersection if z == z_value]
            y_values = [y for x, y, z, a in intersection if z == z_value]
            x_values_center = [x for x, y, z, a in center if z == z_value]
            y_values_center = [y for x, y, z, a in center if z == z_value]

            plt.figure(num=f"Grundriss: {z_value}")
            plt.scatter(x_values, y_values, color="r", marker='x', label="Schnittpunkte")
            plt.scatter(x_values_center, y_values_center, color="b", marker='D', label="Lüftungsauslässe")
            plt.title(f'Höhe: {z_value}')
            plt.subplots_adjust(right=0.7)
            plt.legend(loc="center left", bbox_to_anchor=(1, 0.5))
            plt.xlabel('X-Achse [m]')
            plt.ylabel('Y-Achse [m]')

        plt.show()

    def visualisierung_graph(self,
                             G,
                             steiner_baum,
                             z_value,
                             coordinates_without_airflow,
                             filtered_coords_ceiling_without_airflow,
                             filtered_coords_intersection_without_airflow,
                             name,
                             einheit_kante,
                             mantelflaeche_gesamt
                             ):
        """
        :param G: Graph
        :param steiner_baum: Steinerbaum
        :param z_value: Z-Achse
        :param coordinates_without_airflow: Schnittpunkte
        :param filtered_coords_ceiling_without_airflow: Koordinaten ohne Volumenstrom
        :param filtered_coords_intersection_without_airflow: Schnittpunkte ohne Volumenstrom
        :param name: Diagrammbezeichnung
        :param einheit_kante: Einheit der Kante für Legende Diagramm
        :param mantelflaeche_gesamt: Gesamte Fläche des Kanalmantels
        """
        # Visualisierung
        plt.figure(figsize=(30, 10), dpi=300)
        plt.xlabel('X-Achse [m]')
        plt.ylabel('Y-Achse [m]')
        plt.title(name + f", Z: {z_value}")
        plt.grid(False)
        plt.subplots_adjust(left=0.03, bottom=0.03, right=0.97,
                            top=0.97)  # Entfernt den Rand um das Diagramm, Diagramm quasi Vollbild
        plt.axis('equal')  # Sorgt dafür das Plot maßstabsgebtreu ist

        # Positionen der Knoten festlegen
        pos = {node: (node[0], node[1]) for node in coordinates_without_airflow}

        # Knoten zeichnen
        nx.draw_networkx_nodes(G,
                               pos,
                               nodelist=filtered_coords_ceiling_without_airflow,
                               node_shape='D',
                               node_color='blue',
                               node_size=150)
        nx.draw_networkx_nodes(G,
                               pos,
                               nodelist=filtered_coords_intersection_without_airflow,
                               node_shape='o',
                               node_color='red',
                               node_size=50)

        # Kanten zeichnen
        nx.draw_networkx_edges(G, pos, width=1)
        nx.draw_networkx_edges(steiner_baum, pos, width=4, style="-", edge_color="green")

        # Kantengewichte anzeigen
        edge_labels = nx.get_edge_attributes(steiner_baum, 'weight')
        # nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=10, font_weight=10)
        nx.draw_networkx_edge_labels(steiner_baum, pos, edge_labels=edge_labels, font_size=8, font_weight=10,
                                     rotate=False)

        # Knotengewichte anzeigen
        node_labels = nx.get_node_attributes(G, 'weight')
        nx.draw_networkx_labels(G, pos, labels=node_labels, font_size=8, font_color="white")

        # Legende erstellen
        legend_ceiling = plt.Line2D([0], [0], marker='D', color='w', label='Deckenauslass [m³/h]',
                                    markerfacecolor='blue',
                                    markersize=10)
        legend_intersection = plt.Line2D([0], [0], marker='o', color='w', label='Kreuzungsknoten',
                                         markerfacecolor='red', markersize=6)
        legend_edge = plt.Line2D([0], [0], color='black', lw=1, label="Kante " + einheit_kante)
        legend_steiner_edge = plt.Line2D([0], [0], color='green', lw=4, linestyle='-.', label='Steiner-Kante')

        # Prüfen, ob die Mantelfläche verfügbar ist
        if mantelflaeche_gesamt is not False:
            legend_mantelflaeche = plt.Line2D([0], [0], lw=0, label=f'Mantelfläche: {mantelflaeche_gesamt} [m²]')

            # Legende zum Diagramm hinzufügen, inklusive der Mantelfläche
            plt.legend(
                handles=[legend_ceiling, legend_intersection, legend_edge, legend_steiner_edge, legend_mantelflaeche],
                loc='best')
        else:
            # Legende zum Diagramm hinzufügen, ohne die Mantelfläche
            plt.legend(handles=[legend_ceiling, legend_intersection, legend_edge, legend_steiner_edge],
                       loc='best')  # , bbox_to_anchor=(1.1, 0.5)

        # Setze den Pfad für den neuen Ordner
        ordner_pfad = Path(self.paths.export / f"Z_{z_value}")

        # Erstelle den Ordner
        ordner_pfad.mkdir(parents=True, exist_ok=True)

        # Speichern des Graphens
        gesamte_bezeichnung = name + " Z " + f"{z_value}" + ".png"
        pfad_plus_name = self.paths.export / f"Z_{z_value}" / gesamte_bezeichnung
        plt.savefig(pfad_plus_name)

        # Anzeigen des Graphens
        # plt.show()

        # Schließen des Plotts
        plt.close()

    def notwendiger_kanaldquerschnitt(self, volumenstrom):
        """
        Hier wird der erforderliche Kanalquerschnitt in Abhängigkeit vom Volumenstrom berechnet
        Args:
            volumenstrom:
        Returns:
            kanalquerschnitt [m²]
        """

        # Hier wird der Leitungsquerschnitt ermittelt:
        # Siehe Beispiel Seite 10 "Leitfaden zur Auslegung von lufttechnischen Anlagen" www.aerotechnik.de

        kanalquerschnitt = volumenstrom / (5 * 3600)
        return kanalquerschnitt

    def abmessungen_eckiger_querschnitt(self, kanalquerschnitt, zwischendeckenraum=2000):
        """

        :param kanalquerschnitt:
        :param zwischendeckenraum:
        :return: Querschnittsabmessungen
        """
        # Pfad zur CSV für die Querschnittsdaten
        file_path = Path(
            bim2sim.__file__).parent.parent / ("bim2sim/plugins/PluginLCA/bim2sim_lca/examples/DIN_EN_ISO"
                                               "/rectangular_ventilation_cross-section_area.csv")

        # Lesen der CSV-Datei in einen Pandas DataFrame
        df = pd.read_csv(file_path, sep=',')

        # Konvertieren der Höhenspalten in numerische Werte
        df.columns = ['Breite'] + pd.to_numeric(df.columns[1:], errors='coerce').tolist()

        # Erstellen einer Liste von Höhen als numerische Werte
        hoehen = pd.to_numeric(df.columns[1:], errors='coerce')

        # Filtern der Daten für Höhen bis zur verfügbaren Höhe im Zwischendeckenraum
        filtered_hoehen = hoehen[hoehen <= zwischendeckenraum]

        # Berechnen der Differenzen und Verhältnisse für jede Kombination
        kombinationen = []
        for index, row in df.iterrows():
            breite = row['Breite']
            for hoehe in filtered_hoehen:
                flaeche = row[hoehe]
                if not pd.isna(flaeche) and flaeche >= kanalquerschnitt:
                    diff = abs(flaeche - kanalquerschnitt)
                    verhaeltnis = min(breite, hoehe) / max(breite,
                                                           hoehe)  # Verhältnis als das kleinere geteilt durch das
                    # größere
                    kombinationen.append((breite, hoehe, flaeche, diff, verhaeltnis))

        # Erstellen eines neuen DataFrames aus den Kombinationen
        kombinationen_df = pd.DataFrame(kombinationen,
                                        columns=['Breite', 'Hoehe', 'Flaeche', 'Diff', 'Verhaeltnis'])

        # Finden der besten Kombination
        beste_kombination_index = (kombinationen_df['Diff'] + abs(kombinationen_df['Diff'] - 1)).idxmin()
        beste_breite = int(kombinationen_df.at[beste_kombination_index, 'Breite'])
        beste_hoehe = int(kombinationen_df.at[beste_kombination_index, 'Hoehe'])
        querschnitt = f"{beste_breite} x {beste_hoehe}"

        return querschnitt

    def abmessungen_runder_querschnitt(self, kanalquerschnitt, zwischendeckenraum):
        # lueftungsleitung_rund_durchmesser: Ist ein Dict, was als Eingangsgröße den Querschnitt [m²] hat und als
        # Ausgangsgröße die Durchmesser [mm] nach EN 1506:2007 (D) 4. Tabelle 1

        lueftungsleitung_rund_durchmesser = {0.00312: 60,
                                             0.00503: 80,
                                             0.00785: 100,
                                             0.0123: 125,
                                             0.0201: 160,
                                             0.0314: 200,
                                             0.0491: 250,
                                             0.0779: 315,
                                             0.126: 400,
                                             0.196: 500,
                                             0.312: 630,
                                             0.503: 800,
                                             0.785: 1000,
                                             1.23: 1250
                                             }
        sortierte_schluessel = sorted(lueftungsleitung_rund_durchmesser.keys())
        for key in sortierte_schluessel:
            if key > kanalquerschnitt and lueftungsleitung_rund_durchmesser[key] <= zwischendeckenraum:
                return f"Ø{lueftungsleitung_rund_durchmesser[key]}"
            elif key > kanalquerschnitt and lueftungsleitung_rund_durchmesser[key] > zwischendeckenraum:
                return f"Zwischendeckenraum zu gering"

    def abmessungen_kanal(self, querschnitts_art, kanalquerschnitt, zwischendeckenraum=2000):
        """
        Args:
            querschnitts_art: Rund oder eckig
            kanalquerschnitt: erforderlicher Kanalquerschnitt
            zwischendeckenraum:
        Returns:
             Durchmesser oder Kantenlängen a x b des Kanals
        """

        if querschnitts_art == "rund":
            return self.abmessungen_runder_querschnitt(kanalquerschnitt, zwischendeckenraum)

        elif querschnitts_art == "eckig":
            return self.abmessungen_eckiger_querschnitt(kanalquerschnitt)

        elif querschnitts_art == "optimal":
            if self.abmessungen_runder_querschnitt(kanalquerschnitt,
                                                   zwischendeckenraum) == "Zwischendeckenraum zu gering":
                return self.abmessungen_eckiger_querschnitt(kanalquerschnitt, zwischendeckenraum)
            else:
                return self.abmessungen_runder_querschnitt(kanalquerschnitt, zwischendeckenraum)

    def durchmesser_runder_kanal(self, kanalquerschnitt):
        # lueftungsleitung_rund_durchmesser: Ist ein Dict, was als Eingangsgröße den Querschnitt [m²] hat und als
        # Ausgangsgröße die Durchmesser [mm] nach EN 1506:2007 (D) 4. Tabelle 1

        lueftungsleitung_rund_durchmesser = {0.00312: 60,
                                             0.00503: 80,
                                             0.00785: 100,
                                             0.0123: 125,
                                             0.0201: 160,
                                             0.0314: 200,
                                             0.0491: 250,
                                             0.0779: 315,
                                             0.126: 400,
                                             0.196: 500,
                                             0.312: 630,
                                             0.503: 800,
                                             0.785: 1000,
                                             1.23: 1250
                                             }
        sortierte_schluessel = sorted(lueftungsleitung_rund_durchmesser.keys())
        for key in sortierte_schluessel:
            if key > kanalquerschnitt:
                return lueftungsleitung_rund_durchmesser[key]

    def mantelflaeche_eckiger_kanal(self, kanalquerschnitt, zwischendeckenraum=2000):
        # Pfad zur CSV für die Querschnittsdaten
        file_path = Path(
            bim2sim.__file__).parent.parent / ("bim2sim/plugins/PluginLCA/bim2sim_lca/examples/DIN_EN_ISO"
                                               "/rectangular_ventilation_cross-section_area.csv")

        # Lesen der CSV-Datei in einen Pandas DataFrame
        df = pd.read_csv(file_path, sep=',')

        # Konvertieren der Höhenspalten in numerische Werte
        df.columns = ['Breite'] + pd.to_numeric(df.columns[1:], errors='coerce').tolist()

        # Erstellen einer Liste von Höhen als numerische Werte
        hoehen = pd.to_numeric(df.columns[1:], errors='coerce')

        # Filtern der Daten für Höhen bis zur maximalen Höhe
        filtered_hoehen = hoehen[hoehen <= zwischendeckenraum]

        # Berechnen der Differenzen und Verhältnisse für jede Kombination
        kombinationen = []
        for index, row in df.iterrows():
            breite = row['Breite']
            for hoehe in filtered_hoehen:
                flaeche = row[hoehe]
                if not pd.isna(flaeche) and flaeche >= kanalquerschnitt:
                    diff = abs(flaeche - kanalquerschnitt)
                    verhaeltnis = min(breite, hoehe) / max(breite,
                                                           hoehe)  # Verhältnis als das kleinere geteilt durch das
                    # größere
                    kombinationen.append((breite, hoehe, flaeche, diff, verhaeltnis))

        # Erstellen eines neuen DataFrames aus den Kombinationen
        kombinationen_df = pd.DataFrame(kombinationen,
                                        columns=['Breite', 'Hoehe', 'Flaeche', 'Diff', 'Verhaeltnis'])

        # Finden der besten Kombination
        beste_kombination_index = (kombinationen_df['Diff'] + abs(kombinationen_df['Diff'] - 1)).idxmin()
        beste_breite = int(kombinationen_df.at[beste_kombination_index, 'Breite'])
        beste_hoehe = int(kombinationen_df.at[beste_kombination_index, 'Hoehe'])

        umfang = (2 * beste_breite + 2 * beste_hoehe) / 1000

        return umfang

    def aequivalent_durchmesser(self, kanalquerschnitt, zwischendeckenraum=2000):
        # Pfad zur CSV für die Querschnittsdaten
        file_path = Path(
            bim2sim.__file__).parent.parent / ("bim2sim/plugins/PluginLCA/bim2sim_lca/examples/DIN_EN_ISO"
                                               "/rectangular_ventilation_cross-section_area.csv")

        # Lesen der CSV-Datei in einen Pandas DataFrame
        df = pd.read_csv(file_path, sep=',')

        # Konvertieren der Höhenspalten in numerische Werte
        df.columns = ['Breite'] + pd.to_numeric(df.columns[1:], errors='coerce').tolist()

        # Erstellen einer Liste von Höhen als numerische Werte
        hoehen = pd.to_numeric(df.columns[1:], errors='coerce')

        # Filtern der Daten für Höhen bis zur maximalen Höhe
        filtered_hoehen = hoehen[hoehen <= zwischendeckenraum]

        # Berechnen der Differenzen und Verhältnisse für jede Kombination
        kombinationen = []
        for index, row in df.iterrows():
            breite = row['Breite']
            for hoehe in filtered_hoehen:
                flaeche = row[hoehe]
                if not pd.isna(flaeche) and flaeche >= kanalquerschnitt:
                    diff = abs(flaeche - kanalquerschnitt)
                    verhaeltnis = min(breite, hoehe) / max(breite,
                                                           hoehe)  # Verhältnis als das kleinere geteilt durch das
                    # größere
                    kombinationen.append((breite, hoehe, flaeche, diff, verhaeltnis))

        # Erstellen eines neuen DataFrames aus den Kombinationen
        kombinationen_df = pd.DataFrame(kombinationen,
                                        columns=['Breite', 'Hoehe', 'Flaeche', 'Diff', 'Verhaeltnis'])

        # Finden der besten Kombination
        beste_kombination_index = (kombinationen_df['Diff'] + abs(kombinationen_df['Diff'] - 1)).idxmin()
        beste_breite = int(kombinationen_df.at[beste_kombination_index, 'Breite'])
        beste_hoehe = int(kombinationen_df.at[beste_kombination_index, 'Hoehe'])

        # Für Luftleitungen mit Rechteckquerschnitt (a × b) beträgt der hydraulische Durchmesser nach VDI 2087

        aequivalent_durchmesser = (2 * beste_breite * beste_hoehe) / (beste_breite + beste_hoehe)

        return aequivalent_durchmesser

    def mantelflaeche_kanal(self, querschnitts_art, kanalquerschnitt, zwischendeckenraum=2000):
        """

        :param querschnitts_art: rund, eckig oder optimal
        :param kanalquerschnitt: Querschnittsfläche des Kanals im jeweiligen Abschnitt
        :param zwischendeckenraum: Luftraum zwischen Abhangdecke und Rohdecke
        :return: Mantelfläche pro Meter des Kanals
        """

        if querschnitts_art == "rund":
            return round(math.pi * self.durchmesser_runder_kanal(kanalquerschnitt) / 1000, 3)

        elif querschnitts_art == "eckig":
            return self.mantelflaeche_eckiger_kanal(kanalquerschnitt)

        elif querschnitts_art == "optimal":
            if self.durchmesser_runder_kanal(kanalquerschnitt) <= zwischendeckenraum:
                return round(math.pi * self.durchmesser_runder_kanal(kanalquerschnitt) / 1000, 3)
            else:
                return self.mantelflaeche_eckiger_kanal(kanalquerschnitt, zwischendeckenraum)

    def rechnerischer_durchmesser(self, querschnitts_art, kanalquerschnitt, zwischendeckenraum=2000):
        """

        :param querschnitts_art: rund, eckig oder optimal
        :param kanalquerschnitt: Querschnittsfläche des Kanals im jeweiligen Abschnitt
        :param zwischendeckenraum: Luftraum zwischen Abhangdecke und Rohdecke
        :return: rechnerischer Durchmesser des Kanals
        """

        if querschnitts_art == "rund":
            return self.durchmesser_runder_kanal(kanalquerschnitt)

        elif querschnitts_art == "eckig":
            return self.aequivalent_durchmesser(kanalquerschnitt)

        elif querschnitts_art == "optimal":
            if self.durchmesser_runder_kanal(kanalquerschnitt) <= zwischendeckenraum:
                return self.durchmesser_runder_kanal(kanalquerschnitt)
            else:
                return self.aequivalent_durchmesser(kanalquerschnitt, zwischendeckenraum)

    def euklidische_distanz(self, punkt1, punkt2):
        """
        Calculating the distance between point1 and 2
        :param punkt1:
        :param punkt2:
        :return: Distance between punkt1 and punkt2
        """
        return round(
            math.sqrt((punkt2[0] - punkt1[0]) ** 2 + (punkt2[1] - punkt1[1]) ** 2 + (punkt2[2] - punkt1[2]) ** 2),
            2)

    def plot_schacht(self, graph, name):

        # Plot
        plt.figure(dpi=450)
        plt.xlabel('X-Achse [m]')
        plt.ylabel('Z-Achse [m]')
        plt.title(name)
        plt.grid(False)
        plt.subplots_adjust(left=0.05, bottom=0.05, right=0.95,
                            top=0.95)  # Entfernt den Rand um das Diagramm, Diagramm quasi Vollbild
        plt.axis('equal')  # Sorgt dafür das Plot maßstabsgebtreu ist

        # Positionen der Knoten festlegen
        pos = {node: (node[0], node[2]) for node in graph.nodes()}

        # Knoten zeichnen
        nx.draw_networkx_nodes(graph,
                               pos,
                               nodelist=graph.nodes(),
                               node_shape='D',
                               node_color='blue',
                               node_size=150)

        # Kanten zeichnen
        nx.draw_networkx_edges(graph, pos, width=1)

        # Kantengewichte anzeigen
        edge_labels = nx.get_edge_attributes(graph, 'weight')
        nx.draw_networkx_edge_labels(graph, pos, edge_labels=edge_labels, font_size=4, font_weight=4,
                                     rotate=False)

        # Knotengewichte anzeigen
        node_labels = nx.get_node_attributes(graph, 'weight')
        nx.draw_networkx_labels(graph, pos, labels=node_labels, font_size=4, font_color="white")

        # Legende für Knoten
        legend_knoten = plt.Line2D([0], [0], marker='D', color='w', label='Knoten',
                                   markerfacecolor='blue', markersize=8)

        # Legende zum Plot hinzufügen
        plt.legend(handles=[legend_knoten], loc='best')

        # Setze den Pfad für den neuen Ordner
        ordner_pfad = Path(self.paths.export / "Schacht")

        # Erstelle den Ordner
        ordner_pfad.mkdir(parents=True, exist_ok=True)

        # Speichern des Graphens
        gesamte_bezeichnung = name + ".png"
        pfad_plus_name = self.paths.export / "Schacht" / gesamte_bezeichnung
        plt.savefig(pfad_plus_name)

        # Anzeigen des Graphens
        # plt.show()

        # Schließen des Plotts
        plt.close()

    def find_leaves(self, spanning_tree):
        leaves = []
        for node in spanning_tree:
            if len(spanning_tree[node]) == 1:  # Ein Blatt hat nur einen Nachbarn
                leaves.append(node)
        return leaves

    def graph_erstellen(self, ceiling_point, intersection_points, z_coordinate_set, starting_point,
                        querschnittsart, zwischendeckenraum, export_graphen):
        """The function creates a connected graph for each floor
        Args:
           ceiling_point: Point at the ceiling in the middle of the room
           intersection points: intersection points at the ceiling
           z_coordinate_set: z coordinates for each storey ceiling
           starting_point: Coordinate of the shaft
           querschnittsart: rund, eckig oder optimal
           zwischendeckenraum: verfügbare Höhe (in [mmm]) in der Zwischendecke angegeben! Diese
            entspricht dem verfügbaren Abstand zwischen UKRD (Unterkante Rohdecke) und OKFD (Oberkante Fertigdecke),
            siehe https://www.ctb.de/_wiki/swb/Massbezuege.php
        Returns:
           connected graph for each floor
       """

        def knick_in_lueftungsleitung(lueftungsauslass_zu_x):
            if lueftungsauslass_zu_x != []:
                # Extrahiere die X- und Y-Koordinaten
                x_coords = [x for x, _, _ in lueftungsauslass_zu_x[0]]
                y_coords = [y for _, y, _ in lueftungsauslass_zu_x[0]]

                # Überprüfe, ob alle X-Koordinaten gleich sind oder alle Y-Koordinaten gleich sind
                same_x = all(x == x_coords[0] for x in x_coords)
                same_y = all(y == y_coords[0] for y in y_coords)

                if same_x == True or same_y == True:
                    return False
                else:
                    return True
            else:
                None

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

        # Hier werden leere Dictonaries für die einzelnen Höhen erstellt:
        dict_steinerbaum_mit_leitungslaenge = {schluessel: None for schluessel in z_coordinate_set}
        dict_steinerbaum_mit_luftmengen = {schluessel: None for schluessel in z_coordinate_set}
        dict_steinerbaum_mit_kanalquerschnitt = {schluessel: None for schluessel in z_coordinate_set}
        dict_steinerbaum_mit_rechnerischem_querschnitt = {schluessel: None for schluessel in z_coordinate_set}
        dict_steinerbaum_mit_mantelflaeche = {schluessel: None for schluessel in z_coordinate_set}

        # Spezifische Behandlung für den Fall einer leeren Sequenz
        try:
            for z_value in z_coordinate_set:

                # Hier werden die Koordinaten nach Ebene gefiltert
                filtered_coords_ceiling = [coord for coord in ceiling_point if coord[2] == z_value]
                filtered_coords_intersection = [coord for coord in intersection_points if coord[2] == z_value]
                coordinates = filtered_coords_intersection + filtered_coords_ceiling

                # Koordinaten ohne Luftmengen:
                filtered_coords_ceiling_without_airflow = [(x, y, z) for x, y, z, a in filtered_coords_ceiling]
                filtered_coords_intersection_without_airflow = [(x, y, z) for x, y, z, a in
                                                                filtered_coords_intersection]
                coordinates_without_airflow = (filtered_coords_ceiling_without_airflow
                                               + filtered_coords_intersection_without_airflow)

                # Erstellt den Graphen
                G = nx.Graph()

                # Terminals:
                # Terminals sind die vordefinierten Knoten in einem Graphen, die in der Lösung des Steinerbaum-Problems
                # unbedingt miteinander verbunden werden müssen
                terminals = list()

                # Hinzufügen der Knoten für Lüftungsauslässe zu Terminals
                for x, y, z, a in filtered_coords_ceiling:
                    G.add_node((x, y, z), weight=int(a))
                    if int(a) > 0:  # Bedingung, um Terminals zu bestimmen (z.B. Gewicht > 0)
                        terminals.append((x, y, z))

                # Kanten entlang der X-Achse hinzufügen
                unique_coords = set(coord[0] for coord in coordinates_without_airflow)
                for u in unique_coords:
                    nodes_on_same_axis = sorted([coord for coord in coordinates_without_airflow if coord[0] == u],
                                                key=lambda c: c[1 - 0])
                    for i in range(len(nodes_on_same_axis) - 1):
                        gewicht_kante_y = self.euklidische_distanz(nodes_on_same_axis[i], nodes_on_same_axis[i + 1])
                        G.add_edge(nodes_on_same_axis[i], nodes_on_same_axis[i + 1], weight=gewicht_kante_y)

                # Kanten entlang der Y-Achse hinzufügen
                unique_coords = set(coord[1] for coord in coordinates_without_airflow)
                for u in unique_coords:
                    nodes_on_same_axis = sorted([coord for coord in coordinates_without_airflow if coord[1] == u],
                                                key=lambda c: c[1 - 1])
                    for i in range(len(nodes_on_same_axis) - 1):
                        gewicht_kante_x = self.euklidische_distanz(nodes_on_same_axis[i], nodes_on_same_axis[i + 1])
                        G.add_edge(nodes_on_same_axis[i], nodes_on_same_axis[i + 1], weight=gewicht_kante_x)

                # Erstellung des Steinerbaums
                steiner_baum = steiner_tree(G, terminals, weight="weight")

                # Export
                if export_graphen == True:
                    self.visualisierung_graph(steiner_baum,
                                              steiner_baum,
                                              z_value,
                                              coordinates_without_airflow,
                                              filtered_coords_ceiling_without_airflow,
                                              filtered_coords_intersection_without_airflow,
                                              name=f"Steinerbaum 0. Optimierung",
                                              einheit_kante="",
                                              mantelflaeche_gesamt=False
                                              )

                # Extraierung der Knoten und Katen aus dem Steinerbaum
                knoten = list(steiner_baum.nodes())
                kanten = list(steiner_baum.edges())

                # Erstellung des Baums
                tree = nx.Graph()

                # Hinzufügen der Knoten zum Baum
                for x, y, z in knoten:
                    for point in coordinates:
                        if point[0] == x and point[1] == y and point[2] == z:
                            tree.add_node((x, y, z), weight=point[3])

                # Hinzufügen der Kanten zum Baum
                for kante in kanten:
                    tree.add_edge(kante[0], kante[1], weight=self.euklidische_distanz(kante[0], kante[1]))

                # Hier wird der minimale Spannbaum des Steinerbaums berechnet
                minimum_spanning_tree = nx.minimum_spanning_tree(tree)

                """Optimierungsschritt 1"""
                # Hier wird überprüft, welche Punkte entlang eines Pfades, auf einer Achse liegen.
                # Ziel ist es die Steinerpunkte zu finden, die zwischen zwei Terminalen liegen, damit der Graph
                # optimiert werden kann
                coordinates_on_same_axis = list()
                for startknoten in filtered_coords_ceiling_without_airflow:
                    for zielknoten in filtered_coords_ceiling_without_airflow:
                        for path in nx.all_simple_paths(minimum_spanning_tree, startknoten, zielknoten):
                            # Extrahiere die X- und Y-Koordinaten
                            x_coords = [x for x, _, _ in path]
                            y_coords = [y for _, y, _ in path]

                            # Überprüfe, ob alle X-Koordinaten gleich sind oder alle Y-Koordinaten gleich sind
                            same_x = all(x == x_coords[0] for x in x_coords)
                            same_y = all(y == y_coords[0] for y in y_coords)

                            if same_x == True or same_y == True:
                                for cord in path:
                                    coordinates_on_same_axis.append(cord)

                # Doppelte entfernen:
                coordinates_on_same_axis = set(coordinates_on_same_axis)

                # Wenn die Koordinate ein Lüftungsausslass ist, muss diese ignoriert werden
                coordinates_on_same_axis = [item for item in coordinates_on_same_axis if item not in
                                            filtered_coords_ceiling_without_airflow]

                # Hinzufügen der Koordinaten zu den Terminalen
                for coord in coordinates_on_same_axis:
                    terminals.append(coord)

                # Erstellung des neuen Steinerbaums
                steiner_baum = steiner_tree(G, terminals, weight="weight")

                # Export
                if export_graphen == True:
                    self.visualisierung_graph(steiner_baum,
                                              steiner_baum,
                                              z_value,
                                              coordinates_without_airflow,
                                              filtered_coords_ceiling_without_airflow,
                                              filtered_coords_intersection_without_airflow,
                                              name=f"Steinerbaum 1. Optimierung",
                                              einheit_kante="",
                                              mantelflaeche_gesamt=False
                                              )

                """Optimierungschritt 2"""
                # Hier wird überprüft, ob unnötige Umlenkungen im Graphen vorhanden sind:
                for lueftungsauslass in filtered_coords_ceiling_without_airflow:
                    if steiner_baum.degree(lueftungsauslass) == 2:
                        neighbors = list(nx.all_neighbors(steiner_baum, lueftungsauslass))

                        nachbarauslass_eins = neighbors[0]
                        temp = list()
                        i = 0
                        while nachbarauslass_eins not in filtered_coords_ceiling_without_airflow:
                            temp.append(nachbarauslass_eins)
                            neue_nachbarn = list(nx.all_neighbors(steiner_baum, nachbarauslass_eins))
                            neue_nachbarn = [koord for koord in neue_nachbarn if koord != lueftungsauslass]
                            nachbarauslass_eins = [koord for koord in neue_nachbarn if koord != temp[i - 1]]
                            nachbarauslass_eins = nachbarauslass_eins[0]
                            i += 1
                            if nachbarauslass_eins in filtered_coords_ceiling_without_airflow:
                                break

                        nachbarauslass_zwei = neighbors[1]
                        temp = list()
                        i = 0
                        while nachbarauslass_zwei not in filtered_coords_ceiling_without_airflow:
                            temp.append(nachbarauslass_zwei)
                            neue_nachbarn = list(nx.all_neighbors(steiner_baum, nachbarauslass_zwei))
                            neue_nachbarn = [koord for koord in neue_nachbarn if koord != lueftungsauslass]
                            nachbarauslass_zwei = [koord for koord in neue_nachbarn if koord != temp[i - 1]]
                            nachbarauslass_zwei = nachbarauslass_zwei[0]
                            i += 1
                            if nachbarauslass_zwei in filtered_coords_ceiling_without_airflow:
                                break

                        # Gibt den Pfad vom Nachbarauslass 1 zum Lüftungsauslass in Form von Knoten zurück
                        lueftungsauslass_zu_eins = list(nx.all_simple_paths(steiner_baum, lueftungsauslass,
                                                                            nachbarauslass_eins))

                        # Gibt den Pfad vom Lüftungsauslass zum Nachbarauslass 2 in Form von Knoten zurück
                        lueftungsauslass_zu_zwei = list(nx.all_simple_paths(steiner_baum, lueftungsauslass,
                                                                            nachbarauslass_zwei))

                        if knick_in_lueftungsleitung(lueftungsauslass_zu_eins) == False and knick_in_lueftungsleitung(
                                lueftungsauslass_zu_zwei) == False:
                            None
                        elif knick_in_lueftungsleitung(lueftungsauslass_zu_eins) == True:
                            if lueftungsauslass_zu_eins != [] and lueftungsauslass_zu_zwei != []:
                                if lueftungsauslass[0] == lueftungsauslass_zu_zwei[0][1][0]:
                                    terminals.append((lueftungsauslass[0], nachbarauslass_eins[1], z_value))
                                elif lueftungsauslass[1] == lueftungsauslass_zu_zwei[0][1][1]:
                                    terminals.append((nachbarauslass_eins[0], lueftungsauslass[1], z_value))
                        elif knick_in_lueftungsleitung(lueftungsauslass_zu_zwei) == True:
                            if lueftungsauslass_zu_eins != [] and lueftungsauslass_zu_zwei != []:
                                if lueftungsauslass[0] == lueftungsauslass_zu_eins[0][1][0]:
                                    terminals.append((lueftungsauslass[0], nachbarauslass_zwei[1], z_value))
                                elif lueftungsauslass[1] == lueftungsauslass_zu_eins[0][1][1]:
                                    terminals.append((nachbarauslass_zwei[0], lueftungsauslass[1], z_value))

                # Erstellung des neuen Steinerbaums
                steiner_baum = steiner_tree(G, terminals, weight="weight")

                if export_graphen == True:
                    self.visualisierung_graph(steiner_baum,
                                              steiner_baum,
                                              z_value,
                                              coordinates_without_airflow,
                                              filtered_coords_ceiling_without_airflow,
                                              filtered_coords_intersection_without_airflow,
                                              name=f"Steinerbaum 2. Optimierung",
                                              einheit_kante="",
                                              mantelflaeche_gesamt=False
                                              )

                """3. Optimierung"""
                # Hier werden die Blätter aus dem Graphen ausgelesen
                blaetter = self.find_leaves(steiner_baum)

                # Entfernen der Blätter die kein Lüftungsauslass sind
                for blatt in blaetter:
                    if blatt not in filtered_coords_ceiling_without_airflow:
                        terminals.remove(blatt)

                # Erstellung des neuen Steinerbaums
                steiner_baum = steiner_tree(G, terminals, weight="weight")

                if export_graphen == True:
                    self.visualisierung_graph(steiner_baum,
                                              steiner_baum,
                                              z_value,
                                              coordinates_without_airflow,
                                              filtered_coords_ceiling_without_airflow,
                                              filtered_coords_intersection_without_airflow,
                                              name=f"Steinerbaum 3. Optimierung",
                                              einheit_kante="",
                                              mantelflaeche_gesamt=False
                                              )

                # Steinerbaum mit Leitungslängen
                dict_steinerbaum_mit_leitungslaenge[z_value] = deepcopy(steiner_baum)

                # Hier wird der Startpunt zu den Blättern gesetzt
                start_punkt = (starting_point[0], starting_point[1], z_value)

                # Erstellung des Baums (hier wird der neue, erste verbesserte Baum erstellt! Die Punkte, welche alle
                # zwischen zwei Lüftungsauslässen liegen, werden genutzt um andere Kanäle auch über die gleich
                # Achse zu verlegen

                # Extraierung der Knoten und Katen aus dem Steinerbaum
                knoten = list(steiner_baum.nodes())
                kanten = list(steiner_baum.edges())

                tree = nx.Graph()

                # Hinzufügen der Knoten zum Baum
                for x, y, z in knoten:
                    for point in coordinates:
                        if point[0] == x and point[1] == y and point[2] == z:
                            tree.add_node((x, y, z), weight=point[3])

                # Hinzufügen der Kanten zum Baum
                for kante in kanten:
                    tree.add_edge(kante[0], kante[1], weight=self.euklidische_distanz(kante[0], kante[1]))

                # Hier wird der minimale Spannbaum des Steinerbaums berechnet
                minimum_spanning_tree = nx.minimum_spanning_tree(tree)

                # Hier werden die Wege im Baum vom Lüftungsauslass zum Startpunkt ausgelesen
                ceiling_point_to_root_list = list()
                for point in filtered_coords_ceiling_without_airflow:
                    for path in nx.all_simple_edge_paths(minimum_spanning_tree, point, start_punkt):
                        ceiling_point_to_root_list.append(path)

                # Hier werden die Gewichte der Kanten im Steinerbaum gelöscht, da sonst die Luftmenge auf den
                # Abstand addiert wird. Es darf aber auch anfangs nicht das Gewicht der Kante zu 0 gesetzt
                # werden, da sonst der Steinerbaum nicht korrekt berechnet wird
                for u, v in steiner_baum.edges():
                    steiner_baum[u][v]["weight"] = 0

                # Hier werden die Luftvolumina entlang des Strangs aufaddiert
                for ceiling_point_to_root in ceiling_point_to_root_list:
                    for startpunkt, zielpunkt in ceiling_point_to_root:
                        # Suche die Lüftungsmenge zur Koordinate:
                        wert = int()
                        for x, y, z, a in coordinates:
                            if x == ceiling_point_to_root[0][0][0] and y == ceiling_point_to_root[0][0][1] and z == \
                                    ceiling_point_to_root[0][0][2]:
                                wert = int(a)
                        G[startpunkt][zielpunkt]["weight"] += wert

                # Hier wird der einzelne Steinerbaum mit Volumenstrom der Liste hinzugefügt
                dict_steinerbaum_mit_luftmengen[z_value] = deepcopy(steiner_baum)

                # Graph mit Leitungsgeometrie erstellen
                H_leitungsgeometrie = deepcopy(steiner_baum)

                for u, v in H_leitungsgeometrie.edges():
                    H_leitungsgeometrie[u][v]["weight"] = self.abmessungen_kanal(querschnittsart,
                                                                                 self.notwendiger_kanaldquerschnitt(
                                                                                     H_leitungsgeometrie[u][v][
                                                                                         "weight"]),
                                                                                 zwischendeckenraum)

                # Hinzufügen des Graphens zum Dict
                dict_steinerbaum_mit_kanalquerschnitt[z_value] = deepcopy(H_leitungsgeometrie)

                if export_graphen == True:
                    self.visualisierung_graph(H_leitungsgeometrie,
                                              H_leitungsgeometrie,
                                              z_value,
                                              coordinates_without_airflow,
                                              filtered_coords_ceiling_without_airflow,
                                              filtered_coords_intersection_without_airflow,
                                              name=f"Steinerbaum mit Kanalquerschnitt [mm]",
                                              einheit_kante="",
                                              mantelflaeche_gesamt=False
                                              )

                # für äquivalenten Durchmesser:
                H_aequivalenter_durchmesser = deepcopy(steiner_baum)

                # Hier wird der Leitung der äquivalente Durchmesser des Kanals zugeordnet
                for u, v in H_aequivalenter_durchmesser.edges():
                    H_aequivalenter_durchmesser[u][v]["weight"] = self.rechnerischer_durchmesser(querschnittsart,
                                                                                                 self.notwendiger_kanaldquerschnitt(
                                                                                                     H_aequivalenter_durchmesser[
                                                                                                         u][v][
                                                                                                         "weight"]),
                                                                                                 zwischendeckenraum)

                # Zum Dict hinzufügen
                dict_steinerbaum_mit_rechnerischem_querschnitt[z_value] = deepcopy(H_aequivalenter_durchmesser)

                if export_graphen == True:
                    self.visualisierung_graph(H_aequivalenter_durchmesser,
                                              H_aequivalenter_durchmesser,
                                              z_value,
                                              coordinates_without_airflow,
                                              filtered_coords_ceiling_without_airflow,
                                              filtered_coords_intersection_without_airflow,
                                              name=f"Steinerbaum mit rechnerischem Durchmesser [mm]",
                                              einheit_kante="",
                                              mantelflaeche_gesamt=False
                                              )

                # Um die gesamte Menge der Mantelfläche zu bestimmen, muss diese aufaddiert werden:
                gesamte_matnelflaeche_luftleitung = 0

                # Hier wird der Leitung die Mantelfläche des Kanals zugeordnet
                for u, v in steiner_baum.edges():
                    steiner_baum[u][v]["weight"] = round(self.mantelflaeche_kanal(querschnittsart,
                                                                                  self.notwendiger_kanaldquerschnitt(
                                                                                      steiner_baum[u][v]["weight"]),
                                                                                  zwischendeckenraum)
                                                         * self.euklidische_distanz(u, v),
                                                         2
                                                         )

                    gesamte_matnelflaeche_luftleitung += round(steiner_baum[u][v]["weight"], 2)

                # Hinzufügen des Graphens zum Dict
                dict_steinerbaum_mit_mantelflaeche[z_value] = deepcopy(steiner_baum)

                if export_graphen == True:
                    self.visualisierung_graph(steiner_baum,
                                              steiner_baum,
                                              z_value,
                                              coordinates_without_airflow,
                                              filtered_coords_ceiling_without_airflow,
                                              filtered_coords_intersection_without_airflow,
                                              name=f"Steinerbaum mit Mantelfläche",
                                              einheit_kante="[m²*100]",
                                              mantelflaeche_gesamt=round(gesamte_matnelflaeche_luftleitung, 2)
                                              )

        except ValueError as e:
            if str(e) == "attempt to get argmin of an empty sequence":
                self.logger.info("Zwischendeckenraum zu gering gewählt!")
                exit()
                # TODO wie am besten?

        return (
            dict_steinerbaum_mit_leitungslaenge, dict_steinerbaum_mit_kanalquerschnitt, dict_steinerbaum_mit_luftmengen,
            dict_steinerbaum_mit_mantelflaeche, dict_steinerbaum_mit_rechnerischem_querschnitt)

    def rlt_schacht(self,
                    z_coordinate_set,
                    starting_point,
                    airflow_volume_per_storey,
                    position_rlt,
                    dict_steinerbaum_mit_leitungslaenge,
                    dict_steinerbaum_mit_kanalquerschnitt,
                    dict_steinerbaum_mit_luftmengen,
                    dict_steinerbaum_mit_mantelflaeche,
                    dict_steinerbaum_mit_rechnerischem_querschnitt,
                    export_graphen
                    ):

        nodes_schacht = list()

        # Ab hier wird er Graph für das RLT-Gerät bis zum Schacht erstellt.
        Schacht = nx.Graph()

        for z_value in z_coordinate_set:
            # Hinzufügen der Knoten
            Schacht.add_node((starting_point[0], starting_point[1], z_value),
                             weight=airflow_volume_per_storey[z_value])
            nodes_schacht.append((starting_point[0], starting_point[1], z_value, airflow_volume_per_storey[z_value]))

        # Ab hier wird der Graph über die Geschosse hinweg erstellt:
        # Kanten für Schacht hinzufügen:
        z_coordinate_list = list(z_coordinate_set)
        for i in range(len(z_coordinate_list) - 1):
            weight = self.euklidische_distanz([starting_point[0], starting_point[1], float(z_coordinate_list[i])],
                                              [starting_point[0], starting_point[1], float(z_coordinate_list[i + 1])])
            Schacht.add_edge((starting_point[0], starting_point[1], z_coordinate_list[i]),
                             (starting_point[0], starting_point[1], z_coordinate_list[i + 1]),
                             weight=weight)

        # Summe Airflow
        summe_airflow = int(sum(airflow_volume_per_storey.values()))

        # Knoten der RLT-Anlage mit Gesamtluftmenge anreichern
        Schacht.add_node((position_rlt[0], position_rlt[1], position_rlt[2]),
                         weight=summe_airflow)

        # Verbinden der RLT Anlage mit dem Schacht
        rlt_schacht_weight = self.euklidische_distanz([position_rlt[0], position_rlt[1], position_rlt[2]],
                                                      [starting_point[0], starting_point[1], position_rlt[2]]
                                                      )

        Schacht.add_edge((position_rlt[0], position_rlt[1], position_rlt[2]),
                         (starting_point[0], starting_point[1], position_rlt[2]),
                         weight=rlt_schacht_weight)

        # Wenn die RLT nicht in der Ebene einer Decke liegt, muss die Luftleitung noch mit dem Schacht verbunden werden
        list_schacht_nodes = list(Schacht.nodes())
        closest = None
        min_distance = float('inf')

        for coord in list_schacht_nodes:
            # Skip if it's the same coordinate
            if coord == (starting_point[0], starting_point[1], position_rlt[2]):
                continue

            # Check if the x and y coordinates are the same
            if coord[0] == starting_point[0] and coord[1] == starting_point[1]:
                distance = abs(coord[2] - position_rlt[2])
                if distance < min_distance:
                    min_distance = distance
                    closest = coord

        verbindung_weight = self.euklidische_distanz([starting_point[0], starting_point[1], position_rlt[2]],
                                                     closest
                                                     )
        Schacht.add_edge((starting_point[0], starting_point[1], position_rlt[2]),
                         closest,
                         weight=verbindung_weight)

        # Zum Dict hinzufügen
        dict_steinerbaum_mit_leitungslaenge["Schacht"] = deepcopy(Schacht)

        # Visualisierung Schacht
        if export_graphen == True:
            self.plot_schacht(Schacht, name="Schacht")

        position_rlt_ohne_airflow = (position_rlt[0], position_rlt[1], position_rlt[2])

        # Hier werden die Wege im Baum vom Lüftungsauslass zum Startpunkt ausgelesen
        schacht_to_rlt = list()
        for point in Schacht.nodes():
            for path in nx.all_simple_edge_paths(Schacht, point, position_rlt_ohne_airflow):
                schacht_to_rlt.append(path)

        # Hier werden die Gewichte der Kanten im Steinerbaum gelöscht, da sonst die Luftmenge auf den
        # Abstand addiert wird. Es darf aber auch anfangs nicht das Gewicht der Kante zu 0 gesetzt
        # werden, da sonst der Steinerbaum nicht korrekt berechnet wird
        for u, v in Schacht.edges():
            Schacht[u][v]["weight"] = 0

        # Hier werden die Luftvolumina entlang des Strangs aufaddiert
        for schachtpunkt_zu_rlt in schacht_to_rlt:
            for startpunkt, zielpunkt in schachtpunkt_zu_rlt:
                # Suche die Lüftungsmenge zur Koordinate:
                wert = int()
                for x, y, z, a in nodes_schacht:
                    if x == schachtpunkt_zu_rlt[0][0][0] and y == schachtpunkt_zu_rlt[0][0][1] and z == \
                            schachtpunkt_zu_rlt[0][0][2]:
                        wert = int(a)
                Schacht[startpunkt][zielpunkt]["weight"] += wert

        # Zum Dict hinzufügen
        dict_steinerbaum_mit_luftmengen["Schacht"] = deepcopy(Schacht)

        # Visualisierung Schacht
        if export_graphen == True:
            self.plot_schacht(Schacht, name="Schacht mit Luftvolumina")

        # Graph mit Leitungsgeometrie erstellen
        Schacht_leitungsgeometrie = deepcopy(Schacht)

        # Kanalquerschnitt Schacht und RLT zu Schacht bestimmen
        for u, v in Schacht.edges():
            Schacht_leitungsgeometrie[u][v]["weight"] = self.abmessungen_kanal("eckig",
                                                                               self.notwendiger_kanaldquerschnitt(
                                                                                   Schacht_leitungsgeometrie[u][v][
                                                                                       "weight"]),
                                                                               zwischendeckenraum=2000
                                                                               )

        # Zum Dict hinzufügen
        dict_steinerbaum_mit_kanalquerschnitt["Schacht"] = deepcopy(Schacht_leitungsgeometrie)

        # Visualisierung Schacht
        if export_graphen == True:
            self.plot_schacht(Schacht_leitungsgeometrie, name="Schacht mit Querschnitt")

        # Kopie vom Graphen
        Schacht_rechnerischer_durchmesser = deepcopy(Schacht)

        # Hier wird der Leitung die Mantelfläche des Kanals zugeordnet
        for u, v in Schacht.edges():
            Schacht[u][v]["weight"] = round(self.mantelflaeche_kanal("eckig",
                                                                     self.notwendiger_kanaldquerschnitt(
                                                                         Schacht[u][v]["weight"]),
                                                                     zwischendeckenraum=2000
                                                                     )
                                            * self.euklidische_distanz(u, v),
                                            2
                                            )

        # Zum Dict hinzufügen
        dict_steinerbaum_mit_mantelflaeche["Schacht"] = deepcopy(Schacht)

        # Visualisierung Schacht
        if export_graphen == True:
            self.plot_schacht(Schacht, name="Schacht mit Mantelfläche")

        # Hier wird der Leitung der äquivalente Durchmesser des Kanals zugeordnet
        for u, v in Schacht_rechnerischer_durchmesser.edges():
            Schacht_rechnerischer_durchmesser[u][v]["weight"] = self.rechnerischer_durchmesser("eckig",
                                                                                               self.notwendiger_kanaldquerschnitt(
                                                                                                   Schacht_rechnerischer_durchmesser[
                                                                                                       u][v]["weight"]),
                                                                                               zwischendeckenraum=2000
                                                                                               )

        # Zum Dict hinzufügen
        dict_steinerbaum_mit_rechnerischem_querschnitt["Schacht"] = deepcopy(Schacht_rechnerischer_durchmesser)

        # Visualisierung Schacht
        if export_graphen == True:
            self.plot_schacht(Schacht_rechnerischer_durchmesser, name="Schacht mit rechnerischem Durchmesser")

        return (dict_steinerbaum_mit_leitungslaenge,
                dict_steinerbaum_mit_kanalquerschnitt,
                dict_steinerbaum_mit_luftmengen,
                dict_steinerbaum_mit_mantelflaeche,
                dict_steinerbaum_mit_rechnerischem_querschnitt)

    def drei_dimensionaler_graph(self,
                                 dict_steinerbaum_mit_leitungslaenge,
                                 dict_steinerbaum_mit_kanalquerschnitt,
                                 dict_steinerbaum_mit_luftmengen,
                                 dict_steinerbaum_mit_mantelflaeche,
                                 dict_steinerbaum_mit_rechnerischem_querschnitt):

        # Hier werden leere Graphen erstellt. Diese werden im weiteren Verlauf mit den Graphen der einzelnen Ebenen
        # angereichert
        graph_leitungslaenge = nx.Graph()
        graph_luftmengen = nx.Graph()
        graph_kanalquerschnitt = nx.Graph()
        graph_mantelflaeche = nx.Graph()
        graph_rechnerischer_durchmesser = nx.Graph()

        # für Leitungslänge
        for baum in dict_steinerbaum_mit_leitungslaenge.values():
            graph_leitungslaenge = nx.compose(graph_leitungslaenge, baum)

        # für Luftmengen
        for baum in dict_steinerbaum_mit_luftmengen.values():
            graph_luftmengen = nx.compose(graph_luftmengen, baum)

        # für Kanalquerschnitt
        for baum in dict_steinerbaum_mit_kanalquerschnitt.values():
            graph_kanalquerschnitt = nx.compose(graph_kanalquerschnitt, baum)

        # für Mantelfläche
        for baum in dict_steinerbaum_mit_mantelflaeche.values():
            graph_mantelflaeche = nx.compose(graph_mantelflaeche, baum)

        for baum in dict_steinerbaum_mit_rechnerischem_querschnitt.values():
            graph_rechnerischer_durchmesser = nx.compose(graph_rechnerischer_durchmesser, baum)

        # Darstellung des 3D-Graphens:
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')

        # Knotenpositionen in 3D
        pos = {coord: (coord[0], coord[1], coord[2]) for coord in list(graph_luftmengen.nodes())}

        # Knoten zeichnen
        for node, weight in nx.get_node_attributes(graph_luftmengen, 'weight').items():
            if weight > 0:  # Überprüfen, ob das Gewicht größer als 0 ist
                color = 'blue'
            else:
                color = 'red'  # Andernfalls rot (oder eine andere Farbe für Gewicht = 0)

            # Zeichnen des Knotens mit der bestimmten Farbe
            ax.scatter(*node, color=color)

        # Kanten zeichnen
        for edge in graph_luftmengen.edges():
            start, end = edge
            x_start, y_start, z_start = pos[start]
            x_end, y_end, z_end = pos[end]
            ax.plot([x_start, x_end], [y_start, y_end], [z_start, z_end], "black")

        # Achsenbeschriftungen und Titel
        ax.set_xlabel('X-Achse [m]')
        ax.set_ylabel('Y-Achse [m]')
        ax.set_zlabel('Z-Achse [m]')
        ax.set_title("3D Graph Zuluft")

        # Füge eine Legende hinzu, falls gewünscht
        ax.legend()

        # Diagramm anzeigen
        # plt.show()
        plt.close()

        return (graph_leitungslaenge,
                graph_luftmengen,
                graph_kanalquerschnitt,
                graph_mantelflaeche,
                graph_rechnerischer_durchmesser
                )

    def druckverlust(self,
                     z_coordinate_set,
                     position_rlt,
                     graph_leitungslaenge,
                     graph_luftmengen,
                     graph_kanalquerschnitt,
                     graph_mantelflaeche,
                     graph_rechnerischer_durchmesser):

        position_rlt = (position_rlt[0], position_rlt[1], position_rlt[2])
        #
        # # Findet alle Blätter im Netz
        # leaves = self.find_leaves(graph_leitungslaenge)
        #
        # # Leere Liste für Pfade von RLT zu Auslässen am Ende
        # rlt_zu_auslass = list()
        #
        # # Alle Pfade finden
        # for leaf in leaves:
        #     for path in nx.all_simple_edge_paths(graph_leitungslaenge, position_rlt, leaf):
        #         rlt_zu_auslass.append(path)

        # Druckverlustberechnung
        # Netz erstellen:
        # create an empty network
        # Erstellen des pandapipes Netzwerks
        net = pp.create_empty_network(fluid="air")

        # Auslesen des Fluides
        fluid = pp.get_fluid(net)

        # Auslesen der Dichte
        dichte = fluid.get_density(temperature=293.15)

        # Definition der Parameter für die Junctions
        name_junction = [koordinate for koordinate in list(graph_leitungslaenge.nodes())]
        index_junction = [index for index, wert in enumerate(name_junction)]
        # pn_bar = [0 for koordinate in list(graph_leitungslaenge.nodes())]  # Druck
        # tfluid_k = [293.15 for koordinate in list(graph_leitungslaenge.nodes())]  # Temperatur
        # Erstellen einer Liste für jede Koordinatenachse
        x_koordinaten = [koordinate[0] for koordinate in list(graph_leitungslaenge.nodes())]
        y_koordinaten = [koordinate[1] for koordinate in list(graph_leitungslaenge.nodes())]
        z_koordinaten = [koordinate[2] for koordinate in list(graph_leitungslaenge.nodes())]

        # Erstelle mehrerer Junctions
        for junction in range(len(index_junction)):
            pp.create_junction(net,
                               name=str(name_junction[junction]),
                               index=index_junction[junction],
                               pn_bar=0,
                               tfluid_k=293.15,
                               x=x_koordinaten[junction],
                               y=y_koordinaten[junction],
                               height_m=z_koordinaten[junction]
                               )

        # Print Kreuzungspunkte
        # print(net.junction)

        # Definition der Parameter für die Pipes
        name_pipe = [pipe for pipe in list(graph_leitungslaenge.edges())]  # Bezeichung ist die Start- und Endkoordinate
        length_pipe = [graph_leitungslaenge.get_edge_data(pipe[0], pipe[1])["weight"] for pipe in
                       name_pipe]  # Die Länge wird aus
        # dem Graphen mit Leitungslängen ausgelesen

        from_junction = [pipe[0] for pipe in name_pipe]  # Start Junction des Rohres
        to_junction = [pipe[1] for pipe in name_pipe]  # Ziel Junction des Rohres
        diamenter_pipe = [graph_rechnerischer_durchmesser.get_edge_data(pipe[0], pipe[1])["weight"] for pipe in
                          name_pipe]

        # Hinzufügen der Rohre zum Netz
        for pipe in range(len(name_pipe)):
            pp.create_pipe_from_parameters(net,
                                           from_junction=int(name_junction.index(from_junction[pipe])),
                                           to_junction=int(name_junction.index(to_junction[pipe])),
                                           nr_junctions=pipe,
                                           length_km=length_pipe[pipe]/1000,
                                           diameter_m=diamenter_pipe[pipe]/1000,
                                           k_mm=0.15,
                                           name=str(name_pipe[pipe])
                                           )

        # Print Rohre
        print(net.pipe)

         # Index der RLT-Anlage finden
        index_rlt = name_junction.index(tuple(position_rlt))
        luftmengen = nx.get_node_attributes(graph_luftmengen, 'weight')
        luftmenge_rlt = luftmengen[position_rlt]
        mdot_kg_per_s_rlt = luftmenge_rlt * dichte * 1/3600

        # Externes Grid erstellen, da dann die Visualisierung besser ist
        pp.create_ext_grid(net, junction=index_rlt, p_bar=0, t_k=293.15, name="RLT-Anlage")

        # Hinzufügen der RLT-Anlage zum Netz
        pp.create_source(net,
                         mdot_kg_per_s=mdot_kg_per_s_rlt,
                         junction=index_rlt,
                         p_bar=0,
                         t_k=293.15,
                         name="RLT-Anlage")

        # Hinzu
        for index, element in enumerate(luftmengen):
            if index == index_rlt:
                continue  # Überspringt den aktuellen Durchlauf
            print(element)

        # plot network
        plot.simple_plot(net, plot_sinks=True, plot_sources=True, sink_size=4.0, source_size=4.0,)
