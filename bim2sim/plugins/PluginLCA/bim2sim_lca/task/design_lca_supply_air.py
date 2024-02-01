import bim2sim
import matplotlib.pyplot as plt
import networkx as nx
from itertools import chain
import math
import pandas as pd
import pandapipes as pp
import numpy as np
import requests
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

        export = False
        starting_point = [41, 2.8, -2]
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
        center, airflow_volume_per_storey, dict_koordinate_mit_raumart, datenbank_raeume = self.center(thermal_zones,
                                                                                                       starting_point)
        self.logger.info("Finished calculating points of the ventilation outlet at the ceiling")

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

        self.logger.info("Visualising points on the ceiling for the ventilation outlet:")
        self.visualisierung(center,
                            intersection_points
                            )

        self.logger.info("Visualising intersectionpoints")
        self.visualisierung_punkte_nach_ebene(center,
                                              intersection_points,
                                              z_coordinate_set,
                                              export)

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
                                                                                export
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
                                                                            export
                                                                            )
        self.logger.info("Schacht und RLT verbunden")

        self.logger.info("3D-Graph erstellen")
        (graph_leitungslaenge,
         graph_luftmengen,
         graph_kanalquerschnitt,
         graph_mantelflaeche,
         graph_rechnerischer_durchmesser,
         datenbank_verteilernetz) = self.drei_dimensionaler_graph(dict_steinerbaum_mit_leitungslaenge,
                                                                  dict_steinerbaum_mit_kanalquerschnitt,
                                                                  dict_steinerbaum_mit_luftmengen,
                                                                  dict_steinerbaum_mit_mantelflaeche,
                                                                  dict_steinerbaum_mit_rechnerischem_querschnitt,
                                                                  position_rlt,
                                                                  export,
                                                                  dict_koordinate_mit_raumart)
        self.logger.info("3D-Graph erstellt")

        self.logger.info("Starte Druckverlustberechnung")
        druckverlust, datenbank_verteilernetz = self.druckverlust(dict_steinerbaum_mit_leitungslaenge,
                                                                  z_coordinate_set,
                                                                  position_rlt,
                                                                  starting_point,
                                                                  graph_leitungslaenge,
                                                                  graph_luftmengen,
                                                                  graph_kanalquerschnitt,
                                                                  graph_mantelflaeche,
                                                                  graph_rechnerischer_durchmesser,
                                                                  export,
                                                                  datenbank_verteilernetz
                                                                  )
        self.logger.info("Druckverlustberechnung erfolgreich")

        self.logger.info("Starte Berechnun der Raumanbindung")
        self.raumanbindung(querschnittsart, zwischendeckenraum, datenbank_raeume)

        self.logger.info("Starte C02 Berechnung")
        self.co2(druckverlust,
                 datenbank_raeume,
                 datenbank_verteilernetz)

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
            # print(tz.air_flow)
            room_ceiling_ventilation_outlet.append([self.runde_decimal(tz.space_center.X(), 1),
                                                    self.runde_decimal(tz.space_center.Y(), 1),
                                                    self.runde_decimal(tz.space_center.Z() + tz.height.magnitude / 2,
                                                                       2),
                                                    self.runde_decimal(
                                                        tz.air_flow.to(ureg.meter ** 3 / ureg.hour).magnitude, 0)])
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

        dict_koordinate_mit_raumart = dict()
        for index, koordinate in enumerate(room_ceiling_ventilation_outlet):
            koordinate = (koordinate[0], koordinate[1], koordinate[2])
            dict_koordinate_mit_raumart[koordinate] = room_type[index]

        dict_koordinate_mit_erf_luftvolumen = dict()
        for index, koordinate in enumerate(room_ceiling_ventilation_outlet):
            punkt = (koordinate[0], koordinate[1], koordinate[2])
            dict_koordinate_mit_erf_luftvolumen[punkt] = koordinate[3]

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

        datenbank_raeume = pd.DataFrame()
        datenbank_raeume["Koordinate"] = list(dict_koordinate_mit_raumart.keys())
        datenbank_raeume["Raumart"] = datenbank_raeume["Koordinate"].map(dict_koordinate_mit_raumart)
        datenbank_raeume["Volumenstrom"] = datenbank_raeume["Koordinate"].map(dict_koordinate_mit_erf_luftvolumen)

        for z_coord in z_axis:
            room_ceiling_ventilation_outlet.append((starting_point[0], starting_point[1], z_coord,
                                                    airflow_volume_per_storey[z_coord]))

        return room_ceiling_ventilation_outlet, airflow_volume_per_storey, dict_koordinate_mit_raumart, datenbank_raeume

    def calculate_z_coordinate(self, center):
        z_coordinate_set = set()
        for i in range(len(center)):
            z_coordinate_set.add(center[i][2])
        return z_coordinate_set

    def intersection_points(self, ceiling_point, z_coordinate_set):
        # Liste der Schnittpunkte
        intersection_points_list = []

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

    def visualisierung(self, room_ceiling_ventilation_outlet, intersection):
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
        # plt.show()
        plt.close()

    def visualisierung_punkte_nach_ebene(self, center, intersection, z_coordinate_set, export):
        """The function visualizes the points in a diagram
        Args:
            center: Mittelpunkt es Raumes an der Decke
            intersection: intersection points at the ceiling
            z_coordinate_set: Z-Koordinaten für jedes Geschoss an der Decke
            export: True or False
        Returns:
           2D diagramm for each ceiling
       """
        if export:
            for z_value in z_coordinate_set:
                x_values = [x for x, y, z, a in intersection if z == z_value]
                y_values = [y for x, y, z, a in intersection if z == z_value]
                x_values_center = [x for x, y, z, a in center if z == z_value]
                y_values_center = [y for x, y, z, a in center if z == z_value]

                plt.figure(num=f"Grundriss: {z_value}", figsize=(25, 10), dpi=300)
                plt.scatter(x_values, y_values, color="r", marker='x', label="Schnittpunkte")
                plt.scatter(x_values_center, y_values_center, color="b", marker='D', label="Lüftungsauslässe")
                plt.title(f'Höhe: {z_value}')
                plt.subplots_adjust(right=0.7)
                plt.legend(loc="center left", bbox_to_anchor=(1, 0.5))
                plt.xlabel('X-Achse [m]')
                plt.ylabel('Y-Achse [m]')

                # Setze den Pfad für den neuen Ordner
                ordner_pfad = Path(self.paths.export / "Grundrisse")

                # Erstelle den Ordner
                ordner_pfad.mkdir(parents=True, exist_ok=True)

                # Speichern des Graphens
                gesamte_bezeichnung = "Grundriss Z " + f"{z_value}" + ".png"
                pfad_plus_name = self.paths.export / "Grundrisse" / gesamte_bezeichnung
                plt.savefig(pfad_plus_name)

                plt.close()

                # plt.show()

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
        plt.figure(figsize=(25, 10), dpi=300)
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
                               node_size=250)
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
        legend_ceiling = plt.Line2D([0], [0], marker='D', color='w', label='Deckenauslass [m³ pro h]',
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

        lueftungsleitung_rund_durchmesser = {#0.00312: 60, nicht lieferbar
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

        lueftungsleitung_rund_durchmesser = {# 0.00312: 60, nicht lieferbar
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

                if export_graphen == True:
                    self.visualisierung_graph(steiner_baum,
                                              steiner_baum,
                                              z_value,
                                              coordinates_without_airflow,
                                              filtered_coords_ceiling_without_airflow,
                                              filtered_coords_intersection_without_airflow,
                                              name=f"Steinerbaum mit Luftmenge [m³ pro h]",
                                              einheit_kante="",
                                              mantelflaeche_gesamt=False
                                              )

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
                    H_aequivalenter_durchmesser[u][v]["weight"] = round(self.rechnerischer_durchmesser(querschnittsart,
                                                                                                       self.notwendiger_kanaldquerschnitt(
                                                                                                           H_aequivalenter_durchmesser[
                                                                                                               u][v][
                                                                                                               "weight"]),
                                                                                                       zwischendeckenraum),
                                                                        2)

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
                                                                                  zwischendeckenraum), 2
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
                                              einheit_kante="[m²/m]",
                                              mantelflaeche_gesamt=False
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
                                                                     ),
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

    def finde_abmessung(self, text: str):
        if "Ø" in text:
            # Fall 1: "Ø" gefolgt von einer Zahl
            zahl = text.split("Ø")[1]  # Teilt den String am "Ø" und nimmt den zweiten Teil
            return float(zahl) / 1000
        else:
            # Fall 2: "250 x 200" Format
            zahlen = text.split(" x ")  # Teilt den String bei " x "
            breite = float(zahlen[0]) / 1000
            hoehe = float(zahlen[1]) / 1000
            return breite, hoehe

    def drei_dimensionaler_graph(self,
                                 dict_steinerbaum_mit_leitungslaenge,
                                 dict_steinerbaum_mit_kanalquerschnitt,
                                 dict_steinerbaum_mit_luftmengen,
                                 dict_steinerbaum_mit_mantelflaeche,
                                 dict_steinerbaum_mit_rechnerischem_querschnitt,
                                 position_rlt,
                                 export,
                                 dict_koordinate_mit_raumart):

        # Eine Hilfsfunktion, um den Graphen rekursiv zu durchlaufen, die Kanten zu richten und die Gewichte zu übernehmen
        def add_edges_and_nodes(G, current_node, H, parent=None):
            # Kopieren Sie die Knotenattribute von H zu G
            G.add_node(current_node, **H.nodes[current_node])
            for neighbor in H.neighbors(current_node):
                if neighbor != parent:
                    # Das Gewicht und ggf. weitere Attribute für die Kante abrufen
                    edge_data = H.get_edge_data(current_node, neighbor)
                    # Fügen Sie eine gerichtete Kante mit den kopierten Attributen hinzu
                    G.add_edge(current_node, neighbor, **edge_data)
                    # Rekursiver Aufruf für den Nachbarn
                    add_edges_and_nodes(G, neighbor, H, current_node)

        datenbank_verteilernetz = pd.DataFrame(columns=['Startknoten', 'Zielknoten', 'Leitungslänge'])

        # Hier werden leere Graphen erstellt. Diese werden im weiteren Verlauf mit den Graphen der einzelnen Ebenen
        # angereichert
        graph_leitungslaenge = nx.Graph()
        graph_luftmengen = nx.Graph()
        graph_kanalquerschnitt = nx.Graph()
        graph_mantelflaeche = nx.Graph()
        graph_rechnerischer_durchmesser = nx.Graph()

        position_rlt = (position_rlt[0], position_rlt[1], position_rlt[2])

        # für Leitungslänge
        for baum in dict_steinerbaum_mit_leitungslaenge.values():
            graph_leitungslaenge = nx.compose(graph_leitungslaenge, baum)

        # Graph für Leitungslänge in einen gerichteten Graphen umwandeln
        graph_leitungslaenge_gerichtet = nx.DiGraph()
        add_edges_and_nodes(graph_leitungslaenge_gerichtet, position_rlt, graph_leitungslaenge)

        # Leitungslängen der Datenbank hinzufügen
        for u, v in graph_leitungslaenge_gerichtet.edges():
            data = graph_leitungslaenge_gerichtet.get_edge_data(u, v)["weight"]
            neue_daten = pd.DataFrame(
                {'Kante': [(u, v)],
                 'Startknoten': [u],
                 'Zielknoten': [v],
                 'Raumart Startknoten': dict_koordinate_mit_raumart.get(u, None),
                 'Raumart Zielknoten': dict_koordinate_mit_raumart.get(v, None),
                 'Leitungslänge': [data]})

            datenbank_verteilernetz = pd.concat([datenbank_verteilernetz, neue_daten], ignore_index=True)

        # für Luftmengen
        for baum in dict_steinerbaum_mit_luftmengen.values():
            graph_luftmengen = nx.compose(graph_luftmengen, baum)

        # Graph für Luftmengen in einen gerichteten Graphen umwandeln
        graph_luftmengen_gerichtet = nx.DiGraph()
        add_edges_and_nodes(graph_luftmengen_gerichtet, position_rlt, graph_luftmengen)

        # Luftmengen der Datenbank hinzufügen
        luftmengen = list()
        for u, v in graph_luftmengen_gerichtet.edges():
            luftmengen.append(graph_luftmengen_gerichtet.get_edge_data(u, v)["weight"])
        datenbank_verteilernetz["Luftmenge"] = luftmengen

        # für Kanalquerschnitt
        for baum in dict_steinerbaum_mit_kanalquerschnitt.values():
            graph_kanalquerschnitt = nx.compose(graph_kanalquerschnitt, baum)

        # Graph für Kanalquerschnitt in einen gerichteten Graphen umwandeln
        graph_kanalquerschnitt_gerichtet = nx.DiGraph()
        add_edges_and_nodes(graph_kanalquerschnitt_gerichtet, position_rlt, graph_kanalquerschnitt)

        # Kanalquerschnitt der Datenbank hinzufügen
        kanalquerschnitt = list()
        for u, v in graph_kanalquerschnitt_gerichtet.edges():
            kanalquerschnitt.append(graph_kanalquerschnitt_gerichtet.get_edge_data(u, v)["weight"])

            if "Ø" in graph_kanalquerschnitt_gerichtet.get_edge_data(u, v)["weight"]:
                datenbank_verteilernetz.loc[datenbank_verteilernetz[
                                                'Zielknoten'] == v, 'Durchmesser'] = self.finde_abmessung(
                    graph_kanalquerschnitt_gerichtet.get_edge_data(u, v)["weight"])

            elif "x" in graph_kanalquerschnitt_gerichtet.get_edge_data(u, v)["weight"]:
                datenbank_verteilernetz.loc[datenbank_verteilernetz[
                                                'Zielknoten'] == v, 'Breite'] = \
                    self.finde_abmessung(graph_kanalquerschnitt_gerichtet.get_edge_data(u, v)["weight"])[0]
                datenbank_verteilernetz.loc[datenbank_verteilernetz[
                                                'Zielknoten'] == v, 'Höhe'] = \
                    self.finde_abmessung(graph_kanalquerschnitt_gerichtet.get_edge_data(u, v)["weight"])[1]

        datenbank_verteilernetz["Kanalquerschnitt"] = kanalquerschnitt

        # für Mantelfläche
        for baum in dict_steinerbaum_mit_mantelflaeche.values():
            graph_mantelflaeche = nx.compose(graph_mantelflaeche, baum)

        # Graph für Mantelfläche in einen gerichteten Graphen umwandeln
        graph_mantelflaeche_gerichtet = nx.DiGraph()
        add_edges_and_nodes(graph_mantelflaeche_gerichtet, position_rlt, graph_mantelflaeche)

        # Mantelfläche der Datenbank hinzufügen
        mantelflaeche = list()
        for u, v in graph_mantelflaeche_gerichtet.edges():
            mantelflaeche.append(graph_mantelflaeche_gerichtet.get_edge_data(u, v)["weight"])
        datenbank_verteilernetz["Mantelfläche"] = datenbank_verteilernetz["Leitungslänge"] * mantelflaeche

        # für rechnerischen Querschnitt
        for baum in dict_steinerbaum_mit_rechnerischem_querschnitt.values():
            graph_rechnerischer_durchmesser = nx.compose(graph_rechnerischer_durchmesser, baum)

        # Graph für rechnerischen Querschnitt in einen gerichteten Graphen umwandeln
        graph_rechnerischer_durchmesser_gerichtet = nx.DiGraph()
        add_edges_and_nodes(graph_rechnerischer_durchmesser_gerichtet, position_rlt, graph_rechnerischer_durchmesser)

        # rechnerischen Querschnitt der Datenbank hinzufügen
        rechnerischer_querschnitt = list()
        for u, v in graph_rechnerischer_durchmesser_gerichtet.edges():
            rechnerischer_querschnitt.append(graph_rechnerischer_durchmesser_gerichtet.get_edge_data(u, v)["weight"])
        datenbank_verteilernetz["rechnerischer Durchmesser"] = rechnerischer_querschnitt

        if export == True:
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
            plt.close()

        return (graph_leitungslaenge_gerichtet,
                graph_luftmengen_gerichtet,
                graph_kanalquerschnitt_gerichtet,
                graph_mantelflaeche_gerichtet,
                graph_rechnerischer_durchmesser_gerichtet,
                datenbank_verteilernetz
                )

    def druckverlust(self,
                     dict_steinerbaum_mit_leitungslaenge,
                     z_coordinate_set,
                     position_rlt,
                     position_schacht,
                     graph_leitungslaenge,
                     graph_luftmengen,
                     graph_kanalquerschnitt,
                     graph_mantelflaeche,
                     graph_rechnerischer_durchmesser,
                     export,
                     datenbank_verteilernetz):
        # Standardwerte für Berechnung
        rho = 1.204  # Dichte der Luft bei Standardbedingungen
        nu = 1.33 * 0.00001  # Dynamische Viskosität der Luft

        def darstellung_t_stueck(eingang, rohr, ausgang):
            """
            Erstelle eine 3D-Graphen des T-Stücks
            :param eingang: Lufteinleitung in T-Stück
            :param rohr: Rohr für Verluste
            :param ausgang: Abknickende Rohr
            :return: Grafik
            """
            # Erstellen eines 3D-Plots
            fig = plt.figure()
            ax = fig.add_subplot(111, projection='3d')

            # Funktion zum Zeichnen eines Pfeils
            def zeichne_pfeil(start, ende, farbe, stil='solid'):
                ax.quiver(start[0], start[1], start[2], ende[0] - start[0], ende[1] - start[1], ende[2] - start[2],
                          color=farbe, linestyle=stil, arrow_length_ratio=0.1)

            # Zeichnen der Linien mit Pfeilen
            zeichne_pfeil(eingang[0], eingang[1], 'red')  # Eingang in Rot
            zeichne_pfeil(rohr[0], rohr[1], 'red')  # Rohr in Rot
            zeichne_pfeil(abknickende_leitung[0], abknickende_leitung[1], 'blue',
                          'dashed')  # Abknickende Leitung gestrichelt in Blau

            # Setzen der Achsenbeschriftungen
            ax.set_xlabel('X Achse')
            ax.set_ylabel('Y Achse')
            ax.set_zlabel('Z Achse')

            # Titel des Plots
            ax.set_title('3D Darstellung der Leitungen')

            # Anpassen der Achsengrenzen basierend auf den Koordinaten
            alle_koordinaten = rohr + abknickende_leitung + eingang
            x_min, x_max = min(k[0] for k in alle_koordinaten), max(k[0] for k in alle_koordinaten)
            y_min, y_max = min(k[1] for k in alle_koordinaten), max(k[1] for k in alle_koordinaten)
            z_min, z_max = min(k[2] for k in alle_koordinaten), max(k[2] for k in alle_koordinaten)

            ax.set_xlim([x_min - 1, x_max + 1])
            ax.set_ylim([y_min - 1, y_max + 1])
            ax.set_zlim([z_min - 1, z_max + 1])

            # Anzeigen des Plots
            # plt.show()

        def check_if_lines_are_aligned(line1, line2):
            """
            Überprüft ob zwei Geraden im Raum paralell sind
            :param line1: Linie 1 (x,y,z)
            :param line2: Linie 2 (x,y,z)
            :return: True or False
            """
            # Berechnung der Richtungsvektoren für beide Geraden
            vector1 = np.array([line1[1][0] - line1[0][0], line1[1][1] - line1[0][1], line1[1][2] - line1[0][2]])
            vector2 = np.array([line2[1][0] - line2[0][0], line2[1][1] - line2[0][1], line2[1][2] - line2[0][2]])

            # Überprüfen, ob die Vektoren Vielfache voneinander sind
            # Dies erfolgt durch Kreuzprodukt, das null sein sollte, wenn sie ausgerichtet sind
            cross_product = np.cross(vector1, vector2)

            return np.all(cross_product == 0)

        def widerstandsbeiwert_bogen_rund(winkel: int, mittlerer_radius: float, durchmesser: float) -> float:
            """
            Berechnet den Widerstandsbeiwert fpr einen Bogen rund A01 nach VDI 3803 Blatt 6
            :param winkel: Winkel in Grad
            :param mittlerer_radius: Mittlerer Radius des Bogens in Metern
            :param durchmesser: Durchmesser der Leitung in Metern
            :return: Widerstandsbeiwert Bogen rund A01 nach VDI 3803 Blatt 6
            """

            a = 1.6094 - 1.60868 * math.exp(-0.01089 * winkel)

            b = None
            if 0.5 <= mittlerer_radius / durchmesser <= 1.0:
                b = 0.21 / ((mittlerer_radius / durchmesser) ** 2.5)
            elif 1 <= mittlerer_radius / durchmesser:
                b = (0.21 / (math.sqrt(mittlerer_radius / durchmesser)))

            c = 1

            return a * b * c

        def widerstandsbeiwert_bogen_eckig(winkel, mittlerer_radius, hoehe, breite, rechnerischer_durchmesser):
            """
            Berechnet den Widerstandsbeiwert für einen Bogen eckig A02 nach VDI 3803 Blatt 6
            :param winkel: Winkel in Grad
            :param mittlerer_radius: mittlerer Radius des Bogens in Metern
            :param hoehe: Hoehe der Leitung in Metern
            :param breite: Breite der Leiutung in Metern
            :param rechnerischer_durchmesser: Rechnerischer Durchmesser der Leitung
            :return: Widerstandsbeiwert Bogen eckig
            """

            a = 1.6094 - 1.60868 * math.exp(-0.01089 * winkel)

            b = None
            if 0.5 <= mittlerer_radius / rechnerischer_durchmesser <= 1.0:
                b = 0.21 / ((mittlerer_radius / rechnerischer_durchmesser) ** 2.5)
            elif 1 <= mittlerer_radius / rechnerischer_durchmesser:
                b = (0.21 / (math.sqrt(mittlerer_radius / rechnerischer_durchmesser)))

            c = (- 1.03663 * 10 ** (-4) * (hoehe / breite) ** 5 + 0.00338 * (hoehe / breite) ** 4 - 0.04277 * (
                    hoehe / breite)
                 ** 3 + 0.25496 * (hoehe / breite) ** 2 - 0.66296 * (hoehe / breite) + 1.4499)

            return a * b * c

        def widerstandsbeiwert_querschnittserweiterung(d_1, d_2):
            """
            Berechnet den Widerstandsbeiwert bei einer Querschnittserweiterung A14 nach VDI 3803 Blatt 6
            :param d_1: Durchmesser Lufteingang in Metern
            :param d_2: Durchmesser Luftausgang in Metern
            :return: Widerstandsbeiwert für Querschnittserweiterung
            """

            if d_1 >= d_2:
                self.logger.error("Durchmesser 1 darf nicht größer als Durchmesser 2 sein!")

            else:
                l = 0.5  # Als Standardlänge werden 0,5 Meter festgelegt

                # Winkel
                beta = math.degrees(math.atan((d_2 - d_1) / (2 * l)))

                # Beiwert:
                eta_D = 1.01 / (1 + 10 ** (-0.05333 * (24.15 - beta)))

                # Querschnitt 1:
                A_1 = math.pi * d_1 ** 2 / 4

                # Querschnitt 2:
                A_2 = math.pi * d_2 ** 2 / 4

                zeta_1 = (1 - A_1 / A_2) ** 2 * (1 - eta_D)

                return zeta_1

        def widerstandsbeiwert_querschnittsverengung_stetig(d_1, d_2):
            """
            Berechnet den Widerstandsbeiwert bei einer Querschnittsverengung A15 nach VDI 3803 Blatt 6
            :param d_1: Durchmesser Lufteingang in Metern
            :param d_2: Durchmesser Luftausgang in Metern
            :return: Widerstandsbeiwert für Querschnittsverengung
            """

            if d_1 <= d_2:
                self.logger.error("Durchmesser 2 darf nicht größer als Durchmesser 1 sein!")

            else:
                l = 0.3  # Als Standardlänge werden 0,5 Meter festgelegt

                # Winkel
                beta = math.degrees(math.atan((d_1 - d_2) / (2 * l)))

                # Beiwert:
                k_1 = - 0.0125 + 0.00135 * beta

                # Querschnitt 1:
                A_1 = math.pi * d_1 ** 2 / 4

                # Querschnitt 2:
                A_2 = math.pi * d_2 ** 2 / 4

                zeta_1 = - (k_1) * (A_2 / A_1) ** 2 + k_1

                if zeta_1 < 0:
                    zeta_1 = 0

                return zeta_1

        def widerstandsbeiwert_T_stueck_trennung_rund(d: float, v: float, d_D: float, v_D: float, d_A: float,
                                                      v_A: float,
                                                      richtung: str) -> float:
            """
            Berechnet den Widerstandbeiwert für eine T-Trennung A22 nach VDI 3803 Blatt 6
            :param d: Durchmesser des Eingang in Metern
            :param v: Volumenstrom des Eingangs in m³/h
            :param d_D: Durchmesser des Durchgangs in Metern
            :param v_D: Volumenstrom des Durchgangs in m³/h
            :param d_A: Durchmesser des Abgangs in Metern
            :param v_A: Volumenstrom des Abgangs in m³/h
            :param richtung: "Durchgangsrichtung" oder "abzweigende Richtung"
            :return: Widerstandbeiwert für eine T-Trennung A22
            """

            # Querschnitt Eingang:
            A = math.pi * d ** 2 / 4
            # Strömungsgeschwindigkeit Eingang
            w = v / A * 1 / 3600

            # Querschnitt Durchgang:
            A_D = math.pi * d_D ** 2 / 4
            # Strömunggeschwindkigkeit Durchgang
            w_D = v_D / A_D * 1 / 3600

            # Querschnitt Abzweigung:
            A_A = math.pi * d_A ** 2 / 4
            # Strömungsgeschwindigkeit Abzweig
            w_A = v_A / A_A * 1 / 3600

            # Beiwert
            K_D = 0.4

            if richtung == "Durchgangsrichtung":
                zeta_D = (K_D * (1 - w_D / w) ** 2) / (w_D / w) ** 2
                return zeta_D
            elif richtung == "abzweigende Richtung":
                # Es wird Form "a" nach VDI 3803 Blatt 6 gewählt
                zeta_A = 0.26 + 55.29 * math.exp(-(w_A / w) / 0.1286) + 555.26 * math.exp(
                    -(w_A / w) / 0.041) + 5.73 * math.exp(-(w_A / w) / 0.431)
                return zeta_A
            else:
                self.logger.error("Keine oder falsche Richtungseingabe")

        def widerstandsbeiwert_T_stueck_trennung_eckig(d: float, v: float, d_D: float, v_D: float, d_A: float,
                                                       v_A: float, richtung: str) -> float:
            """
            Berechnet den Widerstandbeiwert für eine T-Trennung A24 nach VDI 3803 Blatt 6
            :param d: rechnerischer Durchmesser des Eingang in Metern
            :param v: Volumenstrom des Eingangs in m³/h
            :param d_D: rechnerischer Durchmesser des Durchgangs in Metern
            :param v_D: Volumenstrom des Durchgangs in m³/h
            :param d_A: rechnerischer Durchmesser des Abgangs in Metern
            :param v_A: Volumenstrom des Abgangs in m³/h
            :param richtung: "Durchgangsrichtung" oder "abzweigende Richtung"
            :return: Widerstandbeiwert für eine T-Trennung A24
            """

            # Querschnitt Eingang:
            A = math.pi * d ** 2 / 4
            # Strömungsgeschwindigkeit Eingang
            w = v / A * 1 / 3600

            # Querschnitt Durchgang:
            A_D = math.pi * d_D ** 2 / 4
            # Strömunggeschwindkigkeit Durchgang
            w_D = v_D / A_D * 1 / 3600

            # Querschnitt Abzweigung:
            A_A = math.pi * d_A ** 2 / 4
            # Strömungsgeschwindigkeit Abzweig
            w_A = v_A / A_A * 1 / 3600

            if richtung == "Durchgangsrichtung":
                K_1 = 183.3
                K_2 = 0.06
                K_3 = 0.17

                zeta_D = K_1 / (math.exp(w_D / w * 1 / K_2)) + K_3

                return zeta_D

            elif richtung == "abzweigende Richtung":
                K_1 = 301.95
                K_2 = 0.06
                K_3 = 0.75

                zeta_D = K_1 / (math.exp(w_A / w * 1 / K_2)) + K_3

                return zeta_D
            else:
                self.logger.error("Keine oder falsche Richtungseingabe")

        def widerstandsbeiwert_kruemmerendstueck_eckig(a: float, b: float, d: float, v: float, d_A: float, v_A: float):
            """
            Berechnet den Widerstandsbeiwert für Krümmerabzweig A25 nach VDI 3803
            :param a: Höhe des Eingangs in Metern
            :param b: Breite des Eingangs in Metern
            :param d: rechnerischer Durchmesser des Eingangs in Metern
            :param v: Volumenstrom des Eingangs in m³/h
            :param d_A: rechnerischer Durchmesser des Abzweiges in Metern
            :param v_A: Volumenstrom des Abzweiges in m³/s
            :return: Widerstandsbeiwert für Krümmerabzweig A25 nach VDI 3803
            """

            # Querschnitt Eingang:
            A = math.pi * d ** 2 / 4
            # Strömungsgeschwindigkeit Eingang
            w = v / A * 1 / 3600

            # Querschnitt Abzweigung:
            A_A = math.pi * d_A ** 2 / 4
            # Strömungsgeschwindigkeit Abzweig
            w_A = v_A / A_A * 1 / 3600

            K_1 = 0.0644
            K_2 = 0.0727
            K_3 = 0.3746
            K_4 = -3.4885

            zeta_A = (K_1 * a / b + K_2) * (w_A / w) ** (K_3 * math.log(a / b) + K_4)

            return zeta_A

        def widerstandsbeiwert_T_endstueck_rund(d: float, v: float, d_A: float, v_A: float):
            """
            Berechnet den Widerstandsbeiwert für ein T-Stück rund A27 nach VDI 3803
            :param d: rechnerischer Durchmesser des Eingangs in Metern
            :param v: Volumenstrom des Eingangs in m³/h
            :param d_A: rechnerischer Durchmesser des Abzweiges in Metern
            :param v_A: Volumenstrom des Abzweiges in m³/s
            :return: Widerstandsbeiwert für ein T-Stück rund A27 nach VDI 3803
            """

            # Querschnitt Eingang:
            A = math.pi * d ** 2 / 4
            # Strömungsgeschwindigkeit Eingang
            w = v / A * 1 / 3600

            # Querschnitt Abzweigung:
            A_A = math.pi * d_A ** 2 / 4
            # Strömungsgeschwindigkeit Abzweig
            w_A = v_A / A_A * 1 / 3600

            Y_0 = 0.662
            A_1 = 128.6
            t_1 = 0.0922
            A_2 = 15.13
            t_2 = 0.3138

            zeta_A = Y_0 + A_1 * math.exp(-(w_A / w) * 1 / t_1) + A_2 * math.exp(-(w_A / w) * 1 / t_2)

            return zeta_A

        position_rlt = (position_rlt[0], position_rlt[1], position_rlt[2])

        # Erstellung einer BFS-Reihenfolge ab dem Startpunkt
        bfs_edges = list(nx.edge_bfs(graph_leitungslaenge, position_rlt))

        graph_leitungslaenge_sortiert = nx.Graph()

        # Kanten in der BFS-Reihenfolge zum neuen Graphen hinzufügen
        for edge in bfs_edges:
            graph_leitungslaenge_sortiert.add_edge(*edge)

        # Druckverlustberechnung
        # Netz erstellen:
        net = pp.create_empty_network(fluid="air")

        # Auslesen des Fluides
        fluid = pp.get_fluid(net)

        # Auslesen der Dichte
        dichte = fluid.get_density(temperature=293.15)

        # Definition der Parameter für die Junctions
        name_junction = [koordinate for koordinate in list(graph_leitungslaenge_sortiert.nodes())]
        index_junction = [index for index, wert in enumerate(name_junction)]

        # Erstellen einer Liste für jede Koordinatenachse
        x_koordinaten = [koordinate[0] for koordinate in list(graph_leitungslaenge_sortiert.nodes())]
        y_koordinaten = [koordinate[1] for koordinate in list(graph_leitungslaenge_sortiert.nodes())]
        z_koordinaten = [koordinate[2] for koordinate in list(graph_leitungslaenge_sortiert.nodes())]

        # Da nur 3D Koordinaten vorhanden sind, jedoch 3D Koordinaten gebraucht werden wird ein Dict erszellt, welches
        # jeder 3D Koordinate einen 2D-Koordinate zuweist
        zwei_d_koodrinaten = dict()
        position_schacht_graph = (position_schacht[0], position_schacht[1], position_schacht[2])

        # Leitung von RLT zu Schacht
        pfad_rlt_zu_schacht = list(nx.all_simple_paths(graph_leitungslaenge, position_rlt, position_schacht_graph))[0]
        anzahl_punkte_pfad_rlt_zu_schacht = -len(pfad_rlt_zu_schacht)

        for punkt in pfad_rlt_zu_schacht:
            zwei_d_koodrinaten[punkt] = (anzahl_punkte_pfad_rlt_zu_schacht, 0)
            anzahl_punkte_pfad_rlt_zu_schacht += 1

        anzahl_knoten_mit_mindestens_drei_kanten = len(
            [node for node, degree in graph_leitungslaenge.degree() if degree >= 3])

        # Versuch, alle Keys in Zahlen umzuwandeln und zu sortieren
        sorted_keys = sorted(
            (key for key in dict_steinerbaum_mit_leitungslaenge.keys() if key != "Schacht"),
            key=lambda x: float(x)
        )

        y = 0  # Start y-Koordinate

        for key in sorted_keys:
            graph_geschoss = dict_steinerbaum_mit_leitungslaenge[key]

            schacht_knoten = [node for node in graph_geschoss.nodes()
                              if node[0] == position_schacht[0] and node[1] == position_rlt[1]][0]

            # Blattknoten identifizieren (Knoten mit Grad 1)
            blatt_knoten = [node for node in graph_geschoss.nodes()
                            if graph_geschoss.degree(node) == 1 and node != schacht_knoten]

            # Pfade vom Startknoten zu jedem Blattknoten berechnen
            pfade = [nx.shortest_path(graph_geschoss, source=schacht_knoten, target=blatt) for blatt in blatt_knoten]

            # Pfade nach ihrer Länge sortieren
            sortierte_pfade = sorted(pfade, key=len, reverse=True)

            x = 0

            for point in sortierte_pfade[0]:
                if point not in zwei_d_koodrinaten:
                    zwei_d_koodrinaten[point] = (x, y)
                x += 2
            x = -2
            y += 2

            pfad_zaehler = 0
            wieder_runter = 0

            for pfad in sortierte_pfade[1:]:
                i = 0
                rest_laenge_pfad = len(pfad)
                zaehler_neue_punkte = 0
                zaehler_punkte_vorhanden = 0
                for point in pfad:
                    if point not in zwei_d_koodrinaten:
                        zaehler_neue_punkte += 1
                        zwei_d_koodrinaten[point] = (x, y)

                        if pfad_zaehler == 0:
                            x += 2

                        if pfad_zaehler >= 1 and rest_laenge_pfad >= 1:
                            if i >= pfad_zaehler:
                                x += 2
                            else:
                                y += 2
                                i += 2

                    elif point in zwei_d_koodrinaten:
                        zaehler_punkte_vorhanden += 1
                        x += 2
                        rest_laenge_pfad -= 1

                y -= i
                x = -2
                pfad_zaehler += 1

            wieder_runter = max(wieder_runter, i) + 4
            y += wieder_runter

        # Erstelle mehrerer Junctions
        for junction in range(len(index_junction)):
            pp.create_junction(net,
                               name=str(name_junction[junction]),
                               index=index_junction[junction],
                               pn_bar=0,
                               tfluid_k=293.15,
                               geodata=zwei_d_koodrinaten[name_junction[junction]],
                               x=x_koordinaten[junction],
                               y=y_koordinaten[junction],
                               height_m=z_koordinaten[junction]
                               )

        # Definition der Parameter für die Pipes
        name_pipe = [pipe for pipe in
                     list(graph_leitungslaenge_sortiert.edges())]  # Bezeichung ist die Start- und Endkoordinate
        length_pipe = [graph_leitungslaenge.get_edge_data(pipe[0], pipe[1])["weight"] for pipe in
                       name_pipe]  # Die Länge wird aus dem Graphen mit Leitungslängen ausgelesen

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
                                           length_km=length_pipe[pipe] / 1000,
                                           diameter_m=diamenter_pipe[pipe] / 1000,
                                           k_mm=0.15,
                                           name=str(name_pipe[pipe]),
                                           loss_coefficient=0
                                           )

        """Ab hier werden die Verlustbeiwerte der Rohre angepasst"""
        for pipe in range(len(name_pipe)):

            # Nachbarn des Startknotens
            neighbors = list(nx.all_neighbors(graph_leitungslaenge, from_junction[pipe]))

            """Bögen:"""
            if len(neighbors) == 2:  # Bögen finden
                eingehende_kante = list(graph_leitungslaenge.in_edges(from_junction[pipe]))[0]
                ausgehende_kante = list(graph_leitungslaenge.out_edges(from_junction[pipe]))[0]
                # Rechnerischer Durchmesser der Leitung
                rechnerischer_durchmesser = \
                    graph_rechnerischer_durchmesser.get_edge_data(from_junction[pipe], to_junction[pipe])[
                        "weight"] / 1000

                # Abmessung des Rohres
                abmessung_kanal = graph_kanalquerschnitt.get_edge_data(from_junction[pipe], to_junction[pipe])[
                    "weight"]

                if not check_if_lines_are_aligned(eingehende_kante, ausgehende_kante):

                    zeta_bogen = None
                    if "Ø" in abmessung_kanal:
                        durchmesser = self.finde_abmessung(abmessung_kanal)
                        zeta_bogen = widerstandsbeiwert_bogen_rund(winkel=90,
                                                                   mittlerer_radius=0.75,
                                                                   durchmesser=durchmesser)
                        # print(f"Zeta-Bogen rund: {zeta_bogen}")

                    elif "x" in abmessung_kanal:
                        breite = self.finde_abmessung(abmessung_kanal)[0]
                        hoehe = self.finde_abmessung(abmessung_kanal)[1]
                        zeta_bogen = widerstandsbeiwert_bogen_eckig(winkel=90,
                                                                    mittlerer_radius=0.75,
                                                                    hoehe=hoehe,
                                                                    breite=breite,
                                                                    rechnerischer_durchmesser=rechnerischer_durchmesser
                                                                    )
                        # print(f"Zeta Bogen eckig: {zeta_bogen}")

                    # Ändern des loss_coefficient-Werts
                    net['pipe'].at[pipe, 'loss_coefficient'] += zeta_bogen

                    datenbank_verteilernetz.loc[datenbank_verteilernetz[
                                                    'Zielknoten'] == to_junction[pipe], 'Zeta Bogen'] = zeta_bogen

            """Reduzierungen"""
            if len(neighbors) == 2:
                rohr = name_pipe[pipe]
                rohr_nachbar = to_junction[pipe]
                abmessung_rohr = graph_kanalquerschnitt.get_edge_data(from_junction[pipe], to_junction[pipe])[
                    "weight"]

                ausgehende_kanten = graph_leitungslaenge.out_edges(from_junction[pipe])

                eingehende_kanten = list(graph_leitungslaenge.in_edges(from_junction[pipe]))[0]
                eingehender_nachbar_knoten = eingehende_kanten[1]
                abmessung_eingehende_kante = \
                    graph_kanalquerschnitt.get_edge_data(eingehende_kanten[0], eingehende_kanten[1])[
                        "weight"]

                """ Daten für Widerstandsbeiwerte"""
                # Durchmesser des Eingangs:
                d = graph_rechnerischer_durchmesser.get_edge_data(eingehende_kanten[0], eingehende_kanten[1])[
                        "weight"] / 1000
                # Volumenstrom des Eingangs:
                v = graph_luftmengen.get_edge_data(eingehende_kanten[0], eingehende_kanten[1])["weight"]

                # Durchmesser des Durchgangs:
                d_D = graph_rechnerischer_durchmesser.get_edge_data(rohr[0], rohr[1])["weight"] / 1000
                # Volumenstrom des Durchgangs:
                v_D = graph_luftmengen.get_edge_data(rohr[0], rohr[1])["weight"]

                if d > d_D:
                    zeta_reduzierung = widerstandsbeiwert_querschnittsverengung_stetig(d, d_D)

                    # print(f"Zeta T-Reduzierung: {zeta_reduzierung}")

                    net['pipe'].at[pipe, 'loss_coefficient'] += zeta_reduzierung

                    datenbank_verteilernetz.loc[datenbank_verteilernetz[
                                                    'Zielknoten'] == to_junction[
                                                    pipe], 'Zeta Reduzierung'] = zeta_reduzierung

            """T-Stücke"""
            if len(neighbors) == 3:  # T-Stücke finden
                rohr = name_pipe[pipe]
                rohr_nachbar = to_junction[pipe]
                abmessung_rohr = graph_kanalquerschnitt.get_edge_data(from_junction[pipe], to_junction[pipe])[
                    "weight"]

                ausgehende_kanten = graph_leitungslaenge.out_edges(from_junction[pipe])

                abknickende_leitung = [p for p in ausgehende_kanten if p != rohr][0]
                abknickende_leitung_knoten = abknickende_leitung[1]
                abmessung_abknickende_leitung = \
                    graph_kanalquerschnitt.get_edge_data(abknickende_leitung[0], abknickende_leitung[1])[
                        "weight"]

                eingehende_kanten = list(graph_leitungslaenge.in_edges(from_junction[pipe]))[0]
                eingehender_nachbar_knoten = eingehende_kanten[1]
                abmessung_eingehende_kante = \
                    graph_kanalquerschnitt.get_edge_data(eingehende_kanten[0], eingehende_kanten[1])[
                        "weight"]

                """ Daten für Widerstandsbeiwerte"""
                # Durchmesser des Eingangs:
                d = graph_rechnerischer_durchmesser.get_edge_data(eingehende_kanten[0], eingehende_kanten[1])[
                        "weight"] / 1000
                # Volumenstrom des Eingangs:
                v = graph_luftmengen.get_edge_data(eingehende_kanten[0], eingehende_kanten[1])["weight"]

                # Durchmesser des Durchgangs:
                d_D = graph_rechnerischer_durchmesser.get_edge_data(rohr[0], rohr[1])["weight"] / 1000
                # Volumenstrom des Durchgangs:
                v_D = graph_luftmengen.get_edge_data(rohr[0], rohr[1])["weight"]

                # Durchmesser des Abgangs:
                d_A = \
                    graph_rechnerischer_durchmesser.get_edge_data(abknickende_leitung[0], abknickende_leitung[1])[
                        "weight"] / 1000
                # Volumenstrom des Abgangs
                v_A = graph_luftmengen.get_edge_data(abknickende_leitung[0], abknickende_leitung[1])["weight"]

                zeta_t_stueck = 0
                zeta_querschnittsverengung = 0

                # 3D Darstellung des T-Stücks
                # darstellung_t_stueck(eingehende_kanten, rohr, abknickende_leitung)

                if check_if_lines_are_aligned(eingehende_kanten, rohr) == True:

                    #   Rohr für Verlust
                    #    |
                    #    |---- Ausgang
                    #    |
                    #  Eingang

                    # print("T-Stück geht durch ")

                    if "Ø" in abmessung_eingehende_kante:

                        zeta_t_stueck = widerstandsbeiwert_T_stueck_trennung_rund(d=d,
                                                                                  v=v,
                                                                                  d_D=d_D,
                                                                                  v_D=v_D,
                                                                                  d_A=d_A,
                                                                                  v_A=v_A,
                                                                                  richtung="Durchgangsrichtung")

                        # print(f"Zeta T-Stück: {zeta_t_stueck}")

                        net['pipe'].at[pipe, 'loss_coefficient'] += zeta_t_stueck

                    elif "x" in abmessung_eingehende_kante:
                        zeta_t_stueck = widerstandsbeiwert_T_stueck_trennung_eckig(d=d,
                                                                                   v=v,
                                                                                   d_D=d_D,
                                                                                   v_D=v_D,
                                                                                   d_A=d_A,
                                                                                   v_A=v_A,
                                                                                   richtung="Durchgangsrichtung")

                        if "Ø" in abmessung_rohr and d > d_D:
                            zeta_querschnittsverengung = widerstandsbeiwert_querschnittsverengung_stetig(d, d_D)
                        else:
                            zeta_querschnittsverengung = 0

                        # print(f"Zeta T-Stück: {zeta_t_stueck + zeta_querschnittsverengung}")

                        net['pipe'].at[pipe, 'loss_coefficient'] += zeta_t_stueck + zeta_querschnittsverengung




                elif check_if_lines_are_aligned(eingehende_kanten, abknickende_leitung) == True:

                    #  Ausgang
                    #    |
                    #    |---- Rohr für Verlust
                    #    |
                    #  Eingang

                    # print("T-Stück knickt ab ")

                    if "Ø" in abmessung_eingehende_kante:

                        zeta_t_stueck = widerstandsbeiwert_T_stueck_trennung_rund(d=d,
                                                                                  v=v,
                                                                                  d_D=d_D,
                                                                                  v_D=v_D,
                                                                                  d_A=d_A,
                                                                                  v_A=v_A,
                                                                                  richtung="abzweigende Richtung")

                        # print(f"Zeta T-Stück: {zeta_t_stueck}")

                        net['pipe'].at[pipe, 'loss_coefficient'] += zeta_t_stueck


                    elif "x" in abmessung_eingehende_kante:
                        zeta_t_stueck = widerstandsbeiwert_T_stueck_trennung_eckig(d=d,
                                                                                   v=v,
                                                                                   d_D=d_D,
                                                                                   v_D=v_D,
                                                                                   d_A=d_A,
                                                                                   v_A=v_A,
                                                                                   richtung="abzweigende Richtung")

                        # print(f"Zeta T-Stück: {zeta_t_stueck}")

                        net['pipe'].at[pipe, 'loss_coefficient'] += zeta_t_stueck



                elif check_if_lines_are_aligned(rohr, abknickende_leitung):
                    # Ausgang ---------- Rohr für Verlust
                    #              |
                    #           Eingang
                    # print("T-Stück ist Verteiler")

                    if "Ø" in abmessung_eingehende_kante:
                        zeta_t_stueck = widerstandsbeiwert_T_endstueck_rund(d=d,
                                                                            v=v,
                                                                            d_A=max(d_A, d_D),
                                                                            v_A=max(v_A, v_D)
                                                                            )
                        # Wenn der Durchmesser des Rohres kleiner ist als der des Abzweiges, muss noch eine
                        # Querschnittsverengung berücksichtigt werden
                        if d_D < d_A:
                            zeta_querschnittsverengung = widerstandsbeiwert_querschnittsverengung_stetig(d_A, d_D)
                        else:
                            zeta_querschnittsverengung = 0

                        # print(f"Zeta T-Stück: {zeta_t_stueck}")

                        net['pipe'].at[pipe, 'loss_coefficient'] += zeta_t_stueck + zeta_querschnittsverengung

                    elif "x" in abmessung_eingehende_kante:
                        breite = self.finde_abmessung(abmessung_eingehende_kante)[0]
                        hoehe = self.finde_abmessung(abmessung_eingehende_kante)[1]
                        zeta_t_stueck = widerstandsbeiwert_kruemmerendstueck_eckig(a=hoehe,
                                                                                   b=breite,
                                                                                   d=d,
                                                                                   v=v,
                                                                                   d_A=d_D,
                                                                                   v_A=v_D
                                                                                   )

                        # print(f"Zeta T-Stück: {zeta_t_stueck}")

                        net['pipe'].at[pipe, 'loss_coefficient'] += zeta_t_stueck

                datenbank_verteilernetz.loc[datenbank_verteilernetz[
                                                'Zielknoten'] == to_junction[
                                                pipe], 'Zeta T-Stück'] = zeta_t_stueck + zeta_querschnittsverengung

        # Luftmengen aus Graphen
        luftmengen = nx.get_node_attributes(graph_luftmengen, 'weight')

        # Index der RLT-Anlage finden
        index_rlt = name_junction.index(tuple(position_rlt))
        luftmenge_rlt = luftmengen[position_rlt]
        mdot_kg_per_s_rlt = luftmenge_rlt * dichte * 1 / 3600

        # Externes Grid erstellen, da dann die Visualisierung besser ist
        pp.create_ext_grid(net, junction=index_rlt, p_bar=0, t_k=293.15, name="RLT-Anlage")

        # Hinzufügen der RLT-Anlage zum Netz
        pp.create_source(net,
                         mdot_kg_per_s=mdot_kg_per_s_rlt,
                         junction=index_rlt,
                         p_bar=0,
                         t_k=293.15,
                         name="RLT-Anlage")

        liste_lueftungsauslaesse = list()

        # Hinzugen der Lüftungsauslässe
        for index, element in enumerate(luftmengen):
            if element == tuple(position_rlt):
                continue  # Überspringt den aktuellen Durchlauf
            if element[0] == position_schacht[0] and element[1] == position_schacht[1]:
                continue
            pp.create_sink(net,
                           junction=name_junction.index(element),
                           mdot_kg_per_s=luftmengen[element] * dichte * 1 / 3600,
                           )
            liste_lueftungsauslaesse.append(name_junction.index(element))

        # Die eigentliche Berechnung wird mit dem pipeflow-Kommando gestartet:
        pp.pipeflow(net)

        # Bestimmung des Druckverlustes
        groesster_druckverlust = abs(net.res_junction["p_bar"].min())
        differenz = net.res_junction["p_bar"].min()

        # Identifizierung der Quelle durch ihren Namen oder Index
        source_index = net['source'].index[net['source']['name'] == "RLT-Anlage"][0]
        # Identifizieren des externen Grids durch seinen Namen oder Index
        ext_grid_index = net['ext_grid'].index[net['ext_grid']['name'] == "RLT-Anlage"][0]

        # Ändern des Druckwerts
        net['source'].at[source_index, 'p_bar'] = groesster_druckverlust
        # Ändern des Druckwerts
        net['ext_grid'].at[ext_grid_index, 'p_bar'] = groesster_druckverlust

        # Erneute Berechnung
        pp.pipeflow(net)

        groesster_druckverlust = net.res_junction["p_bar"].min()

        # Identifizierung der Quelle durch ihren Namen oder Index
        source_index = net['source'].index[net['source']['name'] == "RLT-Anlage"][0]
        # Identifizieren des externen Grids durch seinen Namen oder Index
        ext_grid_index = net['ext_grid'].index[net['ext_grid']['name'] == "RLT-Anlage"][0]

        groesster_druckverlust -= 0.00070  # 30 Pa für Lüftungsauslass und 40 Pa für Schalldämpfer

        # Ändern des Druckwerts
        net['source'].at[source_index, 'p_bar'] -= groesster_druckverlust
        # Ändern des Druckwerts
        net['ext_grid'].at[ext_grid_index, 'p_bar'] -= groesster_druckverlust

        pp.pipeflow(net)

        # Ergebnisse werden in Tabellen mit dem Präfix res_... gespeichert. Auch diese Tabellen sind nach der Berechnung im
        # net-Container abgelegt.
        dataframe_pipes = pd.concat([net.pipe, net.res_pipe], axis=1)
        dataframe_junctions = pd.concat([net.junction, net.res_junction], axis=1)

        for rohr in datenbank_verteilernetz["Kante"]:
            p_from_pa = int(dataframe_pipes.loc[dataframe_pipes["name"] == str(rohr), "p_from_bar"].iloc[0] * 100000)
            p_to_pa = int(dataframe_pipes.loc[dataframe_pipes["name"] == str(rohr), "p_to_bar"].iloc[0] * 100000)

            datenbank_verteilernetz.loc[datenbank_verteilernetz["Kante"] == rohr, "p_from_pa"] = p_from_pa
            datenbank_verteilernetz.loc[datenbank_verteilernetz["Kante"] == rohr, "p_to_pa"] = p_to_pa

        datenbank_verteilernetz.to_excel(self.paths.export / 'Datenbank_Verteilernetz.xlsx', index=False)

        # Pfad für Speichern
        pipes_excel_pfad = self.paths.export / "Druckverlust.xlsx"

        if export == False:
            # Export
            dataframe_pipes.to_excel(pipes_excel_pfad)

            with pd.ExcelWriter(pipes_excel_pfad) as writer:
                dataframe_pipes.to_excel(writer, sheet_name="Pipes")
                dataframe_junctions.to_excel(writer, sheet_name="Junctions")

            # # create additional junction collections for junctions with sink connections and junctions with valve connections
            junction_sink_collection = plot.create_junction_collection(net,
                                                                       junctions=liste_lueftungsauslaesse,
                                                                       patch_type="circle",
                                                                       size=0.1,
                                                                       color="blue")

            junction_source_collection = plot.create_junction_collection(net,
                                                                         junctions=[index_rlt],
                                                                         patch_type="circle",
                                                                         size=0.6,
                                                                         color="green")

            # create additional pipe collection
            pipe_collection = plot.create_pipe_collection(net,
                                                          linewidths=2.,
                                                          color="grey")

            collections = [junction_sink_collection, junction_source_collection, pipe_collection]

            # Zeichnen Sie die Sammlungen
            fig, ax = plt.subplots(num=f"Druckverlust", figsize=(20, 15))
            plot.draw_collections(collections=collections, ax=ax, axes_visible=(True, True))

            # Fügt die Text-Annotationen für die Drücke hinzu
            for idx, junction in enumerate(net.res_junction.index):
                pressure = net.res_junction.iloc[idx]['p_bar']  # Druck am Knoten
                # Koordinaten des Knotens
                if junction in net.junction_geodata.index:
                    coords = net.junction_geodata.loc[junction, ['x', 'y']]
                    ax.text(coords['x'], coords['y'], f'{pressure * 100000:.0f} [Pa]', fontsize=8,
                            horizontalalignment='left', verticalalignment='top', rotation=-45)

            # Setze den Pfad für den neuen Ordner
            ordner_pfad = Path(self.paths.export)

            # Erstelle den Ordner
            ordner_pfad.mkdir(parents=True, exist_ok=True)

            # Speichern des Graphens
            gesamte_bezeichnung = "Druckverlust" + ".png"
            pfad_plus_name = self.paths.export / gesamte_bezeichnung
            plt.savefig(pfad_plus_name)

            # plt.show()

            # plt.close()

        return groesster_druckverlust * 100000, datenbank_verteilernetz

    def blechstaerke(self, druckverlust, abmessung):
        """
        Berechnet die Blechstärke in Abhängigkeit vom Kanal
        :param druckverlust: Durckverlust des Systems
        :param abmessung: Abmessung des Kanals (400x300 oder Ø60)
        :return: Blechstärke
        """

        if "Ø" in abmessung:
            durchmesser = self.finde_abmessung(abmessung)

            if durchmesser <= 0.2:
                blechstaerke = 0.5 / 1000  # In Metern nach MKK Shop Datenblatt Best. Nr. 10782
            elif 0.2 < durchmesser <= 0.4:
                blechstaerke = 0.6 / 1000  # In Metern nach MKK Shop Datenblatt Best. Nr. 10782
            elif 0.4 < durchmesser <= 0.5:
                blechstaerke = 0.7 / 1000  # In Metern nach MKK Shop Datenblatt Best. Nr. 10782
            elif 0.5 < durchmesser <= 0.63:
                blechstaerke = 0.9 / 1000  # In Metern nach MKK Shop Datenblatt Best. Nr. 10782
            elif 0.63 < durchmesser <= 1.25:
                blechstaerke = 1.25 / 1000  # In Metern nach MKK Shop Datenblatt Best. Nr. 10782


        elif "x" in abmessung:
            breite, hoehe = self.finde_abmessung(abmessung)
            laengste_kante = max(breite, hoehe)

            if druckverlust <= 1000:
                if laengste_kante <= 0.500:
                    blechstaerke = 0.6 / 1000  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53
                elif 0.500 < laengste_kante <= 1.000:
                    blechstaerke = 0.8 / 1000  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53
                elif 1.000 < laengste_kante <= 2.000:
                    blechstaerke = 1.0 / 1000  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53

            elif 1000 < druckverlust <= 2000:
                if laengste_kante <= 0.500:
                    blechstaerke = 0.7 / 1000  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53
                elif 0.500 < laengste_kante <= 1.000:
                    blechstaerke = 0.9 / 1000  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53
                elif 1.000 < laengste_kante <= 2.000:
                    blechstaerke = 1.1 / 1000  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53

            elif 2000 < druckverlust <= 3000:
                if laengste_kante <= 1.000:
                    blechstaerke = 0.95 / 1000  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53
                elif 1.000 < laengste_kante <= 2.000:
                    blechstaerke = 1.15 / 1000  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53

        return blechstaerke

    def raumanbindung(self, querschnittsart, zwischendeckenraum, datenbank_raeume):

        # Ermittlung des Kanalquerschnittes
        datenbank_raeume["Kanalquerschnitt"] = \
            datenbank_raeume.apply(lambda row: self.abmessungen_kanal(querschnittsart,
                                                                      self.notwendiger_kanaldquerschnitt(
                                                                          row["Volumenstrom"]),
                                                                      zwischendeckenraum),
                                   axis=1
                                   )

        # Ermittung der Abmessungen
        datenbank_raeume['Leitungslänge'] = 1
        datenbank_raeume['Durchmesser'] = None
        datenbank_raeume['Breite'] = None
        datenbank_raeume['Höhe'] = None

        for index, kanalquerschnitt in enumerate(datenbank_raeume["Kanalquerschnitt"]):
            if "Ø" in kanalquerschnitt:
                datenbank_raeume.at[index, 'Durchmesser'] = self.finde_abmessung(kanalquerschnitt)

            elif "x" in kanalquerschnitt:
                datenbank_raeume.at[index, 'Breite'] = self.finde_abmessung(kanalquerschnitt)[0]
                datenbank_raeume.at[index, 'Höhe'] = self.finde_abmessung(kanalquerschnitt)[1]

        datenbank_raeume["Mantelfläche"] = datenbank_raeume.apply(
            lambda row: round(self.mantelflaeche_kanal(querschnittsart,
                                                                          self.notwendiger_kanaldquerschnitt(
                                                                              row["Volumenstrom"]),
                                                                          zwischendeckenraum), 2
                                                 ), axis=1)

        datenbank_raeume["rechnerischer Durchmesser"] = datenbank_raeume.apply(
            lambda row: round(self.rechnerischer_durchmesser(querschnittsart,
                                                             self.notwendiger_kanaldquerschnitt(row["Volumenstrom"]),
                                                             zwischendeckenraum),
                              2
                              ), axis=1)

        # Ermittlung der Blechstärke
        datenbank_raeume["Blechstärke"] = datenbank_raeume.apply(
            lambda row: self.blechstaerke(70, row["Kanalquerschnitt"]), axis=1)

        # Überprüfung, ob ein Schalldämpfer erfordlerlich ist
        liste_raeume_schalldaempfer = ["Bed room",
                                       "Class room (school), group room (kindergarden)",
                                       "Classroom",
                                       "Examination- or treatment room",
                                       "Exhibition room and museum conservational demands",
                                       "Exhibition, congress",
                                       "Foyer (theater and event venues)",
                                       "Hotel room",
                                       "Laboratory",
                                       "Lecture hall, auditorium",
                                       "Library - magazine and depot",
                                       "Library - open stacks",
                                       "Library - reading room",
                                       "Living",
                                       "Main Hall, Reception",
                                       "Medical and therapeutic practices",
                                       "Meeting, Conference, seminar",
                                       "MultiUseComputerRoom",
                                       "Restaurant",
                                       "Sauna area",
                                       "Spectator area (theater and event venues)",
                                       "Stage (theater and event venues)",
                                       "Traffic area",
                                       "WC and sanitary rooms in non-residential buildings",
                                       "Group Office (between 2 and 6 employees)",
                                       "Open-plan Office (7 or more employees)",
                                       "Single office",
                                       "office_function"
                                       ]
        datenbank_raeume['Schalldämpfer'] = datenbank_raeume['Raumart'].apply(lambda x: 1 if x in liste_raeume_schalldaempfer else 0)

        # Volumenstromregler
        datenbank_raeume["Volumenstromregler"] = 1

        # Berechnung des Blechvolumens
        datenbank_raeume["Blechvolumen"] = datenbank_raeume["Blechstärke"] * datenbank_raeume[
            "Mantelfläche"]

        # Berechnung des Blechgewichts
        datenbank_raeume["Blechgewicht"] = datenbank_raeume[
                                               "Blechvolumen"] * 7850  # Dichte Stahl 7850 kg/m³


    def co2(self,
            druckverlust,
            datenbank_raeume,
            datenbank_verteilernetz):

        def gwp(uuid: str):
            """
            Gibt das globale Erwärmungspotential nach Ökobaudat in Kathegorien zurücvk
            :param uuid: UUID nach Ökobaudat
            :return: Globales Erwärmungspotential nach ÖKOBAUDAT, ReferenceUnit
            """
            # A1-A3: Herstellung
            # C2: Transport
            # C3: Abfallbehandlung
            # D: Recxclingpotential

            OKOBAU_URL = "https://oekobaudat.de/OEKOBAU.DAT/resource/datastocks/c391de0f-2cfd-47ea-8883-c661d294e2ba"

            """Fetches the data of a specific EPD given its UUID"""
            response = requests.get(f"{OKOBAU_URL}/processes/{uuid}?format=json&view=extended")

            response.raise_for_status()
            data = response.json()

            # Extrahieren der Werte für die Module A1-A3, C2, C3, D
            results = {}
            # Loop durch alle 'LCIAResults' Einträge
            for entry in data['LCIAResults']['LCIAResult']:
                # Initialisieren eines leeren Dictionaries für jeden Eintrag
                results[entry['referenceToLCIAMethodDataSet']['shortDescription'][0]['value']] = {}
                # Loop durch alle 'other' Elemente
                for sub_entry in entry['other']['anies']:
                    # Prüfen, ob 'module' als Schlüssel in 'sub_entry' vorhanden ist
                    if 'module' in sub_entry:
                        # Hinzufügen des Wertes zum Dictionary
                        results[entry['referenceToLCIAMethodDataSet']['shortDescription'][0]['value']][
                            sub_entry['module']] = \
                            sub_entry['value']

            wp_reference_unit = data['exchanges']['exchange'][0]['flowProperties'][1]['referenceUnit']

            # Rückgabe der Ergebnisse
            return results['Global Warming Potential - total (GWP-total)'], wp_reference_unit

        """
        Berechnung des CO2 des Lüftungsverteilernetztes des Blechs der Zuluft des Verteilernetzes
        """
        # Ermittlung der Blechstärke
        datenbank_verteilernetz["Blechstärke"] = datenbank_verteilernetz.apply(
            lambda row: self.blechstaerke(druckverlust, row["Kanalquerschnitt"]), axis=1)

        # Berechnung des Blechvolumens
        datenbank_verteilernetz["Blechvolumen"] = datenbank_verteilernetz["Blechstärke"] * datenbank_verteilernetz[
            "Mantelfläche"]

        # Berechnung des Blechgewichts
        datenbank_verteilernetz["Blechgewicht"] = datenbank_verteilernetz[
                                                      "Blechvolumen"] * 7850  # Dichte Stahl 7850 kg/m³

        # Ermittlung des CO2-Kanal
        datenbank_verteilernetz["CO2-Kanal"] = datenbank_verteilernetz["Blechgewicht"] * (
                    float(gwp("ffa736f4-51b1-4c03-8cdd-3f098993b363")[0]["A1-A3"]) + float(
                gwp("ffa736f4-51b1-4c03-8cdd-3f098993b363")[0]["C2"]))

        def querschnittsflaeche_kanaldaemmung(row):
            """
            Berechnet die Querschnittsfläche der Dämmung
            """
            querschnittsflaeche = 0
            if 'Ø' in row['Kanalquerschnitt']:
                durchmesser = row['Durchmesser']
                querschnittsflaeche = math.pi*((durchmesser + 0.04) ** 2 )/4 - math.pi*(durchmesser ** 2 )/4# 20mm Dämmung des Lüftungskanals nach anerkanten
                # Regeln der Technik nach Missel

            elif 'x' in row['Kanalquerschnitt']:
                breite = row['Breite']
                hoehe = row['Höhe']
                querschnittsflaeche = ((breite + 0.04) * (hoehe + 0.04)) - (breite*hoehe)  # 20mm Dämmung des Lüftungskanals nach
                # anerkanten Regeln der Technik nach Missel

            return querschnittsflaeche

        # Berechnung der Dämmung
        datenbank_verteilernetz['Querschnittsfläche Dämmung'] = datenbank_verteilernetz.apply(querschnittsflaeche_kanaldaemmung, axis=1)

        datenbank_verteilernetz['CO2-Kanaldämmung'] = (datenbank_verteilernetz['Querschnittsfläche Dämmung'] *
                                                       datenbank_verteilernetz['Leitungslänge'] *
                                                       (121.8 + 1.96 + 10.21)
                                                       )


        # Export to Excel
        datenbank_verteilernetz.to_excel(self.paths.export / 'Datenbank_Verteilernetz.xlsx', index=False)


        """
        Berechnung des CO2 für die Raumanbindung
        """
        # Ermittlung des CO2-Kanal
        datenbank_raeume["CO2-Kanal"] = datenbank_raeume["Leitungslänge"] * datenbank_raeume[
            "Blechgewicht"] * (float(gwp("ffa736f4-51b1-4c03-8cdd-3f098993b363")[0][
                                                                 "A1-A3"]) + float(
                               gwp("ffa736f4-51b1-4c03-8cdd-3f098993b363")[0]["C2"])
                               )

        # Ermittlung des CO2 der Schalldämpfer

        # Vordefinierte Daten für Trox RN Volumenstromregler
        trox_rn_durchmesser_gewicht = {
            'Durchmesser': [80, 100, 125, 160, 200, 250, 315, 400],
            'Gewicht': [2.2, 3.6, 4.0, 5.0, 6.0, 7.3, 9.8, 11.8]
        }
        df_trox_rn_durchmesser_gewicht = pd.DataFrame(trox_rn_durchmesser_gewicht)

        # Funktion, um das nächstgrößere Gewicht zu finden
        def gewicht_runde_volumenstromregler(row):
            if row['Volumenstromregler'] == 1 and 'Ø' in row['Kanalquerschnitt']:
                rechnerischer_durchmesser = row['rechnerischer Durchmesser']
                next_durchmesser = df_trox_rn_durchmesser_gewicht[
                    df_trox_rn_durchmesser_gewicht['Durchmesser'] >= rechnerischer_durchmesser]['Durchmesser'].min()
                return \
                df_trox_rn_durchmesser_gewicht[df_trox_rn_durchmesser_gewicht['Durchmesser'] == next_durchmesser][
                    'Gewicht'].values[0]
            return None

        # Tabelle mit Breite, Höhe und Gewicht für Trox EN Volumenstromregler
        df_trox_en_durchmesser_gewicht = pd.DataFrame({
            'Breite': [200, 300, 300, 300, 400, 400, 400, 400, 500, 500, 500, 500, 500, 600, 600, 600, 600, 600, 600],
            'Höhe': [100, 100, 150, 200, 200, 250, 300, 400, 200, 250, 300, 400, 500, 200, 250, 300, 400, 500, 600],
            'Gewicht': [6.5, 8, 9, 10, 12, 13, 14, 18, 14, 14.5, 15.5, 20.5, 22, 15.5, 16.5, 18, 23, 25, 27.5]
        })

        # Funktion, um das entsprechende oder nächstgrößere Gewicht zu finden
        def gewicht_eckige_volumenstromregler(row):
            if row['Volumenstromregler'] == 1 and 'x' in row['Kanalquerschnitt']:
                breite, hoehe = row['Breite']*1000, row['Höhe']*1000
                passende_zeilen = df_trox_en_durchmesser_gewicht[
                    (df_trox_en_durchmesser_gewicht['Breite'] >= breite) & (
                                df_trox_en_durchmesser_gewicht['Höhe'] >= hoehe)]
                if not passende_zeilen.empty:
                    return passende_zeilen.sort_values(by=['Breite', 'Höhe', 'Gewicht']).iloc[0]['Gewicht']
            return None

        # Kombinierte Funktion, die beide Funktionen ausführt
        def gewicht_volumenstromregler(row):
            gewicht_rn = gewicht_runde_volumenstromregler(row)
            if gewicht_rn is not None:
                return gewicht_rn
            return gewicht_eckige_volumenstromregler(row)

        # Anwenden der Funktion auf jede Zeile
        datenbank_raeume['Gewicht Volumenstromregler'] = datenbank_raeume.apply(gewicht_volumenstromregler, axis=1)

        datenbank_raeume["CO2-Volumenstromregler"] = datenbank_raeume['Gewicht Volumenstromregler'] * (19.08 + 0.01129 + 0.647) * 0.348432
        # Nach Ökobaudat https://oekobaudat.de/OEKOBAU.DAT/datasetdetail/process.xhtml?uuid=29e922f6-d872-4a67-b579-38bb8cd82abf&version=00.02.000&stock=OBD_2023_I&lang=de

        # CO2 für Schallfämpfer
        # Tabelle Daten für Berechnung nach Trox CA
        durchmesser_tabelle = pd.DataFrame({
            'Durchmesser': [80, 100, 125, 160, 200, 250, 315, 400, 450, 500, 560, 630, 710, 800],
            'Innendurchmesser': [80, 100, 125, 160, 200, 250, 315, 400, 450, 500, 560, 630, 710, 800],
            'Aussendurchmesser': [184, 204, 228, 254, 304, 354, 405, 505, 636, 716, 806, 806, 908, 1008]
        })

        # Funktion zur Berechnung der Fläche des Kreisrings
        def gewicht_daemmung_schalldaempfer(row):
            rechnerischer_durchmesser = row['rechnerischer Durchmesser']
            passende_zeilen = durchmesser_tabelle[durchmesser_tabelle['Durchmesser'] >= rechnerischer_durchmesser]
            if not passende_zeilen.empty:
                naechster_durchmesser = passende_zeilen.iloc[0]
                innen = naechster_durchmesser['Innendurchmesser'] / 2
                aussen = naechster_durchmesser['Aussendurchmesser'] / 2
                gewicht = math.pi * (aussen ** 2 - innen ** 2) * 1/(1000**2) * 0.88 * 100 # Für einen Meter Länge des
                # Schalldämpfers, entspricht nach Datenblatt einer Länge des Dämmkerns von 0.88m, Dichte 100 kg/m³
                # https://oekobaudat.de/OEKOBAU.DAT/datasetdetail/process.xhtml?uuid=89b4bfdf-8587-48ae-9178-33194f6d1314&version=00.02.000&stock=OBD_2023_I&lang=de
                return gewicht
            return None

        # Gewicht Dämmung Schalldämpfer
        datenbank_raeume['Gewicht Dämmung Schalldämpfer'] = datenbank_raeume.apply(gewicht_daemmung_schalldaempfer, axis=1)

        datenbank_raeume["CO2-Dämmung Schalldämpfer"] = datenbank_raeume['Gewicht Dämmung Schalldämpfer'] * (
                    117.4 + 2.132 + 18.43) * 1/100

        # Gewicht des Metalls des Schalldämpfers für Trox CA für Packungsdicke 50 bis 400mm danach Packungsdicke 100
        # Vordefinierte Daten für Trox CA Schalldämpfer
        trox_ca_durchmesser_gewicht = {
            'Durchmesser': [80, 100, 125, 160, 200, 250, 315, 400, 450, 500, 560, 630, 710, 800],
            'Gewicht': [6, 6, 7, 8, 10, 12, 14, 18, 24, 28, 45*2/3, 47*2/3, 54*2/3, 62*2/3]
        }
        df_trox_ca_durchmesser_gewicht = pd.DataFrame(trox_rn_durchmesser_gewicht)

        # Funktion, um das nächstgrößere Gewicht zu finden
        def gewicht_schalldaempfer_ohne_daemmung(row):
            if row['Schalldämpfer'] == 1:
                rechnerischer_durchmesser = row['rechnerischer Durchmesser']
                passende_zeilen = df_trox_ca_durchmesser_gewicht[
                    df_trox_ca_durchmesser_gewicht['Durchmesser'] >= rechnerischer_durchmesser]
                if not passende_zeilen.empty:
                    next_durchmesser = passende_zeilen['Durchmesser'].min()
                    gewicht_schalldaempfer = \
                    df_trox_ca_durchmesser_gewicht[df_trox_ca_durchmesser_gewicht['Durchmesser'] == next_durchmesser][
                        'Gewicht'].values[0]
                    daemmung_gewicht = row[
                        "Gewicht Dämmung Schalldämpfer"] if "Gewicht Dämmung Schalldämpfer" in row and not pd.isnull(
                        row["Gewicht Dämmung Schalldämpfer"]) else 0
                    return gewicht_schalldaempfer - daemmung_gewicht
            return None

        datenbank_raeume['Gewicht Blech Schalldämpfer'] = datenbank_raeume.apply(gewicht_schalldaempfer_ohne_daemmung,
                                                                                  axis=1)

        datenbank_raeume["CO2-Blech Schalldämfer"] = datenbank_raeume["Gewicht Blech Schalldämpfer"] * (
                    float(gwp("ffa736f4-51b1-4c03-8cdd-3f098993b363")[0]["A1-A3"]) + float(
                gwp("ffa736f4-51b1-4c03-8cdd-3f098993b363")[0]["C2"]))


        # Berechnung der Dämmung
        datenbank_raeume['Querschnittsfläche Dämmung'] = datenbank_raeume.apply(querschnittsflaeche_kanaldaemmung, axis=1)

        datenbank_raeume['CO2-Kanaldämmung'] = (datenbank_raeume['Querschnittsfläche Dämmung'] *
                                                datenbank_raeume['Leitungslänge'] *
                                                (121.8 + 1.96 + 10.21)
                                                )

        # Export to Excel
        datenbank_raeume.to_excel(self.paths.export / 'Datenbank_Raumanbindung.xlsx', index=False)
