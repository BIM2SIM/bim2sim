import math
import pandas as pd
from openpyxl.utils import get_column_letter
from bim2sim.tasks.base import ITask
from bim2sim.utilities.common_functions import filter_instances
from bim2sim.elements.mapping.units import ureg
import matplotlib.pyplot as plt
from bim2sim.plugins.PluginLCA.bim2sim_lca.task import (CalcAirFlow)
from mpl_toolkits.mplot3d import Axes3D
class DesignLCA(ITask):
    """Design of the LCA

    Annahmen:
    Inputs: IFC Modell, Räume,

    Args:
        instances: bim2sim elements
    Returns:
        instances: bim2sim elements enriched with needed air flows
    """
    reads = ('instances', )
    touches = ('instances', )

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





    def center(self, thermal_zones):
        """Function calculates the airflow of one specific zone.

        Args:
            tz: ThermalZone bim2sim element
        Returns:
            center of the room
        """
        # Listen:
        room_ceiling_ventilation_outlet = []

        for tz in thermal_zones:
            room_ceiling_ventilation_outlet.append([round(tz.space_center.X(), 2), round(tz.space_center.Y(), 2),
             round(tz.space_center.Z() + tz.height.magnitude, 2)])

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
            airflow_list.append(round(tz.air_flow * (3600 * ureg.second) / (1 * ureg.hour ), 3))
        return airflow_list

    def intersection_points(self, thermal_zones, ceiling_point):
        z_coordinate_set = set(ceiling_point[2])

        intersection_points_list = []
        for i in range(len(ceiling_point)):
            for j in range(i + 1, len(ceiling_point)):
                p1 = ceiling_point[i]
                p2 = ceiling_point[j]
                # Schnittpunkte entlang der X- und Y-Achsen
                intersection_points_list.append((p2[0], p1[1], p1[
                    2]))  # Schnittpunkt auf der Linie parallel zur X-Achse von p1 und zur Y-Achse von p2
                intersection_points_list.append((p1[0], p2[1], p2[
                    2]))  # Schnittpunkt auf der Linie parallel zur Y-Achse von p1 und zur X-Achse von p2


        intersection_points_list_set = list(set(intersection_points_list))
        return intersection_points_list_set


    def visualisierung(self, room_ceiling_ventilation_outlet, air_flow_building, intersection):
        """The function visualizes the points in a diagram

        Args:
            room_ceiling_ventilation_outlet: Point at the ceiling in the middle of the room
            air_flow_building:
        Returns:
            3D diagramm
        """


        labels = air_flow_building

        # 3D-Diagramm erstellen
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')

        # Punkte hinzufügen
        for i in range(len(room_ceiling_ventilation_outlet)):
            if room_ceiling_ventilation_outlet[i][2] == 1.05:
                ax.scatter(room_ceiling_ventilation_outlet[i][0], room_ceiling_ventilation_outlet[i][1],
                           room_ceiling_ventilation_outlet[i][2])

        # for i in range(len(intersection)):
        #     if intersection[i][2] == 1.05:
        #         ax.scatter(intersection [i][0], intersection[i][1], intersection[i][2])

        if False:
            labels = air_flow_building

            # Beschriftungen für jeden Punkt hinzufügen
            for i in range(len(room_ceiling_ventilation_outlet)):
                ax.text(room_ceiling_ventilation_outlet[i][0], room_ceiling_ventilation_outlet[i][1],
                        room_ceiling_ventilation_outlet[i][2], labels[i])

        # Achsenbeschriftungen
        ax.set_xlabel('X-Achse')
        ax.set_ylabel('Y-Achse')
        ax.set_zlabel('Z-Achse')

        # Diagramm anzeigen
        plt.show()
