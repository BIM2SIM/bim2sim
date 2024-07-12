import csv
import pint
from pathlib import Path
import pandas as pd
import numpy as np
import networkx as nx
from networkx.readwrite import json_graph
import ifcopenshell
import json
import matplotlib.pyplot as plt
import math
import colebrook
from pint import Quantity
from scipy.spatial import distance

from bim2sim.elements.mapping.units import ureg
from bim2sim.tasks.base import ITask


class CalculateHydraulicSystem(ITask):
    """Calculates the hydraulic pipe system"""


    """    DIN EN 12828: Heizanlagen in Gebäuden - Planung, Installation und Betrieb
       DIN 1988: Technische Regeln für Trinkwasser-Installationen
       DIN 4751-1: Heizungsanlagen für Wärmeerzeugung - Teil 1: Bemessung
       DIN 4701: Heizlast in Gebäuden
       DIN EN 1717: Schutz des Trinkwassers in Trinkwasser-Installationen und allgemeinen Anforderungen an Sicherheitseinrichtungen

        Berechnung der Volumenstromdichte (v):

    v = Q / (3600 * rho)

    Q: Wärmeleistung in Watt
    rho: Dichte des Mediums in kg/m³

    Berechnung des Innendurchmessers (d):

    d = 2 * sqrt(F * v / (pi * v_max))

    F: Reibungsfaktor (abhängig von der Rohroberfläche und der Strömungsgeschwindigkeit)
    v_max: Maximale Strömungsgeschwindigkeit (abhängig vom Medium)

    Berechnung des Druckverlusts (dp):

    dp = f * (L / d) * (v^2 / 2)

    f: Reibungskoeffizient (abhängig von der Rohroberfläche und der Strömungsgeschwindigkeit)
    L: Rohrlänge in Metern
    d: Rohrdurchmesser in Metern
    v: Strömungsgeschwindigkeit in m/s

    Berechnung des benötigten Pumpendrucks (p):

    p = dp + h_geod + h_zu + h_ab

    h_geod: Geodätische Höhe (Höhenunterschied zwischen Anfangs- und Endpunkt)
    h_zu: Höhendifferenz zur Pumpe (z.B. bei einem Heizkessel im Keller)
    h_ab: Höhendifferenz nach der Pumpe (z.B. bei einem höher gelegenen Heizkörper)

    Dimensionierung der Pumpe:

    Die benötigte Förderhöhe der Pumpe ergibt sich aus dem benötigten Pumpendruck (p) und dem spezifischen Gewicht des Mediums (graph):

    H = p / (rho * graph)

    Die benötigte Fördermenge ergibt sich aus dem Volumenstrom (Q) und der Dichte des Mediums (rho):

    Q = H * A * v

    A: Querschnittsfläche des Rohrs in m²C
    # 1. Massenstrom, Temperatur, Druck (Anfangs und Endpunkten) Ein Rohr: Δp = (128 * η * L * Q) / (π * d^4 * ρ)
    # 2. d (massenstrom, delta_p, l, v): d = (8 * Q * f * L) / (π^2 * Δp * ρ), Q = A * v = A * (volumetrische Durchflussrate) = (π * d^2 / 4) * v = (π * d^2 / 4) * (Q / A) = (π * d^2 / 4) * (2 * Δp / (ρ * v)^2)
    # 3. delta_P (d, l v, fluid)
    # 4. Massenstrom (d, delta_p) v = Q / A = (4 * Q) / (π * d^2)
    # 5. Iteration durchlaufen lassen -> Prüfen Δp = (ρ * v^2 / 2) * (1 - (A2 / A1)^2)
    """
    ureg = pint.UnitRegistry()

    reads = ('heating_graph', 'heat_demand_dict')
    touches = ()

    def run(self, heating_graph, heat_demand_dict):

        self.material_file = self.paths.export / "material_export.xlsx"
        self.heat_demand_dict = heat_demand_dict

        # flags
        self.one_pump_flag = self.playground.sim_settings.one_pump_flag

        ## pipe
        self.density_pipe = self.playground.sim_settings.density_pipe * (ureg.kilogram / ureg.meter ** 3)
        self.absolute_roughness = self.playground.sim_settings.absolute_roughness_pipe

        # temperatures
        self.temperature_forward = self.playground.sim_settings.T_forward * ureg.kelvin
        self.temperature_backward = self.playground.sim_settings.T_backward * ureg.kelvin
        self.temperature_room = self.playground.sim_settings.T_room * ureg.kelvin
        self.delta_T = self.temperature_forward - self.temperature_backward

        self.g = self.playground.sim_settings.g * (ureg.meter / ureg.second ** 2)
        self.density_fluid = self.playground.sim_settings.density_fluid * (ureg.kilogram / ureg.meter ** 3)
        self.c_p_fluid = self.playground.sim_settings.c_p_fluid * (ureg.joule / (ureg.kilogram * ureg.kelvin))
        self.kinematic_velocity_fluid = self.playground.sim_settings.kinematic_velocity_fluid * (
                    ureg.millimeter ** 2 / ureg.second)
        self.v_max = self.playground.sim_settings.v_max * (ureg.meter / ureg.second)
        self.v_mean = self.playground.sim_settings.v_mean * (ureg.meter / ureg.second)
        self.p_max = self.playground.sim_settings.p_max * (ureg.meter / ureg.second)

        # Radiator
        self.f = self.playground.sim_settings.f

        graph = heating_graph

        # Zähle Fenster pro Raum
        graph = self.count_space(graph=graph)
        """graph = nx.convert_node_labels_to_integers(graph, first_label=0, ordering="default",
                                                       label_attribute="old_label")
        print(graph)"""
        # graph = self.index_strang(graph=graph)
        # Entferne nicht notwendige attribute
        graph = self.remove_attributes(graph=graph, attributes=["center_wall_forward", "snapped_nodes"])
        # Versorge Punkte mit Parameter: (Max. Wärmemenge, Reibungskoeffizient zeta, Druckverluste
        graph = self.initilize_design_operating_point(graph=graph, viewpoint="design_operation")

        # 1. Berechne Design der Radiatoren (Endpunkte): Massenstrom/Volumenstrom
        graph = self.update_delivery_node(graph=graph,
                                      heating_exponent=1.3,
                                      viewpoint="design_operation_norm",
                                      nodes=["radiator_forward", "radiator_backward"],
                                      delivery_type="radiator")
        # 2. Berechne Massenstrom/ Volumenstrom an den Endpunkten
        # graph = self.update_radiator_mass_flow_nodes(graph=graph, nodes=["radiator_forward", "radiator_backward"])
        # graph = self.update_radiator_volume_flow_nodes(graph=graph, nodes=["radiator_forward", "radiator_backward"])
        # 3. Trenne Graphen nach End und Anfangspunkten

        # GeometryBuildingsNetworkx.visulize_networkx(graph=forward, type_grid="Vorlaufkreislauf")
        # GeometryBuildingsNetworkx.visulize_networkx(graph=backward, type_grid="Rücklaufkreislauf")
        # plt.show()
        # 3. Iteriere von den Endknoten  zum Anfangspunkt,
        #  summiere die Massenstrom an Knoten, Berechne Durchmesser der Knoten
        composed_graph = self.calculate_mass_volume_flow_node(graph=graph, viewpoint="design_operation_norm")
        # composed_graph = self.reindex_cycle_graph(graph=graph, start_node=start)
        # Berechnet Durchmesser an jeder Kante
        composed_graph = self.update_pipe_inner_diameter_edges(graph=composed_graph,
                                                               v_mittel=self.v_mean,
                                                               viewpoint="design_operation_norm",
                                                               security_factor=1.15)

        # Druckverluste an den Kanten
        self.calculate_pressure_node(graph=composed_graph, viewpoint="design_operation_norm")
        # Ermittlung Druckverlust im System
        """self.plot_attributes_nodes(graph=composed_graph,
                                   type_grid="Vorlaufkreislauf",
                                   viewpoint=None,
                                   attribute=None)"""
        composed_graph = self.iterate_circle_pressure_loss_nodes(graph=composed_graph,
                                                                 viewpoint="design_operation_norm")

        """self.plot_3D_pressure(graph=composed_graph,
                              viewpoint="design_operation_norm",
                              node_attribute="pressure_out",
                              title='Positionsbasierter Druckverlauf in einem Rohrnetzwerk')"""
        # plt.show()
        """self.plot_attributes_nodes(graph=composed_graph, type_grid="Heizung", viewpoint="design_operation_norm",
                                   attribute="heat_flow")"""
        # plt.show()
        # Bestimmung Netzschlechtpunkt im System
        min_pressure, max_pressure, bottleneck_node, pressure_difference, composed_graph = self.calculate_network_bottleneck(
            graph=composed_graph,
            nodes=["radiator_forward"],
            viewpoint="design_operation_norm")
        self.calculate_pump(graph=composed_graph,
                            efficiency=0.5,
                            pressure_difference=pressure_difference,
                            viewpoint="design_operation_norm")
        viewpoint = "design_operation_norm"
        for node, data in graph.nodes(data=True):
            if "Rücklaufabsperrung" in data["type"]:
                pressure_out = data["pressure_out"][viewpoint]
                pressure_in = data["pressure_in"][viewpoint]
                V_flow = data["V_flow"][viewpoint]
                pressure_diff_valve = pressure_in - pressure_out
                autoritat = self.calculate_valve_autoritat(pressure_diff_system=pressure_difference,
                                                           pressure_diff_valve=pressure_diff_valve)
                graph.nodes[node]["autoritat"] = autoritat
                K_v = self.calculate_valve_Kv(V_flow=V_flow, pressure_diff=pressure_diff_valve)
                graph.nodes[node]["K_v"] = K_v

        # self.calculate_flow(graph=graph, source=start_node, sink=bottleneck_node)
        """self.plot_attributes_nodes(graph=composed_graph, type_grid="Vorlaufkreislauf", viewpoint="design_operation_norm",
                                   attribute=None)

        self.plot_3D_pressure(graph=composed_graph,
                              viewpoint="design_operation_norm",
                              node_attribute="pressure_out",
                              title='Positionsbasierter Druckverlauf in einem Rohrnetzwerk')"""
        # plt.show()

        self.calculate_pump_system_curve(graph=composed_graph,
                                         bottleneck_point=bottleneck_node,
                                         viewpoint="design_operation_norm")
        # TODO Graph cannot be saved yet cause of Quantity attributes in graph, which arent json serializable
        # self.save_hydraulic_system_graph_json(graph=graph, filename="hydraulic_system_network.json", type_grid="Calculate Heating Graph")
        # plt.show()
        nodes = ["radiator_forward"]
        radiator_nodes = [n for n, attr in graph.nodes(data=True) if
                          any(t in attr.get("type", []) for t in nodes)]

        self.create_bom_edges(graph=composed_graph,
                              filename=self.material_file,
                              sheet_name="pipe",
                              viewpoint="design_operation_norm")
        bom = self.write_component_list(graph=composed_graph)
        self.create_bom_nodes(graph=graph, filename=self.material_file, bom=bom)
        #plt.show()

    def calc_pipe_friction_resistance(self,
                                      pipe_friction_coefficient,
                                      inner_diameter,
                                      v_mid):

        pipe_friction_resistance = 0.5 * (
                pipe_friction_coefficient * self.density_fluid * (1 / inner_diameter) * v_mid ** 2).to(
            ureg.Pa / ureg.m)
        return round(pipe_friction_resistance, 2)

    def save_hydraulic_system_graph_json(self, graph, filename, type_grid):
        """

        Args:
            graph ():
            file ():
        """
        file = self.paths.export / filename
        print(f"Save Networkx {graph} with type {type_grid} in {file}.")
        data = json_graph.node_link_data(graph)
        with open(file, 'w') as f:
            json.dump(data, f)

    def select_heating_model(self, model_dict: dict, calculated_heat_flow, calculated_volume):
        """

        Args:
            model_dict ():
            calculated_heat_flow ():
            calculated_volume ():

        Returns:

        """

        selected_model = None
        min_mass = float('inf') * ureg.kilogram
        material = None
        l1 = None
        length = None
        norm_heat_flow = None
        length_minimum = 400 * ureg.millimeter
        length_max = 3000 * ureg.millimeter
        for model in model_dict:

            if 'Wasserinhalt' and 'Masse' and 'Normwärmeleistung' and 'Material' in model_dict[model]:

                volume_per_length = model_dict[model]['Wasserinhalt']
                mass_per_length = model_dict[model]['Masse']
                norm_heat_flow_per_length = model_dict[model]['Normwärmeleistung']
                material = model_dict[model]['Material']
                l1 = (calculated_heat_flow / norm_heat_flow_per_length).to_base_units()

                l2 = (calculated_volume / volume_per_length).to_base_units()
                # if length_minimum <= l1 <= length_max: # and length_minimum <= l2 <= length_max:
                if l1 <= length_max:
                    mass = l1 * mass_per_length
                    if mass < min_mass:
                        min_mass = mass
                        selected_model = model
                        length = l1
                        norm_heat_flow = norm_heat_flow_per_length

        return selected_model, min_mass, material, length, norm_heat_flow

    @staticmethod
    def read_radiator_material_excel(filename,
                                     sheet_name,
                                     ):
        """

        Args:
            filename ():
            sheet_name ():

        Returns:

        """
        data = pd.read_excel(filename, sheet_name=sheet_name)
        # Daten aus der Tabelle auslesen und verarbeiten
        model_dict = {}
        for index, row in data.iterrows():
            data_dict = {}
            if not pd.isnull(row['Typ']):
                data_dict["typ"] = row['Typ']
            if not pd.isnull(row['Normwärmeleistung ((75/65/20 °C) in W/m']):
                data_dict["Normwärmeleistung"] = row['Normwärmeleistung ((75/65/20 °C) in W/m'] * (
                            ureg.watt / ureg.meter)
            if not pd.isnull(row['Wasserinhalt in l/m']):
                data_dict["Wasserinhalt"] = row['Wasserinhalt in l/m'] * (ureg.liter / ureg.meter)
            if not pd.isnull(row['Masse in kg/m']):
                data_dict["Masse"] = row['Masse in kg/m'] * (ureg.kilogram / ureg.meter)
            if not pd.isnull(row['Material']):
                data_dict["Material"] = row['Material']
            # Weiterverarbeitung der Daten (hier nur Ausgabe als Beispiel)
            model_dict[index] = data_dict
        return model_dict

    def read_pipe_data_excel(self,
                             filename,
                             sheet_name,
                             calc_inner_diameter: float = 11.5):
        data = pd.read_excel(filename, sheet_name=sheet_name)
        inner_diameter_list = []
        inner_diameter_list = {}
        material = None
        density = None
        pipe_mass = None
        # calc_inner_diameter = calc_inner_diameter.magnitude
        for index, row in data.iterrows():

            material = row['Material']
            mass = row["Rohrgewicht [kg/m]"] * (ureg.kilograms / ureg.meter)
            density = row['Dichte kg/m³'] * (ureg.kilograms / ureg.meter ** 3)
            outer_diameter = row['Außendurchmesser [mm]'] * ureg.millimeter
            wall_thickness = row["Normwanddicke  [mm]"] * ureg.millimeter
            inner_diameter = outer_diameter - 2 * wall_thickness
            if calc_inner_diameter <= inner_diameter:
                inner_diameter_list[inner_diameter] = outer_diameter
                pipe_mass = mass

        inner_diameter = min(inner_diameter_list,
                             key=lambda x: abs(inner_diameter_list[x] - calc_inner_diameter))
        outer_diameter = inner_diameter_list[inner_diameter]
        return inner_diameter, outer_diameter, material, density, pipe_mass

    def calculate_dammung(self,
                          outer_diameter):
        if outer_diameter.magnitude <= 22:
            s = 20 * ureg.millimeter
        elif outer_diameter.magnitude > 22 and outer_diameter.magnitude <= 30:
            s = 30 * ureg.millimeter
        else:
            s = 100 * ureg.millimeter
        return (math.pi / 4) * (s ** 2 - outer_diameter ** 2)

    def read_pipe_material_excel(self,
                                 filename,
                                 sheet_name,
                                 calc_inner_diameter: float = 11.5):
        """

        Args:
            filename ():
            sheet_name ():
            calc_inner_diameter ():

        Returns:

        """

        data = pd.read_excel(filename, sheet_name=sheet_name)
        inner_diameter_list = []
        inner_diameter_list = {}
        material = None
        density = None
        for index, row in data.iterrows():
            data_wall = row['Abmessung Aussendurchmesser X Wanddicke (mm)'].split("x")
            material = row['Material']
            density = row['Dichte kg/m³'] * (ureg.kilograms / ureg.meter ** 3)
            outer_diameter = float(data_wall[0].strip().replace(',', '.')) * ureg.millimeter
            wall_thickness = float(data_wall[1].strip().replace(',', '.')) * ureg.millimeter
            inner_diameter = outer_diameter - 2 * wall_thickness
            if calc_inner_diameter <= inner_diameter:
                inner_diameter_list[inner_diameter] = outer_diameter
        inner_diameter = min(inner_diameter_list,
                             key=lambda x: abs(inner_diameter_list[x] - calc_inner_diameter))
        outer_diameter = inner_diameter_list[inner_diameter]
        return inner_diameter, outer_diameter, material, density

    def calculate_pipe_material(self, density, length, inner_diameter, outer_diameter):
        """
        Args:
            density ():
            length ():
            inner_diameter ():
            outer_diameter ():
        """
        mass_pipe = density * length * math.pi * (outer_diameter ** 2 - inner_diameter ** 2) / 4
        return mass_pipe

    def get_maximal_volume_flow(self, graph, viewpoint: str):
        max_volumenstrom = 0
        # Iteration über alle Knoten
        for node in graph.nodes:
            # Überprüfen, ob der Knoten einen Volumenstrom-Wert hat
            if 'V_flow' in graph.nodes[node]:
                volumenstrom = graph.nodes[node]['V_flow'][viewpoint].to(ureg.meter ** 3 / ureg.hour)
                # Aktualisieren des maximalen Volumenstroms, wenn ein größerer Wert gefunden wird
                if volumenstrom > max_volumenstrom:
                    max_volumenstrom = volumenstrom
        # max_volumenstrom = 1.2 * max_volumenstrom

        return max_volumenstrom

    def calculate_velocity(self, flow_rate, inner_diameter):
        """

        Args:
            flow_rate ():
            inner_diameter ():

        Returns:

        """
        v_mid = flow_rate / ((math.pi * inner_diameter ** 2) / 4)
        return v_mid

    @staticmethod
    def pump_section(data):
        """

        Args:
            data ():
        """
        # fig, ax1 = plt.subplots()
        max_flow = max(data, key=lambda x: x[0])[0]
        max_head = max(data, key=lambda x: x[1])[1]

        # Unterteile die Pumpenkennlinie grafisch in drei Bereiche
        # Bereich 1: Niedrige Förderhöhe und niedriger Volumenstrom (geschlossener Ventilpunkt)
        pump_low_flow_low_head = [p for p in data if p[0] <= 0.33 * max_flow]
        """ax1.plot([p[0] for p in pump_low_flow_low_head], [p[1] for p in pump_low_flow_low_head], 'r--',
                 label='Bereich 1: Niedrige Förderhöhe und niedriger Volumenstrom')"""
        # Bereich 2: Optimaler Betriebspunkt
        pump_optimal_range = [p for p in data if
                              0.33 * max_flow <= p[0] <= 0.66 * max_flow]
        """ax1.plot([p[0] for p in pump_optimal_range], [p[1] for p in pump_optimal_range], 'graph--',
                 label='Bereich 2: Optimaler Betriebspunkt')"""

        # Bereich 3: Hohe Förderhöhe und hoher Volumenstrom (offener Ventilpunkt)
        pump_high_flow_high_head = [p for p in data if p[0] >= 0.66 * max_flow]
        """ax1.plot([p[0] for p in pump_high_flow_high_head], [p[1] for p in pump_high_flow_high_head], 'b--',
                 label='Bereich 3: Hohe Förderhöhe und hoher Volumenstrom')"""

        # Wähle eine passende Pumpe basierend auf dem Betriebspunkt und den technischen Daten aus
        # Hier müsstest du die tatsächlichen technischen Daten verschiedener Pumpenmodelle und die Auswahllogik implementieren.

        # Zeige das Diagramm mit der Legende an
        """plt.legend()
        plt.xlabel('Fördermenge')
        plt.ylabel('Förderhöhe')
        plt.title('Pumpenkennlinie')
        plt.grid(True)
        plt.show()"""
        return pump_low_flow_low_head, pump_optimal_range, pump_high_flow_high_head

    @staticmethod
    def connect_forward_backward(graph,
                                 type_delivery: list,
                                 color: str,
                                 grid_type: str,
                                 edge_type: str,
                                 type_units: float = False):
        element_nodes = {}
        for node, data in graph.nodes(data=True):
            if set(type_delivery) & set(data["type"]):
                element = data["element"]
                for ele in element:
                    if ele not in element_nodes:
                        element_nodes[ele] = []
                    element_nodes[ele].append(node)
        for element, nodes in element_nodes.items():
            source_backward = nodes[0]
            source_forward = nodes[1]
            for node in nodes:
                if "backward" == graph.nodes[node]["grid_type"]:
                    source_backward = node
                else:
                    source_forward = node
            length = abs(
                distance.euclidean(graph.nodes[nodes[0]]["pos"], graph.nodes[nodes[1]]["pos"]))  # * ureg.meter
            if type_units is True:
                length = length * ureg.meter

            graph.add_edge(source_forward,
                           source_backward,
                           color=color,
                           type=edge_type,
                           grid_type=grid_type,
                           length=length,
                           flow_rate=0.0,
                           resistance=2.0)

        return graph

    @staticmethod
    def polynomial_regression(data,
                              degree: int = 2, ):
        """

        Args:
            data ():
            degree ():

        Returns:

        """
        max_x_value = max(data, key=lambda x: x[0])[0]
        # plt.plot([p[0] for p in pump_curve], [p[1] for p in pump_curve], 'bo', label='Pumpenkennlinie')
        # Führe eine Polynom-Regression durch, um die Pumpenkennlinie zu glätten
        degree = degree  # Grad des Polynoms, du kannst auch andere Grade wählen
        coefficients = np.polyfit([p[0] for p in data], [p[1] for p in data], degree)
        polynomial = np.poly1d(coefficients)
        # Erzeuge eine glatte Kurve basierend auf der Regression
        x_values = np.linspace(0, max_x_value, 500)  # Wähle geeignete x-Werte für die glatte Kurve
        y_values = polynomial(x_values)
        # Plote die glatte Kurve
        # plt.plot(x_values, y_values, 'r-', label='Regression')
        # Wähle eine passende Pumpe basierend auf der glatten Kurve und den technischen Daten aus
        # Hier müsstest du die tatsächlichen technischen Daten verschiedener Pumpenmodelle und die Auswahllogik implementieren.
        # Zeige das Diagramm mit der Legende an
        # plt.legend()
        # plt.xlabel('Fördermenge')
        # plt.ylabel('Förderhöhe')
        # plt.title('Pumpenkennlinie')
        # plt.grid(True)
        # plt.show()
        data_points = [(x, y) for x, y in zip(x_values, y_values)]

        return data_points

    def calculate_pump_system_curve(self,
                                    graph,
                                    bottleneck_point,
                                    viewpoint):
        """

        Args:
            graph ():
            flow_rates ():
        """
        # Systemkurve: Berechnung des Druckverlusts im Rohrsystem für verschiedene Volumenströme
        # 1. Verschiedene Volumenströme erstellen
        V_max_flow = self.get_maximal_volume_flow(graph=graph, viewpoint="design_operation_norm")
        flow_rates = np.linspace(0, V_max_flow, 100)
        pump_list = []
        for node, data in graph.nodes(data=True):
            if "heat_source" in set(data["type"]):
                V_flow = graph.nodes[node]["V_flow"][viewpoint].to(ureg.meter ** 3 / ureg.hour)
                head = graph.nodes[node]["head"][viewpoint]
                operation_head = head
                operation_point = (V_flow, head)

            if "Pumpe" in data["type"]:
                pump_list.append(node)
        system_pressure_loss = []
        pump_system_head = {}
        # Liste aus Druckverlusten basierend auf den Volumenströmen
        for pump in pump_list:
            system_head = {}
            # operation_head = graph.nodes[pump]["head"][viewpoint]
            V_flow = graph.nodes[pump]["V_flow"][viewpoint]
            for flow in flow_rates:
                head = self.system_pressure_curve(flow=flow,
                                                  V_flow=V_flow,
                                                  operation_head=operation_head)
                system_head[flow] = head
            pump_system_head[pump] = system_head


        pump_data = self.operation_pump_pressure()
        # pump_pressure_values = [value for value in dp_list]
        # pump_flow_values = [value for value in V_flow_list]
        # Bestimmung des Betriebspunkts (Schnittpunkt)
        system_head_values = [value.magnitude for value in system_head]
        system_pressure_loss_values = [value.magnitude for value in system_pressure_loss]
        # index = np.argmin(np.abs(np.array(pump_pressure_values) - np.array(system_pressure_loss_values)))
        # operating_flow_rate = flow_rates[index]
        for value in system_pressure_loss:
            pressure_unit = value
        for value in system_head:
            head_unit = value

        """self.plot_pump_system_curve(flow_rates=flow_rates,
                                    system_head=pump_system_head,
                                    operation_point=operation_point,
                                    pump_data=pump_data,
                                    # flow_rate_pump = V_flow_list,
                                    # dp_pump = dp_list,
                                    # system_head=system_head_values,
                                    # pump_power=pump_pressure_values,
                                    # pressure_unit=pressure_unit,
                                    # head_unit=head_unit,
                                    # system_loss=system_pressure_loss_values,
                                    # operating_flow_rate=operating_flow_rate,
                                    # operation_pump_pressure=operation_pump_pressure
                                    )"""
        # return operating_flow_rate, operation_pump_pressure

    def calculate_head(self,
                       graph,
                       pressure_difference: float,
                       # length:float,
                       # pipe_friction_resistance:float,
                       # coefficient_resistance:float
                       ):
        """
        H = (P_out - P_in) / (ρ * graph)
        Args:
            pressure_in ():
            pressure_out ():
        """
        #TODO Fehler mit graph
        return round((pressure_difference * 1 / (self.density_fluid * self.g)).to_base_units(), 4)
        # ((pipe_friction_resistance * length * coefficient_resistance) / 10000)
        # return ((pipe_friction_resistance * length )  )

    def heat_norm_radiator(self,
                           log_mean_temperature_operation: float,
                           heating_exponent: float,
                           log_mean_temperature_norm: float,
                           Q_heat_operation: float
                           ):
        """

        Args:
            log_mean_temperature_operation ():
            heating_exponent ():
            log_mean_temperature_norm ():
            Q_heat_operation ():
            Q = 1,15 Q_N
        """
        Q_heat_norm = (Q_heat_operation / (
                    (log_mean_temperature_operation / log_mean_temperature_norm) ** heating_exponent))
        return Q_heat_norm

    def heat_output_radiator(self,
                             log_mean_temperature_operation: float,
                             heating_exponent: float,
                             log_mean_temperature_norm: float,
                             heat_norm: float):
        """
        Radiatoren: n = 1,30
        Konvektoren: n = 1,25 &ndash; 1,50
        Plattenheizkörper: n = 1,20 &ndash; 1,33
        Handtuchradiatoren: n = 1,20 &ndash; 1,30
        Fu&szlig;bodenheizung: n = 1,0 &ndash; 1,05
        https://www.haustechnikverstehen.de/heizkoerper-berechnen/
        """
        return heat_norm * (log_mean_temperature_operation / log_mean_temperature_norm) ** heating_exponent

    def logarithmic_mean_temperature(self, forward_temperature: float = 75,
                                     backward_temperature: float = 65,
                                     room_temperature: float = 20):
        """

        Args:
            forward_temperature ():
            backward_temperature ():
            room_temperature ():

        Returns:

        """
        log_mean_temperature = (forward_temperature - backward_temperature) / (math.log(
            (forward_temperature - room_temperature) / (backward_temperature - room_temperature)))
        if isinstance(log_mean_temperature, Quantity):
            return log_mean_temperature.magnitude
        else:
            return log_mean_temperature

    def plot_pump_system_curve(self,
                               operation_point,
                               pump_data,
                               # flow_rate_pump,
                               # dp_pump,
                               flow_rates,
                               system_head,

                               ##pump_power,
                               # pressure_unit,
                               # head_unit,
                               # system_loss,
                               # operating_flow_rate,
                               # operation_pump_pressure
                               ):
        """

        Args:
            flow_rate ():
            pump_power ():
            system_loss ():
        """
        # Plot der Leistungskurve und Systemkurve
        fig, ax1 = plt.subplots()
        op_x, op_y = operation_point
        plt.plot(op_x, op_y, 'ro', label='Betriebspunkt')
        for pump in system_head:
            x_data = []
            y_data = []
            for flow_rate, pressure_drop in system_head[pump].items():
                x_data.append(flow_rate.magnitude)  # Extrahiere den Wert aus dem Quantity-Objekt
                y_data.append(pressure_drop.magnitude)  # Extrahiere den Wert aus dem Quantity-Objekt
                ax1.set_xlabel(f'Flow Rate in [{flow_rate.units}]')
                ax1.set_ylabel(f'Förderhöhe  [{pressure_drop.units}]')
            ax1.plot(x_data, y_data, label='Systemkurve')

        pump_low_flow_low_head, pump_optimal_range, pump_high_flow_high_head = self.pump_section(data=pump_data)
        # Plote die Datenpunkte
        ax1.plot([p[0] for p in pump_low_flow_low_head], [p[1] for p in pump_low_flow_low_head], 'r--',
                 label='Bereich 1: Niedrige Förderhöhe und niedriger Volumenstrom')
        ax1.plot([p[0] for p in pump_optimal_range], [p[1] for p in pump_optimal_range], 'graph--',
                 label='Bereich 2: Optimaler Betriebspunkt')
        ax1.plot([p[0] for p in pump_high_flow_high_head], [p[1] for p in pump_high_flow_high_head], 'b--',
                 label='Bereich 3: Hohe Förderhöhe und hoher Volumenstrom')
        pump_x, pump_y = zip(*pump_data)

        def find_intersection(x_pump, y_pump, x_system, y_system):
            x_pump = np.asarray(x_pump)
            y_pump = np.asarray(y_pump)
            x_system = np.asarray(x_system)
            y_system = np.asarray(y_system)
            # Interpoliere die Systemkennlinie auf die Pumpenkennlinie
            y_system_interp = np.interp(x_pump, x_system, y_system)

            # Finde den Schnittpunkt
            idx = np.argmin(np.abs(y_pump - y_system_interp))
            x_intersection_low = x_pump[idx]
            y_intersection_low = y_system_interp[idx]

            return x_intersection_low, y_intersection_low

        x_intersection_low, y_intersection_low = find_intersection(pump_x, pump_y, tuple(x_data), tuple(y_data))
        # Markiere den Schnittpunkt im Diagramm
        print(x_intersection_low)
        print(y_intersection_low)
        ax1.plot(x_intersection_low, y_intersection_low, 'bo', label='Schnittpunkt')
        op_x, op_y = operation_point
        if pump_optimal_range[0][0] <= op_x.magnitude <= pump_optimal_range[-1][0] and pump_optimal_range[0][
            1] <= op_y.magnitude <= \
                pump_optimal_range[-1][1]:
            print("Die Pumpe und ihre Pumpenkennlinie sind geeignet für Ihr System.")
        else:
            print("Die Pumpe und ihre Pumpenkennlinie sind nicht geeignet für Ihr System.")

        # ax1.plot(flow_rates.magnitude, system_head, label='System Curve')
        # ax1.set_xlabel(f'Flow Rate in [{flow_rates.units}]')
        # ax1.set_ylabel(f'Druckdifferenz  [{pressure_unit.units}]')
        # ax2 = ax1.twinx()
        # ax2.plot(flow_rates.magnitude, system_head, color='red')
        # ax2.set_ylabel(f'System Loss [{head_unit.units}]')

        # ax1.plot(operating_flow_rate, operation_pump_pressure, 'ro', label='Operating Point')

        fig.tight_layout()
        fig.legend()
        plt.show()
        # ax1.plot(flow_rates.magnitude, pump_power, label='Pump Curve')
        # print('Operating Flow Rate:', operating_flow_rate)
        # print('Operating Pressure:', operation_pump_pressure)

        """
        fig = plt.figure()

        #plt.plot(flow_rates.magnitude, pump_power, label='Pump Curve')
        plt.plot(flow_rates.magnitude, system_loss, label='System Curve')
        #plt.plot(operating_flow_rate, operating_head, 'ro', label='Operating Point')
        plt.xlabel(f'Flow Rate in [{flow_rates.units}]')
        plt.ylabel(f'Pressure  [{pressure_unit.units}]')
        plt.legend()
        plt.show()
        print('Operating Flow Rate:', operating_flow_rate)
        print('Operating Head:', operating_head)"""

    def operation_pump_pressure(self):
        """

        Returns:

        """
        # todo: Mehrere Kennlinien einführen
        """V_flow = np.array([8.4618254914e-06, 0.000274485730449, 0.000555832400486, 0.000837082776634, 0.00110292011218,
                           0.00138657181719, 0.00166761756882, 0.00187198329301])#* (3600 / 0.001) #* (ureg.meter ** 3 / ureg.hour)
        dp = np.array(
            [34808.1176471, 34738.9411765, 34508.1176471, 32430.7058824, 29083.7647059, 24005.6470588, 18004.2352941,
             13041.5294118])  #* ureg.kilopascal
        V_flow_list = V_flow.tolist()
        dp_list = dp.tolist()"""
        pump_curve = [(0, 5), (0.25, 4.75), (0.5, 4.55), (0.75, 4.25), (1.04028084, 2.3916), (2.0, 0.25)]
        data = self.polynomial_regression(data=pump_curve, degree=2)
        # pump_low_flow_low_head, pump_optimal_range, pump_high_flow_high_head = self.pump_section(data=data)
        return data

    def system_pressure_curve(self,
                              flow,
                              V_flow,
                              operation_head):
        """
        # Systemkurve basierend auf den berechneten Druckverlusten im Rohrsystem
        Args:
            graph ():
            start_node ():
            end_node ():
            flow_rate ():

        Returns:

        """

        head = (operation_head * (flow / V_flow) ** 2).to_base_units()
        return round(head, 4)

    def pump(self, graph):
        """

        Args:
            graph ():

        Returns:

        """
        pump_nodes = [node for node, data in graph.nodes(data=True) if 'pump' in set(data.get('type'))]
        strands = []
        for pump_node in pump_nodes:
            successors = nx.dfs_successors(graph, pump_node)
            strand = []
            for end_node in successors.keys():
                if graph.out_degree(end_node) == 0:  # Prüfen, ob der Knoten ein Endknoten ist
                    strand.append(nx.shortest_path(graph, pump_node, end_node))
            strands.append(strand)
        network_weakest_points = []
        for strand in strands:
            weakest_node = min(strand, key=lambda node: graph.nodes[node]['pressure'])
            network_weakest_points.append(weakest_node)

        return graph

    def get_strands(self, graph):
        # Initialisiere eine leere Liste für die Stränge
        # source_nodes = [node for node, data in graph.nodes(data=True) if 'source' in set(data.get('type'))]
        source_nodes = [node for node, data in graph.nodes(data=True) if 'pump' in set(data.get('type'))]
        end_nodes = [node for node, data in graph.nodes(data=True) if 'radiator_forward' in set(data.get('type'))]
        strands = []
        for source in source_nodes:
            # Suche alle Endknoten im Graphen
            # end_nodes = [node for node in graph.nodes() if graph.out_degree(node) == 0]
            # Führe eine Tiefensuche von jedem Endknoten aus, um die Stränge zu identifizieren
            for end_node in end_nodes:
                paths = nx.all_simple_paths(graph, source=source, target=end_node)  # Annahme: Anfangsknoten ist 1
                for path in paths:
                    strands.append(path)

        return strands

    def iterate_pressure_node(self, graph):
        pass

    def reindex_cycle_graph(self, graph, start_node):

        node_order = list(nx.shortest_path_length(graph, start_node).keys())
        mapping = {node: i for i, node in enumerate(node_order)}
        reindexed_G = nx.relabel_nodes(graph, mapping)

        return reindexed_G

    def hardy_cross_method(self, graph: nx.DiGraph(),
                           viewpoint,
                           convergence_limit=0.001,
                           max_iterations=100,
                           ):
        num_nodes = graph.number_of_nodes()
        flow_updates = [0] * num_nodes
        iteration = 0
        while True:
            iteration += 1
            max_update = 0
            cycles = nx.simple_cycles(graph)
            for cycle in cycles:
                for i in range(len(cycle)):
                    current_node = cycle[i]
                    next_node = cycle[(i + 1) % len(cycle)]
                    # Aktuelle Flussrate und Widerstand der Kante

                    flow_rate = graph[current_node][next_node]['flow_rate']
                    resistance = graph[current_node][next_node]['resistance']
                    # pressure_difference = graph.nodes[current_node]['pressure_out'][viewpoint] - graph.nodes[next_node]['pressure_in'][viewpoint]

                    # Berechnung des Volumenstroms
                    flow = flow_rate * resistance  # * pressure_difference

                    # Aktualisierung des Volumenstroms der Kante
                    flow_updates[current_node] -= flow
                    flow_updates[next_node] += flow

                    # Überprüfung der maximalen Änderung des Volumenstroms
                    max_update = max(max_update, abs(flow))
                # Überprüfung der Konvergenz
                if max_update < convergence_limit or iteration >= max_iterations:
                    break

                # Aktualisierung der Volumenströme für die nächste Iteration
                for node in graph.nodes:
                    graph.nodes[node]['flow'] += flow_updates[node]
                    graph[node] = 0
            # Berechnung der Druckverteilung im Netzwerk
            pressures = nx.get_node_attributes(graph, 'pressure')

    def find_longest_cycle(self, graph):
        # Finde alle einfachen Zyklen im Graphen
        cycles = list(nx.simple_cycles(graph))
        # Wähle den längsten Zyklus basierend auf der Anzahl der Knoten
        longest_cycle = max(cycles, key=len)
        return longest_cycle

    def find_critical_cycle(self, graph, viewpoint):
        critical_cycle = None
        max_pressure_loss = 0

        for cycle in nx.simple_cycles(graph):
            pressure_loss = sum(graph[u][v]['pressure_loss'][viewpoint] for u, v in zip(cycle, cycle[1:] + [cycle[0]]))
            if pressure_loss > max_pressure_loss:
                max_pressure_loss = pressure_loss
                critical_cycle = cycle

        return critical_cycle, max_pressure_loss

    def hardy_cross(self, graph, viewpoint, max_iterations=1000, tolerance=1e-6):
        # Setzen Sie die Anfangswerte für die Drücke in den Knoten
        for node in graph.nodes:
            graph.nodes[node]['pressure'] = 1.5 * 10 ** 5 * ureg.pascal  # Anfangswert von 1.5 bar

        # Führen Sie die Iterationen für den Druckverlust aus
        for i in range(max_iterations):
            max_pressure_diff = 0
            for cycle in nx.simple_cycles(graph):
                sum_pressure_loss = 0
                for u, v in zip(cycle, cycle[1:] + [cycle[0]]):
                    # Berechnen Sie den Druckverlust in jeder Kante der Schleife
                    edge_pressure_loss = graph[u][v]['pressure_loss'][viewpoint]
                    sum_pressure_loss += edge_pressure_loss

                # Verteilen Sie den Druckverlust gleichmäßig auf die Knoten der Schleife
                pressure_diff = sum_pressure_loss / len(cycle)
                for node in cycle:
                    new_pressure = graph.nodes[node]['pressure'] + pressure_diff
                    # Berechnen Sie die Druckdifferenz
                    node_pressure_diff = abs(new_pressure - graph.nodes[node]['pressure'])
                    if node_pressure_diff > max_pressure_diff:
                        max_pressure_diff = node_pressure_diff
                    # Aktualisieren Sie den Druckwert des Knotens
                    graph.nodes[node]['pressure'] = new_pressure
            # Überprüfen Sie die Konvergenz anhand einer Toleranz
            if max_pressure_diff.magnitude < tolerance:
                break
        return graph

    def calculate_valve_autoritat(self, pressure_diff_system, pressure_diff_valve):
        """

        Args:
            pressure_diff_system ():
            pressure_diff_valve ():

        Returns:

        """
        return pressure_diff_valve.to(ureg.bar) / pressure_diff_system.to(ureg.bar)

    def calculate_valve_Kv(self, V_flow, pressure_diff):
        return V_flow * math.sqrt((1 * ureg.bar * self.density_fluid) / (
                    pressure_diff.to(ureg.bar) * 1000 * (ureg.kilogram / ureg.meter ** 3)))

    def iterate_circle_pressure_loss_nodes(self,
                                           graph,
                                           viewpoint: str,
                                           initial_pressure=(1.5 * 10 ** 5)):
        """

        Args:
            graph ():
            initial_pressure ():

        Returns:

        """
        max_iterations = 100
        convergence_threshold = 1e-6

        for node, data in graph.nodes(data=True):
            data['pressure_out'][viewpoint] = initial_pressure * ureg.pascal
            data['pressure_in'][viewpoint] = initial_pressure * ureg.pascal
        for iteration in range(max_iterations):
            prev_node_pressures = {node: graph.nodes[node]['pressure_out'][viewpoint] for node in graph.nodes}
            for node in list(nx.topological_sort(graph)):
                if "Pumpe" in set(graph.nodes[node]["type"]):
                    prev_pressure_out = graph.nodes[node]['pressure_out'][viewpoint]
                    graph.nodes[node]['pressure_out'][viewpoint] = prev_pressure_out
                # Druck am Eingang des Knotens berechnen
                prev_pressure_out = graph.nodes[node]['pressure_out'][viewpoint]
                successors = list(graph.successors(node))
                if len(successors) > 0 or successors is not None:
                    for succ in successors:
                        next_node = succ
                        predecessors = list(graph.predecessors(next_node))
                        if len(predecessors) > 1:
                            min_pressure = float('inf') * ureg.pascal
                            pre_node = None
                            for pre in predecessors:
                                next_pressure_out = graph.nodes[pre]['pressure_out'][viewpoint]
                                if next_pressure_out < min_pressure:
                                    min_pressure = next_pressure_out
                                    pre_node = pre
                            prev_pressure_out = graph.nodes[pre_node]['pressure_out'][viewpoint]
                            edge_pressure_loss = graph[pre_node][next_node]['pressure_loss'][viewpoint]
                            node_pressure_loss = graph.nodes[pre_node]['pressure_loss'][viewpoint]
                            next_pressure_in = prev_pressure_out - edge_pressure_loss
                            next_pressure_out = next_pressure_in - node_pressure_loss
                            graph.nodes[next_node]['pressure_in'][viewpoint] = next_pressure_in
                            graph.nodes[next_node]['pressure_out'][viewpoint] = next_pressure_out
                        else:
                            edge_pressure_loss = graph[node][next_node]['pressure_loss'][viewpoint]
                            node_pressure_loss = graph.nodes[next_node]['pressure_loss'][viewpoint]
                            next_pressure_in = prev_pressure_out - edge_pressure_loss
                            next_pressure_out = next_pressure_in - node_pressure_loss
                            graph.nodes[next_node]['pressure_in'][viewpoint] = next_pressure_in
                            graph.nodes[next_node]['pressure_out'][viewpoint] = next_pressure_out
                else:
                    continue
            convergence = True
            for node in graph.nodes:
                pressure_diff = abs(graph.nodes[node]['pressure_out'][viewpoint] - prev_node_pressures[node])
                if pressure_diff.magnitude > convergence_threshold:
                    convergence = False
                    break

            if convergence:
                break

        return graph

        """



        max_iterations = 1000
        tolerance = 1e-6
        for node in graph.nodes:
            graph.nodes[node]['pressure_out'][viewpoint] = 1.5 * 10**5 * ureg.pascal # Anfangswert von 1.5 bar

            # Führen Sie die Iterationen für den Druckverlust aus
        for i in range(max_iterations):
            max_pressure_diff = 0
            for cycle in nx.simple_cycles(graph):
                sum_pressure_loss = 0
                for u, v in zip(cycle, cycle[1:] + [cycle[0]]):
                    # Berechnen Sie den Druckverlust in jeder Kante der Schleife
                    edge_pressure_loss = graph[u][v]['pressure_loss'][viewpoint]
                    sum_pressure_loss += edge_pressure_loss

                # Verteilen Sie den Druckverlust gleichmäßig auf die Knoten der Schleife
                pressure_diff = sum_pressure_loss / len(cycle)
                for node in cycle:
                    new_pressure = graph.nodes[node]['pressure_out'][viewpoint] + pressure_diff
                    # Berechnen Sie die Druckdifferenz
                    node_pressure_diff = abs(new_pressure - graph.nodes[node]['pressure_out'][viewpoint])
                    if node_pressure_diff > max_pressure_diff:
                        max_pressure_diff = node_pressure_diff
                    # Aktualisieren Sie den Druckwert des Knotens
                    graph.nodes[node]['pressure_out'][viewpoint] = new_pressure

            # Überprüfen Sie die Konvergenz anhand einer Toleranz
            if max_pressure_diff.magnitude < tolerance:
                break

        return graph"""
        # graph = self.hardy_cross(graph=graph, viewpoint=viewpoint)
        """critical_cycle, max_pressure_loss = self.find_critical_cycle(graph=graph, viewpoint=viewpoint)
        print(max_pressure_loss)
        print(critical_cycle)
        longest_cycle = self.find_longest_cycle(graph=graph)
        print(longest_cycle)
        pump_nodes = [node for node in longest_cycle if "Pumpe" in set(graph.nodes[node]["type"])]
        print(pump_nodes)
        # Starte die Iteration an der Pumpe mit dem höchsten Index
        pump_nodes.sort(reverse=True)
        for start_node in pump_nodes:
            # Die Iteration erfolgt entlang des Zyklus, beginnend bei der Pumpe und endend bei der Pumpe
            cycle_iter = nx.dfs_edges(graph, start_node)
            print(cycle_iter)
            print("hallo")
            prev_pressure_out = initial_pressure
            for node, next_node in cycle_iter:
                edge_pressure_loss = graph[node][next_node]['pressure_loss'][viewpoint]
                node_pressure_loss = graph.nodes[next_node]['pressure_loss'][viewpoint]
                next_pressure_in = prev_pressure_out - edge_pressure_loss
                next_pressure_out = next_pressure_in - node_pressure_loss
                graph.nodes[next_node]['pressure_in'][viewpoint] = next_pressure_in
                graph.nodes[next_node]['pressure_out'][viewpoint] = next_pressure_out
                prev_pressure_out = next_pressure_out"""
        # exit(0)
        """initial_pressure = initial_pressure * ureg.pascal
        start_node = ["start_node",  ]
        # Speicherung des vorherigen Zustands der Drücke
        for node in list(nx.topological_sort(graph)):
            if "Pumpe" in set(graph.nodes[node]["type"]):
                prev_pressure_out = initial_pressure
                graph.nodes[node]['pressure_out'][viewpoint] = prev_pressure_out
                continue
            # Druck am Eingang des Knotens berechnen
            if viewpoint in graph.nodes[node]['pressure_out']:
                prev_pressure_out = graph.nodes[node]['pressure_out'][viewpoint]
            else:
                prev_pressure_out = initial_pressure
                graph.nodes[node]['pressure_out'][viewpoint] = prev_pressure_out
            successors = list(graph.successors(node))
            for succ in successors:
                next_node = succ
                edge_pressure_loss = graph[node][next_node]['pressure_loss'][viewpoint]
                node_pressure_loss = graph.nodes[next_node]['pressure_loss'][viewpoint]
                next_pressure_in = prev_pressure_out - edge_pressure_loss
                next_pressure_out = next_pressure_in - node_pressure_loss
                graph.nodes[next_node]['pressure_in'][viewpoint] = next_pressure_in
                graph.nodes[next_node]['pressure_out'][viewpoint] = next_pressure_out
        return graph"""

    def iterate_pressure_loss_fittings_nodes(self,
                                             graph,
                                             viewpoint: str,
                                             v_mid: float,
                                             initial_pressure=(1.5 * 10 ** 5)
                                             ):
        """

        Args:
            graph ():
            viewpoint ():
            v_mid ():
            initial_pressure ():

        Returns:

        """
        initial_pressure = initial_pressure * ureg.pascal
        for node, data in graph.nodes(data=True):
            coefficient_resistance = data["coefficient_resistance"]
            pressure_loss_node = self.calculate_pressure_loss_fittings(coefficient_resistance=coefficient_resistance,
                                                                       mid_velocity=v_mid)
            graph.nodes[node]["pressure_loss"].update({viewpoint: pressure_loss_node})
        return graph

    def iterate_pressure_loss_nodes(self,
                                    graph,
                                    viewpoint: str,
                                    v_mittel: float,
                                    initial_pressure=(1.5 * 10 ** 5)):
        """

        Args:
            graph ():
            initial_pressure ():

        Returns:

        """
        initial_pressure = initial_pressure * ureg.pascal
        # Berechnung des Drucks entlang des Pfades
        for node in nx.topological_sort(graph):
            # Berechnung des Drucks anhand der eingehenden Kanten
            if "start_node" in set(graph.nodes[node]["type"]):
                graph.nodes[node]["pressure_out"].update({viewpoint: initial_pressure})
                pressure_out = initial_pressure
            else:
                pressure_out = graph.nodes[node]["pressure_out"][viewpoint]

            if viewpoint in graph.nodes[node]["pressure_out"]:
                pressure_out = graph.nodes[node]["pressure_out"][viewpoint]
            else:
                graph.nodes[node]["pressure_out"].update({viewpoint: initial_pressure})
                pressure_out = initial_pressure

            successors = list(graph.successors(node))
            for succ in successors:
                pressure_loss_edge = graph.edges[node, succ]["pressure_loss"][viewpoint]
                pressure_in = pressure_out - pressure_loss_edge
                graph.nodes[succ]["pressure_in"].update({viewpoint: pressure_in})
                coefficient_resistance = graph.nodes[succ]["coefficient_resistance"]
                pressure_loss_node = self.calculate_pressure_loss_fittings(
                    coefficient_resistance=coefficient_resistance,
                    mid_velocity=v_mittel)
                graph.nodes[succ]["pressure_loss"].update({viewpoint: pressure_loss_node})
                pressure_out_node = pressure_in - pressure_loss_node
                graph.nodes[succ]["pressure_out"].update({viewpoint: pressure_out_node})

        return graph

    def hardy_cross_algorithm(self, graph, iterations=100, convergence_threshold=0.001):
        """

        Args:
            graph ():
            iterations ():
            convergence_threshold ():

        Returns:

        """
        num_nodes = len(graph.nodes)
        pressures = np.zeros(num_nodes)  # Array zur Speicherung der Drücke an jedem Knoten

        for _ in range(iterations):
            prev_pressures = np.copy(pressures)
            for node in graph.nodes():
                # inflows = [graph.nodes[pred][node]['m_flow'] for pred in graph.predecessors(node)]
                inflows = [graph.nodes[pred]['m_flow'] for pred in graph.predecessors(node)]
                outflows = [graph.nodes[succ]['m_flow'] for succ in graph.successors(node)]
                inflow_sum = sum(inflows)
                outflow_sum = sum(outflows)
                pressures = inflow_sum - outflow_sum
                # pressures[node] = inflow_sum - outflow_sum

            max_delta = np.abs(pressures - prev_pressures).max()
            if max_delta < convergence_threshold:
                break

        return pressures

    def calculate_pump_power(self, m_flow, efficiency, pressure_difference):
        """

        Args:
            m_flow ():
            efficiency ():
            pressure_difference ():

        Returns:

        """
        return round((m_flow * pressure_difference) / (efficiency * self.density_fluid), 2)

    def update_pipe_inner_diameter_edges(self,
                                         graph: nx.Graph(),
                                         viewpoint: str,
                                         v_mittel: float,
                                         security_factor: float = 1.15,
                                         material_pipe: str = "Stahl"):
        """

        Args:
            viewpoint ():
            v_mittel ():
            security_factor ():
            graph ():

        Returns:
        """
        print("Calculate Inner diameter")
        # list(nx.topological_sort(graph))
        for node in graph.nodes():
            successors = list(graph.successors(node))
            m_flow_in = graph.nodes[node]["m_flow"][viewpoint]
            for succ in successors:
                m_flow_out = graph.nodes[succ]["m_flow"][viewpoint]
                V_flow_out = graph.nodes[succ]["V_flow"][viewpoint]
                heat_flow_out = graph.nodes[succ]["heat_flow"][viewpoint]
                if "m_flow" and "V_flow" and "heat_flow" in graph.edges[node, succ]:
                    graph.edges[node, succ]['m_flow'][viewpoint] = m_flow_out
                    graph.edges[node, succ]['V_flow'][viewpoint] = V_flow_out
                    graph.edges[node, succ]['heat_flow'][viewpoint] = heat_flow_out
                else:
                    graph.edges[node, succ]['heat_flow'] = {viewpoint: 1.0 * ureg.kilowatt}
                    graph.edges[node, succ]['m_flow'] = {viewpoint: 1.0 * (ureg.kilogram / ureg.seconds)}
                    graph.edges[node, succ]['V_flow'] = {viewpoint: 1.0 * (ureg.meter ** 3 / ureg.seconds)}
                calc_inner_diameter = self.calculate_pipe_inner_diameter(m_flow=m_flow_out,
                                                                         v_mittel=v_mittel,
                                                                         security_factor=security_factor)

                inner_diameter, outer_diameter, material, density, pipe_mass = self.read_pipe_data_excel(
                        filename=self.playground.sim_settings.hydraulic_components_data_file_path,
                        calc_inner_diameter=calc_inner_diameter,
                        sheet_name=self.playground.sim_settings.hydraulic_components_data_file_pipe_sheet)
                graph.edges[node, succ]['inner_diameter'] = inner_diameter
                graph.edges[node, succ]['outer_diameter'] = outer_diameter
                graph.edges[node, succ]['material'] = material
                graph.edges[node, succ]['density'] = density
                graph.edges[node, succ]['mass'] = pipe_mass * graph.edges[node, succ]['length']
                graph.edges[node, succ]['dammung'] = self.calculate_dammung(outer_diameter)
                # print(graph.edges[node, succ]['length'])
                # print(pipe_mass)
                # print(graph.edges[node, succ]['mass'])
        return graph

    def calculate_mass_flow_circular_graph(self, graph, known_nodes, viewpoint):
        """
        Args:
            graph (nx.DiGraph): Der gerichtete Graph
            known_nodes (list): Eine Liste der bekannten Knoten, an denen der Massenstrom bekannt ist
            viewpoint (str): Der betrachtete Standpunkt
        Returns:
            nx.DiGraph: Der Graph mit aktualisierten Massenströmen
        """

        # Erstelle die Adjazenzmatrix
        # Erstelle die Adjazenzmatrix
        # Erstelle die Adjazenzmatrix
        nodes = []
        for node, data in graph.nodes(data=True):
            if "end_node" in data["type"]:
                continue
            else:
                nodes.append(node)
            # Setze den bekannten Massenstrom für die bekannten Knoten
        """for node in known_nodes:
            graph.nodes[node]['m_flow'][viewpoint] = known_nodes[node]"""

        # Iteriere über die Knoten in einer Schleife, bis sich die Massenströme nicht mehr ändern
        while True:
            # Kopiere den aktuellen Zustand der Massenströme
            previous_m_flow = nx.get_node_attributes(graph, 'm_flow')

            # Aktualisiere die Massenströme für die unbekannten Knoten
            for node in graph.nodes:
                if node not in known_nodes:
                    predecessors = list(graph.predecessors(node))
                    num_predecessors = len(predecessors)

                    # Berechne den eingehenden Massenstrom basierend auf der Kontinuitätsgleichung
                    incoming_m_flow = sum(graph.nodes[predecessor][viewpoint] for predecessor in predecessors)

                    # Berechne den ausgehenden Massenstrom basierend auf der Knotenregel
                    outgoing_m_flow = incoming_m_flow / num_predecessors

                    # Aktualisiere den Massenstrom für den aktuellen Knoten
                    graph.nodes[node]['m_flow'][viewpoint] = outgoing_m_flow

            # Überprüfe, ob sich die Massenströme nicht mehr ändern
            current_m_flow = nx.get_node_attributes(graph, 'm_flow')
            if current_m_flow == previous_m_flow:
                break

        return graph

    def calculate_pressure_node(self, graph, viewpoint: str):
        print("Calculate pressure node")
        graph = self.iterate_pressure_loss_edges(graph=graph,
                                                 v_mid=self.v_mean,
                                                 viewpoint=viewpoint)
        # Druckverluste über die Knoten
        graph = self.iterate_pressure_loss_fittings_nodes(graph=graph,
                                                          viewpoint=viewpoint,
                                                          v_mid=self.v_mean)

        return graph

    # todo: Für Systemkennlinie interessant
    def calculate_flow(self, graph, source, sink):
        # Füge eine Kantenkapazität zu den Kanten hinzu
        # Führe den Ford-Fulkerson-Algorithmus durch
        print("Calculate pressure node")
        flow_value, flow_dict = nx.maximum_flow(graph, source, sink)
        # Extrahiere den Massenstrom aus dem Flussdictionary

        flow = {node: flow_dict[source][node] for node in flow_dict[source]}

        return flow

    def calculate_mass_volume_flow_node(self, graph, viewpoint: str):
        """

        Args:
            graph ():
            viewpoint ():
        """
        print("Caluclate Mass flow")
        forward, backward, connection = self.separate_graph(graph=graph)
        forward = self.iterate_forward_nodes_mass_volume_flow(graph=forward, viewpoint=viewpoint)
        #self.plot_attributes_nodes(graph=forward, type_grid="Vorlaufkreislauf", viewpoint=viewpoint,
        #                           attribute="m_flow")
        backward = self.iterate_backward_nodes_mass_volume_flow(graph=backward, viewpoint=viewpoint)
        #self.plot_attributes_nodes(graph=forward, type_grid="Vorlaufkreislauf", viewpoint=viewpoint,
        #                           attribute="m_flow")
        composed_graph = nx.disjoint_union(forward, backward)
        composed_graph = self.connect_forward_backward(graph=composed_graph,
                                                       color="orange",
                                                       edge_type="radiator",
                                                       grid_type="connection",
                                                       type_delivery=["radiator_forward",
                                                                      "radiator_backward"],
                                                       type_units=True)
        """composed_graph = GeometryBuildingsNetworkx.connect_sources(graph=composed_graph,
                                                                   type_edge="source",
                                                                   grid_type="connection",
                                                                   color="orange",
                                                                   type_units=True)"""
        return composed_graph

    def iterate_forward_nodes_mass_volume_flow(self, graph, viewpoint: str):
        """
        Args:
            graph ():
        Returns:
        """
        # Iteriere über die Knoten in umgekehrter Reihenfolge (von den Endpunkten zum Startpunkt)

        for node in reversed(list(nx.topological_sort(graph))):
            # Überprüfe, ob der Knoten Verzweigungen hat
            successors = list(graph.successors(node))
            if len(successors) > 1:
                # Summiere die Massenströme der Nachfolgerknoten
                massenstrom_sum = sum(graph.nodes[succ]['m_flow'][viewpoint] for succ in successors)
                volumen_flow_sum = sum(graph.nodes[succ]['V_flow'][viewpoint] for succ in successors)
                Q_flow_sum = sum(graph.nodes[succ]['heat_flow'][viewpoint] for succ in successors)
                # Speichere den summierten Massenstrom im aktuellen Knoten
                graph.nodes[node]['m_flow'].update({viewpoint: massenstrom_sum})
                graph.nodes[node]['V_flow'].update({viewpoint: volumen_flow_sum})
                graph.nodes[node]['heat_flow'].update({viewpoint: Q_flow_sum})
            elif len(successors) == 1:
                # Kopiere den Massenstrom des einzigen Nachfolgerknotens
                graph.nodes[node]['m_flow'].update({viewpoint: graph.nodes[successors[0]]['m_flow'][viewpoint]})
                graph.nodes[node]['V_flow'].update({viewpoint: graph.nodes[successors[0]]['V_flow'][viewpoint]})
                graph.nodes[node]['heat_flow'].update({viewpoint: graph.nodes[successors[0]]['heat_flow'][viewpoint]})
            for succ in successors:
                m_flow = graph.nodes[node]['m_flow'][viewpoint]
                graph.edges[node, succ]["capacity"] = m_flow
        return graph

    def iterate_edges(self, graph):
        for node_1, node_2 in graph.edges():
            m_flow_1 = 0.1

    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D

    def plot_3D_pressure(self, graph, viewpoint: str, node_attribute: str, title: str, edge_attributes: str = None):
        # Positionen der Knoten im Diagramm
        t = nx.get_node_attributes(graph, "pos")
        new_dict = {key: (x, y, z) for key, (x, y, z) in t.items()}
        node_size = 50
        # Zeichnen des Rohrnetzwerks
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_zlabel('Z')
        # Zeichnen der Knoten mit entsprechender Farbe und Druck als Label
        # node_pressure_in = {node: round((graph.nodes[node]['pressure_in'] * 10 ** -5), 1) for node in graph.nodes()}
        node_pressure_out = {node: round((graph.nodes[node][node_attribute][viewpoint] * 10 ** -5), 1) for node in
                             graph.nodes()}

        node_colors = []
        for node, attrs in graph.nodes(data=True):
            node_colors.append(node_pressure_out[node].magnitude)
            x, y, z = attrs["pos"]
            m_flow = attrs[node_attribute][viewpoint].to(ureg.bar)
            ax.text(x, y, z, str(round(m_flow, 3)), fontsize=8, ha='center', va='center')

        cmap = plt.cm.get_cmap('cool')  # Farbkarte für Druckverlauf
        # node_colors = [node_pressure_in[node] for node in graph.nodes()]
        ax.scatter([x for x, y, z in new_dict.values()], [y for x, y, z in new_dict.values()],
                   [z for x, y, z in new_dict.values()], c=node_colors, cmap='cool', s=node_size, label='Pressure')

        # Zeichnen der Kanten mit Farben entsprechend dem Druck
        """edge_colors = [graph[u][v]['pressure_loss'][viewpoint] for u, v in graph.edges()]
        edge_colors_normalized = [(c - min(edge_colors)) / (max(edge_colors) - min(edge_colors)) for c in edge_colors]
        edge_colors_mapped = plt.cm.get_cmap('cool')(edge_colors_normalized)
        edge_colors_mapped = cmap(edge_colors_normalized)"""

        for u, v, data in graph.edges(data=True):
            attribute_value = data.get(edge_attributes, None)
            color = graph.edges[u, v]['color']
            x1, y1, z1 = graph.nodes[u]['pos']
            x2, y2, z2 = graph.nodes[v]['pos']
            if attribute_value is not None:
                # Bestimme die Position der Knoten

                # Zeichne die Kante mit entsprechendem Attributwert
                ax.plot([x1, x2], [y1, y2], [z1, z2], alpha=0.6, marker='o', color=color)
                # Textbeschriftung mit dem Wert des Attributs neben der Kante
                x_text = (x1 + x2) / 2
                y_text = (y1 + y2) / 2
                z_text = (z1 + z2) / 2
                if edge_attributes is not None:
                    if isinstance(attribute_value, dict):
                        ax.text(x_text, y_text, z_text, str(attribute_value[viewpoint]), fontsize=8, ha='center',
                                va='center')
                    else:
                        ax.text(x_text, y_text, z_text, str(attribute_value), fontsize=8, ha='center', va='center')
            else:
                ax.plot([x1, x2], [y1, y2], [z1, z2], alpha=0.6, marker='o', color=color)
        # Anpassen der Farblegende basierend auf dem Druckverlauf
        # sm = plt.cm.ScalarMappable(cmap=cmap)
        sm = plt.cm.ScalarMappable(cmap=cmap)
        sm.set_array(node_colors)
        colorbar = plt.colorbar(sm, label='Druck [bar]')

        colorbar.ax.set_ylabel('Druck [bar]', rotation=270, labelpad=20)  # Label-Rotation und Abstand
        colorbar.ax.yaxis.set_tick_params(pad=10)  # Abstand zwischen den Tick-Markierungen und dem Label
        colorbar.ax.tick_params(axis='y', width=0.5)  # Dicke der Tick-Markierungen
        colorbar.ax.tick_params(axis='y', length=5)  # Länge der Tick-Markierungen
        colorbar.ax.yaxis.set_ticks_position('left')  # Position der Tick-Markierungen

        # sm.set_array(list(node_pressure_out.values()))

        # sm = plt.cm.ScalarMappable(cmap='cool')
        # sm.set_array(node_colors)
        # plt.colorbar(sm, label='Druck')

        # Anzeigen des Diagramms
        plt.title(title)
        # plt.show()

        """


        # Positionen der Knoten im Diagramm
        t = nx.get_node_attributes(graph, "pos")
        new_dict = {key: (x, y, z) for key, (x, y, z) in t.items()}
        node_size = 10
        # Zeichnen des Rohrnetzwerks
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_zlabel('Z')
        # Zeichnen der Knoten mit entsprechender Farbe und Druck als Label
        # Zeichnen der Knoten mit entsprechender Farbe und Druck als Label
        node_pressure_out = {node: round((graph.nodes[node]['pressure_in'] * 10 ** -5), 1) for node in graph.nodes()}
        node_colors = [node_pressure_out[node].magnitude for node in graph.nodes()]

        cmap = plt.cm.get_cmap('cool')  # Farbkarte für Druckverlauf
        ax.scatter([x for x, y, z in new_dict.values()], [y for x, y, z in new_dict.values()],
                   [z for x, y, z in new_dict.values()], c=node_colors, cmap='cool', s=node_size, label='Pressure')
        # Zeichnen der Kanten mit Farben entsprechend dem Druckabfall
        edge_colors = []
        for u, v in graph.edges():
            pressure_difference = graph.nodes[u]['pressure_in'] - graph.nodes[v]['pressure_in']
            edge_colors.append(pressure_difference)

            # Zeichnen der Kanten mit fließendem Farbverlauf entsprechend dem Druckabfall
        edge_color = []
        pressure_min = min(node_colors)
        pressure_max = max(node_colors)
        cmap = plt.cm.get_cmap('cool')  # Farbkarte für den Farbverlauf
        for (u, v) in graph.edges():
            pressure_start = round(graph.nodes[u]['pressure_out'].magnitude * 10 ** -5, 2)
            pressure_end = round(graph.nodes[v]['pressure_in'].magnitude * 10 ** -5, 2)
            #print(pressure_start)
            #print(pressure_end)
            #print(pressure_max)
            #print(pressure_min)
            #pressure_difference = (pressure_end - pressure_start) / (pressure_max - pressure_min)
            pressure_difference = (pressure_end - pressure_start)
            color = cmap(pressure_difference)
            color_start = cmap((pressure_start - min(node_colors)) / (pressure_max - pressure_min))
            color_end = cmap((pressure_end - min(node_colors)) / (pressure_max - pressure_min))
            # edge_color.append(color_start)
            edge_color.append(color_start)
            edge_color.append(color)
            edge_color.append(color_end)
            # edge_color.append(color_end)
            # edge_color = [color_start, color_end]
            num_points = 10  # Anzahl der Zwischenpunkte für den Farbverlauf
            edge_colors = np.linspace(0, 1, num_points)[:, np.newaxis] * edge_color[1] + (
                    1 - np.linspace(0, 1, num_points)[:, np.newaxis]) * edge_color[0]
            edge_colors = edge_colors.squeeze()

            points = np.linspace(new_dict[u], new_dict[v], num_points + 2)
            for i in range(num_points + 1):
                if i == num_points:
                    color = edge_colors[i - 1]
                else:
                    color = edge_colors[i]

                ax.plot([points[i][0], points[i + 1][0]], [points[i][1], points[i + 1][1]],
                        [points[i][2], points[i + 1][2]], alpha=0.6, color=color)

            # Anpassen der Farblegende basierend auf dem Druckverlauf
        sm = plt.cm.ScalarMappable(cmap=cmap)
        sm.set_array(node_colors)
        plt.colorbar(sm, label='Druck [bar]')

        # Anzeigen des Diagramms
        plt.title('Positionsbasierter Druckverlauf in einem Rohrnetzwerk')"""
        """plt.show()

        min_edge_color = min(edge_colors)
        max_edge_color = max(edge_colors)
        edge_colors_normalized = [(c - min_edge_color) / (max_edge_color - min_edge_color) for c in edge_colors]
        edge_colors_mapped = cmap(edge_colors_normalized)

        for (u, v), color in zip(graph.edges(), edge_colors_mapped):
            ax.plot([new_dict[u][0], new_dict[v][0]], [new_dict[u][1], new_dict[v][1]],
                    [new_dict[u][2], new_dict[v][2]], alpha=0.6, color=color)

        # Anpassen der Farblegende basierend auf dem Druckverlauf
        sm = plt.cm.ScalarMappable(cmap=cmap)
        sm.set_array(node_colors)
        plt.colorbar(sm, label='Druck [bar]')

        # Anzeigen des Diagramms
        plt.title('Positionsbasierter Druckverlauf in einem Rohrnetzwerk')
        plt.show()


        # Zeichnen der Kanten mit Farben entsprechend dem Druck
        edge_colors = [graph[u][v]['pressure_loss'] for u, v in graph.edges()]
        min_edge_color = min(edge_colors)
        max_edge_color = max(edge_colors)
        edge_colors_normalized = [(c - min_edge_color) / (max_edge_color - min_edge_color) for c in edge_colors]
        edge_colors_mapped = cmap(edge_colors_normalized)

        for (u, v), color in zip(graph.edges(), edge_colors_mapped):
            ax.plot([new_dict[u][0], new_dict[v][0]], [new_dict[u][1], new_dict[v][1]],
                    [new_dict[u][2], new_dict[v][2]], alpha=0.6, color=color)

        # Anpassen der Farblegende basierend auf dem Druckverlauf
        sm = plt.cm.ScalarMappable(cmap=cmap)
        sm.set_array(node_colors)
        plt.colorbar(sm, label='Druck [bar]')

        # Anzeigen des Diagramms
        plt.title('Positionsbasierter Druckverlauf in einem Rohrnetzwerk')
        plt.show()




        # node_pressure_in = {node: round((graph.nodes[node]['pressure_in'] * 10 ** -5), 1) for node in graph.nodes()}
        node_pressure_out = {node: round((graph.nodes[node]['pressure_in'] * 10 ** -5), 1) for node in graph.nodes()}
        node_colors = []
        for node in graph.nodes():
            node_colors.append(node_pressure_out[node].magnitude)

        cmap = plt.cm.get_cmap('cool')  # Farbkarte für Druckverlauf
        # node_colors = [node_pressure_in[node] for node in graph.nodes()]
        ax.scatter([x for x, y, z in new_dict.values()], [y for x, y, z in new_dict.values()],
                   [z for x, y, z in new_dict.values()], c=node_colors, cmap='cool', s=node_size, label='Pressure')

        # Zeichnen der Kanten mit Farben entsprechend dem Druck
        edge_colors = [graph[u][v]['pressure_loss'] for u, v in graph.edges()]
        edge_colors_normalized = [(c - min(edge_colors)) / (max(edge_colors) - min(edge_colors)) for c in edge_colors]
        edge_colors_mapped = plt.cm.get_cmap('cool')(edge_colors_normalized)
        edge_colors_mapped = cmap(edge_colors_normalized)

        for u, v in graph.edges():
            ax.plot([new_dict[u][0], new_dict[v][0]], [new_dict[u][1], new_dict[v][1]],
                    [new_dict[u][2], new_dict[v][2]], alpha=0.6, color="grey")

        # Anpassen der Farblegende basierend auf dem Druckverlauf
        sm = plt.cm.ScalarMappable(cmap=cmap)
        # sm.set_array(list(node_pressure_out.values()))
        sm.set_array(node_colors)
        plt.colorbar(sm, label='Druck [bar]')
        # sm = plt.cm.ScalarMappable(cmap='cool')
        # sm.set_array(node_colors)
        # plt.colorbar(sm, label='Druck')

        # Anzeigen des Diagramms
        plt.title('Positionsbasierter Druckverlauf in einem Rohrnetzwerk')
        plt.show()"""

    def remove_attributes(self, graph, attributes):
        print("Delete unnecessary attributes.")
        for node, data in graph.nodes(data=True):
            if set(attributes) & set(data["type"]):
                for attr in attributes:
                    if attr in data["type"]:
                        data["type"].remove(attr)
        return graph

    def plot_pressure(self, graph):
        """

        Args:
            graph ():
        """
        # Positionen der Knoten im Diagramm
        # Zeichnen des Rohrnetzwerks
        t = nx.get_node_attributes(graph, "pos")
        new_dict = {key: (x, y) for key, (x, y, z) in t.items()}
        node_size = 100
        nx.draw_networkx(G=graph, pos=new_dict, with_labels=False, node_size=node_size)
        node_pressure = {}
        for node in graph.nodes():
            node_pressure[node] = round((graph.nodes[node]['pressure_out'] * 10 ** -5).magnitude, 1)

        # Zeichnen des Druckverlaufs als Positions  basiertes Diagramm
        # node_sizes = [100 * node_pressure[node] for node in graph.nodes()]
        cmap = plt.cm.get_cmap('cool')  # Farbkarte für Druckverlauf
        nx.draw_networkx_nodes(G=graph,
                               pos=new_dict,
                               node_size=node_size,
                               node_color=list(node_pressure.values()),
                               cmap=cmap)
        nx.draw_networkx_labels(G=graph, pos=new_dict, labels={node: str(node_pressure[node]) for node in graph.nodes})
        # Zeichnen der Kanten mit Farben entsprechend dem Druck
        # Zeichnen der Kanten mit Farben entsprechend dem Druck
        edge_colors = [graph[u][v]['pressure_loss'] for u, v in graph.edges()]
        edge_colors_normalized = [(c - min(edge_colors)) / (max(edge_colors) - min(edge_colors)) for c in edge_colors]
        edge_colors_mapped = cmap(edge_colors_normalized)
        # nx.draw_networkx_edges(G=graph, pos=new_dict, edge_color=edge_colors_mapped)
        nx.draw_networkx_edges(G=graph, pos=new_dict, edge_color="grey")

        # Anpassen der Farblegende basierend auf dem Druckverlauf
        sm = plt.cm.ScalarMappable(cmap=cmap)
        sm.set_array(list(node_pressure.values()))
        plt.colorbar(sm, label='Druck')

        # Anzeigen des Diagramms
        plt.title('Positionsbasierter Druckverlauf in einem Rohrnetzwerk')
        plt.axis('on')
        # plt.show()

    def plot_attributes_nodes(self,
                              graph: nx.Graph(),
                              type_grid: str = None,
                              title: str = None,
                              attribute: str = None,
                              text_node: bool = False,
                              viewpoint: str = None):
        """

        Args:
            graph ():
        """
        node_xyz = np.array(sorted(nx.get_node_attributes(graph, "pos").values(), key=lambda x: (x[0], x[1], x[2])))
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        # Dictionaries zum Speichern der Komponentenfarben und -labels
        component_colors = {}
        component_labels = {}
        # Iteriere über die Knoten des Graphen
        for node, attrs in graph.nodes(data=True):
            # Extrahiere den Massenstromwert des Knotens
            component = tuple(attrs.get('type', []))
            # Bestimme die Größe des Knotens basierend auf dem Massenstrom
            # node_size = m_flow * 500
            node_size = 50
            # Bestimme die Position des Knotens
            x, y, z = attrs["pos"]
            # Zeichne den Knoten als Punkt im 3D-Raum
            if component not in component_colors:
                component_colors[component] = plt.cm.get_cmap('tab20')(len(component_colors) % 20)
                component_labels[component] = str(component)
            # Zeichne den Knoten als Punkt im 3D-Raum mit der entsprechenden Farbe
            ax.scatter(x, y, z, s=node_size, c=component_colors[component])
            if text_node is True:
                if viewpoint and attribute is not None:
                    m_flow = attrs[attribute][viewpoint]
                    ax.text(x, y, z, str(round(m_flow, 3)), fontsize=8, ha='center', va='center')
                elif attribute is not None:
                    if attribute in attrs:
                        attr_node = attrs[attribute]
                        ax.text(x, y, z, str(attr_node), fontsize=8, ha='center', va='center')
                else:
                    ax.text(x, y, z, str(node), fontsize=8, ha='left', va='center')

        if graph.is_directed():
            for u, v in graph.edges():
                edge = np.array([(graph.nodes[u]['pos'], graph.nodes[v]['pos'])])
                direction = edge[0][1] - edge[0][0]
                length = graph.edges[u, v]['length']
                self.arrow3D(ax, *edge[0][0], *direction, arrowstyle="-|>",
                                                  color=graph.edges[u, v]['color'],
                                                  length=length)
        else:
            for u, v in graph.edges():
                edge = np.array([(graph.nodes[u]['pos'], graph.nodes[v]['pos'])])
                ax.plot(*edge.T, color=graph.edges[u, v]['color'])
        ax.set_xlabel("x [m]")
        ax.set_ylabel("y [m]")
        ax.set_zlabel("z [m]")
        ax.set_xlim(0, 43)
        # Achsenlimits festlegen
        ax.set_xlim(node_xyz[:, 0].min(), node_xyz[:, 0].max())
        ax.set_ylim(node_xyz[:, 1].min(), node_xyz[:, 1].max())
        ax.set_zlim(node_xyz[:, 2].min(), node_xyz[:, 2].max())
        ax.set_box_aspect([3, 1.5, 1])
        legend_handles = []
        for component, color in component_colors.items():
            legend_handles.append(plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=color, markersize=10))
        ax.legend(legend_handles, component_labels.values(), loc='upper left')
        if title is None:
            plt.title(f'Graphennetzwerk vom Typ {type_grid}')
        else:
            plt.title(title)
        fig.tight_layout()

    @staticmethod
    def arrow3D(ax, x, y, z, dx, dy, dz, length, arrowstyle="-|>", color="black"):
        """

                Args:
                    ax ():
                    x ():
                    y ():
                    z ():
                    dx ():
                    dy ():
                    dz ():
                    length ():
                    arrowstyle ():
                    color ():
                """
        if length != 0:
            arrow = 0.1 / length
        else:
            arrow = 0.1 / 0.0001

        if isinstance(arrow, Quantity):
            arrow = arrow.magnitude

        ax.quiver(x, y, z, dx, dy, dz, color=color, arrow_length_ratio=arrow)
        # ax.quiver(x, y, z, dx, dy, dz, color=color, normalize=True)

    def plot_nodes(self, graph):
        # Knotendiagramm erstellen
        t = nx.get_node_attributes(graph, "pos")
        new_dict = {key: (x, y) for key, (x, y, z) in t.items()}
        node_sizes = [graph.nodes[node]['m_flow'].magnitude for node in
                      graph.nodes()]  # Knotengrößen basierend auf m_flow festlegen
        node_color = [
            'red' if "radiator_forward" in set(graph.nodes[node]['type']) else 'graph' if 'heat_source' in graph.nodes[node][
                'type'] else 'b'
            for node in graph.nodes()]
        nx.draw(G=graph,
                pos=new_dict,
                node_color=node_color,
                node_shape='o',
                node_size=node_sizes,
                font_size=12)
        edge_widths = [graph.edges[edge]['inner_diameter'] for edge in graph.edges()]
        min_diameter = min(edge_widths)
        max_diameter = max(edge_widths)
        scaled_edge_widths = [(diameter - min_diameter) / (max_diameter - min_diameter) * 3 + 1 for diameter in
                              edge_widths]
        nx.draw_networkx_edges(G=graph, pos=new_dict, width=scaled_edge_widths)
        plt.axis('off')
        plt.title('Knoten und m_flow')
        # plt.show()"""

    def calculate_massenstrom_reward(self, graph, end_nodes):
        # Iteriere über die Endknoten
        for end_node in end_nodes:
            # Weise den bekannten Massenstrom am Endknoten zu
            graph.nodes[end_node]['m_flow'] = 10
            # Füge die Predecessor-Knoten des Endknotens zur Warteschlange hinzu
            queue = list(graph.predecessors(end_node))
            # Iteriere über die Knoten in der Warteschlange
            while queue:
                current_node = queue.pop(0)
                massenstrom = graph.nodes[current_node]['m_flow']
                # Iteriere über die eingehenden Kanten des aktuellen Knotens
                for predecessor_node in graph.predecessors(current_node):
                    edge = graph.edges[(predecessor_node, current_node)]
                    # durchmesser = calculate_durchmesser(massenstrom)  # Funktion zur Berechnung des Rohrdurchmessers
                    # Weise den berechneten Durchmesser der Kante als Attribut zu
                    # edge['durchmesser'] = durchmesser
                    # Berechne den Massenstrom für den Vorgängerknoten
                    predecessor_massenstrom = self.calculate_successor_massenstrom(
                        massenstrom)  # Funktion zur Berechnung des Massenstroms
                    # Wenn der Massenstrom noch nicht berechnet wurde, füge den Knoten zur Warteschlange hinzu
                    if 'm_flow' not in graph.nodes[predecessor_node]:
                        queue.append(predecessor_node)
                    # Weise den berechneten Massenstrom dem Vorgängerknoten als Attribut zu
                    graph.nodes[predecessor_node]['m_flow'] = predecessor_massenstrom

    def calculate_massenstrom(self, graph, start_node):
        # Initialisiere den Massenstrom des Startknotens
        graph.nodes[start_node]['massenstrom'] = 100
        # Erstelle eine Warteschlange und füge den Startknoten hinzu
        queue = [start_node]
        # Iteriere über die Knoten in der Warteschlange
        while queue:
            current_node = queue.pop(0)
            massenstrom = graph.nodes[current_node]['massenstrom']
            # Iteriere über die ausgehenden Kanten des aktuellen Knotens
            for successor_node in graph.successors(current_node):
                edge = graph.edges[(current_node, successor_node)]
                # durchmesser = calculate_durchmesser(massenstrom)  # Funktion zur Berechnung des Rohrdurchmessers
                # Weise den berechneten Durchmesser der Kante als Attribut zu
                # edge['durchmesser'] = durchmesser
                # Berechne den Massenstrom für den Nachfolgeknoten
                successor_massenstrom = self.calculate_successor_massenstrom(
                    massenstrom)  # Funktion zur Berechnung des Massenstroms
                if 'massenstrom' not in graph.nodes[successor_node]:
                    # Wenn der Massenstrom noch nicht berechnet wurde, füge den Knoten zur Warteschlange hinzu
                    queue.append(successor_node)

                # Weise den berechneten Massenstrom dem Nachfolgeknoten als Attribut zu
                graph.nodes[successor_node]['massenstrom'] = successor_massenstrom

    def calculate_volume_flow(self, m_flow: float):
        V_flow = (m_flow / self.density_fluid).to(ureg.liter / ureg.seconds)
        return V_flow

    def calculate_volume(self, Q_heat_flow: float):
        """
        Args:
            V_flow ():
            Q_heat_flow ():
        Returns:
        """
        volume = (Q_heat_flow * 1 * ureg.hour) / (self.c_p_fluid * self.density_fluid * (
                    self.temperature_forward - self.temperature_backward)).to_base_units()
        # volume = volume.to(ureg.liter/ureg.seconds)
        return volume

    def calculate_successor_massenstrom(self, massenstrom):
        # Führe hier deine Berechnungen für den Massenstrom des Nachfolgeknotens basierend auf dem aktuellen Massenstrom und dem Durchmesser durch
        successor_massenstrom = massenstrom + massenstrom  # Berechnung des Massenstroms des Nachfolgeknotensmassenstrom
        return successor_massenstrom

    def update_radiator_mass_flow_nodes(self, graph, nodes: list):
        """

        Args:
            graph ():
            nodes ():

        Returns:

        """
        radiator_nodes = [n for n, attr in graph.nodes(data=True) if
                          any(t in attr.get("type", []) for t in nodes
                              )]
        for node in radiator_nodes:
            Q_radiator = graph.nodes[node]['heat_flow']["design_operation_norm"]
            m_flow = self.calculate_m_dot(Q_H=Q_radiator)
            graph.nodes[node]['m_flow'].update({"design_operation_norm": m_flow})
        return graph

    def update_delivery_node(self,
                             graph,
                             nodes: list,
                             viewpoint: str,
                             heating_exponent: float,
                             delivery_type: str = "radiator"):
        """

        Wohn- und Arbeitsräume: 20 bis 22°C
        Kinderzimmer: 20 bis 22°C
        Schlafzimmer: 16 bis 18°C
        Küche: 18 bis 20°C
        Bad: 24 bis 26°C
        Unbeheizter Keller: 10 bis 15°C
        https://www.sbz-monteur.de/erklaer-mal/erklaer-mal-norm-aussen-und-innentempertur
        Args:
            graph ():
            nodes ():
        Returns:
        """
        print("Update delivery node")
        if delivery_type == "radiator":
            radiator_nodes = [n for n, attr in graph.nodes(data=True) if
                              any(t in attr.get("type", []) for t in nodes)]

            radiator_dict = self.read_radiator_material_excel(
                filename=self.playground.sim_settings.hydraulic_components_data_file_path,
                sheet_name=self.playground.sim_settings.hydraulic_components_data_file_radiator_sheet)
            for node in radiator_nodes:
                norm_indoor_temperature = graph.nodes[node]['norm_indoor_temperature']
                Q_radiator_operation = graph.nodes[node]['heat_flow']["design_operation"]
                log_mean_temperature_norm = round(self.logarithmic_mean_temperature(forward_temperature=75,
                                                                                    backward_temperature=65,
                                                                                    room_temperature=20), 2)
                log_mean_temperature_operation = round(
                    self.logarithmic_mean_temperature(forward_temperature=self.temperature_forward,
                                                      backward_temperature=self.temperature_backward,
                                                      room_temperature=norm_indoor_temperature), 2)
                Q_heat_design_norm = self.heat_norm_radiator(
                    log_mean_temperature_operation=log_mean_temperature_operation,
                    heating_exponent=heating_exponent,
                    log_mean_temperature_norm=log_mean_temperature_norm,
                    Q_heat_operation=Q_radiator_operation)
                m_flow_design_norm = self.calculate_m_dot(Q_H=Q_heat_design_norm)
                V_flow_design_norm = self.calculate_volume_flow(m_flow=m_flow_design_norm)
                calculated_volume = self.calculate_volume(Q_heat_flow=Q_heat_design_norm)
                graph.nodes[node]['heat_flow'][viewpoint] = Q_heat_design_norm
                graph.nodes[node]['m_flow'][viewpoint] = m_flow_design_norm
                graph.nodes[node]['V_flow'][viewpoint] = V_flow_design_norm
                # todo: Wie berechne ich das Volumen/ Wasserinhalt

                selected_model, min_mass, material, l1, norm_heat_flow_per_length = self.select_heating_model(
                    model_dict=radiator_dict,
                    calculated_heat_flow=Q_heat_design_norm,
                    calculated_volume=calculated_volume)

                graph.nodes[node]['material_mass'] = min_mass
                graph.nodes[node]['material'] = material
                graph.nodes[node]['model'] = selected_model
                graph.nodes[node]['length'] = l1
                graph.nodes[node]['norm_heat_flow_per_length'] = norm_heat_flow_per_length

        return graph

    def iterate_backward_nodes_mass_volume_flow(self, graph, viewpoint: str):
        """
        Args:
            graph ():
        Returns:
        """
        # Iteriere über die Knoten in umgekehrter Reihenfolge (von den Endpunkten zum Startpunkt)
        for node in list(nx.topological_sort(graph)):
            # Überprüfe, ob der Knoten Verzweigungen hat
            predecessors = list(graph.predecessors(node))
            if len(predecessors) > 1:
                # Summiere die Massenströme der Nachfolgerknoten
                massenstrom_sum = sum(graph.nodes[succ]['m_flow'][viewpoint] for succ in predecessors)
                volumen_flow_sum = sum(graph.nodes[succ]['V_flow'][viewpoint] for succ in predecessors)
                Q_flow_sum = sum(graph.nodes[succ]['heat_flow'][viewpoint] for succ in predecessors)
                # Speichere den summierten Massenstrom im aktuellen Knoten
                graph.nodes[node]['m_flow'].update({viewpoint: massenstrom_sum})
                graph.nodes[node]['V_flow'].update({viewpoint: volumen_flow_sum})
                graph.nodes[node]['heat_flow'].update({viewpoint: Q_flow_sum})
            elif len(predecessors) == 1:
                # Kopiere den Massenstrom des einzigen Nachfolgerknotens
                graph.nodes[node]['m_flow'].update({viewpoint: graph.nodes[predecessors[0]]['m_flow'][viewpoint]})
                graph.nodes[node]['V_flow'].update({viewpoint: graph.nodes[predecessors[0]]['V_flow'][viewpoint]})
                graph.nodes[node]['heat_flow'].update({viewpoint: graph.nodes[predecessors[0]]['heat_flow'][viewpoint]})
            for presucc in predecessors:
                m_flow = graph.nodes[node]['m_flow'][viewpoint]
                graph.edges[presucc, node]["capacity"] = m_flow

        # Zeige den berechneten Massenstrom für jeden Knoten an
        return graph

    def separate_graph(self, graph):
        forward_list = []
        backward_list = []
        connection_list = []
        for node, data in graph.nodes(data=True):
            if "forward" == data["grid_type"]:
                forward_list.append(node)
            elif "backward" == data["grid_type"]:
                backward_list.append(node)
            elif "connection" == data["grid_type"]:
                connection_list.append(node)
        forward = graph.subgraph(forward_list)
        backward = graph.subgraph(backward_list)
        connection = graph.subgraph(connection_list)

        return forward, backward, connection

    def count_space(self, graph):
        """

        Args:
            graph ():

        Returns:

        """
        print("Count elements in space.")
        window_count = {}
        for node, data in graph.nodes(data=True):
            if "radiator_forward" in data["type"]:
                room_id = data["belongs_to"][0]
                if room_id in window_count:
                    window_count[room_id] += 1
                else:
                    window_count[room_id] = 1
        for node, data in graph.nodes(data=True):
            if "radiator_forward" or "radiator_backward" in data["type"]:
                for window in window_count:
                    if window == data["belongs_to"][0]:
                        data["window_count"] = window_count[window]
        return graph

    def define_standard_indoor_temperature(self, usage):
        """
        Wohn- und Arbeitsräume: 20 bis 22°C
        Kinderzimmer: 20 bis 22°C
        Schlafzimmer: 16 bis 18°C
        Küche: 18 bis 20°C
        Bad: 24 bis 26°C
        Unbeheizter Keller: 10 bis 15°C
        https://www.sbz-monteur.de/erklaer-mal/erklaer-mal-norm-aussen-und-innentempertur
        """
        # todo: Schauen wie das im interface heißt
        if usage == "Single office":
            standard_indoor_temperature = 22 * ureg.kelvin
        if usage == "Küche":
            standard_indoor_temperature = 20 * ureg.kelvin
        if usage == "Kinderzimmer":
            standard_indoor_temperature = 22 * ureg.kelvin
        if usage == "Schlafzimmer":
            standard_indoor_temperature = 28 * ureg.kelvin
        if usage == "Bad":
            standard_indoor_temperature = 24 * ureg.kelvin
        if usage == "Keller":
            standard_indoor_temperature = 15 * ureg.kelvin
        else:
            standard_indoor_temperature = 20 * ureg.kelvin
        return standard_indoor_temperature

    def read_bim2sim_data(self, space_id):

        for d in self.heat_demand_dict:

            space_guids = self.heat_demand_dict[d]["space_guids"]
            if set(space_id) & set(space_guids):
                standard_indoor_temperature = self.define_standard_indoor_temperature(usage=self.heat_demand_dict[d]["usage"])
                PHeater = self.heat_demand_dict[d]["PHeater"]
                PHeater_max = np.max(PHeater)
                return PHeater_max, standard_indoor_temperature

    def initilize_design_operating_point(self,
                                         graph: nx.Graph(),
                                         viewpoint):
        """
        Args:
            graph ():
            http://www.bosy-online.de/hydraulischer_abgleich/Rohrnetzberechnung6.jpg
        Returns:
        """
        # todo: coefficient_resistance aus dicitonary lesen
        # todo: Norm Innentemperatur
        # todo: Verengung und erweiterung erkennen
        print("Initilize attributes for nodes and egdes")
        for node, data in graph.nodes(data=True):
            coefficient_resistance = 0.0
            velocity = 0.5 * (ureg.meter / ureg.seconds)
            Q_H = 0.0 * ureg.kilowatt
            design_operation_m_flow = 0.0 * (ureg.kilogram / ureg.second)
            design_operation_V_flow = 0.0 * (ureg.meter ** 3 / ureg.second)
            norm_indoor_temperature = 22 * ureg.kelvin
            if "forward" == data["grid_type"]:
                graph.nodes[node]['temperature'] = {viewpoint: self.temperature_forward * ureg.kelvin}
            if "backward" == data["grid_type"]:
                graph.nodes[node]['temperature'] = {viewpoint: self.temperature_backward * ureg.kelvin}
            # if "start_node" in graph.nodes[node]["type"]:
            if "radiator_forward" in graph.nodes[node]["type"]:
                PHeater_max, norm_indoor_temperature = self.read_bim2sim_data(space_id=graph.nodes[node]["belongs_to"])
                velocity = 0.4 * (ureg.meter / ureg.seconds)
                # todo: PHeater wieder einfügen und größen kontrollieren
                # PHeater_max = 4000 #* ureg.watt
                coefficient_resistance = 4.0
                Q_H = (PHeater_max / data["window_count"]) * ureg.kilowatt
                design_operation_m_flow = self.calculate_m_dot(Q_H=Q_H)
                design_operation_V_flow = self.calculate_volume_flow(m_flow=design_operation_m_flow)
            elif "radiator_backward" in graph.nodes[node]["type"]:
                # PHeater_max, norm_indoor_temperature = self.read_bim2sim_data(space_id=graph.nodes[node]["belongs_to"])
                velocity = 0.4 * ureg.meter / ureg.seconds
                coefficient_resistance = 4.0
                # PHeater_max = 4000 #* ureg.watt
                Q_H = (PHeater_max / data["window_count"]) * ureg.kilowatt
                design_operation_m_flow = self.calculate_m_dot(Q_H=Q_H)
                design_operation_V_flow = self.calculate_volume_flow(m_flow=design_operation_m_flow)

            elif "heat_source" in graph.nodes[node]["type"]:
                coefficient_resistance = 4.0
                graph.nodes[node]['head'] = {viewpoint: 0 * ureg.meter}
            elif "Membranausdehnunggefäß" in graph.nodes[node]["type"]:
                coefficient_resistance = 0.5
            elif "Schmutzfänger" in graph.nodes[node]["type"]:
                coefficient_resistance = 0.35
            elif "Schwerkraftbremse" in graph.nodes[node]["type"]:
                coefficient_resistance = 0.5
            elif "Rücklaufabsperrung" in graph.nodes[node]["type"]:
                coefficient_resistance = 2.0
            elif "Sicherheitsventil" in graph.nodes[node]["type"]:
                coefficient_resistance = 1.5
            elif "Speicher" in graph.nodes[node]["type"]:
                coefficient_resistance = 2.5
            elif "Verteiler" in graph.nodes[node]["type"]:
                coefficient_resistance = 1.5
            elif "Rückschlagventil" in graph.nodes[node]["type"]:
                coefficient_resistance = 4.0
            elif "Dreiwegemischer" in graph.nodes[node]["type"]:
                coefficient_resistance = 6.0
            elif "Vierwegemischer" in graph.nodes[node]["type"]:
                coefficient_resistance = 8.0
            elif "Reduzierung" in graph.nodes[node]["type"]:
                coefficient_resistance = 0.5
            elif "Durchgangsventil" in graph.nodes[node]["type"]:
                coefficient_resistance = 8.0
            elif "Schieber" in graph.nodes[node]["type"]:
                coefficient_resistance = 0.5
            elif "Pumpe" in graph.nodes[node]["type"]:
                coefficient_resistance = 3.0
                graph.nodes[node]['head'] = {viewpoint: 0 * ureg.meter}
            elif "Thermostatventil" in graph.nodes[node]["type"]:
                coefficient_resistance = 4.0
            elif "Krümmer" in graph.nodes[node]["type"]:
                coefficient_resistance = 1.50
            # Parameter: Initialize Punkte
            graph.nodes[node]['coefficient_resistance'] = coefficient_resistance
            graph.nodes[node]['heat_flow'] = {viewpoint: Q_H}
            graph.nodes[node]['m_flow'] = {viewpoint: design_operation_m_flow}
            graph.nodes[node]['V_flow'] = {viewpoint: design_operation_V_flow}
            graph.nodes[node]['velocity'] = {viewpoint: velocity}
            graph.nodes[node]['coefficient_resistance'] = coefficient_resistance
            graph.nodes[node]['pressure_loss'] = {viewpoint: 0.0 * 10 ** 5 * ureg.pascal}
            graph.nodes[node]['pressure_in'] = {viewpoint: 2.5 * 10 ** 5 * ureg.pascal}
            graph.nodes[node]['pressure_out'] = {viewpoint: 2.5 * 10 ** 5 * ureg.pascal}
            graph.nodes[node]['pressure_out'] = {viewpoint: 2.5 * 10 ** 5 * ureg.pascal}
            graph.nodes[node]['norm_indoor_temperature'] = norm_indoor_temperature
        for edge in graph.edges():
            # Initialize Kanten Beispiel-Durchmesser (initial auf 0 setzen)
            graph.edges[edge]['inner_diameter'] = 0.0 * ureg.meter
            graph.edges[edge]['outer_diameter'] = 1.0 * ureg.meter
            graph.edges[edge]['heat_flow'] = {viewpoint: 1.0 * ureg.kilowatt}
            graph.edges[edge]['velocity'] = {viewpoint: 0.5 * (ureg.meter / ureg.seconds)}
            graph.edges[edge]['m_flow'] = {viewpoint: 1.0 * (ureg.kilogram / ureg.seconds)}
            graph.edges[edge]['V_flow'] = {viewpoint: 1.0 * (ureg.meter ** 3 / ureg.seconds)}
            graph.edges[edge]['pressure_loss'] = {viewpoint: 0.0 * 10 ** 5 * ureg.pascal}
            graph.edges[edge]["length"] = graph.edges[edge]["length"] * ureg.meter
            graph.edges[edge]["capacity"] = 0 * ureg.meter * (ureg.kilogram / ureg.seconds)
        return graph

    def create_bom_nodes(self, graph, filename, bom):
        # df_new_sheet = pd.DataFrame.from_dict(bom, orient='index', columns=['Anzahl'])
        df_new_sheet = pd.DataFrame.from_dict(bom, orient='index')

        with pd.ExcelWriter(filename, mode='a', engine='openpyxl') as writer:
            # Schreiben Sie das neue Sheet in die Excel-Datei

            df_new_sheet.to_excel(writer, sheet_name='Komponenten')
        # Bestätigung, dass das Sheet hinzugefügt wurde
        print(f"Das neue Sheet {filename} wurde erfolgreich zur Excel-Datei hinzugefügt.")



    def create_bom_edges(self, graph, filename, sheet_name, viewpoint: str):
        bom_edges = {}  # Stückliste für Kanten (Rohre)
        total_mass = 0  # Gesamtmasse der Kanten (Rohre)
        total_length = 0
        total_flow = 0
        total_dammung = 0
        for u, v in graph.edges():
            length = graph.edges[u, v]['length']
            inner_diameter = graph.edges[u, v]['inner_diameter']
            outer_diameter = graph.edges[u, v]['outer_diameter']
            dammung = graph.edges[u, v]['dammung']
            density = graph.edges[u, v]['density']
            material = graph.edges[u, v]['material']
            m_flow = graph.nodes[u]['m_flow'][viewpoint]
            # Berechne die Materialmenge basierend auf den Kantenattributen (Beispielberechnung)
            material_quantity = ((length * (math.pi / 4) * (
                        outer_diameter ** 2 - inner_diameter ** 2)) * density).to_base_units()
            # material_dammung = ((length *(math.pi/4) * (dammung**2 - outer_diameter**2)) *  55.0 *(ureg.kg/ureg.meter**3)).to_base_units()
            material_dammung = ((length * dammung * 55.0 * (ureg.kg / ureg.meter ** 3))).to_base_units()
            pos = f'{graph.nodes[u]["pos"]} - {graph.nodes[v]["pos"]}'
            x_1 = round(graph.nodes[u]["pos"][0], 3)
            y_1 = round(graph.nodes[u]["pos"][1], 3)
            z_1 = round(graph.nodes[u]["pos"][2], 3)
            x_2 = round(graph.nodes[v]["pos"][0], 3)
            y_2 = round(graph.nodes[v]["pos"][1], 3)
            z_2 = round(graph.nodes[v]["pos"][2], 3)
            position = f'[{x_1}, {y_1}, {z_1}] - [{x_1}], {y_2}, {z_2}]'
            # bom_edges[(pos)] = material_quantity
            bom_edges[position] = {
                # 'Rohr': pos,
                'Materialmenge [kg]': round(material_quantity, 4),
                'Material dammung [kg]': round(material_dammung, 4),
                'inner_diameter [m]': inner_diameter,
                'outer_diameter [m]': outer_diameter,
                'm_flow [kg/h]': m_flow,
                'Länge [m]': round(length, 4),
                'material': material,
                'density': density
            }
            total_mass += material_quantity
            total_length += length
            total_flow += m_flow
            total_dammung += material_dammung
        # df = pd.DataFrame(list(bom_edges.items()), columns=['Kante', 'Materialmenge'])
        df = pd.DataFrame.from_dict(bom_edges, orient='index')
        # Füge die Gesamtmasse hinzu
        total_mass_row = {'inner_diameter [m]': '', 'outer_diameter [m]': '', 'm_flow [kg/h]': total_flow,
                          'Länge [m]': total_length,
                          'Materialmenge [kg]': round(total_mass, 4),
                          'Material dammung [kg]': round(total_dammung, 4)}
        df = pd.concat([df, pd.DataFrame(total_mass_row, index=['Gesamtmasse'])])
        # Schreibe das DataFrame in eine Excel-Tabelle
        df.to_excel(filename, sheet_name=sheet_name, index_label='Rohre')

    def write_component_list(self, graph):
        bom = {}  # Stückliste (Komponente: Materialmenge)
        for node, data in graph.nodes(data=True):

            if "Pumpe" in set(data["type"]):
                pass
                #print(node)
                #print(data)

            if node not in bom:
                bom[node] = {}
            if "type" in data:
                bom[node]["type"] = data["type"]
            if "material" in data:
                bom[node]["material"] = data["material"]
            if "model" in data:
                bom[node]["model"] = data["model"]
            if "material_mass" in data:
                bom[node]["material_mass"] = data["material_mass"]
            if "norm_indoor_temperature" in data:
                bom[node]["norm_indoor_temperature"] = data["norm_indoor_temperature"]
            if "Power" in data:
                bom[node]["Power"] = data["Power"]
            if "heat_flow" in data:
                bom[node]["heat_flow"] = data["heat_flow"]
            if "length" in data:
                bom[node]["length"] = data["length"]
            if "norm_heat_flow_per_length" in data:
                bom[node]["norm_heat_flow_per_length"] = data["norm_heat_flow_per_length"]
        """for node,data  in graph.nodes(data=True):
            print(data)
            component_type = graph.nodes[node].get('type')
            for comp in component_type:
                if comp in bom:
                    bom[comp] += 1  # Erhöhe die Materialmenge für die Komponente um 1
                else:
                    bom[comp] = 1  # Initialisiere die Materialmenge für die Komponente mit 1"""

        return bom

    def calculate_pressure_pipe_lost(self, length, inner_diameter, v_mid):
        """
        f * (rho * v**2) / (2 * D * graph)
        Args:
            length ():

        Returns:
        """
        return self.f * (self.density_fluid * v_mid ** 2) * length / (2 * inner_diameter * self.g)

    def update_radiator_volume_flow_nodes(self, graph, nodes: list):
        """

        Args:
            graph ():
            nodes ():

        Returns:

        """
        radiator_nodes = [n for n, attr in graph.nodes(data=True) if
                          any(t in attr.get("type", []) for t in nodes)]
        for node in radiator_nodes:
            m_flow = graph.nodes[node]['m_flow']["design_operation_norm"]
            V_flow = m_flow / self.density_fluid
            graph.nodes[node]['V_flow'].update({"design_operation_norm": V_flow})
        return graph

    def hardy_cross_methods(self, graph, viewpoint: str):
        """
        Args:
            graph ():
        Returns:
        """
        # Initialisiere die Iterationsvariablen
        max_iterations = 100
        iteration = 0
        error_tolerance = 1e-5
        error = float('inf')

        # Iteriere, bis der Fehler unter die Toleranz fällt oder die maximale Anzahl an Iterationen erreicht ist
        while error > error_tolerance and iteration < max_iterations:
            error = 0

            # Iteriere über die Knoten in umgekehrter Reihenfolge (von den Endpunkten zum Startpunkt)
            for node in reversed(list(nx.topological_sort(graph))):
                # Überprüfe, ob der Knoten Verzweigungen hat
                successors = list(graph.successors(node))
                if len(successors) > 1:
                    # Summiere die Massenströme der Nachfolgerknoten
                    massenstrom_sum = sum(graph.nodes[succ]['m_flow'][viewpoint] for succ in successors)
                    volumen_flow_sum = sum(graph.nodes[succ]['V_flow'][viewpoint] for succ in successors)
                    # Speichere den summierten Massenstrom im aktuellen Knoten
                    graph.nodes[node]['m_flow'].update({viewpoint: massenstrom_sum})
                    graph.nodes[node]['V_flow'].update({viewpoint: volumen_flow_sum})
                elif len(successors) == 1:
                    # Kopiere den Massenstrom des einzigen Nachfolgerknotens
                    graph.nodes[node]['m_flow'].update({viewpoint: graph.nodes[successors[0]]['m_flow'][viewpoint]})
                    graph.nodes[node]['V_flow'].update({viewpoint: graph.nodes[successors[0]]['V_flow'][viewpoint]})

            # Iteriere über die Knoten in aufsteigender Reihenfolge (vom Startpunkt zu den Endpunkten)
            for node in nx.topological_sort(graph):
                # Überprüfe, ob der Knoten Verzweigungen hat
                predecessors = list(graph.predecessors(node))
                if len(predecessors) == 1:
                    # Berechne den Massenstrom im Rohr basierend auf dem bekannten Druckverlust
                    predecessor = predecessors[0]
                    pipe_id = graph[predecessor][node]['pipe_id']
                    pipe_length = graph[predecessor][node]['length']
                    pipe_diameter = graph[predecessor][node]['diameter']
                    # Führe die Berechnungen für den Massenstrom im Rohr durch
                    # und aktualisiere den Massenstrom im aktuellen Knoten

            # Berechne den Fehler zwischen den alten und neuen Massenströmen
            for node in graph.nodes:
                error += abs(graph.nodes[node]['m_flow'][viewpoint] - graph.nodes[node]['m_flow_old'][viewpoint])

            # Erhöhe die Iterationszählung
            iteration += 1

        # Gib den aktualisierten Graphen zurück
        return graph

    def calculate_pipe_inner_diameter(self, m_flow, v_mittel, security_factor):
        """
        d_i = sqrt((4 * m_flow) / (pi * rho * v_max))
        Args:
            m_flow ():
        """
        # innter_diameter = math.sqrt(result.magnitude) * result.units**0.5 # in SI-Basiseinheiten umwandeln
        inner_diameter = (((4 * m_flow / (math.pi * self.density_fluid * v_mittel)) ** 0.5) * security_factor).to(
            ureg.millimeter)
        diameter = round(inner_diameter, 3)
        return diameter

    def calculate_radiator_area(self, Q_H: float, alpha: float = 0.7, delta_T: int = 30):
        """
        Q_H = alpha * A * delta_T
        """
        return Q_H / (alpha * delta_T)

    def calculate_diameter_DIN_EN_12828(self, Q_H: float):
        """
        Args:
            Q_H ():
        Returns:
        """
        return 1.1 * (Q_H / (self.v_mean * (self.temperature_forward - self.temperature_backward))) ** 0.5

    def calculate_diameter_VDI_2035(self, Q_H: float):
        # Q_vol = Q_H * Calc_pipes.watt/ (3600 * self.rho  * Calc_pipes.kg/Calc_pipes.m**3)
        Q_vol = Q_H / (3600 * self.density_fluid)
        return (4 * self.f * Q_vol / (math.pi * self.kinematic_velocity_fluid))

    def calculate_inner_diameter(self, Q_H: float, delta_p: float, length: float):
        """
        Q_H = alpha *pi * (d**2 / 4) * delta_T
        d = 2 * ((m_dot / (rho * v_max * pi)) ** 0.5) * (p_max / p)
        d = (8fLQ^2)/(pi^2delta_p)
        d = (8 * Q * f * L) / (π^2 * Δp * ρ)
        """
        # return math.sqrt(4 * Q_H/(alpha * self.delta_T * math.pi))
        return (8 * self.f * length * Q_H ** 2) / (math.pi ** 2 * delta_p * self.density_fluid)

    def calculate_m_dot(self, Q_H: float):
        """
        Q_H = m_dot * c_p_fluid * delta_T
        """
        return round(
            (Q_H / (self.c_p_fluid * (self.temperature_forward - self.temperature_backward))).to(ureg.kilogram / ureg.second),
            5)

    def calculate_network_bottleneck_strands(self, graph, strands, start_nodes: list):
        """bottleneck_point = [n for n, attr in graph.nodes(data=True) if
                 any(t in attr.get("type", []) for t in end_nodes)]

        Args:
            graph ():
            strands ():
            start_nodes (): """
        start_node = [n for n, attr in graph.nodes(data=True) if
                      any(t in attr.get("type", []) for t in start_nodes)]

        pressure_dict = {}
        for start in start_node:
            min_pressure = float('inf')
            for strand in strands:
                if start in set(strand):
                    # Iteration über die Endpunkte
                    # for node in bottleneck_point:
                    for strang in strand:
                        pressure = graph.nodes[strang]['pressure']
                        if pressure < min_pressure:
                            min_pressure = pressure
            pressure_dict[start] = min_pressure
        return pressure_dict

    def calculate_pump(self,
                       graph,
                       pressure_difference,
                       viewpoint: str,
                       efficiency: float = 0.5):
        pump_node = []
        for node, data in graph.nodes(data=True):
            if "Pumpe" in graph.nodes[node]["type"]:
                pump_node.append(node)

        head = self.calculate_head(graph = graph, pressure_difference=pressure_difference)
        for pump in pump_node:
            m_flow = graph.nodes[pump]['m_flow'][viewpoint]
            pump_power = self.calculate_pump_power(m_flow=m_flow,
                                                   efficiency=efficiency,
                                                   pressure_difference=2 * pressure_difference)
            graph.nodes[pump]['Power'] = pump_power.to(ureg.kilowatt)

            graph.nodes[pump]['head'][viewpoint] = head

    def calculate_network_bottleneck(self, graph, nodes: list, viewpoint: str):
        """

        Args:
            graph ():
            nodes ():

        Returns:

        """
        nodes = [n for n, attr in graph.nodes(data=True) if
                 any(t in attr.get("type", []) for t in nodes)]

        bottleneck_node = None
        min_pressure = float('inf') * ureg.pascal
        for node in nodes:
            pressure = graph.nodes[node]['pressure_out'][viewpoint]
            if pressure < min_pressure:
                min_pressure = pressure
                bottleneck_node = node

        graph.nodes[bottleneck_node]["type"].append("Netzschlechtpunkt")
        max_node = None
        max_pressure = -float('inf') * ureg.pascal
        for nodes, data in graph.nodes(data=True):
            pressure = data['pressure_out'][viewpoint]
            if pressure > max_pressure:
                max_pressure = pressure
                max_node = node
        pressure_difference = (max_pressure - min_pressure) * 2

        head = self.calculate_head(graph=graph, pressure_difference=pressure_difference)
        for node, data in graph.nodes(data=True):
            if "heat_source" in data["type"]:
                graph.nodes[node]['head'][viewpoint] = head
        return min_pressure, max_pressure, bottleneck_node, pressure_difference * 2, graph

    def calculate_reynold(self, inner_diameter: float, mid_velocity: float):
        """
        Args:
            inner_diameter ():
            mid_velocity ():
             * self.rho
        """
        return (mid_velocity * inner_diameter) / self.kinematic_velocity_fluid
        # return (mid_velocity * inner_diameter* self.rho) / 0.001 *(ureg.kilogram/(ureg.meter*ureg.seconds))

    def calculate_friction_pressure_loss(self, inner_diameter, v_mid, length):
        """
        Args:
            inner_diameter ():
            v_mid ():
            length ():
        Returns:
        """

        reynold = self.calculate_reynold(inner_diameter=inner_diameter,
                                         mid_velocity=v_mid)

        if reynold <= 2300:
            pipe_friction_coefficient = self.pipe_friction_coefficient_laminar_hagen_poiseuille(reynold=reynold)
        else:
            pipe_friction_coefficient = colebrook.sjFriction(reynold, self.absolute_roughness)

        delta_p_friction, pipe_friction_resistance = self.darcy_weisbach_equation(
            pipe_friction_coefficient=pipe_friction_coefficient,
            mid_velocity=v_mid,
            length=length,
            inner_diameter=inner_diameter)
        delta_p_friction = delta_p_friction.to(ureg.pascal)

        return delta_p_friction, pipe_friction_resistance

    def iterate_pressure_loss_edges(self,
                                    graph: nx.Graph(),
                                    v_mid: float,
                                    viewpoint: str):
        """
        Args:
            graph ():
            v_mid ():
        Returns:
        """
        for node in graph.nodes():
            successors = list(graph.successors(node))
            for succ in successors:
                # todo: v_max/2
                length = graph.edges[node, succ]['length']
                inner_diameter = graph.edges[node, succ]['inner_diameter']
                delta_p_friction, pipe_friction_resistance = self.calculate_friction_pressure_loss(
                    inner_diameter=inner_diameter,
                    v_mid=self.v_max / 2,
                    length=length)

                h = (graph.nodes[node]['pos'][2] - graph.nodes[succ]['pos'][2]) * ureg.meter
                delta_p_hydro = self.calculate_pressure_hydro(delta_h=h)
                graph.edges[node, succ]['pipe_friction_resistance'] = pipe_friction_resistance
                if "pressure_loss" in graph.edges[node, succ]:
                    graph.edges[node, succ]['pressure_loss'].update({viewpoint: delta_p_friction + delta_p_hydro})

                else:
                    graph.edges[node, succ]['pressure_loss'] = {viewpoint: delta_p_friction + delta_p_hydro}
        return graph

    def pipe_friction_coefficient_laminar_hagen_poiseuille(self, reynold):
        """

        Args:
            reynold ():
        """
        return 64 / reynold

    # Druckverluste Rohr
    def darcy_weisbach_equation(self,
                                pipe_friction_coefficient: float,
                                mid_velocity: float,
                                length: float,
                                inner_diameter: float):
        """

        Args:
            pipe_friction_coefficient ():
        """

        pipe_friction_resistance = self.calc_pipe_friction_resistance(
            pipe_friction_coefficient=pipe_friction_coefficient,
            inner_diameter=inner_diameter,
            v_mid=mid_velocity)
        # pressure_drop = 0.5 * (length / inner_diameter) * (self.density_fluid * pipe_friction_coefficient) * mid_velocity ** 2
        pressure_drop = pipe_friction_resistance * length
        pressure_drop = pressure_drop.to(ureg.pascal)
        return round(pressure_drop, 4), pipe_friction_resistance

    def calculate_pressure_hydro(self, delta_h):
        """

        Args:
            delta_h ():

        Returns:

        """
        # todo: Wird bei Heizungsanlagen nicht betrachtet
        return 0
        # return self.rho * self.graph * delta_h

    def calculate_pressure_loss_fittings(self, coefficient_resistance: float, mid_velocity: float):
        """
        Druckverluste Einbauten Widerstandsbeiwerts
        Args:
            coefficient_resistance ():
        """
        return (0.5 * self.density_fluid * coefficient_resistance * mid_velocity ** 2).to(ureg.pascal)
