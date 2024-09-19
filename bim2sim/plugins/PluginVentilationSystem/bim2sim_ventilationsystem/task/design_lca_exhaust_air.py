import PIL
from matplotlib import image as mpimg

import bim2sim
import matplotlib.pyplot as plt
import networkx as nx
from itertools import chain
import math
import pandas as pd
import pandapipes as pp
import numpy as np
import requests
import pandapipes.plotting as plot
from pathlib import Path
from bim2sim.elements.mapping.units import ureg
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_elements
from decimal import Decimal, ROUND_HALF_UP
from networkx.utils import pairwise
from copy import deepcopy
from scipy.interpolate import interpolate, interp1d, griddata, LinearNDInterpolator


class DesignExaustLCA(ITask):
    """Design of the LCA

    Annahmen:
    Inputs: IFC Modell, Räume,

    Args:
        elements: bim2sim elements
    Returns:
        elements: bim2sim elements enriched with needed air flows
    """
    reads = ('elements',
             'graph_ventilation_duct_length_supply_air',
             'dict_steiner_tree_with_duct_cross_section')
    touches = ('corners_building',
               'building_shaft_exhaust_air',
               'graph_ventilation_duct_length_exhaust_air',
               'pressure_loss_exhaust_air',
               'dataframe_rooms_exhaust_air',
               'dataframe_distribution_network_exhaust_air',
               'dict_steiner_tree_with_air_volume_exhaust_air')

    def run(self, elements, graph_ventilation_duct_length_supply_air, dict_steiner_tree_with_duct_cross_section):

        self.supply_graph = graph_ventilation_duct_length_supply_air
        self.dict_supply_graph_cross_section = dict_steiner_tree_with_duct_cross_section

        export = self.playground.sim_settings.ventilation_lca_export_exhaust
        building_shaft_exhaust_air = [1, 2.8, -2]
        position_rlt = [25, building_shaft_exhaust_air[1], building_shaft_exhaust_air[2]]
        # y-Achse von Schacht und RLT müssen identisch sein
        cross_section_type = "optimal"  # Wähle zwischen rund, eckig und optimal
        zwischendeckenraum = 200 * ureg.millimeter  # Hier wird die verfügbare Höhe (in [mmm]) in der Zwischendecke angegeben! Diese
        # entspricht dem verfügbaren Abstand zwischen UKRD (Unterkante Rohdecke) und OKFD (Oberkante Fertigdecke),
        # siehe https://www.ctb.de/_wiki/swb/Massbezuege.php

        self.logger.info("Start design LCA")
        thermal_zones = filter_elements(elements, 'ThermalZone')
        thermal_zones = [tz for tz in thermal_zones if tz.ventilation_system == True]

        self.logger.info("Start calculating points of the ventilation outlet at the ceiling")
        # Hier werden die Mittelpunkte der einzelnen Räume aus dem IFC-Modell ausgelesen und im Anschluss um die
        # halbe Höhe des Raumes nach oben verschoben. Es wird also der Punkt an der UKRD (Unterkante Rohdecke)
        # in der Mitte des Raumes berechnet. Hier soll im weiteren Verlauf der Lüftungsauslass angeordnet werden
        (corner,
         airflow_volume_per_storey,
         dict_koordinate_mit_raumart,
         dataframe_rooms,
         corners_building) = self.corner(thermal_zones,
                                         building_shaft_exhaust_air)
        self.logger.info("Finished calculating points of the ventilation outlet at the ceiling")

        self.logger.info("Calculating the Coordinates of the ceiling hights")
        # Hier werden die Koordinaten der Höhen an der UKRD berechnet und in ein Set
        # zusammengefasst, da diese Werte im weiterem Verlauf häufig benötigt werden, somit müssen diese nicht
        # immer wieder neu berechnet werden:
        z_coordinate_list = self.calculate_z_coordinate(corner)

        self.logger.info("Calculating intersection points")
        # Hier werden die Schnittpunkte aller Punkte pro Geschoss berechnet. Es entsteht ein Raster im jeweiligen
        # Geschoss. Es wird als Verlegeraster für die Zuluft festgelegt. So werden die einzelnen Punkte der Lüftungs-
        # auslässe zwar nicht direkt verbunden, aber in der Praxis und nach Norm werden Lüftungskanäle nicht diagonal
        # durch ein Gebäude verlegt
        intersection_points = self.intersection_points(corner,
                                                       z_coordinate_list
                                                       )
        self.logger.info("Calculating intersection points successful")

        self.logger.info("Visualising points on the ceiling for the ventilation outlet:")
        self.visualisierung(corner,
                            intersection_points
                            )

        self.logger.info("Visualising intersectionpoints")
        self.visualization_points_by_level(corner,
                                           intersection_points,
                                           z_coordinate_list,
                                           building_shaft_exhaust_air,
                                           export)

        self.logger.info("Graph für jedes Geschoss erstellen")
        (dict_steinerbaum_mit_leitungslaenge,
         dict_steinerbaum_mit_kanalquerschnitt,
         dict_steiner_tree_with_air_volume_exhaust_air,
         dict_steinerbaum_mit_mantelflaeche,
         dict_steinerbaum_mit_rechnerischem_querschnitt) = self.create_graph(corner,
                                                                             intersection_points,
                                                                             z_coordinate_list,
                                                                             building_shaft_exhaust_air,
                                                                             cross_section_type,
                                                                             zwischendeckenraum,
                                                                             export
                                                                             )
        self.logger.info("Graph für jedes Geschoss wurde erstellt")

        self.logger.info("Schacht und RLT verbinden")
        (dict_steinerbaum_mit_leitungslaenge,
         dict_steinerbaum_mit_kanalquerschnitt,
         dict_steiner_tree_with_air_volume_exhaust_air,
         dict_steinerbaum_mit_mantelflaeche,
         dict_steinerbaum_mit_rechnerischem_querschnitt) = self.rlt_schacht(z_coordinate_list,
                                                                            building_shaft_exhaust_air,
                                                                            airflow_volume_per_storey,
                                                                            position_rlt,
                                                                            dict_steinerbaum_mit_leitungslaenge,
                                                                            dict_steinerbaum_mit_kanalquerschnitt,
                                                                            dict_steiner_tree_with_air_volume_exhaust_air,
                                                                            dict_steinerbaum_mit_mantelflaeche,
                                                                            dict_steinerbaum_mit_rechnerischem_querschnitt,
                                                                            export
                                                                            )
        self.logger.info("Schacht und RLT verbunden")

        self.logger.info("3D-Graph erstellen")
        (graph_ventilation_duct_length_exhaust_air,
         graph_luftmengen,
         graph_kanalquerschnitt,
         graph_mantelflaeche,
         graph_rechnerischer_durchmesser,
         dataframe_distribution_network_exhaust_air) = self.drei_dimensionaler_graph(dict_steinerbaum_mit_leitungslaenge,
                                                                                    dict_steinerbaum_mit_kanalquerschnitt,
                                                                                    dict_steiner_tree_with_air_volume_exhaust_air,
                                                                                    dict_steinerbaum_mit_mantelflaeche,
                                                                                    dict_steinerbaum_mit_rechnerischem_querschnitt,
                                                                                    position_rlt,
                                                                                    export,
                                                                                    dict_koordinate_mit_raumart)
        self.logger.info("3D-Graph erstellt")

        self.logger.info("Starte Druckverlustberechnung")
        druckverlust, dataframe_distribution_network_exhaust_air = self.druckverlust(dict_steinerbaum_mit_leitungslaenge,
                                                                                    z_coordinate_list,
                                                                                    position_rlt,
                                                                                    building_shaft_exhaust_air,
                                                                                    graph_ventilation_duct_length_exhaust_air,
                                                                                    graph_luftmengen,
                                                                                    graph_kanalquerschnitt,
                                                                                    graph_mantelflaeche,
                                                                                    graph_rechnerischer_durchmesser,
                                                                                    export,
                                                                                    dataframe_distribution_network_exhaust_air
                                                                                    )
        self.logger.info("Druckverlustberechnung erfolgreich")

        self.logger.info("Starte Berechnung der Raumanbindung")
        dataframe_rooms = self.raumanbindung(cross_section_type, zwischendeckenraum, dataframe_rooms)

        self.logger.info("Starte CO2 Berechnung")
        (pressure_loss_exhaust_air,
         dataframe_rooms_exhaust_air,
         dataframe_distribution_network_exhaust_air) = self.co2(export,
                                                               druckverlust,
                                                               dataframe_rooms,
                                                               dataframe_distribution_network_exhaust_air)

        return (corners_building,
                building_shaft_exhaust_air,
                graph_ventilation_duct_length_exhaust_air,
                pressure_loss_exhaust_air,
                dataframe_rooms_exhaust_air,
                dataframe_distribution_network_exhaust_air,
                dict_steiner_tree_with_air_volume_exhaust_air)

    def corner(self, thermal_zones, building_shaft_exhaust_air):
        """Function calculates position of the outlet of the LVA

        Args:
            thermal_zones: thermal_zones bim2sim element
            building_shaft_exhaust_air: Schachtkoordinate
        Returns:
            corner of the room at the ceiling
        """
        # Listen:
        room_ceiling_ventilation_outlet = []
        room_type = []

        liste_koordinaten_fuer_gebaeudeabmessungen = list()
        for tz in thermal_zones:
            if tz.with_ahu:
                liste_koordinaten_fuer_gebaeudeabmessungen.append([round(tz.space_center.X(), 1),
                                                                   round(tz.space_center.Y(), 1),
                                                                   round(tz.space_center.Z(), 1)
                                                                   ])

        # Finde die kleinsten Koordinaten für x, y, z
        kleinste_x = min(liste_koordinaten_fuer_gebaeudeabmessungen, key=lambda k: k[0])[0]
        kleinste_y = min(liste_koordinaten_fuer_gebaeudeabmessungen, key=lambda k: k[1])[1]
        kleinste_z = min(liste_koordinaten_fuer_gebaeudeabmessungen, key=lambda k: k[2])[2]

        # Finde die größten Koordinaten für x, y, z
        groesste_x = max(liste_koordinaten_fuer_gebaeudeabmessungen, key=lambda k: k[0])[0]
        groesste_y = max(liste_koordinaten_fuer_gebaeudeabmessungen, key=lambda k: k[1])[1]
        groesste_z = max(liste_koordinaten_fuer_gebaeudeabmessungen, key=lambda k: k[2])[2]

        center_gebauede_x = (kleinste_x + groesste_x) / 2
        center_gebauede_y = (kleinste_y + groesste_y) / 2
        center_gebauede_z = (kleinste_z + groesste_z) / 2

        center_gebaeude = (center_gebauede_x, center_gebauede_y, center_gebauede_z)

        list_corner_one = []
        list_corner_two = []

        for tz in thermal_zones:
            if tz.with_ahu:
                center = [round(tz.space_center.X(), 1),
                          round(tz.space_center.Y(), 1),
                          round(tz.space_center.Z(), 1)]
                name = tz.name

                ecke_eins = [round(tz.space_corners[0].X(), 1),
                             round(tz.space_corners[0].Y(), 1),
                             round(tz.space_corners[0].Z(), 1)]

                list_corner_one.append(ecke_eins)

                ecke_zwei = [round(tz.space_corners[1].X(), 1),
                             round(tz.space_corners[1].Y(), 1),
                             round(tz.space_corners[1].Z(), 1)]

                list_corner_two.append(ecke_zwei)

                lueftungseinlass_abluft = [0, 0, 0]

                if center[0] > center_gebaeude[0]:
                    lueftungseinlass_abluft[0] = ecke_zwei[0] - 1
                elif center[0] < center_gebaeude[0]:
                    lueftungseinlass_abluft[0] = ecke_eins[0] + 1
                elif center[0] == center_gebaeude[0]:
                    lueftungseinlass_abluft[0] = center[0]

                if center[1] > center_gebaeude[1]:
                    lueftungseinlass_abluft[1] = ecke_zwei[1] - 1
                elif center[1] < center_gebaeude[1]:
                    lueftungseinlass_abluft[1] = ecke_eins[1] + 1
                elif center[1] == center_gebaeude[1]:
                    lueftungseinlass_abluft[1] = center[1]

                room_ceiling_ventilation_outlet.append([round(lueftungseinlass_abluft[0], 1),
                                                        round(lueftungseinlass_abluft[1], 1),
                                                        round(tz.space_center.Z() + tz.height.magnitude / 2,
                                                                           2),
                                                        math.ceil(tz.air_flow.to(ureg.meter ** 3 / ureg.hour).magnitude) * (
                                                                    ureg.meter ** 3 / ureg.hour)])

                room_type.append(tz.usage)

        # Finde die kleinsten Koordinaten für x, y, z
        lowest_x_corner = min(list_corner_one, key=lambda k: k[0])[0]
        lowest_y_corner = min(list_corner_one, key=lambda k: k[1])[1]
        lowest_z_corner = min(list_corner_one, key=lambda k: k[2])[2]

        # Finde die größten Koordinaten für x, y, z
        highest_x_corner = max(list_corner_two, key=lambda k: k[0])[0]
        highest_y_corner = max(list_corner_two, key=lambda k: k[1])[1]
        highest_z_corner = max(list_corner_two, key=lambda k: k[2])[2]

        corner_building = ((lowest_x_corner, lowest_y_corner, lowest_z_corner),
                           (highest_x_corner, highest_y_corner, highest_z_corner))

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
                    adjusted_coords_x.append((round(x_avg, 1), y, z, a))
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
                    adjusted_coords_y.append((x, round(average_y, 1), z, a))

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

        dataframe_rooms = pd.DataFrame()
        dataframe_rooms["Koordinate"] = list(dict_koordinate_mit_raumart.keys())
        dataframe_rooms["X"] = [x for x, _, _ in dataframe_rooms["Koordinate"]]
        dataframe_rooms["Y"] = [y for _, y, _ in dataframe_rooms["Koordinate"]]
        dataframe_rooms["Z"] = [z for _, _, z in dataframe_rooms["Koordinate"]]
        dataframe_rooms["Raumart"] = dataframe_rooms["Koordinate"].map(dict_koordinate_mit_raumart)
        dataframe_rooms["Volumenstrom"] = dataframe_rooms["Koordinate"].map(dict_koordinate_mit_erf_luftvolumen)

        for z_coord in z_axis:
            room_ceiling_ventilation_outlet.append(
                (building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], z_coord,
                 airflow_volume_per_storey[z_coord]))

        return room_ceiling_ventilation_outlet, airflow_volume_per_storey, dict_koordinate_mit_raumart, dataframe_rooms, corner_building

    def calculate_z_coordinate(self, center):
        z_coordinate_list = set()
        for i in range(len(center)):
            z_coordinate_list.add(center[i][2])
        return sorted(z_coordinate_list)

    def intersection_points(self, ceiling_point, z_coordinate_list):
        # Liste der Schnittpunkte
        intersection_points_list = []

        # Schnittpunkte
        for z_value in z_coordinate_list:
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

    def visualization_points_by_level(self, corner, intersection, z_coordinate_list, building_shaft_exhaust_air,
                                      export):
        """The function visualizes the points in a diagram
        Args:
            corner: Ecke es Raumes an der Decke
            intersection: intersection points at the ceiling
            z_coordinate_list: Z-Koordinaten für jedes Geschoss an der Decke
            building_shaft_exhaust_air
            export: True or False
        Returns:
           2D diagramm for each ceiling
       """
        if export:
            for z_value in z_coordinate_list:
                xy_values = [(x, y) for x, y, z, a in intersection if z == z_value]
                xy_shaft = (building_shaft_exhaust_air[0], building_shaft_exhaust_air[1])
                xy_values_center = [(x, y) for x, y, z, a in corner if z == z_value]

                # Entfernen Sie xy_shaft aus xy_values und xy_values_center
                xy_values = [xy for xy in xy_values if xy != xy_shaft]
                xy_values_center = [xy for xy in xy_values_center if xy != xy_shaft]

                plt.figure(num=f"Grundriss: {z_value}", figsize=(15, 8), dpi=200)
                plt.xlabel('X-Achse [m]')
                plt.ylabel('Y-Achse [m]')
                plt.grid(False)
                plt.subplots_adjust(left=0.1, bottom=0.1, right=0.96,
                                    top=0.96)

                # Plot für Schnittpunkte ohne die xy_shaft Koordinate
                plt.scatter(*zip(*xy_values), color="r", marker='o', label="Schnittpunkte")

                # Plot für den Schacht
                plt.scatter(xy_shaft[0], xy_shaft[1], color="g", marker='s', label="Schacht")

                # Plot für Lüftungsauslässe ohne die xy_shaft Koordinate
                plt.scatter(*zip(*xy_values_center), color="b", marker='D', label="Lüftungsauslässe")

                plt.title(f'Höhe: {z_value}')
                plt.legend(loc="best")

                # Setze den Pfad für den neuen Ordner
                ordner_pfad = Path(self.paths.export / 'Abluft' / "Grundrisse")

                # Erstelle den Ordner
                ordner_pfad.mkdir(parents=True, exist_ok=True)

                # Speichern des Graphens
                gesamte_bezeichnung = "Grundriss Z " + f"{z_value}" + ".png"
                pfad_plus_name = self.paths.export / 'Abluft' / "Grundrisse" / gesamte_bezeichnung
                plt.savefig(pfad_plus_name)

                # plt.show()

                plt.close()

    def visualisierung_graph(self,
                             G,
                             steiner_baum,
                             z_value,
                             coordinates_without_airflow,
                             filtered_coords_ceiling_without_airflow,
                             filtered_coords_intersection_without_airflow,
                             name,
                             einheit_kante,
                             mantelflaeche_gesamt,
                             building_shaft_exhaust_air
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
        plt.figure(figsize=(15, 8), dpi=200)
        plt.xlabel('X-Achse [m]')
        plt.ylabel('Y-Achse [m]')
        plt.title(name + f", Z: {z_value}")
        plt.grid(False)
        plt.subplots_adjust(left=0.04, bottom=0.04, right=0.96,
                            top=0.96)  # Entfernt den Rand um das Diagramm, Diagramm quasi Vollbild
        # plt.axis('equal')  # Sorgt dafür das Plot maßstabsgebtreu ist

        # Positionen der Knoten festlegen
        pos = {node: (node[0], node[1]) for node in coordinates_without_airflow}

        # Zu löschender Eintrag
        entry_to_remove = (building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], z_value)

        # Filter die Liste, um alle Einträge zu entfernen, die entry_to_remove entsprechen
        filtered_coords_ceiling_without_airflow = [entry for entry in filtered_coords_ceiling_without_airflow if
                                                   entry != entry_to_remove]

        # Knoten zeichnen
        nx.draw_networkx_nodes(G,
                               pos,
                               nodelist=filtered_coords_ceiling_without_airflow,
                               node_shape='D',
                               node_color='blue',
                               node_size=300)
        nx.draw_networkx_nodes(G,
                               pos,
                               nodelist=[(building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], z_value)],
                               node_shape="s",
                               node_color="green",
                               node_size=400)

        nx.draw_networkx_nodes(G,
                               pos,
                               nodelist=filtered_coords_intersection_without_airflow,
                               node_shape='o',
                               node_color='red',
                               node_size=50)

        # Kanten zeichnen
        nx.draw_networkx_edges(G, pos, width=1)
        nx.draw_networkx_edges(steiner_baum, pos, width=4, style="-", edge_color="blue")

        # Kantengewicht
        edge_labels = nx.get_edge_attributes(steiner_baum, 'weight')
        try:
            edge_labels_without_unit = {key: float(value.magnitude) for key, value in edge_labels.items()}
        except AttributeError:
            edge_labels_without_unit = edge_labels
        for key, value in edge_labels_without_unit.items():
            try:
                if "Ø" in value:
                    # Entfernen der Einheit und Beibehalten der Zahl nach "Ø"
                    zahl = value.split("Ø")[1].split()[0]  # Nimmt den Teil nach "Ø" und dann die Zahl vor der Einheit
                    edge_labels_without_unit[key] = f"Ø{zahl}"
                elif "x" in value:
                    # Trennen der Maße und Entfernen der Einheiten
                    zahlen = value.split(" x ")
                    breite = zahlen[0].split()[0]
                    hoehe = zahlen[1].split()[0]
                    edge_labels_without_unit[key] = f"{breite} x {hoehe}"
            except:
                None

        nx.draw_networkx_edge_labels(steiner_baum, pos, edge_labels=edge_labels_without_unit, font_size=8,
                                     font_weight=10,
                                     rotate=False)

        # Knotengewichte anzeigen
        node_labels = nx.get_node_attributes(G, 'weight')
        node_labels_without_unit = dict()
        for key, value in node_labels.items():
            try:
                node_labels_without_unit[key] = f"{value.magnitude}"
            except AttributeError:
                node_labels_without_unit[key] = ""
        nx.draw_networkx_labels(G, pos, labels=node_labels_without_unit, font_size=8, font_color="white")

        # Legende erstellen
        legend_ceiling = plt.Line2D([0], [0], marker='D', color='w', label='Deckenauslass in m³ pro h',
                                    markerfacecolor='blue',
                                    markersize=10)
        legend_intersection = plt.Line2D([0], [0], marker='o', color='w', label='Kreuzungsknoten',
                                         markerfacecolor='red', markersize=6)
        legend_shaft = plt.Line2D([0], [0], marker='s', color='w', label='Schacht',
                                  markerfacecolor='green', markersize=10)
        legend_steiner_edge = plt.Line2D([0], [0], color='blue', lw=4, linestyle='-.',
                                         label=f'Steiner-Kante in {einheit_kante}')

        # Prüfen, ob die Mantelfläche verfügbar ist
        if mantelflaeche_gesamt is not False:
            legend_mantelflaeche = plt.Line2D([0], [0], lw=0, label=f'Mantelfläche: {mantelflaeche_gesamt} [m²]')

            # Legende zum Diagramm hinzufügen, inklusive der Mantelfläche
            plt.legend(
                handles=[legend_ceiling, legend_intersection, legend_shaft, legend_steiner_edge, legend_mantelflaeche],
                loc='best')
        else:
            # Legende zum Diagramm hinzufügen, ohne die Mantelfläche
            plt.legend(handles=[legend_ceiling, legend_intersection, legend_shaft, legend_steiner_edge],
                       loc='best')  # , bbox_to_anchor=(1.1, 0.5)

        # Setze den Pfad für den neuen Ordner
        ordner_pfad = Path(self.paths.export / 'Abluft' / f"Z_{z_value}")

        # Erstelle den Ordner
        ordner_pfad.mkdir(parents=True, exist_ok=True)

        # Speichern des Graphens
        gesamte_bezeichnung = name + " Z " + f"{z_value}" + ".png"
        pfad_plus_name = self.paths.export / 'Abluft' / f"Z_{z_value}" / gesamte_bezeichnung
        plt.savefig(pfad_plus_name)

        # Anzeigen des Graphens
        # plt.show()

        # Schließen des Plotts
        plt.close()

    def visualisierung_graph_neu(self,
                                 steiner_baum,
                                 coordinates_without_airflow,
                                 z_value,
                                 name,
                                 einheit_kante
                                 ):

        # Image URLs for graph nodes
        icons = {
            "Supply air diffuser": Path(
                bim2sim.__file__).parent.parent / (
                                       'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/Zuluftdurchlass.png'),
            "Exhaust air diffuser": Path(
                bim2sim.__file__).parent.parent / (
                                        'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/Abluftdurchlass.png'),
            "gps_not_fixed": Path(
                bim2sim.__file__).parent.parent / (
                                 'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/gps_not_fixed.png'),
            "north": Path(
                bim2sim.__file__).parent.parent / (
                         'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/north.png'),
            "bar_blue": Path(
                bim2sim.__file__).parent.parent / (
                            'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/bar_blue.png'),
            "rlt": Path(
                bim2sim.__file__).parent.parent / (
                       'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/rlt.png')
        }
        # Load images
        images = {k: PIL.Image.open(fname) for k, fname in icons.items()}

        # Plot settings
        fig, ax = plt.subplots(figsize=(18, 8), dpi=300)
        fig.subplots_adjust(left=0.03, bottom=0.03, right=0.97,
                            top=0.97)  # Entfernt den Rand um das Diagramm, Diagramm quasi Vollbild
        ax.set_xlabel('X-Achse [m]')
        ax.set_ylabel('Y-Achse [m]')
        ax.set_title(name + f", Z: {z_value}")

        # Node positions
        pos = {node: (node[0], node[1]) for node in coordinates_without_airflow}

        # Note: the min_source/target_margin kwargs only work with FancyArrowPatch objects.
        # Force the use of FancyArrowPatch for edge drawing by setting `arrows=True`,
        # but suppress arrowheads with `arrowstyle="-"`
        nx.draw_networkx_edges(
            steiner_baum,
            pos=pos,
            edge_color="blue",
            ax=ax,
            arrows=True,
            arrowstyle="-",
            min_source_margin=0,
            min_target_margin=0,
        )

        # Kantengewicht
        edge_labels = nx.get_edge_attributes(steiner_baum, 'weight')
        try:
            edge_labels_without_unit = {key: float(value.magnitude) for key, value in edge_labels.items()}
        except AttributeError:
            edge_labels_without_unit = edge_labels
        for key, value in edge_labels_without_unit.items():
            try:
                if "Ø" in value:
                    # Entfernen der Einheit und Beibehalten der Zahl nach "Ø"
                    zahl = value.split("Ø")[1].split()[0]  # Nimmt den Teil nach "Ø" und dann die Zahl vor der Einheit
                    edge_labels_without_unit[key] = f"Ø{zahl}"
                elif "x" in value:
                    # Trennen der Maße und Entfernen der Einheiten
                    zahlen = value.split(" x ")
                    breite = zahlen[0].split()[0]
                    hoehe = zahlen[1].split()[0]
                    edge_labels_without_unit[key] = f"{breite} x {hoehe}"
            except:
                None

        nx.draw_networkx_edge_labels(steiner_baum, pos, edge_labels=edge_labels_without_unit, font_size=8,
                                     font_weight=10,
                                     rotate=False)

        # Zeichnen der Bilder zuerst
        for n in steiner_baum.nodes:
            if steiner_baum.nodes[n]["image"] == images["gps_not_fixed"]:
                # Transform from data coordinates (scaled between xlim and ylim) to display coordinates
                tr_figure = ax.transData.transform
                # Transform from display to figure coordinates
                tr_axes = fig.transFigure.inverted().transform

                # Select the size of the image (relative to the X axis)
                icon_size = (ax.get_xlim()[1] - ax.get_xlim()[0]) * 0.0003
                icon_center = icon_size / 2.0
                xf, yf = tr_figure(pos[n])
                xa, ya = tr_axes((xf, yf))
                # Bildpositionierung
                a = plt.axes([xa - icon_center, ya - icon_center, icon_size, icon_size], frameon=False)
                a.imshow(steiner_baum.nodes[n]["image"])
                a.axis("off")
            else:
                # Transform from data coordinates (scaled between xlim and ylim) to display coordinates
                tr_figure = ax.transData.transform
                # Transform from display to figure coordinates
                tr_axes = fig.transFigure.inverted().transform

                # Select the size of the image (relative to the X axis)
                icon_size = (ax.get_xlim()[1] - ax.get_xlim()[0]) * 0.0008
                icon_center = icon_size / 2.0
                xf, yf = tr_figure(pos[n])
                xa, ya = tr_axes((xf, yf))
                # Bildpositionierung
                a = plt.axes([xa - icon_center, ya - icon_center, icon_size, icon_size], frameon=False)
                a.imshow(steiner_baum.nodes[n]["image"])
                a.axis("off")

        node_labels = nx.get_node_attributes(steiner_baum, 'weight')
        node_labels_without_unit = dict()
        for key, value in node_labels.items():
            try:
                node_labels_without_unit[key] = f"{value.magnitude} m³/h"
            except AttributeError:
                node_labels_without_unit[key] = ""

        # Knotengewicht
        for n in steiner_baum.nodes:
            xf, yf = tr_figure(pos[n])
            xa, ya = tr_axes((xf, yf))
            # Etwas Versatz hinzufügen, um die Labels sichtbar zu machen
            ax.text(xa + 0.02, ya + 0.03, f"{node_labels_without_unit[n]}",
                    transform=fig.transFigure, ha='center', va='center',
                    fontsize=8, color="black",
                    bbox=dict(facecolor='white', alpha=0.5, edgecolor='black', boxstyle='round,pad=0.2'))

        path_bar = Path(
            bim2sim.__file__).parent.parent / (
                       'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/bar_blue.png')
        path_zuluftdurchlass = Path(
            bim2sim.__file__).parent.parent / (
                                   'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/Zuluftdurchlass.png')
        path_abluftdurchlass = Path(
            bim2sim.__file__).parent.parent / (
                                   'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/Abluftdurchlass.png')
        path_north = Path(
            bim2sim.__file__).parent.parent / (
                         'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/north.png')
        path_gps_not_fixed = Path(
            bim2sim.__file__).parent.parent / (
                                 'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/gps_not_fixed.png')
        path_rlt = Path(
            bim2sim.__file__).parent.parent / (
                       'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/rlt.png')

        # Legenden-Bilder
        legend_ax0 = fig.add_axes(
            [0.85, 0.92, 0.02, 0.02])  # Position: [links, unten, Breite, Höhe] in Figur-Koordinaten
        legend_ax0.axis('off')  # Keine Achsen für die Legenden-Achse
        img0 = mpimg.imread(path_bar)
        legend_ax0.imshow(img0)
        legend_ax0.text(1.05, 0.5, f'Kante {einheit_kante}', transform=legend_ax0.transAxes, ha='left', va='center')

        legend_ax1 = fig.add_axes(
            [0.85, 0.89, 0.02, 0.02])  # Position: [links, unten, Breite, Höhe] in Figur-Koordinaten
        legend_ax1.axis('off')  # Keine Achsen für die Legenden-Achse
        img1 = mpimg.imread(path_zuluftdurchlass)
        legend_ax1.imshow(img1)
        legend_ax1.text(1.05, 0.5, 'Zuluftdurchlass', transform=legend_ax1.transAxes, ha='left', va='center')

        legend_ax2 = fig.add_axes(
            [0.85, 0.86, 0.02, 0.02])  # Position: [links, unten, Breite, Höhe] in Figur-Koordinaten
        legend_ax2.axis('off')  # Keine Achsen für die Legenden-Achse
        img2 = mpimg.imread(path_abluftdurchlass)
        legend_ax2.imshow(img2)
        legend_ax2.text(1.05, 0.5, 'Abluftdurchlass', transform=legend_ax2.transAxes, ha='left', va='center')

        legend_ax3 = fig.add_axes(
            [0.85, 0.83, 0.02, 0.02])  # Position: [links, unten, Breite, Höhe] in Figur-Koordinaten
        legend_ax3.axis('off')  # Keine Achsen für die Legenden-Achse
        img3 = mpimg.imread(path_north)
        legend_ax3.imshow(img3)
        legend_ax3.text(1.05, 0.5, 'Schacht', transform=legend_ax3.transAxes, ha='left', va='center')

        legend_ax4 = fig.add_axes(
            [0.85, 0.8, 0.02, 0.02])  # Position: [links, unten, Breite, Höhe] in Figur-Koordinaten
        legend_ax4.axis('off')  # Keine Achsen für die Legenden-Achse
        img4 = mpimg.imread(path_gps_not_fixed)
        legend_ax4.imshow(img4)
        legend_ax4.text(1.05, 0.5, 'Steinerknoten', transform=legend_ax4.transAxes, ha='left', va='center')

        # Setze den Pfad für den neuen Ordner
        ordner_pfad = Path(self.paths.export / 'Abluft' / f"Z_{z_value}")

        # Erstelle den Ordner
        ordner_pfad.mkdir(parents=True, exist_ok=True)

        # Speichern des Graphens
        gesamte_bezeichnung = name + "_Zuluft_Z " + f"{z_value}" + ".png"
        pfad_plus_name = self.paths.export / 'Abluft' / f"Z_{z_value}" / gesamte_bezeichnung
        plt.savefig(pfad_plus_name)

        # plt.show()

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

        kanalquerschnitt = (volumenstrom / (5 * (ureg.meter / ureg.second))).to('meter**2')
        return kanalquerschnitt

    # Dimensions according to EN 1505 table 1
    df_EN_1505 = pd.DataFrame({
        "Breite": [200 * ureg.millimeter, 250 * ureg.millimeter, 300 * ureg.millimeter, 400 * ureg.millimeter,
                   500 * ureg.millimeter, 600 * ureg.millimeter, 800 * ureg.millimeter, 1000 * ureg.millimeter,
                   1200 * ureg.millimeter, 1400 * ureg.millimeter, 1600 * ureg.millimeter, 1800 * ureg.millimeter,
                   2000 * ureg.millimeter],
        100 * ureg.millimeter: [0.020 * ureg.meter ** 2, 0.025 * ureg.meter ** 2, 0.030 * ureg.meter ** 2,
                                0.040 * ureg.meter ** 2, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan,
                                np.nan, np.nan],
        150 * ureg.millimeter: [0.030 * ureg.meter ** 2, 0.038 * ureg.meter ** 2, 0.045 * ureg.meter ** 2,
                                0.060 * ureg.meter ** 2, 0.075 * ureg.meter ** 2, 0.090 * ureg.meter ** 2, np.nan,
                                np.nan, np.nan, np.nan, np.nan, np.nan, np.nan],
        200 * ureg.millimeter: [0.04 * ureg.meter ** 2, 0.05 * ureg.meter ** 2, 0.06 * ureg.meter ** 2,
                                0.08 * ureg.meter ** 2, 0.10 * ureg.meter ** 2, 0.12 * ureg.meter ** 2,
                                0.16 * ureg.meter ** 2, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan],
        250 * ureg.millimeter: [np.nan, 0.063 * ureg.meter ** 2, 0.075 * ureg.meter ** 2, 0.100 * ureg.meter ** 2,
                                0.130 * ureg.meter ** 2, 0.150 * ureg.meter ** 2, 0.200 * ureg.meter ** 2,
                                0.250 * ureg.meter ** 2, np.nan, np.nan, np.nan, np.nan, np.nan],
        300 * ureg.millimeter: [np.nan, np.nan, 0.090 * ureg.meter ** 2, 0.120 * ureg.meter ** 2,
                                0.150 * ureg.meter ** 2, 0.180 * ureg.meter ** 2, 0.240 * ureg.meter ** 2,
                                0.300 * ureg.meter ** 2, 0.360 * ureg.meter ** 2, np.nan, np.nan, np.nan, np.nan],
        400 * ureg.millimeter: [np.nan, np.nan, np.nan, 0.160 * ureg.meter ** 2, 0.200 * ureg.meter ** 2,
                                0.240 * ureg.meter ** 2, 0.320 * ureg.meter ** 2, 0.400 * ureg.meter ** 2,
                                0.480 * ureg.meter ** 2, 0.640 * ureg.meter ** 2, np.nan, np.nan, np.nan],
        500 * ureg.millimeter: [np.nan, np.nan, np.nan, np.nan, 0.250 * ureg.meter ** 2, 0.300 * ureg.meter ** 2,
                                0.400 * ureg.meter ** 2, 0.500 * ureg.meter ** 2, 0.600 * ureg.meter ** 2,
                                0.800 * ureg.meter ** 2, 1.0 * ureg.meter ** 2, np.nan, np.nan],
        600 * ureg.millimeter: [np.nan, np.nan, np.nan, np.nan, np.nan, 0.360 * ureg.meter ** 2,
                                0.480 * ureg.meter ** 2, 0.600 * ureg.meter ** 2, 0.720 * ureg.meter ** 2,
                                0.960 * ureg.meter ** 2, 1.2 * ureg.meter ** 2, 1.44 * ureg.meter ** 2, np.nan],
        800 * ureg.millimeter: [np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, 0.560 * ureg.meter ** 2,
                                0.700 * ureg.meter ** 2, 0.840 * ureg.meter ** 2, 1.120 * ureg.meter ** 2,
                                1.4 * ureg.meter ** 2, 1.68 * ureg.meter ** 2, np.nan],
        1000 * ureg.millimeter: [np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, 0.640 * ureg.meter ** 2,
                                 0.800 * ureg.meter ** 2, 0.960 * ureg.meter ** 2, 1.28 * ureg.meter ** 2,
                                 1.6 * ureg.meter ** 2, 1.92 * ureg.meter ** 2],
        1200 * ureg.millimeter: [np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan,
                                 0.900 * ureg.meter ** 2, 1.080 * ureg.meter ** 2, 1.44 * ureg.meter ** 2,
                                 1.8 * ureg.meter ** 2, 2.16 * ureg.meter ** 2],
        1400 * ureg.millimeter: [np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan,
                                 1.000 * ureg.meter ** 2, 1.20 * ureg.meter ** 2, 1.60 * ureg.meter ** 2,
                                 2.0 * ureg.meter ** 2],
        1600 * ureg.millimeter: [np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan,
                                 1.44 * ureg.meter ** 2, 1.68 * ureg.meter ** 2, 1.92 * ureg.meter ** 2],
        1800 * ureg.millimeter: [np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan,
                                 np.nan, 2.16 * ureg.meter ** 2, 2.40 * ureg.meter ** 2]
    })

    def abmessungen_eckiger_querschnitt(self, kanalquerschnitt, zwischendeckenraum=2000 * ureg.millimeter,
                                        df_EN_1505=df_EN_1505):
        """

        :param kanalquerschnitt:
        :param zwischendeckenraum:
        :return: Querschnittsabmessungen
        """
        # Erstellen einer Liste von Höhen als numerische Werte
        hoehen = pd.to_numeric(df_EN_1505.columns[1:], errors='coerce')

        # Filtern der Daten für Höhen bis zur verfügbaren Höhe im Zwischendeckenraum
        filtered_hoehen = hoehen[hoehen <= zwischendeckenraum]

        # Berechnen der Differenzen und Verhältnisse für jede Kombination
        kombinationen = []
        for index, row in df_EN_1505.iterrows():
            breite = row['Breite']
            for hoehe in filtered_hoehen:
                flaeche = row[hoehe]
                # try:
                #     flaeche_without_unit = flaeche.magnitude
                # except AttributeError:
                #     flaeche_without_unit=flaeche
                if not pd.isna(flaeche) and flaeche >= kanalquerschnitt:
                    diff = abs(flaeche - kanalquerschnitt).magnitude
                    verhaeltnis = min(breite, hoehe) / max(breite,
                                                           hoehe)  # Verhältnis als das kleinere geteilt durch das
                    # größere
                    kombinationen.append((breite, hoehe, flaeche, diff, verhaeltnis))

        # Erstellen eines neuen dataframes aus den Kombinationen
        kombinationen_df = pd.DataFrame(kombinationen,
                                        columns=['Breite', 'Hoehe', 'Flaeche', 'Diff', 'Verhaeltnis'])

        # Finden der besten Kombination
        beste_kombination_index = (kombinationen_df['Diff'] + abs(kombinationen_df['Diff'] - 1)).idxmin()
        beste_breite = kombinationen_df.at[beste_kombination_index, 'Breite']
        beste_hoehe = kombinationen_df.at[beste_kombination_index, 'Hoehe']
        querschnitt = f"{beste_breite} x {beste_hoehe}"

        return querschnitt

    def abmessungen_runder_querschnitt(self, kanalquerschnitt, zwischendeckenraum=2000 * ureg.millimeter):
        # lueftungsleitung_rund_durchmesser: Ist ein Dict, was als Eingangsgröße den Querschnitt [m²] hat und als
        # Ausgangsgröße die Durchmesser [mm] nach EN 1506:2007 (D) 4. Tabelle 1

        lueftungsleitung_rund_durchmesser = {  # 0.00312: 60, nicht lieferbar
            0.00503 * ureg.meter ** 2: 80 * ureg.millimeter,
            0.00785 * ureg.meter ** 2: 100 * ureg.millimeter,
            0.0123 * ureg.meter ** 2: 125 * ureg.millimeter,
            0.0201 * ureg.meter ** 2: 160 * ureg.millimeter,
            0.0314 * ureg.meter ** 2: 200 * ureg.millimeter,
            0.0491 * ureg.meter ** 2: 250 * ureg.millimeter,
            0.0779 * ureg.meter ** 2: 315 * ureg.millimeter,
            0.126 * ureg.meter ** 2: 400 * ureg.millimeter,
            0.196 * ureg.meter ** 2: 500 * ureg.millimeter,
            0.312 * ureg.meter ** 2: 630 * ureg.millimeter,
            0.503 * ureg.meter ** 2: 800 * ureg.millimeter,
            0.785 * ureg.meter ** 2: 1000 * ureg.millimeter,
            1.23 * ureg.meter ** 2: 1250 * ureg.millimeter
        }
        sortierte_schluessel = sorted(lueftungsleitung_rund_durchmesser.keys())
        for key in sortierte_schluessel:
            if key > kanalquerschnitt and lueftungsleitung_rund_durchmesser[key] <= zwischendeckenraum:
                return f"Ø{lueftungsleitung_rund_durchmesser[key]}"
            elif key > kanalquerschnitt and lueftungsleitung_rund_durchmesser[key] > zwischendeckenraum:
                return f"Zwischendeckenraum zu gering"

    def abmessungen_kanal(self, querschnitts_art, kanalquerschnitt, zwischendeckenraum=2000 * ureg.millimeter):
        """
        Args:
            querschnitts_art: Rund oder eckig
            kanalquerschnitt: erforderlicher Kanalquerschnitt in m²
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

        lueftungsleitung_rund_durchmesser = {  # 0.00312: 60, nicht lieferbar
            0.00503 * ureg.meter ** 2: 80 * ureg.millimeter,
            0.00785 * ureg.meter ** 2: 100 * ureg.millimeter,
            0.0123 * ureg.meter ** 2: 125 * ureg.millimeter,
            0.0201 * ureg.meter ** 2: 160 * ureg.millimeter,
            0.0314 * ureg.meter ** 2: 200 * ureg.millimeter,
            0.0491 * ureg.meter ** 2: 250 * ureg.millimeter,
            0.0779 * ureg.meter ** 2: 315 * ureg.millimeter,
            0.126 * ureg.meter ** 2: 400 * ureg.millimeter,
            0.196 * ureg.meter ** 2: 500 * ureg.millimeter,
            0.312 * ureg.meter ** 2: 630 * ureg.millimeter,
            0.503 * ureg.meter ** 2: 800 * ureg.millimeter,
            0.785 * ureg.meter ** 2: 1000 * ureg.millimeter,
            1.23 * ureg.meter ** 2: 1250 * ureg.millimeter
        }
        sortierte_schluessel = sorted(lueftungsleitung_rund_durchmesser.keys())
        for key in sortierte_schluessel:
            if key > kanalquerschnitt:
                return lueftungsleitung_rund_durchmesser[key]

    def mantelflaeche_eckiger_kanal(self, kanalquerschnitt, zwischendeckenraum=2000 * ureg.millimeter,
                                    df_EN_1505=df_EN_1505):
        # Erstellen einer Liste von Höhen als numerische Werte
        hoehen = pd.to_numeric(df_EN_1505.columns[1:], errors='coerce')

        # Filtern der Daten für Höhen bis zur maximalen Höhe
        filtered_hoehen = hoehen[hoehen <= zwischendeckenraum]

        # Berechnen der Differenzen und Verhältnisse für jede Kombination
        kombinationen = []
        for index, row in df_EN_1505.iterrows():
            breite = row['Breite']
            for hoehe in filtered_hoehen:
                flaeche = row[hoehe]
                if not pd.isna(flaeche) and flaeche >= kanalquerschnitt:
                    diff = abs(flaeche - kanalquerschnitt).magnitude
                    verhaeltnis = min(breite, hoehe) / max(breite,
                                                           hoehe)  # Verhältnis als das kleinere geteilt durch das
                    # größere
                    kombinationen.append((breite, hoehe, flaeche, diff, verhaeltnis))

        # Erstellen eines neuen dataframes aus den Kombinationen
        kombinationen_df = pd.DataFrame(kombinationen,
                                        columns=['Breite', 'Hoehe', 'Flaeche', 'Diff', 'Verhaeltnis'])

        # Finden der besten Kombination
        beste_kombination_index = (kombinationen_df['Diff'] + abs(kombinationen_df['Diff'] - 1)).idxmin()
        beste_breite = kombinationen_df.at[beste_kombination_index, 'Breite']
        beste_hoehe = kombinationen_df.at[beste_kombination_index, 'Hoehe']

        umfang = (2 * beste_breite + 2 * beste_hoehe).to(ureg.meter)

        return umfang

    def aequivalent_durchmesser(self, kanalquerschnitt, zwischendeckenraum=2000 * ureg.millimeter,
                                df_EN_1505=df_EN_1505):
        # Erstellen einer Liste von Höhen als numerische Werte
        hoehen = pd.to_numeric(df_EN_1505.columns[1:], errors='coerce')

        # Filtern der Daten für Höhen bis zur maximalen Höhe
        filtered_hoehen = hoehen[hoehen <= zwischendeckenraum]

        # Berechnen der Differenzen und Verhältnisse für jede Kombination
        kombinationen = []
        for index, row in df_EN_1505.iterrows():
            breite = row['Breite']
            for hoehe in filtered_hoehen:
                flaeche = row[hoehe]
                if not pd.isna(flaeche) and flaeche >= kanalquerschnitt:
                    diff = abs(flaeche - kanalquerschnitt).magnitude
                    verhaeltnis = min(breite, hoehe) / max(breite,
                                                           hoehe)  # Verhältnis als das kleinere geteilt durch das
                    # größere
                    kombinationen.append((breite, hoehe, flaeche, diff, verhaeltnis))

        # Erstellen eines neuen dataframes aus den Kombinationen
        kombinationen_df = pd.DataFrame(kombinationen,
                                        columns=['Breite', 'Hoehe', 'Flaeche', 'Diff', 'Verhaeltnis'])

        # Finden der besten Kombination
        beste_kombination_index = (kombinationen_df['Diff'] + abs(kombinationen_df['Diff'] - 1)).idxmin()
        beste_breite = kombinationen_df.at[beste_kombination_index, 'Breite']
        beste_hoehe = kombinationen_df.at[beste_kombination_index, 'Hoehe']

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
            return (math.pi * self.durchmesser_runder_kanal(kanalquerschnitt)).to(ureg.meter)

        elif querschnitts_art == "eckig":
            return self.mantelflaeche_eckiger_kanal(kanalquerschnitt)

        elif querschnitts_art == "optimal":
            if self.durchmesser_runder_kanal(kanalquerschnitt) <= zwischendeckenraum:
                return (math.pi * self.durchmesser_runder_kanal(kanalquerschnitt)).to(ureg.meter)
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
        ordner_pfad = Path(self.paths.export / 'Abluft' / "Schacht")

        # Erstelle den Ordner
        ordner_pfad.mkdir(parents=True, exist_ok=True)

        # Speichern des Graphens
        gesamte_bezeichnung = name + ".png"
        pfad_plus_name = self.paths.export / 'Abluft' / "Schacht" / gesamte_bezeichnung
        plt.savefig(pfad_plus_name)

        # Anzeigen des Graphens
        # plt.show()

        # Schließen des Plotts
        plt.close()

    def plot_schacht_neu(self, steiner_baum,
                         name,
                         einheit_kante
                         ):

        # Image URLs for graph nodes
        icons = {
            "Supply air diffuser": Path(
                bim2sim.__file__).parent.parent / (
                                       'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/Zuluftdurchlass.png'),
            "Exhaust air diffuser": Path(
                bim2sim.__file__).parent.parent / (
                                        'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/Abluftdurchlass.png'),
            "gps_not_fixed": Path(
                bim2sim.__file__).parent.parent / (
                                 'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/gps_not_fixed.png'),
            "north": Path(
                bim2sim.__file__).parent.parent / (
                         'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/north.png'),
            "bar_blue": Path(
                bim2sim.__file__).parent.parent / (
                            'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/bar_blue.png'),
            "rlt": Path(
                bim2sim.__file__).parent.parent / (
                       'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/rlt.png')
        }
        # Load images
        images = {k: PIL.Image.open(fname) for k, fname in icons.items()}

        # Plot settings
        fig, ax = plt.subplots(figsize=(12, 10), dpi=300)
        fig.subplots_adjust(left=0.03, bottom=0.03, right=0.97,
                            top=0.97)  # Entfernt den Rand um das Diagramm, Diagramm quasi Vollbild
        ax.set_xlabel('X-Achse [m]')
        ax.set_ylabel('Y-Achse [m]')
        ax.set_title(name)

        # Node positions
        pos = {node: (node[0], node[2]) for node in steiner_baum.nodes()}

        # Note: the min_source/target_margin kwargs only work with FancyArrowPatch objects.
        # Force the use of FancyArrowPatch for edge drawing by setting `arrows=True`,
        # but suppress arrowheads with `arrowstyle="-"`
        nx.draw_networkx_edges(
            steiner_baum,
            pos=pos,
            edge_color="blue",
            ax=ax,
            arrows=True,
            arrowstyle="-",
            min_source_margin=0,
            min_target_margin=0,
        )

        # Kantengewicht
        edge_labels = nx.get_edge_attributes(steiner_baum, 'weight')
        try:
            edge_labels_without_unit = {key: float(value.magnitude) for key, value in edge_labels.items()}
        except AttributeError:
            edge_labels_without_unit = edge_labels
        nx.draw_networkx_edge_labels(steiner_baum, pos, edge_labels=edge_labels_without_unit, font_size=8,
                                     font_weight=10,
                                     rotate=False)

        # Zeichnen der Bilder
        for n in steiner_baum.nodes:
            if steiner_baum.nodes[n]["image"] == images["rlt"]:
                # Transform from data coordinates (scaled between xlim and ylim) to display coordinates
                tr_figure = ax.transData.transform
                # Transform from display to figure coordinates
                tr_axes = fig.transFigure.inverted().transform

                # Select the size of the image (relative to the X axis)
                icon_size = (ax.get_xlim()[1] - ax.get_xlim()[0]) * 0.003
                icon_center = icon_size / 2.0
                xf, yf = tr_figure(pos[n])
                xa, ya = tr_axes((xf, yf))

                # Bildpositionierung
                a = plt.axes([xa - icon_center, ya - icon_center, 5 * icon_size, 5 * icon_size], frameon=False)
                a.imshow(steiner_baum.nodes[n]["image"])
                a.axis("off")
            else:
                # Transform from data coordinates (scaled between xlim and ylim) to display coordinates
                tr_figure = ax.transData.transform
                # Transform from display to figure coordinates
                tr_axes = fig.transFigure.inverted().transform

                # Select the size of the image (relative to the X axis)
                icon_size = (ax.get_xlim()[1] - ax.get_xlim()[0]) * 0.0008
                icon_center = icon_size / 2.0
                xf, yf = tr_figure(pos[n])
                xa, ya = tr_axes((xf, yf))
                # Bildpositionierung
                a = plt.axes([xa - icon_center, ya - icon_center, icon_size, icon_size], frameon=False)
                a.imshow(steiner_baum.nodes[n]["image"])
                a.axis("off")

        node_labels = nx.get_node_attributes(steiner_baum, 'weight')
        node_labels_without_unit = dict()
        for key, value in node_labels.items():
            try:
                node_labels_without_unit[key] = f"{value.magnitude} m³"
            except AttributeError:
                node_labels_without_unit[key] = ""

        # Knotengewicht
        for n in steiner_baum.nodes:
            xf, yf = tr_figure(pos[n])
            xa, ya = tr_axes((xf, yf))
            # Etwas Versatz hinzufügen, um die Labels sichtbar zu machen
            ax.text(xa + 0.03, ya + 0.04, f"{node_labels_without_unit[n]}",
                    transform=fig.transFigure, ha='center', va='center',
                    fontsize=8, color="black",
                    bbox=dict(facecolor='white', alpha=0.5, edgecolor='black', boxstyle='round,pad=0.2'))

        path_bar = Path(
            bim2sim.__file__).parent.parent / (
                       'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/bar_blue.png')
        path_zuluftdurchlass = Path(
            bim2sim.__file__).parent.parent / (
                                   'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/Zuluftdurchlass.png')
        path_abluftdurchlass = Path(
            bim2sim.__file__).parent.parent / (
                                   'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/Abluftdurchlass.png')
        path_north = Path(
            bim2sim.__file__).parent.parent / (
                         'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/north.png')
        path_gps_not_fixed = Path(
            bim2sim.__file__).parent.parent / (
                                 'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/gps_not_fixed.png')
        path_rlt = Path(
            bim2sim.__file__).parent.parent / (
                       'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/rlt.png')

        # Legenden-Bilder
        legend_ax0 = fig.add_axes(
            [1 - 0.85, 0.92, 0.02, 0.02])  # Position: [links, unten, Breite, Höhe] in Figur-Koordinaten
        legend_ax0.axis('off')  # Keine Achsen für die Legenden-Achse
        img0 = mpimg.imread(path_bar)
        legend_ax0.imshow(img0)
        legend_ax0.text(1.05, 0.5, f'Kante {einheit_kante}', transform=legend_ax0.transAxes, ha='left', va='center')

        legend_ax1 = fig.add_axes(
            [1 - 0.85, 0.89, 0.02, 0.02])  # Position: [links, unten, Breite, Höhe] in Figur-Koordinaten
        legend_ax1.axis('off')  # Keine Achsen für die Legenden-Achse
        img1 = mpimg.imread(path_zuluftdurchlass)
        legend_ax1.imshow(img1)
        legend_ax1.text(1.05, 0.5, 'Zuluftdurchlass', transform=legend_ax1.transAxes, ha='left', va='center')

        legend_ax2 = fig.add_axes(
            [1 - 0.85, 0.86, 0.02, 0.02])  # Position: [links, unten, Breite, Höhe] in Figur-Koordinaten
        legend_ax2.axis('off')  # Keine Achsen für die Legenden-Achse
        img2 = mpimg.imread(path_abluftdurchlass)
        legend_ax2.imshow(img2)
        legend_ax2.text(1.05, 0.5, 'Abluftdurchlass', transform=legend_ax2.transAxes, ha='left', va='center')

        legend_ax3 = fig.add_axes(
            [1 - 0.85, 0.83, 0.02, 0.02])  # Position: [links, unten, Breite, Höhe] in Figur-Koordinaten
        legend_ax3.axis('off')  # Keine Achsen für die Legenden-Achse
        img3 = mpimg.imread(path_north)
        legend_ax3.imshow(img3)
        legend_ax3.text(1.05, 0.5, 'Schacht', transform=legend_ax3.transAxes, ha='left', va='center')

        legend_ax4 = fig.add_axes(
            [1 - 0.85, 0.8, 0.02, 0.02])  # Position: [links, unten, Breite, Höhe] in Figur-Koordinaten
        legend_ax4.axis('off')  # Keine Achsen für die Legenden-Achse
        img4 = mpimg.imread(path_gps_not_fixed)
        legend_ax4.imshow(img4)
        legend_ax4.text(1.05, 0.5, 'Steinerknoten', transform=legend_ax4.transAxes, ha='left', va='center')

        legend_ax5 = fig.add_axes(
            [1 - 0.85, 0.77, 0.02, 0.02])  # Position: [links, unten, Breite, Höhe] in Figur-Koordinaten
        legend_ax5.axis('off')  # Keine Achsen für die Legenden-Achse
        img5 = mpimg.imread(path_rlt)
        legend_ax5.imshow(img5)
        legend_ax5.text(1.05, 0.5, 'RLT-Anlage', transform=legend_ax5.transAxes, ha='left', va='center')

        # Setze den Pfad für den neuen Ordner
        ordner_pfad = Path(self.paths.export / 'Abluft' / "Schacht")

        # Erstelle den Ordner
        ordner_pfad.mkdir(parents=True, exist_ok=True)

        # Speichern des Graphens
        gesamte_bezeichnung = name + ".png"
        pfad_plus_name = self.paths.export / 'Abluft' / "Schacht" / gesamte_bezeichnung
        plt.savefig(pfad_plus_name)

        # plt.show()

        plt.close()

    def find_leaves(self, spanning_tree):
        leaves = []
        for node in spanning_tree:
            if len(spanning_tree[node]) == 1:  # Ein Blatt hat nur einen Nachbarn
                leaves.append(node)
        return leaves

    def find_collisions(self, supply_graph, exhaust_graph):
        def orientation(p, q, r):
            """Get orientation of triples (p, q, r)
            Returns:
            0 -> p, q and r are colinear
            1 -> Clockwise
            2 -> Anti-clockwise
            """
            val = (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])
            if val == 0:
                return 0  # kollinear
            elif val > 0:
                return 1  # im Uhrzeigersinn
            else:
                return 2  # gegen den Uhrzeigersinn

        def find_crossing_edges(p1, q1, p2, q2):
            """Check if edges (p1, q1) and (p2, q2) are cutting each other"""
            o1 = orientation(p1, q1, p2)
            o2 = orientation(p1, q1, q2)
            o3 = orientation(p2, q2, p1)
            o4 = orientation(p2, q2, q1)

            if o1 != o2 and o3 != o4:
                return True
            return False

        def crossing_point(p1, q1, p2, q2):
            """Calculate crossing point of edges (p1, q1) and (p2, q2)"""
            A1 = q1[1] - p1[1]
            B1 = p1[0] - q1[0]
            C1 = A1 * p1[0] + B1 * p1[1]

            A2 = q2[1] - p2[1]
            B2 = p2[0] - q2[0]
            C2 = A2 * p2[0] + B2 * p2[1]

            determinant = A1 * B2 - A2 * B1

            if determinant == 0:
                return None
            else:
                # Berechnung des Schnittpunkts
                x = (B2 * C1 - B1 * C2) / determinant
                y = (A1 * C2 - A2 * C1) / determinant
                return (x, y)

        colinear_edges = set(supply_graph.edges()) & set(exhaust_graph.edges())

        crossing_edges = []
        crossing_points = []
        for (u1, v1) in exhaust_graph.edges():
            for (u2, v2) in supply_graph.edges():
                if find_crossing_edges(u1, v1, u2, v2) and (u1, v1) not in crossing_edges:
                    cross_point = crossing_point(u1, v1, u2, v2)
                    if (cross_point not in (u2, v2)) or \
                        (cross_point == u2 and supply_graph.degree[u2] != 1) or \
                        (cross_point == v2 and supply_graph.degree[v2] != 1):
                            crossing_edges.append(((u2, v2),(u1,v1)))
                            crossing_points.append(cross_point)

        return colinear_edges, crossing_edges, crossing_points

    def minimize_collisions_with_supply_graph(self, supply_graph, exhaust_graph, terminal_nodes):

        colinear_edges, crossing_edges, crossing_points = self.find_collisions(supply_graph, exhaust_graph)
        exhaust_crossing_edges = [edge[0] for edge in crossing_edges]

        exhaust_graph.remove_edges_from(colinear_edges)
        exhaust_graph.remove_edges_from(exhaust_crossing_edges)

        if not nx.is_connected(exhaust_graph):

            not_connected_terminal_nodes = []
            for terminal_node in terminal_nodes:
                if not exhaust_graph.edges(terminal_node):
                    not_connected_terminal_nodes.append(terminal_node)

            new_nodes = []
            for terminal_node in not_connected_terminal_nodes:
                deleted_edges_from_terminal_node = [edge for edge in exhaust_crossing_edges if terminal_node in [edge[0],edge[1]]]
                for edge in deleted_edges_from_terminal_node:
                    exhaust_graph.add_edge(edge[0], edge[1], weight=self.euklidische_distanz(edge[0], edge[1]))
                    for node in edge:
                        if node != terminal_node:
                            new_nodes.append(node)

        if not all(element in list(nx.connected_components(exhaust_graph))[0] for element in terminal_nodes):

            trigger = True
            i = 0
            while trigger:
                i += 1
                new_new_nodes = []
                for node in new_nodes:
                    edges_to_be_added_again = [edge for edge in exhaust_crossing_edges if node in [edge[0], edge[1]] and
                                               edge not in exhaust_graph.edges()]
                    for edge in edges_to_be_added_again:
                        exhaust_graph.add_edge(edge[0], edge[1], weight=self.euklidische_distanz(edge[0], edge[1]))
                        for new_node in edge:
                            if new_node != node:
                                new_new_nodes.append(new_node)
                new_nodes = new_new_nodes

                if all(element in list(nx.connected_components(exhaust_graph))[0] for element in terminal_nodes):
                    trigger = False

                if i == 200:
                    assert KeyError("Exhaust graph cannot be connected properly!")

        exhaust_graph = exhaust_graph.subgraph(list(list(nx.connected_components(exhaust_graph))[0]))

        return exhaust_graph


    def create_graph(self, ceiling_point, intersection_points, z_coordinate_list, building_shaft_exhaust_air,
                     querschnittsart, zwischendeckenraum, export_graphen):
        """The function creates a connected graph for each floor
        Args:
           ceiling_point: Point at the ceiling in the middle of the room
           intersection points: intersection points at the ceiling
           z_coordinate_list: z coordinates for each storey ceiling
           building_shaft_exhaust_air: Coordinate of the shaft
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

        # Image URLs for graph nodes
        icons = {
            "Supply air diffuser": Path(
                bim2sim.__file__).parent.parent / (
                                       'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/Zuluftdurchlass.png'),
            "Exhaust air diffuser": Path(
                bim2sim.__file__).parent.parent / (
                                        'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/Abluftdurchlass.png'),
            "gps_not_fixed": Path(
                bim2sim.__file__).parent.parent / (
                                 'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/gps_not_fixed.png'),
            "north": Path(
                bim2sim.__file__).parent.parent / (
                         'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/north.png'),
            "bar_blue": Path(
                bim2sim.__file__).parent.parent / (
                            'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/bar_blue.png'),
            "rlt": Path(
                bim2sim.__file__).parent.parent / (
                       'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/rlt.png')
        }
        # Load images
        images = {k: PIL.Image.open(fname) for k, fname in icons.items()}

        # Hier werden leere Dictonaries für die einzelnen Höhen erstellt:
        dict_steinerbaum_mit_leitungslaenge = {schluessel: None for schluessel in z_coordinate_list}
        dict_steiner_tree_with_air_volume_exhaust_air = {schluessel: None for schluessel in z_coordinate_list}
        dict_steinerbaum_mit_kanalquerschnitt = {schluessel: None for schluessel in z_coordinate_list}
        dict_steinerbaum_mit_rechnerischem_querschnitt = {schluessel: None for schluessel in z_coordinate_list}
        dict_steinerbaum_mit_mantelflaeche = {schluessel: None for schluessel in z_coordinate_list}

        for z_value in z_coordinate_list:

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
                if x == building_shaft_exhaust_air[0] and y == building_shaft_exhaust_air[1]:
                    G.add_node((x, y, z), weight=a, image=images["north"])
                else:
                    G.add_node((x, y, z), weight=a, image=images["Exhaust air diffuser"])
                if a > 0:  # Bedingung, um Terminals zu bestimmen (z.B. Gewicht > 0)
                    terminals.append((x, y, z))

            for x, y, z, a in filtered_coords_intersection:
                G.add_node((x, y, z), weight=0, image=images["gps_not_fixed"])

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

            # TODO Checke Kollisionen mit Zuluftgraph und lösche entsprechende Kanten im Abluftgraph

            G = self.minimize_collisions_with_supply_graph(self.supply_graph, G, terminals)


            # Erstellung des Steinerbaums
            steiner_baum = steiner_tree(G, terminals, weight="weight")

            if export_graphen == True:
                self.visualisierung_graph(steiner_baum,
                                          steiner_baum,
                                          z_value,
                                          coordinates_without_airflow,
                                          filtered_coords_ceiling_without_airflow,
                                          filtered_coords_intersection_without_airflow,
                                          name=f"Steinerbaum 0. Optimierung",
                                          einheit_kante="m",
                                          mantelflaeche_gesamt=False,
                                          building_shaft_exhaust_air=building_shaft_exhaust_air
                                          )

            # if export_graphen == True:
            #     self.visualisierung_graph_neu(steiner_baum,
            #                                   coordinates_without_airflow,
            #                                   z_value,
            #                                   name=f"Steinerbaum 0. Optimierung",
            #                                   einheit_kante="[m]"
            #                                   )

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

            if export_graphen == True:
                self.visualisierung_graph(steiner_baum,
                                          steiner_baum,
                                          z_value,
                                          coordinates_without_airflow,
                                          filtered_coords_ceiling_without_airflow,
                                          filtered_coords_intersection_without_airflow,
                                          name=f"Steinerbaum 1. Optimierung",
                                          einheit_kante="m",
                                          mantelflaeche_gesamt=False,
                                          building_shaft_exhaust_air=building_shaft_exhaust_air
                                          )

            # if export_graphen == True:
            #     self.visualisierung_graph_neu(steiner_baum,
            #                                   coordinates_without_airflow,
            #                                   z_value,
            #                                   name=f"Steinerbaum 1. Optimierung",
            #                                   einheit_kante="m"
            #                                   )

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
                                          einheit_kante="m",
                                          mantelflaeche_gesamt=False,
                                          building_shaft_exhaust_air=building_shaft_exhaust_air
                                          )

            # if export_graphen == True:
            #     self.visualisierung_graph_neu(steiner_baum,
            #                                   coordinates_without_airflow,
            #                                   z_value,
            #                                   name=f"Steinerbaum 2. Optimierung",
            #                                   einheit_kante="m"
            #                                   )

            """3. Optimierung"""
            # Hier werden die Blätter aus dem Graphen ausgelesen
            blaetter = self.find_leaves(steiner_baum)

            # Entfernen der Blätter die kein Lüftungsauslass sind
            for blatt in blaetter:
                if blatt not in filtered_coords_ceiling_without_airflow:
                    terminals.remove(blatt)

            # Erstellung des neuen Steinerbaums
            steiner_baum = steiner_tree(G, terminals, weight="weight")

            # Add unit
            for u, v, data in steiner_baum.edges(data=True):
                gewicht_ohne_einheit = data['weight']

                # Füge die Einheit meter hinzu
                gewicht_mit_einheit = gewicht_ohne_einheit * ureg.meter

                # Aktualisiere das Gewicht der Kante im Steinerbaum
                data['weight'] = gewicht_mit_einheit

            if export_graphen == True:
                self.visualisierung_graph(steiner_baum,
                                          steiner_baum,
                                          z_value,
                                          coordinates_without_airflow,
                                          filtered_coords_ceiling_without_airflow,
                                          filtered_coords_intersection_without_airflow,
                                          name=f"Steinerbaum 3. Optimierung",
                                          einheit_kante="m",
                                          mantelflaeche_gesamt=False,
                                          building_shaft_exhaust_air=building_shaft_exhaust_air
                                          )

            # if export_graphen == True:
            #     self.visualisierung_graph_neu(steiner_baum,
            #                                   coordinates_without_airflow,
            #                                   z_value,
            #                                   name=f"Steinerbaum 3. Optimierung",
            #                                   einheit_kante="[m]"
            #                                   )

            # Steinerbaum mit Leitungslängen
            dict_steinerbaum_mit_leitungslaenge[z_value] = deepcopy(steiner_baum)

            # Hier wird der Startpunt zu den Blättern gesetzt
            start_punkt = (building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], z_value)

            # Erstellung des Baums (hier wird der neue, erste verbesserte Baum erstellt! Die Punkte, welche alle
            # zwischen zwei Lüftungsauslässen liegen, werden genutzt, um andere Kanäle auch über die gleich
            # Achse zu verlegen

            # Extraierung der Knoten und Kanten aus dem Steinerbaum
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
                    wert = None
                    for x, y, z, a in coordinates:
                        if x == ceiling_point_to_root[0][0][0] and y == ceiling_point_to_root[0][0][1] and z == \
                                ceiling_point_to_root[0][0][2]:
                            wert = a
                    G[startpunkt][zielpunkt]["weight"] += wert

            # Hier wird der einzelne Steinerbaum mit Volumenstrom der Liste hinzugefügt
            dict_steiner_tree_with_air_volume_exhaust_air[z_value] = deepcopy(steiner_baum)

            if export_graphen == True:
                self.visualisierung_graph(steiner_baum,
                                          steiner_baum,
                                          z_value,
                                          coordinates_without_airflow,
                                          filtered_coords_ceiling_without_airflow,
                                          filtered_coords_intersection_without_airflow,
                                          name=f"Steinerbaum mit Luftmenge m³ pro h",
                                          einheit_kante="m³/h",
                                          mantelflaeche_gesamt=False,
                                          building_shaft_exhaust_air=building_shaft_exhaust_air
                                          )
            #
            # if export_graphen == True:
            #     self.visualisierung_graph_neu(steiner_baum,
            #                                   coordinates_without_airflow,
            #                                   z_value,
            #                                   name=f"Steinerbaum mit Luftmenge m³ pro h",
            #                                   einheit_kante="m³/h"
            #                                   )

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
                                          name=f"Steinerbaum mit Kanalquerschnitt in mm",
                                          einheit_kante="mm",
                                          mantelflaeche_gesamt=False,
                                          building_shaft_exhaust_air=building_shaft_exhaust_air
                                          )

            # if export_graphen == True:
            #     self.visualisierung_graph_neu(H_leitungsgeometrie,
            #                                   coordinates_without_airflow,
            #                                   z_value,
            #                                   name=f"Steinerbaum mit Kanalquerschnitt in mm",
            #                                   einheit_kante="mm"
            #                                   )

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
                                          name=f"Steinerbaum mit rechnerischem Durchmesser in mm",
                                          einheit_kante="mm",
                                          mantelflaeche_gesamt=False,
                                          building_shaft_exhaust_air=building_shaft_exhaust_air
                                          )
            #
            # if export_graphen == True:
            #     self.visualisierung_graph_neu(H_aequivalenter_durchmesser,
            #                                   coordinates_without_airflow,
            #                                   z_value,
            #                                   name=f"Steinerbaum mit rechnerischem Durchmesser in mm",
            #                                   einheit_kante="mm"
            #                                   )

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
                                          einheit_kante="m²/m",
                                          mantelflaeche_gesamt="",
                                          building_shaft_exhaust_air=building_shaft_exhaust_air
                                          )

            # if export_graphen == True:
            #     self.visualisierung_graph_neu(steiner_baum,
            #                                   coordinates_without_airflow,
            #                                   z_value,
            #                                   name=f"Steinerbaum mit Mantelfläche",
            #                                   einheit_kante="[m²/m]"
            #                                   )

        # except ValueError as e:
        #     if str(e) == "attempt to get argmin of an empty sequence":
        #         self.logger.info("Zwischendeckenraum zu gering gewählt!")
        #         exit()
        #         # TODO wie am besten?

        return (
            dict_steinerbaum_mit_leitungslaenge, dict_steinerbaum_mit_kanalquerschnitt, dict_steiner_tree_with_air_volume_exhaust_air,
            dict_steinerbaum_mit_mantelflaeche, dict_steinerbaum_mit_rechnerischem_querschnitt)

    def rlt_schacht(self,
                    z_coordinate_list,
                    building_shaft_exhaust_air,
                    airflow_volume_per_storey,
                    position_rlt,
                    dict_steiner_tree_with_duct_length,
                    dict_steiner_tree_with_duct_cross_section,
                    dict_steiner_tree_with_air_volume,
                    dict_steiner_tree_with_sheath_area,
                    dict_steiner_tree_with_calculated_cross_section,
                    export_graphen
                    ):

        # Image URLs for graph nodes
        icons = {
            "Supply air diffuser": Path(
                bim2sim.__file__).parent.parent / (
                                       'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/Zuluftdurchlass.png'),
            "Exhaust air diffuser": Path(
                bim2sim.__file__).parent.parent / (
                                        'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/Abluftdurchlass.png'),
            "gps_not_fixed": Path(
                bim2sim.__file__).parent.parent / (
                                 'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/gps_not_fixed.png'),
            "north": Path(
                bim2sim.__file__).parent.parent / (
                         'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/north.png'),
            "bar_blue": Path(
                bim2sim.__file__).parent.parent / (
                            'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/bar_blue.png'),
            "rlt": Path(
                bim2sim.__file__).parent.parent / (
                       'bim2sim/plugins/PluginVentilationSystem/bim2sim_ventilationsystem/assets/rlt.png')
        }
        # Load images
        images = {k: PIL.Image.open(fname) for k, fname in icons.items()}

        nodes_schacht = list()
        z_coordinate_list = list(z_coordinate_list)
        # Ab hier wird er Graph für das RLT-Gerät bis zum Schacht erstellt.
        Schacht = nx.Graph()

        for z_value in z_coordinate_list:
            # Hinzufügen der Knoten
            Schacht.add_node((building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], z_value),
                             weight=airflow_volume_per_storey[z_value], image=images["north"])
            nodes_schacht.append((building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], z_value,
                                  airflow_volume_per_storey[z_value]))

        # Ab hier wird der Graph über die Geschosse hinweg erstellt:
        # Kanten für Schacht hinzufügen:
        for i in range(len(z_coordinate_list) - 1):
            weight = self.euklidische_distanz(
                [building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], float(z_coordinate_list[i])],
                [building_shaft_exhaust_air[0], building_shaft_exhaust_air[1],
                 float(z_coordinate_list[i + 1])]) * ureg.meter
            Schacht.add_edge((building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], z_coordinate_list[i]),
                             (building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], z_coordinate_list[i + 1]),
                             weight=weight)

        # Summe Airflow
        summe_airflow = sum(airflow_volume_per_storey.values())

        # Knoten der RLT-Anlage mit Gesamtluftmenge anreichern
        Schacht.add_node((position_rlt[0], position_rlt[1], position_rlt[2]),
                         weight=summe_airflow, image=images["rlt"])

        Schacht.add_node((building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], position_rlt[2]),
                         weight=summe_airflow, image=images["north"])

        # Verbinden der RLT Anlage mit dem Schacht
        rlt_schacht_weight = self.euklidische_distanz([position_rlt[0], position_rlt[1], position_rlt[2]],
                                                      [building_shaft_exhaust_air[0], building_shaft_exhaust_air[1],
                                                       position_rlt[2]]
                                                      ) * ureg.meter

        Schacht.add_edge((position_rlt[0], position_rlt[1], position_rlt[2]),
                         (building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], position_rlt[2]),
                         weight=rlt_schacht_weight)

        # Wenn die RLT nicht in der Ebene einer Decke liegt, muss die Luftleitung noch mit dem Schacht verbunden werden
        list_schacht_nodes = list(Schacht.nodes())
        closest = None
        min_distance = float('inf')

        for coord in list_schacht_nodes:
            # Skip if it's the same coordinate
            if coord == (building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], position_rlt[2]):
                continue
            # Check if the x and y coordinates are the same
            if coord[0] == building_shaft_exhaust_air[0] and coord[1] == building_shaft_exhaust_air[1]:
                distance = abs(coord[2] - position_rlt[2])
                if distance < min_distance:
                    min_distance = distance
                    closest = coord

        verbindung_weight = self.euklidische_distanz(
            [building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], position_rlt[2]],
            closest
        ) * ureg.meter
        Schacht.add_edge((building_shaft_exhaust_air[0], building_shaft_exhaust_air[1], position_rlt[2]),
                         closest,
                         weight=verbindung_weight)

        # Zum Dict hinzufügen
        dict_steiner_tree_with_duct_length["Schacht"] = deepcopy(Schacht)

        # Visualisierung Schacht
        if export_graphen == True:
            self.plot_schacht_neu(Schacht, name="Schacht", einheit_kante="[m]")

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
                        wert = a
                Schacht[startpunkt][zielpunkt]["weight"] += wert

        # Zum Dict hinzufügen
        dict_steiner_tree_with_air_volume["Schacht"] = deepcopy(Schacht)

        # Visualisierung Schacht
        if export_graphen == True:
            self.plot_schacht_neu(Schacht, name="Schacht mit Luftvolumina", einheit_kante="[m3/h]")

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
        dict_steiner_tree_with_duct_cross_section["Schacht"] = deepcopy(Schacht_leitungsgeometrie)

        # Visualisierung Schacht
        if export_graphen == True:
            self.plot_schacht_neu(Schacht_leitungsgeometrie, name="Schacht mit Querschnitt", einheit_kante="")

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
        dict_steiner_tree_with_sheath_area["Schacht"] = deepcopy(Schacht)

        # Visualisierung Schacht
        if export_graphen == True:
            self.plot_schacht_neu(Schacht, name="Schacht mit Mantelfläche", einheit_kante="[m2/m]")

        # Hier wird der Leitung der äquivalente Durchmesser des Kanals zugeordnet
        for u, v in Schacht_rechnerischer_durchmesser.edges():
            Schacht_rechnerischer_durchmesser[u][v]["weight"] = self.rechnerischer_durchmesser("eckig",
                                                                                               self.notwendiger_kanaldquerschnitt(
                                                                                                   Schacht_rechnerischer_durchmesser[
                                                                                                       u][v]["weight"]),
                                                                                               zwischendeckenraum=2000
                                                                                               )

        # Zum Dict hinzufügen
        dict_steiner_tree_with_calculated_cross_section["Schacht"] = deepcopy(Schacht_rechnerischer_durchmesser)

        # Visualisierung Schacht
        if export_graphen == True:
            self.plot_schacht_neu(Schacht_rechnerischer_durchmesser, name="Schacht mit rechnerischem Durchmesser",
                                  einheit_kante="[mm]")

        return (dict_steiner_tree_with_duct_length,
                dict_steiner_tree_with_duct_cross_section,
                dict_steiner_tree_with_air_volume,
                dict_steiner_tree_with_sheath_area,
                dict_steiner_tree_with_calculated_cross_section)

    def finde_abmessung(self, text: str):
        if "Ø" in text:
            # Fall 1: "Ø" gefolgt von einer Zahl
            zahl = ureg(text.split("Ø")[1])  # Teilt den String am "Ø" und nimmt den zweiten Teil
            return zahl
        else:
            # Fall 2: "250 x 200" Format
            zahlen = text.split(" x ")  # Teilt den String bei " x "
            breite = ureg(zahlen[0])
            hoehe = ureg(zahlen[1])
            return breite, hoehe

    def drei_dimensionaler_graph(self,
                                 dict_steinerbaum_mit_leitungslaenge,
                                 dict_steinerbaum_mit_kanalquerschnitt,
                                 dict_steiner_tree_with_air_volume_exhaust_air,
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

        # für Luftmengen
        for baum in dict_steiner_tree_with_air_volume_exhaust_air.values():
            graph_luftmengen = nx.compose(graph_luftmengen, baum)

        # Graph für Luftmengen in einen gerichteten Graphen umwandeln
        graph_luftmengen_gerichtet = nx.DiGraph()
        add_edges_and_nodes(graph_luftmengen_gerichtet, position_rlt, graph_luftmengen)

        # für Kanalquerschnitt
        for baum in dict_steinerbaum_mit_kanalquerschnitt.values():
            graph_kanalquerschnitt = nx.compose(graph_kanalquerschnitt, baum)

        # Graph für Kanalquerschnitt in einen gerichteten Graphen umwandeln
        graph_kanalquerschnitt_gerichtet = nx.DiGraph()
        add_edges_and_nodes(graph_kanalquerschnitt_gerichtet, position_rlt, graph_kanalquerschnitt)

        # für Mantelfläche
        for baum in dict_steinerbaum_mit_mantelflaeche.values():
            graph_mantelflaeche = nx.compose(graph_mantelflaeche, baum)

        # Graph für Mantelfläche in einen gerichteten Graphen umwandeln
        graph_mantelflaeche_gerichtet = nx.DiGraph()
        add_edges_and_nodes(graph_mantelflaeche_gerichtet, position_rlt, graph_mantelflaeche)

        # für rechnerischen Querschnitt
        for baum in dict_steinerbaum_mit_rechnerischem_querschnitt.values():
            graph_rechnerischer_durchmesser = nx.compose(graph_rechnerischer_durchmesser, baum)

        # Graph für rechnerischen Querschnitt in einen gerichteten Graphen umwandeln
        graph_rechnerischer_durchmesser_gerichtet = nx.DiGraph()
        add_edges_and_nodes(graph_rechnerischer_durchmesser_gerichtet, position_rlt, graph_rechnerischer_durchmesser)

        dataframe_distribution_network_exhaust_air = pd.DataFrame(columns=[
            'Startknoten',
            'Zielknoten',
            'Kante',
            'Raumart Startknoten',
            'Raumart Zielknoten',
            'Leitungslänge',
            'Luftmenge',
            'Kanalquerschnitt',
            'Mantelfläche',
            'rechnerischer Durchmesser'
        ])

        # Daten der Datenbank hinzufügen
        for u, v in graph_leitungslaenge_gerichtet.edges():
            temp_df = pd.DataFrame({
                'Startknoten': [v],  # Gedreht da Abluft
                'Zielknoten': [u],  # Gedreht da Abluft
                'Kante': [(v, u)],  # Gedreht da Abluft
                'Raumart Startknoten': [dict_koordinate_mit_raumart.get(v, None)],
                'Raumart Zielknoten': [dict_koordinate_mit_raumart.get(u, None)],
                'Leitungslänge': [graph_leitungslaenge_gerichtet.get_edge_data(u, v)["weight"]],
                'Luftmenge': [graph_luftmengen_gerichtet.get_edge_data(u, v)["weight"]],
                'Kanalquerschnitt': [graph_kanalquerschnitt_gerichtet.get_edge_data(u, v)["weight"]],
                'Mantelfläche': [graph_mantelflaeche_gerichtet.get_edge_data(u, v)["weight"] *
                                 graph_leitungslaenge_gerichtet.get_edge_data(u, v)["weight"]],
                'rechnerischer Durchmesser': [graph_rechnerischer_durchmesser_gerichtet.get_edge_data(u, v)["weight"]]
            })
            dataframe_distribution_network_exhaust_air = pd.concat([dataframe_distribution_network_exhaust_air, temp_df],
                                                                  ignore_index=True)

        for index, zeile in dataframe_distribution_network_exhaust_air.iterrows():
            kanalquerschnitt = zeile['Kanalquerschnitt']

            if "Ø" in kanalquerschnitt:
                # Finde den Durchmesser und aktualisiere den entsprechenden Wert in der Datenbank
                dataframe_distribution_network_exhaust_air.at[index, 'Durchmesser'] = str(
                    self.finde_abmessung(kanalquerschnitt))

            elif "x" in kanalquerschnitt:
                # Finde Breite und Höhe, zerlege den Querschnittswert und aktualisiere die entsprechenden Werte in der Datenbank
                breite, hoehe = self.finde_abmessung(kanalquerschnitt)
                dataframe_distribution_network_exhaust_air.at[index, 'Breite'] = str(breite)
                dataframe_distribution_network_exhaust_air.at[index, 'Höhe'] = str(hoehe)

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
                dataframe_distribution_network_exhaust_air
                )

    def druckverlust(self,
                     dict_steinerbaum_mit_leitungslaenge,
                     z_coordinate_list,
                     position_rlt,
                     position_schacht,
                     graph_leitungslaenge,
                     graph_luftmengen,
                     graph_kanalquerschnitt,
                     graph_mantelflaeche,
                     graph_rechnerischer_durchmesser,
                     export,
                     dataframe_distribution_network_exhaust_air):
        # Standardwerte für Berechnung
        rho = 1.204 * (ureg.kilogram / (ureg.meter ** 3))  # Dichte der Luft bei Standardbedingungen
        nu = 1.33 * 0.00001  # Dynamische Viskosität der Luft

        def darstellung_t_stueck(eingang1, eingang2, kanal):
            """
            Erstelle eine 3D-Graphen des T-Stücks
            :param eingang1: Lufteinleitung 1 in T-Stück
            :param eingang2: Lufteinleitung 2 in T-Stück
            :param kanal: Kanal
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
            zeichne_pfeil(eingang1[0], eingang1[1], 'green',
                          'dashed')  # Eingang1
            zeichne_pfeil(eingang2[0], eingang2[1], 'red',
                          'dashed')  # Eingang2
            zeichne_pfeil(kanal[0], kanal[1], 'blue')  # Kanal gestrichelt in Blau

            # Setzen der Achsenbeschriftungen
            ax.set_xlabel('X Achse')
            ax.set_ylabel('Y Achse')
            ax.set_zlabel('Z Achse')

            # Titel des Plots
            ax.set_title('3D Darstellung der Leitungen')

            # Anpassen der Achsengrenzen basierend auf den Koordinaten
            alle_koordinaten = eingang1 + eingang2 + kanal
            x_min, x_max = min(k[0] for k in alle_koordinaten), max(k[0] for k in alle_koordinaten)
            y_min, y_max = min(k[1] for k in alle_koordinaten), max(k[1] for k in alle_koordinaten)
            z_min, z_max = min(k[2] for k in alle_koordinaten), max(k[2] for k in alle_koordinaten)

            ax.set_xlim([x_min - 1, x_max + 1])
            ax.set_ylim([y_min - 1, y_max + 1])
            ax.set_zlim([z_min - 1, z_max + 1])

            # Anzeigen des Plots
            # plt.show()

            plt.close()

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
            :param rechnerischer_durchmesser: Rechnerischer Durchmesser der Leitung in Metern
            :return: Widerstandsbeiwert Bogen eckig
            """

            a = 1.6094 - 1.60868 * math.exp(-0.01089 * winkel)

            b = 0
            if 0.5 <= (mittlerer_radius / rechnerischer_durchmesser) <= 1.0:
                b = 0.21 / ((mittlerer_radius / rechnerischer_durchmesser) ** 2.5)
            elif 1 <= mittlerer_radius / rechnerischer_durchmesser:
                b = (0.21 / (math.sqrt(mittlerer_radius / rechnerischer_durchmesser)))

            c = (- 1.03663 * 10 ** (-4) * (hoehe / breite) ** 5 + 0.00338 * (hoehe / breite) ** 4 - 0.04277 * (
                    hoehe / breite)
                 ** 3 + 0.25496 * (hoehe / breite) ** 2 - 0.66296 * (hoehe / breite) + 1.4499)

            return a * b * c

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
                l = 0.3 * ureg.meter  # Als Standardlänge werden 0,5 Meter festgelegt

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

        def widerstandsbeiwert_querschnittserweiterung_stetig(d_1, d_2):
            """
            Berechnet den Widerstandsbeiwert bei einer Querschnittserweiterung A14 nach VDI 3803 Blatt 6
            :param d_1: Durchmesser Lufteingang in Metern
            :param d_2: Durchmesser Luftausgang in Metern
            :return: Widerstandsbeiwert für Querschnittserweiterung
            """

            if d_1 >= d_2:
                self.logger.error("Durchmesser 1 darf nicht größer als Durchmesser 2 sein!")

            else:
                l = 0.3 * ureg.meter  # Als Standardlänge werden 0,5 Meter festgelegt

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
            w = (v / A).to(ureg.meter / ureg.second)

            # Querschnitt Durchgang:
            A_D = math.pi * d_D ** 2 / 4
            # Strömunggeschwindkigkeit Durchgang
            w_D = (v_D / A_D).to(ureg.meter / ureg.second)

            # Querschnitt Abzweigung:
            A_A = math.pi * d_A ** 2 / 4
            # Strömungsgeschwindigkeit Abzweig
            w_A = (v_A / A_A).to(ureg.meter / ureg.second)

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
            w = (v / A).to(ureg.meter / ureg.second)

            # Querschnitt Durchgang:
            A_D = math.pi * d_D ** 2 / 4
            # Strömunggeschwindkigkeit Durchgang
            w_D = (v_D / A_D).to(ureg.meter / ureg.second)

            # Querschnitt Abzweigung:
            A_A = math.pi * d_A ** 2 / 4
            # Strömungsgeschwindigkeit Abzweig
            w_A = (v_A / A_A).to(ureg.meter / ureg.second)

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
            :param v_A: Volumenstrom des Abzweiges in m³/h
            :return: Widerstandsbeiwert für Krümmerabzweig A25 nach VDI 3803
            """

            # Querschnitt Eingang:
            A = math.pi * d ** 2 / 4
            # Strömungsgeschwindigkeit Eingang
            w = (v / A).to(ureg.meter / ureg.second)

            # Querschnitt Abzweigung:
            A_A = math.pi * d_A ** 2 / 4
            # Strömungsgeschwindigkeit Abzweig
            w_A = (v_A / A_A).to(ureg.meter / ureg.second)

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
            :param v_A: Volumenstrom des Abzweiges in m³/h
            :return: Widerstandsbeiwert für ein T-Stück rund A27 nach VDI 3803
            """

            # Querschnitt Eingang:
            A = math.pi * d ** 2 / 4
            # Strömungsgeschwindigkeit Eingang
            w = (v / A).to(ureg.meter / ureg.second)

            # Querschnitt Abzweigung:
            A_A = math.pi * d_A ** 2 / 4
            # Strömungsgeschwindigkeit Abzweig
            w_A = (v_A / A_A).to(ureg.meter / ureg.second)

            Y_0 = 0.662
            A_1 = 128.6
            t_1 = 0.0922
            A_2 = 15.13
            t_2 = 0.3138

            zeta_A = Y_0 + A_1 * math.exp(-(w_A / w) * 1 / t_1) + A_2 * math.exp(-(w_A / w) * 1 / t_2)

            return zeta_A

        def wiederstandsbeiwert_T_endstueck_stromvereinigung_rund(d_A: float, v_A: float, d: float, v: float):
            """
            Berechnet den Widerstandsbeiwert für ein T-Stück rund A30 nach VDI 3803 Blatt 6
            :param d_A: rechnerischer Durchmesser des Eingangs in Metern
            :param v_A: Volumenstrom des Eingangs in m³/h
            :param d: rechnerischer Durchmesser des HAuptstroms Kanals in Metern
            :param v: Volumenstrom des Hauptstrom Kanals in m³/h
            :return: Widerstandsbeiwert für ein T-Stück rund A30 nach VDI 3803
            """
            # Beiwerte
            K_1 = 109.63
            K_2 = -35.79
            K_3 = 0.013
            K_4 = 0.144
            K_5 = 1.829
            K_6 = -0.38

            # Querschnitt Kanal:
            A = math.pi * d ** 2 / 4
            # Strömungsgeschwindigkeit Hauptkanal
            w = (v / A).to(ureg.meter / ureg.second)

            # Querschnitt Teilstrom:
            A_A = math.pi * d_A ** 2 / 4
            # Strömungsgeschwindigkeit Teilstrom
            w_A = (v_A / A_A).to(ureg.meter / ureg.second)

            zeta = (K_1 / (A_A / A) + K_2) * math.exp((-w_A / w) / (K_3 / (A_A / A + K_4))) + (
                        K_5 * (1 / (A_A / A)) ** K_6)

            return zeta

        def wiederstandsbeiwert_T_endstueck_stromvereinigung_eckig():
            """
            Berechnet den Widerstandsbeiwert für ein T-Stück eckig A31 nach VDI 3803 Blatt 6
            :return: Wiederstandsbeiwert auf der sicheren Seite
            """
            return 0.28

        def wiederstandsbeiwert_T_stueck_stromvereinigung_rund(d: float, v: float, d_D: float, v_D: float, d_A: float,
                                                               v_A: float, richtung: str, alpha: float = 90) -> float:
            """
            Berechnet den Widerstandbeiwert für eine T-Vereinigung A28 nach VDI 3803 Blatt 6
            :param d: rechnerischer Durchmesser des Kanals in Metern
            :param v: Volumenstrom des Kanals in m³/h
            :param d_D: rechnerischer Durchmesser des Eingangs des Durchgangs in Metern
            :param v_D: Volumenstrom des Eingangs des Durchgangs in m³/h
            :param d_A: rechnerischer Durchmesser des Abgangs in Metern
            :param v_A: Volumenstrom des Abgangs in m³/h
            :param richtung: "Durchgangsrichtung" oder "zuströmende Richtung"
            :param alpha: Winkel in Grad
            :return: Widerstandbeiwert für eine T-Vereinigung A28
            """
            # Querschnitt Kanals:
            A = math.pi * d ** 2 / 4
            # Strömungsgeschwindigkeit Kanals
            w = (v / A).to(ureg.meter / ureg.second)

            # Querschnitt Durchgangsrichtung Eingang:
            A_D = math.pi * d_D ** 2 / 4
            # Strömunggeschwindkigkeit Durchgangrichtung Eingang
            w_D = (v_D / A_D).to(ureg.meter / ureg.second)

            # Querschnitt Abzweigung:
            A_A = math.pi * d_A ** 2 / 4
            # Strömungsgeschwindigkeit Abzweig
            w_A = (v_A / A_A).to(ureg.meter / ureg.second)

            if richtung == "Durchgangsrichtung":
                if A_A + A_D > A or A_D == A:
                    # Beiwerte
                    K1 = -906.220
                    K2 = -740.620
                    K3 = -0.197
                    K4 = 0.132
                    K5 = 0.078
                    K6 = 0.0054
                    K7 = -158.058
                    K8 = -1.517
                    K9 = 152.528
                    K10 = 34.897
                    K11 = 0.530
                    K12 = -0.527
                    K13 = -11.215
                    K14 = -1.705
                    K15 = 1.799

                    xi = (K1 * (A_A / A) + K2) * np.exp(-(w_A / w) / (K3 * (A_A / A) + K4) + K5 * A_A / A + K6)
                    a = K7 + K9 * np.exp(((A_A / A) - K8) / K10)
                    b = K11 + K12 * np.exp((A_A / A) / K13)
                    c = K14 * (A_A / A) + K15

                    gamma = a + b * alpha ** c

                    # Widerstandsbeiwert ζ_D
                    zeta = xi * gamma

                    return zeta

                elif A_A + A_D == A:
                    K1 = 43.836
                    K2 = 26.78
                    K3 = 0.20
                    K4 = 2.7804
                    K5 = -0.6327

                    zeta = (K1 * A_A / A + K2) * math.exp(-(w_A / w) / K3) + (K4 * A_A / A + K5)

                    return zeta

            elif richtung == "zuströmende Richtung":
                if A_A + A_D > A or A_D == A:
                    # Beiwerte
                    K1 = 80.953
                    K2 = -64.126
                    K3 = 0.17
                    K4 = 0.5784
                    K5 = 0.4834

                    zeta = (K1 * A_A / A + K2) * math.exp(-(w_A / w) / K3) + (K4 * A_A / A + K5)

                    return zeta

                elif A_A + A_D == A:
                    # Beiwerte
                    K1 = -232.1
                    K2 = -38.743
                    K3 = 0.171
                    K4 = -2.477
                    K5 = 0.597

                    zeta = (K1 * A_A / A + K2) * math.exp(-(w_A / w) / K3) + (K4 * A_A / A + K5)

                    return zeta

        def wiederstandsbeiwert_T_stueck_stromvereinigung_eckig(d: float, v: float, d_D: float, v_D: float, d_A: float,
                                                                v_A: float, richtung: str) -> float:
            """
            Berechnet den Widerstandbeiwert für eine T-Vereinigung A28 nach VDI 3803 Blatt 6
            :param d: rechnerischer Durchmesser des Kanals in Metern
            :param v: Volumenstrom des Kanals in m³/h
            :param d_D: rechnerischer Durchmesser des Eingangs des Durchgangs in Metern
            :param v_D: Volumenstrom des Eingangs des Durchgangs in m³/h
            :param d_A: rechnerischer Durchmesser des Abgangs in Metern
            :param v_A: Volumenstrom des Abgangs in m³/h
            :param richtung: "Durchgangsrichtung" oder "zuströmende Richtung"
            :return: Widerstandbeiwert für eine T-Vereinigung A29 nach VDI 3803-6
            """
            # Querschnitt Kanals:
            A = math.pi * d ** 2 / 4
            # Strömungsgeschwindigkeit Kanals
            w = (v / A).to(ureg.meter / ureg.second)

            # Querschnitt Durchgangsrichtung Eingang:
            A_D = math.pi * d_D ** 2 / 4
            # Strömunggeschwindkigkeit Durchgangrichtung Eingang
            w_D = (v_D / A_D).to(ureg.meter / ureg.second)

            # Querschnitt Abzweigung:
            A_A = math.pi * d_A ** 2 / 4
            # Strömungsgeschwindigkeit Abzweig
            w_A = (v_A / A_A).to(ureg.meter / ureg.second)

            if richtung == "Durchgangsrichtung":
                # Eingabewerte
                input_points = np.array([
                    [1.0, 0.5],  # A_D/A, A_A/A für die erste Zeile
                    [0.5, 0.5],  # A_D/A, A_A/A für die zweite Zeile
                    [1.0, 1.0]  # A_D/A, A_A/A für die dritte Zeile
                ])

                # a-Werte
                a2_values = np.array([-0.5604, -1.8281, -0.2756])
                a1_values = np.array([1.0706, 2.8312, 1.7256])
                a0_values = np.array([-0.2466, -0.6536, -1.8292])

                # Zweidimensionale Interpolationsfunktionen für a2, a1, a0
                def interpolate_2d_durchgehende_richtung(A_D, A_A, A):
                    input_point = np.array([(A_D / A, A_A / A)])

                    # Verwendung von 'nearest' als Workaround für Extrapolation
                    a2 = griddata(input_points, a2_values, input_point, method='nearest')[0]
                    a1 = griddata(input_points, a1_values, input_point, method='nearest')[0]
                    a0 = griddata(input_points, a0_values, input_point, method='nearest')[0]

                    return a2, a1, a0

                a2, a1, a0 = interpolate_2d_durchgehende_richtung(A_D, A_A, A)

                zeta = a2 * (1 / (w_D / w)) ** 2 + a1 * (1 / (w_D / w)) + a0

                return zeta

            elif richtung == "zuströmende Richtung":
                # Eingabewerte
                input_points = np.array([
                    [1.0, 0.5],  # A_D/A, A_A/A für die erste Zeile
                    [0.5, 0.5],  # A_D/A, A_A/A für die zweite Zeile
                    [1.0, 1.0]  # A_D/A, A_A/A für die dritte Zeile
                ])

                # b-Werte
                b2_values = np.array([-0.5769, -2.644, -0.8982])
                b1_values = np.array([0.5072, 2.7448, 2.8556])
                b0_values = np.array([0.4924, -0.1258, -1.5221])

                # Zweidimensionale Interpolationsfunktionen für b2, b1, b0
                def interpolate_2d_abzweigende_richtung(A_D, A_A, A):
                    input_point = np.array([(A_D / A, A_A / A)])

                    # Verwendung von 'nearest' als Workaround für Extrapolation
                    b2 = griddata(input_points, b2_values, input_point, method='nearest')[0]
                    b1 = griddata(input_points, b1_values, input_point, method='nearest')[0]
                    b0 = griddata(input_points, b0_values, input_point, method='nearest')[0]

                    return b2, b1, b0

                b2, b1, b0 = interpolate_2d_abzweigende_richtung(A_D, A_A, A)

                zeta = b2 * (1 / (w_A / w)) ** 2 + b1 * (1 / (w_A / w)) + b0

                return zeta

        # Position der RLT-Auslesen
        position_rlt = (position_rlt[0], position_rlt[1], position_rlt[2])

        # Erstellung einer BFS-Reihenfolge ab dem Startpunkt
        lueftungskanal_zuluft_richtung = list(nx.edge_bfs(graph_leitungslaenge, position_rlt))

        # Für die Abluft muss die Luft vom Deckeneinlass zur RLT strömen. Daher muss die Richtung der Koordinaten
        # umgedreht werden

        lueftungskanal_abluft_richtung = [(b, a) for a, b in lueftungskanal_zuluft_richtung]

        graph_leitungslaenge_abluft = nx.DiGraph()

        # Kanten in der BFS-Reihenfolge zum neuen Graphen hinzufügen
        for edge in lueftungskanal_abluft_richtung:
            graph_leitungslaenge_abluft.add_edge(*edge)

        # Druckverlustberechnung
        # Netz erstellen:
        net = pp.create_empty_network(fluid="air")

        # Auslesen des Fluides
        fluid = pp.get_fluid(net)

        # Auslesen der Dichte
        dichte = fluid.get_density(temperature=293.15) * ureg.kilogram / ureg.meter ** 3

        # Definition der Parameter für die Junctions
        name_junction = [koordinate for koordinate in list(graph_leitungslaenge_abluft.nodes())]
        index_junction = [index for index, wert in enumerate(name_junction)]

        # Erstellen einer Liste für jede Koordinatenachse
        x_koordinaten = [koordinate[0] for koordinate in list(graph_leitungslaenge_abluft.nodes())]
        y_koordinaten = [koordinate[1] for koordinate in list(graph_leitungslaenge_abluft.nodes())]
        z_koordinaten = [koordinate[2] for koordinate in list(graph_leitungslaenge_abluft.nodes())]

        """2D-Koordinaten erstellen"""
        # Da nur 3D Koordinaten vorhanden sind, jedoch 3D Koordinaten gebraucht werden wird ein Dict erstellt, welches
        # jeder 3D Koordinate einen 2D-Koordinate zuweist
        zwei_d_koodrinaten = dict()
        position_schacht_graph = (position_schacht[0], position_schacht[1], position_schacht[2])

        # Leitung von RLT zu Schacht
        pfad_rlt_zu_schacht = list(nx.all_simple_paths(graph_leitungslaenge, position_rlt, position_schacht_graph))[0]
        anzahl_punkte_pfad_rlt_zu_schacht = len(pfad_rlt_zu_schacht)

        for punkt in pfad_rlt_zu_schacht:
            zwei_d_koodrinaten[punkt] = (-anzahl_punkte_pfad_rlt_zu_schacht, 0)
            anzahl_punkte_pfad_rlt_zu_schacht -= 1

        anzahl_knoten_mit_mindestens_drei_kanten = len(
            [node for node, degree in graph_leitungslaenge.degree() if degree >= 3])

        # Versuch, alle Keys in Zahlen umzuwandeln und zu sortieren
        sorted_keys = sorted(
            (key for key in dict_steinerbaum_mit_leitungslaenge.keys() if key != "Schacht"),
            key=lambda x: float(x)
        )

        y = 0  # Start y-Koordinate

        collisions = {}

        for key in sorted_keys:
            graph_geschoss = dict_steinerbaum_mit_leitungslaenge[key]

            # TODO Pressure loss for collisions of exhaust and supply air systems should be added here

            """
            supply_graph_cross_section = self.dict_supply_graph_cross_section[key]
            colinear_edges, crossing_edges, crossing_points = self.find_collisions(supply_graph_cross_section, graph_geschoss)
            exhaust_crossing_edges = [edge[0] for edge in crossing_edges]
            supply_crossing_edges = [edge[1] for edge in crossing_edges]

            for edge in list(colinear_edges):
                collisions[edge] = {}
                collisions[edge]["pos"] = edge
            for i in range(len(supply_crossing_edges)-1):
                if (crossing_points[i] not in (supply_crossing_edges[i][0][:2], supply_crossing_edges[i][1][:2])) or \
                  (crossing_points[i] == supply_crossing_edges[i][0][:2] and graph_geschoss.degree[supply_crossing_edges[i][0][:2]] != 1) or \
                  (crossing_points[i] == supply_crossing_edges[i][1][:2] and graph_geschoss.degree[supply_crossing_edges[i][1][:2]] != 1):
                    collisions.append(supply_crossing_edges[i])
                    collisions[supply_crossing_edges[i]] = {}
                    collisions[supply_crossing_edges[i]]["pos"] = supply_crossing_edges[i]
            """
            #


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

                        if pfad_zaehler >= 1:
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

        """2D-Koordinaten erstellt"""

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

        # Definition der Parameter für die Pipe
        name_pipe = dataframe_distribution_network_exhaust_air["Kante"].tolist()
        length_pipe = dataframe_distribution_network_exhaust_air["Leitungslänge"].tolist()
        from_junction = dataframe_distribution_network_exhaust_air["Startknoten"].tolist()
        to_junction = dataframe_distribution_network_exhaust_air["Zielknoten"].tolist()
        diameter_pipe = dataframe_distribution_network_exhaust_air["rechnerischer Durchmesser"].tolist()

        # Hinzufügen der Rohre zum Netz
        for index, pipe in enumerate(name_pipe):
            pp.create_pipe_from_parameters(net,
                                           from_junction=int(name_junction.index(from_junction[index])),
                                           to_junction=int(name_junction.index(to_junction[index])),
                                           nr_junctions=index,
                                           length_km=length_pipe[index].to(ureg.kilometer).magnitude,
                                           diameter_m=diameter_pipe[index].to(ureg.meter).magnitude,
                                           k_mm=0.15,
                                           name=str(name_pipe[index]),
                                           loss_coefficient=0
                                           )

        """Ab hier werden die Verlustbeiwerte der Rohre angepasst"""
        for index, pipe in enumerate(name_pipe):

            # Nachbarn des Startknotens
            neighbors = list(nx.all_neighbors(graph_leitungslaenge_abluft, from_junction[index]))

            """Bögen:"""
            if len(neighbors) == 2:  # Bögen finden
                eingehende_kante = list(graph_leitungslaenge_abluft.in_edges(from_junction[index]))[0]
                ausgehende_kante = list(graph_leitungslaenge_abluft.out_edges(from_junction[index]))[0]

                # Rechnerischer Durchmesser des Kanals
                rechnerischer_durchmesser = dataframe_distribution_network_exhaust_air.loc[
                    (dataframe_distribution_network_exhaust_air['Startknoten'] == from_junction[index]) &
                    (dataframe_distribution_network_exhaust_air['Zielknoten'] == to_junction[index]),
                    'rechnerischer Durchmesser'
                ].iloc[0].to(ureg.meter)

                # Abmessung des Kanals
                abmessung_kanal = dataframe_distribution_network_exhaust_air.loc[
                    (dataframe_distribution_network_exhaust_air['Startknoten'] == from_junction[index]) &
                    (dataframe_distribution_network_exhaust_air['Zielknoten'] == to_junction[index]),
                    'Kanalquerschnitt'
                ].iloc[0]

                if not check_if_lines_are_aligned(eingehende_kante, ausgehende_kante):

                    zeta_bogen = None
                    if "Ø" in abmessung_kanal:
                        durchmesser = self.finde_abmessung(abmessung_kanal)
                        zeta_bogen = widerstandsbeiwert_bogen_rund(winkel=90,
                                                                   mittlerer_radius=0.75 * ureg.meter,
                                                                   durchmesser=durchmesser)
                        # print(f"Zeta-Bogen rund: {zeta_bogen}")

                    elif "x" in abmessung_kanal:
                        breite = self.finde_abmessung(abmessung_kanal)[0].to(ureg.meter)
                        hoehe = self.finde_abmessung(abmessung_kanal)[1].to(ureg.meter)
                        zeta_bogen = widerstandsbeiwert_bogen_eckig(winkel=90,
                                                                    mittlerer_radius=0.75 * ureg.meter,
                                                                    hoehe=hoehe,
                                                                    breite=breite,
                                                                    rechnerischer_durchmesser=rechnerischer_durchmesser
                                                                    )
                        # print(f"Zeta Bogen eckig: {zeta_bogen}")

                    # Ändern des loss_coefficient-Werts
                    net['pipe'].at[index, 'loss_coefficient'] += zeta_bogen

                    dataframe_distribution_network_exhaust_air.loc[dataframe_distribution_network_exhaust_air[
                                                                      'Zielknoten'] == to_junction[
                                                                      index], 'Zeta Bogen'] = zeta_bogen

            """Reduzierungen"""
            if len(neighbors) == 2:
                kanal = name_pipe[index]

                eingehende_kante = list(graph_leitungslaenge_abluft.in_edges(from_junction[index]))[0]
                ausgehende_kante = list(graph_leitungslaenge_abluft.out_edges(from_junction[index]))[0]

                """ Daten für Widerstandsbeiwerte"""
                # Durchmesser des Eingangs:
                d = dataframe_distribution_network_exhaust_air.loc[
                    (dataframe_distribution_network_exhaust_air['Startknoten'] == eingehende_kante[0]) &
                    (dataframe_distribution_network_exhaust_air['Zielknoten'] == eingehende_kante[1]),
                    'rechnerischer Durchmesser'
                ].iloc[0].to(ureg.meter)

                # Durchmesser des Durchgangs:
                d_D = dataframe_distribution_network_exhaust_air.loc[
                    (dataframe_distribution_network_exhaust_air['Startknoten'] == ausgehende_kante[0]) &
                    (dataframe_distribution_network_exhaust_air['Zielknoten'] == ausgehende_kante[1]),
                    'rechnerischer Durchmesser'
                ].iloc[0].to(ureg.meter)

                if d > d_D:
                    zeta_reduzierung = widerstandsbeiwert_querschnittsverengung_stetig(d, d_D)

                    # print(f"Zeta Reduzierung: {zeta_reduzierung}")

                    net['pipe'].at[index, 'loss_coefficient'] += zeta_reduzierung

                    dataframe_distribution_network_exhaust_air.loc[dataframe_distribution_network_exhaust_air[
                                                                      'Zielknoten'] == to_junction[
                                                                      index], 'Zeta Reduzierung'] = zeta_reduzierung

                elif d_D > d:
                    zeta_erweiterung = widerstandsbeiwert_querschnittserweiterung_stetig(d, d_D)

                    # print(f"Zeta Erweiterung: {zeta_erweiterung}")

                    net['pipe'].at[index, 'loss_coefficient'] += zeta_erweiterung

                    dataframe_distribution_network_exhaust_air.loc[dataframe_distribution_network_exhaust_air[
                                                                      'Zielknoten'] == to_junction[
                                                                      index], 'Zeta Erweiterung'] = zeta_erweiterung

            """T-Stücke"""
            if len(neighbors) == 3:  # T-Stücke finden
                kanal = name_pipe[index]

                # Rechnerischer Durchmesser des Kanals
                rechnerischer_durchmesser_kanal = dataframe_distribution_network_exhaust_air.loc[
                    (dataframe_distribution_network_exhaust_air['Startknoten'] == from_junction[index]) &
                    (dataframe_distribution_network_exhaust_air['Zielknoten'] == to_junction[index]),
                    'rechnerischer Durchmesser'
                ].iloc[0].to(ureg.meter)

                # Abmessung des Kanals
                abmessung_kanal = dataframe_distribution_network_exhaust_air.loc[
                    (dataframe_distribution_network_exhaust_air['Startknoten'] == from_junction[index]) &
                    (dataframe_distribution_network_exhaust_air['Zielknoten'] == to_junction[index]),
                    'Kanalquerschnitt'
                ].iloc[0]

                luftmenge_kanal = dataframe_distribution_network_exhaust_air.loc[
                    (dataframe_distribution_network_exhaust_air['Startknoten'] == from_junction[index]) &
                    (dataframe_distribution_network_exhaust_air['Zielknoten'] == to_junction[index]),
                    'Luftmenge'
                ].iloc[0]

                # Liste der eingehenden Kanten
                eingehende_kanten = list(graph_leitungslaenge_abluft.in_edges(from_junction[index]))

                # Aufteilen in eingehende Kante 1
                eingehende_kante_1 = eingehende_kanten[0]
                # Aufteilen in eingenden Kante 2
                eingehende_kante_2 = eingehende_kanten[1]

                # Lage überprüfen, sonst tauschen
                if check_if_lines_are_aligned(eingehende_kante_2, kanal):
                    eingehende_kante_1 = eingehende_kanten[1]
                    eingehende_kante_2 = eingehende_kanten[0]

                # Rechnerischer Durchmesser eingehende Kante 1
                rechnerischer_durchmesser_eingehende_kante_1 = dataframe_distribution_network_exhaust_air.loc[
                    (dataframe_distribution_network_exhaust_air['Startknoten'] == eingehende_kante_1[0]) &
                    (dataframe_distribution_network_exhaust_air['Zielknoten'] == eingehende_kante_1[1]),
                    'rechnerischer Durchmesser'
                ].iloc[0].to(ureg.meter)

                # Abmessung des Kanals eingehende Kante 1
                abmessung_kanal_eingehende_kante_1 = dataframe_distribution_network_exhaust_air.loc[
                    (dataframe_distribution_network_exhaust_air['Startknoten'] == eingehende_kante_1[0]) &
                    (dataframe_distribution_network_exhaust_air['Zielknoten'] == eingehende_kante_1[1]),
                    'Kanalquerschnitt'
                ].iloc[0]

                luftmenge_eingehende_kante_1 = dataframe_distribution_network_exhaust_air.loc[
                    (dataframe_distribution_network_exhaust_air['Startknoten'] == from_junction[index]) &
                    (dataframe_distribution_network_exhaust_air['Zielknoten'] == to_junction[index]),
                    'Luftmenge'
                ].iloc[0]

                # Rechnerischer Durchmesser eingehende Kante 2
                rechnerischer_durchmesser_eingehende_kante_2 = dataframe_distribution_network_exhaust_air.loc[
                    (dataframe_distribution_network_exhaust_air['Startknoten'] == eingehende_kante_2[0]) &
                    (dataframe_distribution_network_exhaust_air['Zielknoten'] == eingehende_kante_2[1]),
                    'rechnerischer Durchmesser'
                ].iloc[0].to(ureg.meter)

                # Abmessung des Kanals eingehende Kante 1
                abmessung_kanal_eingehende_kante_2 = dataframe_distribution_network_exhaust_air.loc[
                    (dataframe_distribution_network_exhaust_air['Startknoten'] == eingehende_kante_2[0]) &
                    (dataframe_distribution_network_exhaust_air['Zielknoten'] == eingehende_kante_2[1]),
                    'Kanalquerschnitt'
                ].iloc[0]

                luftmenge_eingehende_kante_2 = dataframe_distribution_network_exhaust_air.loc[
                    (dataframe_distribution_network_exhaust_air['Startknoten'] == from_junction[index]) &
                    (dataframe_distribution_network_exhaust_air['Zielknoten'] == to_junction[index]),
                    'Luftmenge'
                ].iloc[0]

                # 3D Darstellung des T-Stücks
                # darstellung_t_stueck(eingehende_kante_1, eingehende_kante_2, kanal)

                """ Daten für Widerstandsbeiwerte"""
                if check_if_lines_are_aligned(eingehende_kante_1, eingehende_kante_2) == True:
                    # Eingehende Kante 1 --→ ←-- Eingehende Kante 2
                    #                       ↓
                    #                     Kanal

                    if "Ø" in abmessung_kanal:
                        if rechnerischer_durchmesser_eingehende_kante_1 > rechnerischer_durchmesser_eingehende_kante_2:
                            zeta_eingehende_kante_1 = wiederstandsbeiwert_T_endstueck_stromvereinigung_rund(
                                d_A=rechnerischer_durchmesser_eingehende_kante_1,
                                v_A=luftmenge_eingehende_kante_1,
                                d=rechnerischer_durchmesser_kanal,
                                v=luftmenge_kanal)

                            net['pipe'].at[
                                name_pipe.index(eingehende_kante_1), 'loss_coefficient'] += zeta_eingehende_kante_1
                            dataframe_distribution_network_exhaust_air.loc[dataframe_distribution_network_exhaust_air[
                                                                              'Kante'] == eingehende_kante_1, 'Zeta T-Stück'] = zeta_eingehende_kante_1

                            zeta_eingehende_kante_2 = wiederstandsbeiwert_T_endstueck_stromvereinigung_rund(
                                d_A=rechnerischer_durchmesser_eingehende_kante_2,
                                v_A=luftmenge_eingehende_kante_2,
                                d=rechnerischer_durchmesser_kanal,
                                v=luftmenge_kanal) + widerstandsbeiwert_querschnittserweiterung_stetig(
                                rechnerischer_durchmesser_eingehende_kante_2,
                                rechnerischer_durchmesser_eingehende_kante_1)

                            net['pipe'].at[
                                name_pipe.index(eingehende_kante_2), 'loss_coefficient'] += zeta_eingehende_kante_2
                            dataframe_distribution_network_exhaust_air.loc[dataframe_distribution_network_exhaust_air[
                                                                              'Kante'] == eingehende_kante_2, 'Zeta T-Stück'] = zeta_eingehende_kante_2

                        elif rechnerischer_durchmesser_eingehende_kante_2 > rechnerischer_durchmesser_eingehende_kante_1:
                            zeta_eingehende_kante_2 = wiederstandsbeiwert_T_endstueck_stromvereinigung_rund(
                                d_A=rechnerischer_durchmesser_eingehende_kante_2,
                                v_A=luftmenge_eingehende_kante_2,
                                d=rechnerischer_durchmesser_kanal,
                                v=luftmenge_kanal)

                            net['pipe'].at[
                                name_pipe.index(eingehende_kante_2), 'loss_coefficient'] += zeta_eingehende_kante_2
                            dataframe_distribution_network_exhaust_air.loc[dataframe_distribution_network_exhaust_air[
                                                                              'Kante'] == eingehende_kante_2, 'Zeta T-Stück'] = zeta_eingehende_kante_2

                            zeta_eingehende_kante_1 = wiederstandsbeiwert_T_endstueck_stromvereinigung_rund(
                                d_A=rechnerischer_durchmesser_eingehende_kante_1,
                                v_A=luftmenge_eingehende_kante_1,
                                d=rechnerischer_durchmesser_kanal,
                                v=luftmenge_kanal) + widerstandsbeiwert_querschnittserweiterung_stetig(
                                rechnerischer_durchmesser_eingehende_kante_1,
                                rechnerischer_durchmesser_eingehende_kante_2)

                            net['pipe'].at[
                                name_pipe.index(eingehende_kante_1), 'loss_coefficient'] += zeta_eingehende_kante_1
                            dataframe_distribution_network_exhaust_air.loc[dataframe_distribution_network_exhaust_air[
                                                                              'Kante'] == eingehende_kante_1, 'Zeta T-Stück'] = zeta_eingehende_kante_1
                    elif "x" in abmessung_kanal:
                        zeta_eingehende_kante_1 = wiederstandsbeiwert_T_endstueck_stromvereinigung_eckig()

                        net['pipe'].at[
                            name_pipe.index(eingehende_kante_1), 'loss_coefficient'] += zeta_eingehende_kante_1
                        dataframe_distribution_network_exhaust_air.loc[dataframe_distribution_network_exhaust_air[
                                                                          'Kante'] == eingehende_kante_1, 'Zeta T-Stück'] = zeta_eingehende_kante_1

                        zeta_eingehende_kante_2 = wiederstandsbeiwert_T_endstueck_stromvereinigung_eckig()

                        net['pipe'].at[
                            name_pipe.index(eingehende_kante_2), 'loss_coefficient'] += zeta_eingehende_kante_2
                        dataframe_distribution_network_exhaust_air.loc[dataframe_distribution_network_exhaust_air[
                                                                          'Kante'] == eingehende_kante_2, 'Zeta T-Stück'] = zeta_eingehende_kante_2

                if check_if_lines_are_aligned(eingehende_kante_1, kanal) == True:
                    # Eingehende Kante 1 --→ --→ Kanal
                    #                       ↑
                    #               Eingehende Kante 2
                    if "Ø" in abmessung_kanal:
                        zeta_eingehende_kante_1 = wiederstandsbeiwert_T_stueck_stromvereinigung_rund(
                            d=rechnerischer_durchmesser_kanal,
                            v=luftmenge_kanal,
                            d_D=rechnerischer_durchmesser_eingehende_kante_1,
                            v_D=luftmenge_eingehende_kante_1,
                            d_A=rechnerischer_durchmesser_eingehende_kante_2,
                            v_A=luftmenge_eingehende_kante_2,
                            richtung="Durchgangsrichtung")

                        net['pipe'].at[
                            name_pipe.index(eingehende_kante_1), 'loss_coefficient'] += zeta_eingehende_kante_1
                        dataframe_distribution_network_exhaust_air.loc[dataframe_distribution_network_exhaust_air[
                                                                          'Kante'] == eingehende_kante_1, 'Zeta T-Stück'] = zeta_eingehende_kante_1

                        zeta_eingehende_kante_2 = wiederstandsbeiwert_T_stueck_stromvereinigung_rund(
                            d=rechnerischer_durchmesser_kanal,
                            v=luftmenge_kanal,
                            d_D=rechnerischer_durchmesser_eingehende_kante_1,
                            v_D=luftmenge_eingehende_kante_1,
                            d_A=rechnerischer_durchmesser_eingehende_kante_2,
                            v_A=luftmenge_eingehende_kante_2,
                            richtung="zuströmende Richtung")

                        net['pipe'].at[
                            name_pipe.index(eingehende_kante_2), 'loss_coefficient'] += zeta_eingehende_kante_2
                        dataframe_distribution_network_exhaust_air.loc[dataframe_distribution_network_exhaust_air[
                                                                          'Kante'] == eingehende_kante_2, 'Zeta T-Stück'] = zeta_eingehende_kante_2

                    if "x" in abmessung_kanal:
                        zeta_eingehende_kante_1 = wiederstandsbeiwert_T_stueck_stromvereinigung_eckig(
                            d=rechnerischer_durchmesser_kanal,
                            v=luftmenge_kanal,
                            d_D=rechnerischer_durchmesser_eingehende_kante_1,
                            v_D=luftmenge_eingehende_kante_1,
                            d_A=rechnerischer_durchmesser_eingehende_kante_2,
                            v_A=luftmenge_eingehende_kante_2,
                            richtung="Durchgangsrichtung")

                        net['pipe'].at[
                            name_pipe.index(eingehende_kante_1), 'loss_coefficient'] += zeta_eingehende_kante_1
                        dataframe_distribution_network_exhaust_air.loc[dataframe_distribution_network_exhaust_air[
                                                                          'Kante'] == eingehende_kante_1, 'Zeta T-Stück'] = zeta_eingehende_kante_1

                        zeta_eingehende_kante_2 = wiederstandsbeiwert_T_stueck_stromvereinigung_eckig(
                            d=rechnerischer_durchmesser_kanal,
                            v=luftmenge_kanal,
                            d_D=rechnerischer_durchmesser_eingehende_kante_1,
                            v_D=luftmenge_eingehende_kante_1,
                            d_A=rechnerischer_durchmesser_eingehende_kante_2,
                            v_A=luftmenge_eingehende_kante_2,
                            richtung="zuströmende Richtung")

                        net['pipe'].at[
                            name_pipe.index(eingehende_kante_2), 'loss_coefficient'] += zeta_eingehende_kante_2
                        dataframe_distribution_network_exhaust_air.loc[dataframe_distribution_network_exhaust_air[
                                                                          'Kante'] == eingehende_kante_2, 'Zeta T-Stück'] = zeta_eingehende_kante_2

        # Luftmengen aus Graphen
        luftmengen = nx.get_node_attributes(graph_luftmengen, 'weight')

        # Index der RLT-Anlage finden
        index_rlt = name_junction.index(tuple(position_rlt))
        luftmenge_rlt = luftmengen[position_rlt]
        mdot_kg_per_s_rlt = (luftmenge_rlt * dichte).to(ureg.kilogram / ureg.second)

        # Externes Grid erstellen, da dann die Visualisierung besser ist
        pp.create_ext_grid(net, junction=index_rlt, p_bar=0, t_k=293.15, name="RLT-Anlage")

        # Hinzufügen der RLT-Anlage zum Netz
        pp.create_source(net,
                         mdot_kg_per_s=-mdot_kg_per_s_rlt.magnitude,
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
            if luftmengen[element] == 0:
                continue
            pp.create_sink(net,
                           junction=name_junction.index(element),
                           mdot_kg_per_s=(-luftmengen[element] * dichte).to(ureg.kilogram / ureg.second).magnitude,
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

        groesster_druckverlust -= 0.00100  # 30 Pa für Lüftungseinlass und 50 Pa für Schalldämpfer + 20 Reserve

        # Ändern des Druckwerts
        net['source'].at[source_index, 'p_bar'] -= groesster_druckverlust
        # Ändern des Druckwerts
        net['ext_grid'].at[ext_grid_index, 'p_bar'] -= groesster_druckverlust

        pp.pipeflow(net)

        # Ergebnisse werden in Tabellen mit dem Präfix res_... gespeichert. Auch diese Tabellen sind nach der Berechnung im
        # net-Container abgelegt.
        dataframe_pipes = pd.concat([net.pipe, net.res_pipe], axis=1)
        dataframe_junctions = pd.concat([net.junction, net.res_junction], axis=1)

        for kanal in dataframe_distribution_network_exhaust_air["Kante"]:
            p_from_pa = int(dataframe_pipes.loc[dataframe_pipes["name"] == str(kanal), "p_from_bar"].iloc[0] * 100000)
            p_to_pa = int(dataframe_pipes.loc[dataframe_pipes["name"] == str(kanal), "p_to_bar"].iloc[0] * 100000)

            dataframe_distribution_network_exhaust_air.loc[
                dataframe_distribution_network_exhaust_air["Kante"] == kanal, "p_from_pa"] = p_from_pa
            dataframe_distribution_network_exhaust_air.loc[
                dataframe_distribution_network_exhaust_air["Kante"] == kanal, "p_to_pa"] = p_to_pa

        if export == True:
            # Export
            dataframe_distribution_network_exhaust_air.to_excel(
                self.paths.export / 'Abluft' / 'dataframe_distribution_network_exhaust_air.xlsx', index=False)

            # Pfad für Speichern
            pipes_excel_pfad = self.paths.export / 'Abluft' / "Druckverlust.xlsx"

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
                                                                         color="orange")

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
            ordner_pfad = Path(self.paths.export / 'Abluft')

            # Erstelle den Ordner
            ordner_pfad.mkdir(parents=True, exist_ok=True)

            # Speichern des Graphens
            gesamte_bezeichnung = "Druckverlust" + ".png"
            pfad_plus_name = self.paths.export / 'Abluft' / gesamte_bezeichnung
            plt.savefig(pfad_plus_name)

            # plt.show()

            plt.close()

        return groesster_druckverlust * 100000, dataframe_distribution_network_exhaust_air

    #
    def blechstaerke(self, druckverlust, abmessung):
        """
        Berechnet die Blechstärke in Abhängigkeit vom Kanal
        :param druckverlust: Durckverlust des Systems
        :param abmessung: Abmessung des Kanals (400x300 oder Ø60)
        :return: Blechstärke
        """

        if "Ø" in abmessung:
            durchmesser = self.finde_abmessung(abmessung).to(ureg.meter)

            if durchmesser <= 0.2 * ureg.meter:
                blechstaerke = (0.5 * ureg.millimeter).to(
                    ureg.meter)  # In Metern nach MKK Shop Datenblatt Best. Nr. 10782
            elif 0.2 * ureg.meter < durchmesser <= 0.4 * ureg.meter:
                blechstaerke = (0.6 * ureg.millimeter).to(
                    ureg.meter)  # In Metern nach MKK Shop Datenblatt Best. Nr. 10782
            elif 0.4 * ureg.meter < durchmesser <= 0.5 * ureg.meter:
                blechstaerke = (0.7 * ureg.millimeter).to(
                    ureg.meter)  # In Metern nach MKK Shop Datenblatt Best. Nr. 10782
            elif 0.5 * ureg.meter < durchmesser <= 0.63 * ureg.meter:
                blechstaerke = (0.9 * ureg.millimeter).to(
                    ureg.meter)  # In Metern nach MKK Shop Datenblatt Best. Nr. 10782
            elif 0.63 * ureg.meter < durchmesser <= 1.25 * ureg.meter:
                blechstaerke = (1.25 * ureg.millimeter).to(
                    ureg.meter)  # In Metern nach MKK Shop Datenblatt Best. Nr. 10782


        elif "x" in abmessung:
            breite, hoehe = self.finde_abmessung(abmessung)
            laengste_kante = max(breite.to(ureg.meter), hoehe.to(ureg.meter))

            if druckverlust <= 1000:
                if laengste_kante <= 0.500 * ureg.meter:
                    blechstaerke = (0.6 * ureg.millimeter).to(
                        ureg.meter)  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53
                elif 0.500 * ureg.meter < laengste_kante <= 1.000 * ureg.meter:
                    blechstaerke = (0.8 * ureg.millimeter).to(
                        ureg.meter)  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53
                elif 1.000 * ureg.meter < laengste_kante <= 2.000 * ureg.meter:
                    blechstaerke = (1.0 * ureg.millimeter).to(
                        ureg.meter)  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53

            elif 1000 < druckverlust <= 2000:
                if laengste_kante <= 0.500 * ureg.meter:
                    blechstaerke = (0.7 * ureg.millimeter).to(
                        ureg.meter)  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53
                elif 0.500 * ureg.meter < laengste_kante <= 1.000 * ureg.meter:
                    blechstaerke = (0.9 * ureg.millimeter).to(
                        ureg.meter)  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53
                elif 1.000 * ureg.meter < laengste_kante <= 2.000 * ureg.meter:
                    blechstaerke = (1.1 * ureg.millimeter).to(
                        ureg.meter)  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53

            elif 2000 < druckverlust <= 3000:
                if laengste_kante <= 1.000 * ureg.meter:
                    blechstaerke = (0.95 * ureg.millimeter).to(
                        ureg.meter)  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53
                elif 1.000 * ureg.meter < laengste_kante <= 2.000 * ureg.meter:
                    blechstaerke = (1.15 * ureg.millimeter).to(
                        ureg.meter)  # In Metern nach BerlinerLuft Gesamtkatalog Seite 53

        return blechstaerke

    def raumanbindung(self, cross_section_type, zwischendeckenraum, dataframe_rooms):

        # Ermittlung des Kanalquerschnittes
        dataframe_rooms["Kanalquerschnitt"] = \
            dataframe_rooms.apply(lambda row: self.abmessungen_kanal(cross_section_type,
                                                                     self.notwendiger_kanaldquerschnitt(
                                                                         row["Volumenstrom"]),
                                                                     zwischendeckenraum),
                                  axis=1
                                  )

        # Ermittung der Abmessungen
        dataframe_rooms['Leitungslänge'] = 2*ureg.meter
        dataframe_rooms['Durchmesser'] = None
        dataframe_rooms['Breite'] = None
        dataframe_rooms['Höhe'] = None

        for index, kanalquerschnitt in enumerate(dataframe_rooms["Kanalquerschnitt"]):
            if "Ø" in kanalquerschnitt:
                dataframe_rooms.at[index, 'Durchmesser'] = self.finde_abmessung(kanalquerschnitt)

            elif "x" in kanalquerschnitt:
                dataframe_rooms.at[index, 'Breite'] = self.finde_abmessung(kanalquerschnitt)[0]
                dataframe_rooms.at[index, 'Höhe'] = self.finde_abmessung(kanalquerschnitt)[1]

        dataframe_rooms["Mantelfläche"] = dataframe_rooms.apply(
            lambda row: self.mantelflaeche_kanal(
                cross_section_type,
                self.notwendiger_kanaldquerschnitt(row["Volumenstrom"]),
                zwischendeckenraum
            ) * row["Leitungslänge"], axis=1)

        dataframe_rooms["rechnerischer Durchmesser"] = dataframe_rooms.apply(
            lambda row: round(self.rechnerischer_durchmesser(cross_section_type,
                                                             self.notwendiger_kanaldquerschnitt(row["Volumenstrom"]),
                                                             zwischendeckenraum),
                              2
                              ), axis=1)

        # Ermittlung der Blechstärke
        dataframe_rooms["Blechstärke"] = dataframe_rooms.apply(
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
        dataframe_rooms['Schalldämpfer'] = dataframe_rooms['Raumart'].apply(
            lambda x: 1 if x in liste_raeume_schalldaempfer else 0)

        # Volumenstromregler
        dataframe_rooms["Volumenstromregler"] = 1

        # Berechnung des Blechvolumens
        dataframe_rooms["Blechvolumen"] = dataframe_rooms["Blechstärke"] * dataframe_rooms[
            "Mantelfläche"]

        list_dataframe_rooms_blechgewicht = [v * (7850 * ureg.kilogram / ureg.meter ** 3) for v in
                                             dataframe_rooms["Blechvolumen"]]
        # Dichte Stahl 7850 kg/m³

        # Berechnung des Blechgewichts
        dataframe_rooms["Blechgewicht"] = list_dataframe_rooms_blechgewicht

        return dataframe_rooms

    def co2(self,
            export,
            druckverlust,
            dataframe_rooms,
            dataframe_distribution_network_exhaust_air):

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
        dataframe_distribution_network_exhaust_air["Blechstärke"] = dataframe_distribution_network_exhaust_air.apply(
            lambda row: self.blechstaerke(druckverlust, row["Kanalquerschnitt"]), axis=1)

        # Berechnung des Blechvolumens
        dataframe_distribution_network_exhaust_air["Blechvolumen"] = dataframe_distribution_network_exhaust_air[
                                                                        "Blechstärke"] * \
                                                                    dataframe_distribution_network_exhaust_air[
                                                                        "Mantelfläche"]

        list_dataframe_distribution_network_exhaust_air_blechgewicht = [v * (7850 * ureg.kilogram / ureg.meter ** 3) for
                                                                       v
                                                                       in
                                                                       dataframe_distribution_network_exhaust_air[
                                                                           "Blechvolumen"]]
        # Dichte Stahl 7850 kg/m³

        # Berechnung des Blechgewichts
        dataframe_distribution_network_exhaust_air[
            "Blechgewicht"] = list_dataframe_distribution_network_exhaust_air_blechgewicht

        # Ermittlung des CO2-Kanal
        dataframe_distribution_network_exhaust_air["CO2-Kanal"] = dataframe_distribution_network_exhaust_air[
                                                                     "Blechgewicht"] * (
                                                                         float(
                                                                             gwp("ffa736f4-51b1-4c03-8cdd-3f098993b363")[
                                                                                 0]["A1-A3"]) + float(
                                                                     gwp("ffa736f4-51b1-4c03-8cdd-3f098993b363")[0][
                                                                         "C2"]))

        def querschnittsflaeche_kanaldaemmung(row):
            """
            Berechnet die Querschnittsfläche der Dämmung
            Abluft bekommt keine Dämmung!
            """
            querschnittsflaeche = 0
            if 'Ø' in row['Kanalquerschnitt']:
                try:
                    durchmesser = ureg(row['Durchmesser'])
                except AttributeError:
                    durchmesser = row['Durchmesser']
                querschnittsflaeche = math.pi * ((durchmesser + 0.04 * ureg.meter) ** 2) / 4 - math.pi * (
                        durchmesser ** 2) / 4  # 20mm Dämmung des Lüftungskanals nach anerkanten
                # Regeln der Technik nach Missel Seite 42

            elif 'x' in row['Kanalquerschnitt']:
                try:
                    breite = ureg(row['Breite'])
                    hoehe = ureg(row['Höhe'])
                except AttributeError:
                    breite = row['Breite']
                    hoehe = row['Höhe']
                querschnittsflaeche = ((breite + 0.04 * ureg.meter) * (hoehe + 0.04 * ureg.meter)) - (
                        breite * hoehe)  # 20mm Dämmung des Lüftungskanals nach anerkanten Regeln der Technik nach Missel Seite 42

            return 0*ureg.meter ** 2 # querschnittsflaeche.to(ureg.meter ** 2)

        # Berechnung der Dämmung
        dataframe_distribution_network_exhaust_air[
            'Querschnittsfläche Dämmung'] = dataframe_distribution_network_exhaust_air.apply(
            querschnittsflaeche_kanaldaemmung, axis=1)

        dataframe_distribution_network_exhaust_air['Volumen Dämmung'] = dataframe_distribution_network_exhaust_air[
                                                                           'Querschnittsfläche Dämmung'] * \
                                                                       dataframe_distribution_network_exhaust_air[
                                                                           'Leitungslänge']

        gwp_daemmung = (
                121.8 * ureg.kilogram / ureg.meter ** 3 + 1.96 * ureg.kilogram / ureg.meter ** 3 + 10.21 * ureg.kilogram / ureg.meter ** 3)
        # https://www.oekobaudat.de/OEKOBAU.DAT/datasetdetail/process.xhtml?lang=de&uuid=eca9691f-06d7-48a7-94a9-ea808e2d67e8

        list_dataframe_distribution_network_exhaust_air_CO2_kanaldaemmung = [v * gwp_daemmung for v in
                                                                            dataframe_distribution_network_exhaust_air[
                                                                                "Volumen Dämmung"]]

        dataframe_distribution_network_exhaust_air[
            "CO2-Kanaldämmung"] = list_dataframe_distribution_network_exhaust_air_CO2_kanaldaemmung

        if export:
            # Export to Excel
            dataframe_distribution_network_exhaust_air.to_excel(
                self.paths.export / 'Abluft' / 'dataframe_distribution_network_exhaust_air.xlsx', index=False)

        """
        Berechnung des CO2 für die Raumanbindung
        """
        # Ermittlung des CO2-Kanal
        dataframe_rooms["CO2-Kanal"] = dataframe_rooms["Blechgewicht"] * (float(gwp("ffa736f4-51b1-4c03-8cdd-3f098993b363")[0][
                                         "A1-A3"]) + float(gwp("ffa736f4-51b1-4c03-8cdd-3f098993b363")[0]["C2"])
                               )


        # Vordefinierte Daten für Trox RN Volumenstromregler
        # https://cdn.trox.de/4ab7c57caaf55be6/3450dc5eb9d7/TVR_PD_2022_08_03_DE_de.pdf
        trox_tvr_durchmesser_gewicht = {
            'Durchmesser': [100*ureg.millimeter, 125*ureg.millimeter, 160*ureg.millimeter, 200*ureg.millimeter, 250*ureg.millimeter, 315*ureg.millimeter, 400*ureg.millimeter],
            'Gewicht': [3.3*ureg.kilogram, 3.6*ureg.kilogram, 4.2*ureg.kilogram, 5.1*ureg.kilogram, 6.1*ureg.kilogram, 7.2*ureg.kilogram, 9.4*ureg.kilogram]
        }
        df_trox_tvr_durchmesser_gewicht = pd.DataFrame(trox_tvr_durchmesser_gewicht)

        # Funktion, um das nächstgrößere Gewicht zu finden
        def gewicht_runde_volumenstromregler(row):
            if row['Volumenstromregler'] == 1 and 'Ø' in row['Kanalquerschnitt']:
                rechnerischer_durchmesser = row['rechnerischer Durchmesser']
                next_durchmesser = df_trox_tvr_durchmesser_gewicht[
                    df_trox_tvr_durchmesser_gewicht['Durchmesser'] >= rechnerischer_durchmesser]['Durchmesser'].min()
                return \
                    df_trox_tvr_durchmesser_gewicht[df_trox_tvr_durchmesser_gewicht['Durchmesser'] == next_durchmesser][
                        'Gewicht'].values[0]
            return None

        # Tabelle mit Breite, Höhe und Gewicht für Trox TVJ Volumenstromregler
        # https://cdn.trox.de/502e3cb43dff27e2/af9a822951e1/TVJ_PD_2021_07_19_DE_de.pdf
        df_trox_tvj_durchmesser_gewicht = pd.DataFrame({
            'Breite': [200*ureg.millimeter, 300*ureg.millimeter, 400*ureg.millimeter, 500*ureg.millimeter, 600*ureg.millimeter,

                       200 * ureg.millimeter, 300 * ureg.millimeter, 400 * ureg.millimeter, 500 * ureg.millimeter, 600 * ureg.millimeter, 700 * ureg.millimeter, 800 * ureg.millimeter,

                       300*ureg.millimeter, 400*ureg.millimeter, 500*ureg.millimeter, 600*ureg.millimeter, 700*ureg.millimeter, 800*ureg.millimeter, 900*ureg.millimeter, 1000*ureg.millimeter,

                       400 * ureg.millimeter, 500*ureg.millimeter, 600*ureg.millimeter, 700*ureg.millimeter, 800*ureg.millimeter, 900*ureg.millimeter, 1000*ureg.millimeter
                       ],

            'Höhe': [100*ureg.millimeter, 100*ureg.millimeter, 100*ureg.millimeter, 100*ureg.millimeter, 100*ureg.millimeter,

                     200 * ureg.millimeter, 200 * ureg.millimeter, 200 * ureg.millimeter, 200 * ureg.millimeter, 200 * ureg.millimeter, 200 * ureg.millimeter, 200 * ureg.millimeter,


                     300*ureg.millimeter, 300*ureg.millimeter, 300*ureg.millimeter, 300*ureg.millimeter, 300*ureg.millimeter, 300*ureg.millimeter, 300*ureg.millimeter, 300*ureg.millimeter,

                     400 * ureg.millimeter, 400 * ureg.millimeter, 400 * ureg.millimeter, 400 * ureg.millimeter, 400 * ureg.millimeter, 400 * ureg.millimeter, 400 * ureg.millimeter
                     ],

            'Gewicht': [6*ureg.kilogram, 7*ureg.kilogram, 8*ureg.kilogram, 9*ureg.kilogram, 10*ureg.kilogram,
                        9*ureg.kilogram, 10*ureg.kilogram, 11*ureg.kilogram, 12*ureg.kilogram, 13*ureg.kilogram, 14*ureg.kilogram, 15*ureg.kilogram,
                        10*ureg.kilogram, 11*ureg.kilogram, 12*ureg.kilogram, 13*ureg.kilogram, 15*ureg.kilogram, 16*ureg.kilogram, 18*ureg.kilogram, 19*ureg.kilogram,
                        14*ureg.kilogram, 15*ureg.kilogram, 16*ureg.kilogram, 17*ureg.kilogram, 18*ureg.kilogram, 21*ureg.kilogram, 20*ureg.kilogram]
        })

        # Funktion, um das entsprechende oder nächstgrößere Gewicht zu finden
        def gewicht_eckige_volumenstromregler(row):
            if row['Volumenstromregler'] == 1 and 'x' in row['Kanalquerschnitt']:
                breite, hoehe = row['Breite'], row['Höhe']
                passende_zeilen = df_trox_tvj_durchmesser_gewicht[
                    (df_trox_tvj_durchmesser_gewicht['Breite'] >= breite) & (
                            df_trox_tvj_durchmesser_gewicht['Höhe'] >= hoehe)]
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
        dataframe_rooms['Gewicht Volumenstromregler'] = dataframe_rooms.apply(gewicht_volumenstromregler, axis=1)

        dataframe_rooms["CO2-Volumenstromregler"] = dataframe_rooms['Gewicht Volumenstromregler'] * (
                19.08 + 0.01129 + 0.647) * 0.348432
        # Nach Ökobaudat https://oekobaudat.de/OEKOBAU.DAT/datasetdetail/process.xhtml?uuid=29e922f6-d872-4a67-b579-38bb8cd82abf&version=00.02.000&stock=OBD_2023_I&lang=de

        # CO2 für Schallfämpfer
        # Tabelle Daten für Berechnung nach Trox CA
        durchmesser_tabelle = pd.DataFrame({
            'Durchmesser': [80 * ureg.millimeter, 100 * ureg.millimeter, 125 * ureg.millimeter, 160 * ureg.millimeter,
                            200 * ureg.millimeter, 250 * ureg.millimeter, 315 * ureg.millimeter, 400 * ureg.millimeter,
                            450 * ureg.millimeter, 500 * ureg.millimeter, 560 * ureg.millimeter, 630 * ureg.millimeter,
                            710 * ureg.millimeter, 800 * ureg.millimeter],
            'Innendurchmesser': [80 * ureg.millimeter, 100 * ureg.millimeter, 125 * ureg.millimeter,
                                 160 * ureg.millimeter, 200 * ureg.millimeter, 250 * ureg.millimeter,
                                 315 * ureg.millimeter, 400 * ureg.millimeter, 450 * ureg.millimeter,
                                 500 * ureg.millimeter, 560 * ureg.millimeter, 630 * ureg.millimeter,
                                 710 * ureg.millimeter, 800 * ureg.millimeter],
            'Aussendurchmesser': [184 * ureg.millimeter, 204 * ureg.millimeter, 228 * ureg.millimeter,
                                  254 * ureg.millimeter, 304 * ureg.millimeter, 354 * ureg.millimeter,
                                  405 * ureg.millimeter, 505 * ureg.millimeter, 636 * ureg.millimeter,
                                  716 * ureg.millimeter, 806 * ureg.millimeter, 806 * ureg.millimeter,
                                  908 * ureg.millimeter, 1008 * ureg.millimeter]
        })

        # Funktion zur Berechnung der Fläche des Kreisrings
        def volumen_daemmung_schalldaempfer(row):
            rechnerischer_durchmesser = row['rechnerischer Durchmesser']
            passende_zeilen = durchmesser_tabelle[durchmesser_tabelle['Durchmesser'] >= rechnerischer_durchmesser]
            if not passende_zeilen.empty:
                naechster_durchmesser = passende_zeilen.iloc[0]
                innen = naechster_durchmesser['Innendurchmesser']
                aussen = naechster_durchmesser['Aussendurchmesser']
                volumen = math.pi * (aussen ** 2 - innen ** 2) / 4 * 0.88 * ureg.meter  # Für einen Meter Länge des
                # Schalldämpfers, entspricht nach Datenblatt einer Länge des Dämmkerns von 0.88m,
                return volumen.to(ureg.meter**3)
            return None

        # Gewicht Dämmung Schalldämpfer
        dataframe_rooms['Volumen Dämmung Schalldämpfer'] = dataframe_rooms.apply(volumen_daemmung_schalldaempfer,
                                                                                 axis=1)

        gwp_daemmung_schalldaempfer = (117.4 + 2.132 + 18.43) * (ureg.kilogram / (ureg.meter ** 3))
        # https://oekobaudat.de/OEKOBAU.DAT/datasetdetail/process.xhtml?uuid=89b4bfdf-8587-48ae-9178-33194f6d1314&version=00.02.000&stock=OBD_2023_I&lang=de

        list_dataframe_distribution_network_exhaust_air_CO2_schalldaempferdaemmung = [v * gwp_daemmung_schalldaempfer for
                                                                                     v in dataframe_rooms[
                                                                                         "Volumen Dämmung Schalldämpfer"]]

        dataframe_rooms[
            "CO2-Dämmung Schalldämpfer"] = list_dataframe_distribution_network_exhaust_air_CO2_schalldaempferdaemmung

        # Gewicht des Metalls des Schalldämpfers für Trox CA für Packungsdicke 50 bis 400mm danach Packungsdicke 100
        # vordefinierte Daten für Trox CA Schalldämpfer
        trox_ca_durchmesser_gewicht = {
            'Durchmesser': [80 * ureg.millimeter, 100 * ureg.millimeter, 125 * ureg.millimeter, 160 * ureg.millimeter,
                            200 * ureg.millimeter, 250 * ureg.millimeter, 315 * ureg.millimeter, 400 * ureg.millimeter,
                            450 * ureg.millimeter, 500 * ureg.millimeter, 560 * ureg.millimeter, 630 * ureg.millimeter,
                            710 * ureg.millimeter, 800 * ureg.millimeter],
            'Gewicht': [6 * ureg.kilogram, 6 * ureg.kilogram, 7 * ureg.kilogram, 8 * ureg.kilogram, 10 * ureg.kilogram,
                        12 * ureg.kilogram, 14 * ureg.kilogram, 18 * ureg.kilogram, 24 * ureg.kilogram,
                        28 * ureg.kilogram, 45 * ureg.kilogram * 2 / 3, 47 * ureg.kilogram * 2 / 3,
                        54 * ureg.kilogram * 2 / 3, 62 * ureg.kilogram * 2 / 3]
        }
        df_trox_ca_durchmesser_gewicht = pd.DataFrame(trox_ca_durchmesser_gewicht)

        # Funktion, um das nächstgrößere Gewicht zu finden
        def gewicht_schalldaempfer_ohne_daemmung(row):
            if row['Schalldämpfer'] == 1:
                rechnerischer_durchmesser = row['rechnerischer Durchmesser']
                passende_zeilen = df_trox_ca_durchmesser_gewicht[
                    df_trox_ca_durchmesser_gewicht['Durchmesser'] >= rechnerischer_durchmesser]
                if not passende_zeilen.empty:
                    next_durchmesser = passende_zeilen['Durchmesser'].min()
                    gewicht_schalldaempfer = \
                        df_trox_ca_durchmesser_gewicht[
                            df_trox_ca_durchmesser_gewicht['Durchmesser'] == next_durchmesser][
                            'Gewicht'].values[0]
                    daemmung_gewicht = row[
                        "Gewicht Dämmung Schalldämpfer"] if "Gewicht Dämmung Schalldämpfer" in row and not pd.isnull(
                        row["Gewicht Dämmung Schalldämpfer"]) else 0
                    return gewicht_schalldaempfer - daemmung_gewicht
            return None

        dataframe_rooms['Gewicht Blech Schalldämpfer'] = dataframe_rooms.apply(gewicht_schalldaempfer_ohne_daemmung,
                                                                               axis=1)

        dataframe_rooms["CO2-Blech Schalldämfer"] = dataframe_rooms["Gewicht Blech Schalldämpfer"] * (
                float(gwp("ffa736f4-51b1-4c03-8cdd-3f098993b363")[0]["A1-A3"]) + float(
            gwp("ffa736f4-51b1-4c03-8cdd-3f098993b363")[0]["C2"]))

        # Berechnung der Dämmung
        dataframe_rooms['Querschnittsfläche Dämmung'] = dataframe_rooms.apply(querschnittsflaeche_kanaldaemmung,
                                                                              axis=1)

        dataframe_rooms['Volumen Dämmung'] = dataframe_rooms['Querschnittsfläche Dämmung'] * dataframe_rooms[
            'Leitungslänge']

        gwp_kanaldaemmung = (
                    121.8 * (ureg.kilogram / ureg.meter ** 3) + 1.96 * (ureg.kilogram / ureg.meter ** 3) + 10.21 * (
                        ureg.kilogram / ureg.meter ** 3))
        # https://www.oekobaudat.de/OEKOBAU.DAT/datasetdetail/process.xhtml?lang=de&uuid=eca9691f-06d7-48a7-94a9-ea808e2d67e8

        list_dataframe_rooms_CO2_kanaldaemmung = [v * gwp_kanaldaemmung for v in dataframe_rooms["Volumen Dämmung"]]

        dataframe_rooms['CO2-Kanaldämmung'] = list_dataframe_rooms_CO2_kanaldaemmung


        if export:
            # Export to Excel
            dataframe_rooms.to_excel(self.paths.export / 'Abluft' / 'Datenbank_Raumanbindung.xlsx', index=False)

        return druckverlust, dataframe_rooms, dataframe_distribution_network_exhaust_air
