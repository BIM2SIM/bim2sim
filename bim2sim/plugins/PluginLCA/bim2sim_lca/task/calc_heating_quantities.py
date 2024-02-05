import logging

from bim2sim.tasks.base import ITask
from bim2sim.utilities.graph_functions import read_json_graph
import networkx as nx
from bim2sim.elements.mapping.units import ureg
from pathlib import Path
from ebcpy.data_types import TimeSeriesData
import json
import math
import pandas as pd
import colebrook
from bim2sim.utilities.visualize_graph_functions import visualzation_networkx_3D, visulize_networkx

class CalcHeatingQuantities(ITask):
    """short docs.

    longs docs.

    Args:
        ...
    Returns:
        ...
    """

    reads = ('heating_graph', )
    touches = ('calculate_heating_graph_list', )
    final = True


    components_parameter = {
        "coefficient_resistance":
            {
            "component": {
                "membrane_expansion_vessel": 0.5,
                "gate_valve": 4.0,
                "strainer": 0.5,
                "distributor": 3.5,
                "gravity_break": 0.5,
                "thermostatic_valve": 4.0,
                "backflow_preventer": 4.0,
                "pump": 4.0,
                "safety_valve": 4.0,
                "heat_source": 4.0,
                'bends': 4.0,
                'separator': 3.0,
                'deaerator': 3.0,
                'unifier': 3.0,
                "radiator": 4.0,
                "underfloor_heating": 4.0,
                "coupling" : 3.5
        },
                "unit": ureg.dimensionless
            },
        #"max_velocity"
    }

    room_parameter = {
        "standard_indoor_temperature":
            {
            "room":  {
                "Single office": 22+273.15,
                "Küche": 20+273.145,
                "Kinderzimmer": 22+273.15,
                "Schlafzimmer": 18+273.15,
                "Bad": 24+273.15,
                "Keller": 15+273.15,
            },
                "unit": ureg.kelvin
            }
    }

    def __init__(self, playground):
        super().__init__(playground)

        self.specific_heat_capacity = 4.186 * (ureg.kilojoule / (ureg.kilogram * ureg.kelvin))
        self.supply_norm_temperature = (75+273.15) * ureg.kelvin
        self.return_norm_temperature = (65+273.15) * ureg.kelvin
        self.room_norm_temperature = (20+273.15) * ureg.kelvin
        self.density_water = 997 * (ureg.kilogram / ureg.meter ** 3)
        self.maximal_velocity = 0.5  * ureg.meter / ureg.seconds
        self.radiator_heating_exponent = 1.3 * ureg.dimensionless
        self.kinetic_viscosity =  1.002 * (ureg.millimeter ** 2 / ureg.second)
        self.absolute_roughness = 0.0023
        self.g = 9.81 * (ureg.meter / ureg.second ** 2)
        self.radiator_sheet_name = "Profilierte Flachheizkörper"
        self.radiator_filename = self.playground.sim_settings.distribution_file_path



    def run(self, heating_graph: nx.Graph()):

        calculate_heating_graph_list = []


        for temperature in self.playground.sim_settings.design_distribution_temperatures:

            supply_temperature = (temperature.value[0] + 273.15) * ureg.kelvin
            return_temperature = (temperature.value[1] + 273.15) * ureg.kelvin
            # number of delivery component each room/space
            caluclated_heating_graph = self.number_delivery_nodes_each_room(heating_graph,
                                                                            component_type=self.playground.sim_settings.distribution_system_type)
            caluclated_heating_graph.graph["temperature_niveau"] = temperature.value

            #caluclated_heating_graph = self.remove_node_attributes(caluclated_heating_graph, attributes=["snapped", "IfcWindow", "IfcDoor"])
            # Add physical attributes to nodes
            caluclated_heating_graph = self.initialize_node_physical_attributes(caluclated_heating_graph)
            # Add physical attributes to edges
            caluclated_heating_graph = self.initialize_edge_physical_attributes(caluclated_heating_graph)
            caluclated_heating_graph = self.initialize_node_parameters(caluclated_heating_graph, parameter_key="coefficient_resistance")

            # initialize or load parameter
            variable_zone_dict = self.load_simulation_results(self.playground.sim_settings.simulation_file_path)
            thermalzone_mapping = self.load_thermalzone_mapping(self.playground.sim_settings.thermalzone_mapping_file_path)
            for key in variable_zone_dict:
                max_P_Heater = max(variable_zone_dict[key]["PHeater"].values())
                thermalzone_mapping[int(key)]["PHeater"] = max_P_Heater

            caluclated_heating_graph = self.initialize_delivery_nodes(graph=caluclated_heating_graph,
                                                                      th_mapping=thermalzone_mapping,
                                                                      supply_temperature=supply_temperature,
                                                                      return_temperature=return_temperature,
                                                                      heating_system_type=self.playground.sim_settings.distribution_system_type)
            #  calculate mass flow/volume flow
            caluclated_heating_graph = self.calculate_distribution_pipe_system(caluclated_heating_graph)
            caluclated_heating_graph = self.calculate_edge_attributes(caluclated_heating_graph)

            # pressure difference pipes
            caluclated_heating_graph = self.iterate_pressure_loss_edges(caluclated_heating_graph)
            # pressure difference components
            caluclated_heating_graph = self.iterate_pressure_loss_fittings_nodes(caluclated_heating_graph)
            caluclated_heating_graph = self.calculate_pressure_loss_system(caluclated_heating_graph)
            min_pressure, max_pressure, bottleneck_node, pressure_difference, caluclated_heating_graph = self.calculate_network_bottleneck(caluclated_heating_graph, nodes=["delivery_node_supply"])
            # calculate pump power
            caluclated_heating_graph = self.calculate_pump_power(caluclated_heating_graph, pressure_difference)
            calculate_heating_graph_list.append(caluclated_heating_graph)
        return calculate_heating_graph_list,

    def calculate_pump_power(self,
                             graph: nx.DiGraph(),
                             pressure_difference,
                             operation_point: str = "design_operation_point",
                             efficiency: float = 0.5
                             ) -> nx.DiGraph():
        pump_node = []
        for node, data in graph.nodes(data=True):
            if "pump" == graph.nodes[node]["component_type"]:
                pump_node.append(node)
        head = self.calculate_head(pressure_difference=pressure_difference)
        for pump in pump_node:
            m_flow = graph.nodes[pump][operation_point]['mass_flow']
            pump_power = self.calculate_pump_performance(m_flow=m_flow,
                                                   efficiency=efficiency,
                                                   pressure_difference=2 * pressure_difference)
            graph.nodes[pump][operation_point]['power'] = pump_power.to(ureg.kilowatt)
            graph.nodes[pump][operation_point]['head'] = head
        return graph

    def calculate_pump_performance(self,
                                   m_flow,
                                   pressure_difference,
                                   efficiency):
        return round((m_flow * pressure_difference) / (efficiency * self.density_water), 2)

    def calculate_network_bottleneck(self,
                                     graph: nx.DiGraph(),
                                     nodes:list,
                                     operation_point: str = "design_operation_point"):
        nodes = [n for n, attr in graph.nodes(data=True) if
                 any(t in attr.get("node_type", []) for t in nodes)]

        bottleneck_node = None
        min_pressure = float('inf') * ureg.pascal
        for node in nodes:
            pressure = graph.nodes[node][operation_point]['pressure_out']
            if pressure < min_pressure:
                min_pressure = pressure
                bottleneck_node = node

        graph.nodes[bottleneck_node]["node_type"] = "network_weak_point"
        max_pressure = -float('inf') * ureg.pascal
        for nodes, data in graph.nodes(data=True):
            pressure = data[operation_point]['pressure_out']
            if pressure > max_pressure:
                max_pressure = pressure

        pressure_difference = (max_pressure - min_pressure) * 2

        head = self.calculate_head(pressure_difference=pressure_difference)
        for node, data in graph.nodes(data=True):
            if "heat_source" == data["node_type"]:
                graph.nodes[node][operation_point]['head'] = head
        return min_pressure, max_pressure, bottleneck_node, pressure_difference * 2, graph

    def calculate_head(self, pressure_difference: float):
        return round((pressure_difference * 1 / (self.density_water * self.g)).to_base_units(), 4)

    def calculate_pressure_loss_system(self,
                                       graph: nx.DiGraph(),
                                       viewpoint: str = "design_operation_point",
                                       initial_pressure=(1.5 * 10 ** 5)):
        max_iterations = 100
        convergence_threshold = 1e-6

        for node, data in graph.nodes(data=True):
            data[viewpoint]['pressure_out'] = initial_pressure * ureg.pascal
            data[viewpoint]['pressure_in'] = initial_pressure * ureg.pascal
        for iteration in range(max_iterations):
            prev_node_pressures = {node: graph.nodes[node][viewpoint]['pressure_out'] for node in graph.nodes}
            for node in list(nx.topological_sort(graph)):
                if "pump" == graph.nodes[node]["component_type"]:
                    prev_pressure_out = graph.nodes[node][viewpoint]['pressure_out']
                    graph.nodes[node][viewpoint]['pressure_out'] = prev_pressure_out
                # Druck am Eingang des Knotens berechnen
                prev_pressure_out = graph.nodes[node][viewpoint]['pressure_out']
                successors = list(graph.successors(node))
                if len(successors) > 0 or successors is not None:
                    for succ in successors:
                        next_node = succ
                        predecessors = list(graph.predecessors(next_node))
                        if len(predecessors) > 1:
                            min_pressure = float('inf') * ureg.pascal
                            pre_node = None
                            for pre in predecessors:
                                next_pressure_out = graph.nodes[pre][viewpoint]['pressure_out']
                                if next_pressure_out < min_pressure:
                                    min_pressure = next_pressure_out
                                    pre_node = pre
                            prev_pressure_out = graph.nodes[pre_node][viewpoint]['pressure_out']
                            edge_pressure_loss = graph[pre_node][next_node][viewpoint]['pressure_loss']
                            node_pressure_loss = graph.nodes[pre_node][viewpoint]['pressure_loss']
                            next_pressure_in = prev_pressure_out - edge_pressure_loss
                            next_pressure_out = next_pressure_in - node_pressure_loss
                            graph.nodes[next_node][viewpoint]['pressure_in'] = next_pressure_in
                            graph.nodes[next_node][viewpoint]['pressure_out'] = next_pressure_out
                        else:
                            edge_pressure_loss = graph[node][next_node][viewpoint]['pressure_loss']
                            node_pressure_loss = graph.nodes[next_node][viewpoint]['pressure_loss']
                            next_pressure_in = prev_pressure_out - edge_pressure_loss
                            next_pressure_out = next_pressure_in - node_pressure_loss
                            graph.nodes[next_node][viewpoint]['pressure_in'] = next_pressure_in
                            graph.nodes[next_node][viewpoint]['pressure_out'] = next_pressure_out
                else:
                    continue
            convergence = True
            for node in graph.nodes:
                pressure_diff = abs(graph.nodes[node][viewpoint]['pressure_out'] - prev_node_pressures[node])
                if pressure_diff.magnitude > convergence_threshold:
                    convergence = False
                    break
            if convergence:
                break
        return graph

    def load_pipe_data(self,
                       filename: Path,
                       sheet_name: str,
                       calc_inner_diameter: float):
        """

        Args:
            filename ():
            sheet_name ():
            calc_inner_diameter ():
        """
        data = pd.read_excel(filename, sheet_name=sheet_name)

        inner_diameter_list = {}
        material = None
        density = None
        for index, row in data.iterrows():
            try:
                outer_diameter = row['outer_diameter [mm]'] * ureg.millimeter
                wall_thickness = row['normal_wall_thickness [mm]'] * ureg.millimeter
                material = row['material']
                pipe_mass = row['pipe_mass [kg/m]']
                density = row['density [kg/m³]'] * (ureg.kilograms / ureg.meter ** 3)
                inner_diameter = (outer_diameter - 2 * wall_thickness)
                if calc_inner_diameter <= inner_diameter:
                    inner_diameter_list[inner_diameter] = outer_diameter
            except KeyError as e:
                self.logger.warning(e)

        if len(inner_diameter_list) >0:
            inner_diameter = min(inner_diameter_list,
                                 key=lambda x: abs(inner_diameter_list[x] - calc_inner_diameter))
            outer_diameter = inner_diameter_list[inner_diameter]
        else:
            inner_diameter = calc_inner_diameter
            outer_diameter = inner_diameter + 2 * 5  * ureg.millimeter


        return inner_diameter, outer_diameter, material, density




    def calculate_pipe_inner_diameter(self,
                                      mass_flow: float,
                                      security_factor: float = 1.15):
        """self.logger.info(f"Calculate pipe inner diameter with pipe material {pipe_material}, "
                         f"with a security factor {security_factor} and "
                         f"a velocity of {maximal_velocity}.")"""
        return (((4 * mass_flow / (math.pi * self.density_water * self.maximal_velocity)) ** 0.5) * security_factor).to(
            ureg.millimeter)



    def calculate_distribution_pipe_system(self,
                                           graph: nx.DiGraph(),
                                           viewpoint: str = "design_operation_point") -> nx.DiGraph():
        sorten_nodes = {}
        for node, data in graph.nodes(data=True):
            sorten_nodes.setdefault(data["grid_type"], []).append(node)
        # supply_line:
        supply_line_graph = graph.subgraph(sorten_nodes["supply_line"])
        supply_line_graph = self.iterate_in_reversed_topological_direction(supply_line_graph,
                                                                           operation_point=viewpoint)
        # return line:
        return_line_graph = graph.subgraph(sorten_nodes["return_line"])
        return_line_graph = self.iterate_in_topological_direction(return_line_graph,
                                                                  viewpoint=viewpoint)
        # heating_graph
        heating_graph = nx.disjoint_union(supply_line_graph, return_line_graph)



        return heating_graph



    def iterate_in_topological_direction(self,
                                         graph: nx.DiGraph(),
                                         viewpoint: str = "design_operation_point") -> nx.DiGraph():
        """

        Args:
            graph ():
            viewpoint ():

        Returns:

        """
        for node in list(nx.topological_sort(graph)):
            predecessors = list(graph.predecessors(node))
            if len(predecessors) > 1:
                mass_flow_sum = sum(graph.nodes[succ][viewpoint]['mass_flow'] for succ in predecessors)
                volume_flow_sum = sum(graph.nodes[succ][viewpoint]['volume_flow'] for succ in predecessors)
                heat_flow_sum = sum(graph.nodes[succ][viewpoint]['heat_flow'] for succ in predecessors)
                graph.nodes[node][viewpoint]["mass_flow"] = mass_flow_sum
                graph.nodes[node][viewpoint]["volume_flow"] = volume_flow_sum
                graph.nodes[node][viewpoint]["heat_flow"] = heat_flow_sum
            elif len(predecessors) == 1:
                graph.nodes[node][viewpoint]["mass_flow"] = graph.nodes[predecessors[0]][viewpoint]['mass_flow']
                graph.nodes[node][viewpoint]["volume_flow"] = graph.nodes[predecessors[0]][viewpoint]['volume_flow']
                graph.nodes[node][viewpoint]["heat_flow"] = graph.nodes[predecessors[0]][viewpoint]['heat_flow']
        return graph


    def iterate_in_reversed_topological_direction(self,
                                                  graph: nx.DiGraph(),
                                                  operation_point: str = "design_operation_point") -> nx.DiGraph():
        """

        Args:
            graph ():
            operation_point ():
        """
        # iterative nodes
        for node in reversed(list(nx.topological_sort(graph))):
            successors = list(graph.successors(node))
            if len(successors) > 1:
                mass_flow_sum = sum(graph.nodes[succ][operation_point]['mass_flow'] for succ in successors)
                volume_flow_sum = sum(graph.nodes[succ][operation_point]['volume_flow'] for succ in successors)
                heat_flow_sum = sum(graph.nodes[succ][operation_point]['heat_flow'] for succ in successors)
                graph.nodes[node][operation_point]["mass_flow"] = mass_flow_sum
                graph.nodes[node][operation_point]["volume_flow"] = volume_flow_sum
                graph.nodes[node][operation_point]["heat_flow"] = heat_flow_sum
            elif len(successors) == 1:
                graph.nodes[node][operation_point]["mass_flow"] = graph.nodes[successors[0]][operation_point]['mass_flow']
                graph.nodes[node][operation_point]["volume_flow"] = graph.nodes[successors[0]][operation_point]['volume_flow']
                graph.nodes[node][operation_point]["heat_flow"] = graph.nodes[successors[0]][operation_point]['heat_flow']




        return graph




    def initialize_delivery_nodes(self,
                                  graph: nx.DiGraph(),
                                  th_mapping: dict,
                                  supply_temperature:float,
                                  return_temperature:float,
                                  heating_system_type: str = "radiator",
                                  operation_point: str = "design_operation_point") -> nx.DiGraph():
        """

        Args:
            supply_temperature (): The design flow temperature of the distribution system
            return_temperature (): The design return temperature of the distribution system
            heating_system_type (): Type of heating system (radiator, underfloor_heating=
            graph (): Heating system graph
            th_mapping ():
            operation_point ():

        Returns:

        """
        radiator_dict = self.load_radiator_model(filename=self.playground.sim_settings.distribution_file_path,
                                                 sheet_name=self.radiator_sheet_name
                                 )
        for node, data in graph.nodes(data=True):
            if data["component_type"] == heating_system_type:
                for th in th_mapping:
                    if set(data["belongs_to_room"]) & set(th_mapping[th]["space_guids"]):
                        # PHeater
                        heat_flow = th_mapping[th]["PHeater"]

                        data[operation_point]["heat_flow"] = (heat_flow/data["delivery_number"]) * ureg.kilowatt
                        data[operation_point]["mass_flow"] = self.calculate_mass_flow(heat_flow=data[operation_point]["heat_flow"],
                                                                                      supply_temperature=supply_temperature,
                                                                                      return_temperature=return_temperature)

                        data[operation_point]["volume_flow"] = self.calculate_volume_flow(data[operation_point]["mass_flow"])

                        # Norm indoor temperature
                        room_type = th_mapping[th]["usage"]
                        temp_unit = self.room_parameter["standard_indoor_temperature"]["unit"]
                        try:
                            temperature = self.room_parameter["standard_indoor_temperature"]["room"][room_type]
                            data[operation_point]["norm_indoor_temperature"] = temperature * temp_unit
                        except KeyError:
                            data[operation_point]["norm_indoor_temperature"] = 293.15 * temp_unit
                        # radiator
                        if heating_system_type == "radiator":

                            log_op_temp = self.calculate_logarithmic_mean_temperature(standard_indoor_temperature=data[operation_point]["norm_indoor_temperature"],
                                                                                      supply_temperature=supply_temperature,
                                                                                      return_temperature=return_temperature)
                            heat_flow_norm = self.calculate_norm_heat_flow_radiator(heat_flow_operation=data[operation_point]["heat_flow"],
                                                                   logarithmic_mean_temperature_operation=log_op_temp)
                            mass_flow_norm = self.calculate_mass_flow(heat_flow=heat_flow_norm,
                                                                      supply_temperature=supply_temperature,
                                                                              return_temperature=return_temperature)
                            volume_flow_norm = self.calculate_volume_flow(mass_flow_norm)
                            selected_model, min_mass, material, length, norm_heat_flow = self.calculate_radiator_model(radiator_dict=radiator_dict,
                                                          heat_flow=heat_flow_norm,
                                                          volume_flow=volume_flow_norm)
                            graph.nodes[node]['material_mass'] = min_mass

                            graph.nodes[node]['material'] = material
                            graph.nodes[node]['model'] = selected_model
                            graph.nodes[node]['length'] = length
                            graph.nodes[node]['norm_heat_flow_per_length'] = norm_heat_flow
                        elif heating_system_type == "underfloor_heating":
                            pass
        return graph


    def load_radiator_model(self,
                            filename,
                            sheet_name):
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

    def calculate_radiator_model(self,
                                 radiator_dict: dict,
                                 heat_flow,
                                 volume_flow):
        """

        Args:
            radiator_dict ():
            heat_flow ():
            volume_flow ():

        Returns:

        """
        selected_model = None
        min_mass = float('inf') * ureg.kilogram
        material = None
        l1 = None
        length = None
        norm_heat_flow = None
        length_minimum = 400 * ureg.millimeter
        length_max = 4000 * ureg.millimeter
        for model in radiator_dict:
            if 'Wasserinhalt' and 'Masse' and 'Normwärmeleistung' and 'Material' in radiator_dict[model]:
                volume_per_length = radiator_dict[model]['Wasserinhalt']
                mass_per_length = radiator_dict[model]['Masse']

                norm_heat_flow_per_length = radiator_dict[model]['Normwärmeleistung']
                material = radiator_dict[model]['Material']
                l1 = (heat_flow / norm_heat_flow_per_length).to_base_units()
                l2 = (volume_flow / volume_per_length).to_base_units()
                if l1 <= length_max:
                    mass = l1 * mass_per_length

                    if mass < min_mass:
                        min_mass = mass
                        selected_model = model
                        length = l1
                        norm_heat_flow = norm_heat_flow_per_length

        return selected_model, min_mass, material, length, norm_heat_flow

    def calculate_norm_heat_flow_radiator(self,
                                          logarithmic_mean_temperature_operation: float,
                                          heat_flow_operation: float,
                                          logarithmic_mean_temperature_norm: float = 49.8 * ureg.kelvin):
        """

        Args:
            logarithmic_mean_temperature_operation ():
            heat_flow_operation ():
            logarithmic_mean_temperature_norm ():

        Returns:
            norm_heat_flow_radiator():
        """

        return (heat_flow_operation / (
                    (logarithmic_mean_temperature_operation / logarithmic_mean_temperature_norm) ** self.radiator_heating_exponent))

    def calculate_logarithmic_mean_temperature(self,
                                               supply_temperature: float,
                                               return_temperature:float,
                                               standard_indoor_temperature: float) -> float:
        """

        Args:
            supply_temperature ():
            return_temperature ():
            standard_indoor_temperature ():

        Returns:
            logarithmic_mean_temperature()
        """
        return (supply_temperature - return_temperature) /  \
               (math.log((supply_temperature - standard_indoor_temperature) / (return_temperature - standard_indoor_temperature)))


    def calculate_volume_flow(self, mass_flow: float) -> float:
        """

        Args:
            mass_flow ():
        Returns:
            volume_flow ():
        """
        return (mass_flow / self.density_water).to(ureg.liter / ureg.seconds)

    def calculate_mass_flow(self,
                            heat_flow: float,
                            supply_temperature:float,
                            return_temperature:float) -> float:
        """

        Args:
            supply_temperature ():
            return_temperature ():
            heat_flow ():
        Returns:
            mass_flow ():
        """
        return (heat_flow / (self.specific_heat_capacity * (supply_temperature - return_temperature))).to(ureg.kilogram / ureg.second)



    def load_thermalzone_mapping(self, mapping_json: Path) -> dict:
        """

        Args:
            mapping_json ():A json file with the thermal zones and their usages

        Returns:

        """
        self.logger.info(f"Load thermal mapping from file {mapping_json}.")
        with open(mapping_json, "r") as file:
            json_data = json.load(file)
            # Lesen der Daten aus der JSON-Datei
        space_dict = {}
        i = 1
        for key, value in json_data.items():
            usage_dict = {}
            space_guids_dict = {}
            space_guids = value["space_guids"]
            usage = value["usage"]
            usage_dict["usage"] = usage
            space_guids_dict["space_guids"] = space_guids
            if i not in space_dict:
                space_dict[i] = {}
            space_dict[i].update(space_guids_dict)
            space_dict[i].update(usage_dict)
            i = i + 1
        return space_dict

    def load_simulation_results(self,
                                simulation_file: Path) -> dict:
        """

                Args:
                    simulation_file (): A simulation file with the heat quantities of the considered ifc model in -mat file format
                Returns:
                Gives a dicitonary of the amount of heat divided into the considered thermal zones
                """
        self.logger.info(f"Load simulation result from file {simulation_file}.")
        tsd = TimeSeriesData(simulation_file)
        # Assuming you have already extracted the variable data
        time_column = tsd.index
        # Zeige alle Variablen in der MATLAB-Datei an
        variable_names = tsd.get_variable_names()
        variable_zone_dict = {}
        for variable_name in variable_names:  # multizonePostProcessing.PHeaterSum
            variable = variable_name.split(".")[1]
            # Zonenvariablen
            if variable.find("[") > -1:
                var = variable[:variable.find("[")]
                zone = variable[variable.find("[") + 1:variable.rfind("]")]
                if zone.find(",") > -1:
                    split = zone.split(",")
                    zone = split[0]
                    var = f'{var.lstrip()}_{split[1].lstrip()}'
                if zone not in variable_zone_dict:
                    variable_zone_dict[zone] = {}
                if var not in variable_zone_dict[zone]:
                    variable_zone_dict[zone][var] = {}
                value_list = (tsd[variable_name].values.tolist())
                result_dict = {time_column[i]: value_list[i][0] * 10 ** (-3) for i in range(len(time_column))}
                variable_zone_dict[zone][var] = result_dict
            # Nicht Zonenvariablen

        return variable_zone_dict


    def initialize_node_parameters(self,
                                   graph: nx.DiGraph(),
                                   parameter_key: str ,
                                   filling_parameter: float = 0.0,
                                   operation_point: str = "design_operation_point") -> nx.DiGraph():
        """

        Args:
            graph (): Heating graph
            parameter_key (): key from dictionary components_parameter
            filling_parameter (): If no value is given, an initial value is given
            operation_point (): Current operating point in the system

        Returns:
            returns a graph with initialised parameters of the nodes
        """
        for node, data in graph.nodes(data=True):
            try:
                value = self.components_parameter[parameter_key]["component"][data["component_type"]]
                unit = self.components_parameter[parameter_key]["unit"]
                graph.nodes[node][operation_point][parameter_key] = value * unit
            except KeyError:
                unit = self.components_parameter[parameter_key]["unit"]
                self.logger.warning(f"Component {data['component_type']} not found. Set {parameter_key} value to {filling_parameter}.")
                graph.nodes[node][operation_point][parameter_key] = filling_parameter * unit

        return graph

    def calculate_edge_attributes(self,
                                  graph: nx.DiGraph(),
                                  operation_point: str = "design_operation_point") -> nx.DiGraph():
        # iterative edges
        self.logger.info(f"Load pipe data with material {self.playground.sim_settings.distribution_pipe_material}.")
        for node, data in graph.nodes(data=True):
            successors = list(graph.successors(node))
            for succ in successors:
                mass_flow_out = graph.nodes[succ][operation_point]["mass_flow"]
                volume_flow_out = graph.nodes[succ][operation_point]["volume_flow"]
                heat_flow_out = graph.nodes[succ][operation_point]["heat_flow"]
                graph.edges[node, succ][operation_point]["mass_flow"] = mass_flow_out
                graph.edges[node, succ][operation_point]["volume_flow"] = volume_flow_out
                graph.edges[node, succ][operation_point]["heat_flow"] = heat_flow_out
                calc_inner_diameter = self.calculate_pipe_inner_diameter(mass_flow=mass_flow_out)
                graph.edges[node, succ][operation_point]["calculate_inner_diameter"] = calc_inner_diameter
                inner_diameter, outer_diameter, material, density = self.load_pipe_data(filename=self.playground.sim_settings.distribution_file_path,
                                    sheet_name=self.playground.sim_settings.distribution_pipe_material,
                                    calc_inner_diameter=calc_inner_diameter)
                graph.edges[node, succ][operation_point]["inner_diameter"] = inner_diameter
                graph.edges[node, succ][operation_point]["outer_diameter"] = outer_diameter
                graph.edges[node, succ][operation_point]["material"] = material
                graph.edges[node, succ][operation_point]["density"] = density
                graph.edges[node, succ][operation_point]["material_mass"] = self.calculate_mass_pipe_material(density=density,
                                                                                                              length=graph.edges[node, succ]['length'],
                                                                                                              inner_diameter=inner_diameter,
                                                                                                              outer_diameter=outer_diameter)
                graph.edges[node, succ][operation_point]["pipe_insulation"] = self.calculate_pipe_insulation(outer_diameter)
        return graph


    def iterate_pressure_loss_edges(self, graph: nx.DiGraph(), operation_point: str = "design_operation_point"):
        for node in graph.nodes():
            successors = list(graph.successors(node))
            for succ in successors:
                length = graph.edges[node, succ][operation_point]['length']
                inner_diameter = graph.edges[node, succ][operation_point]['inner_diameter']
                delta_p_friction, pipe_friction_resistance = self.calculate_friction_pressure_loss(
                    inner_diameter=inner_diameter,
                    v_mid=self.maximal_velocity / 2,
                    length=length)
                graph.edges[node, succ]['pipe_friction_resistance'] = pipe_friction_resistance
                graph.edges[node, succ][operation_point]['pressure_loss'] = delta_p_friction
        return graph

    def calculate_reynold(self, inner_diameter: float, mid_velocity: float):
        """
        Args:
            inner_diameter ():
            mid_velocity ():
             * self.rho
        """
        return (mid_velocity * inner_diameter) / self.kinetic_viscosity

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

    def pipe_friction_coefficient_laminar_hagen_poiseuille(self, reynold):
        """

        Args:
            reynold ():
        """
        return 64 / reynold

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
        pressure_drop = pipe_friction_resistance * length
        pressure_drop = pressure_drop.to(ureg.pascal)
        return round(pressure_drop, 4), pipe_friction_resistance

    def calc_pipe_friction_resistance(self,
                                      pipe_friction_coefficient,
                                      inner_diameter,
                                      v_mid):

        pipe_friction_resistance = 0.5 * (
                    pipe_friction_coefficient * self.density_water * (1 / inner_diameter) * v_mid ** 2).to(
            ureg.Pa / ureg.m)
        return round(pipe_friction_resistance, 2)

    def iterate_pressure_loss_fittings_nodes(self,
                                             graph: nx.DiGraph(),
                                             operation_point: str = "design_operation_point") -> nx.DiGraph():
        for node, data in graph.nodes(data=True):
            coefficient_resistance = data[operation_point]["coefficient_resistance"]
            pressure_loss_node = self.calculate_pressure_loss_fittings(coefficient_resistance=coefficient_resistance,
                                                                       mid_velocity=self.maximal_velocity)
            graph.nodes[node][operation_point]["pressure_loss"] = pressure_loss_node
        return graph

    def calculate_pressure_loss_fittings(self, coefficient_resistance: float, mid_velocity: float):
        """
        Druckverluste Einbauten Widerstandsbeiwerts
        Args:
            coefficient_resistance ():
        """
        return (0.5 * self.density_water * coefficient_resistance * mid_velocity ** 2).to(ureg.pascal)


    def calculate_mass_pipe_material(self,
                                     density,
                                     length,
                                     inner_diameter,
                                     outer_diameter
                                     ):
        return density * length * math.pi * (outer_diameter ** 2 - inner_diameter ** 2) / 4



    def calculate_pipe_insulation(self, outer_diameter):
        if outer_diameter <= 22 * ureg.millimeter:
            s = 20 * ureg.millimeter
        elif outer_diameter > 22 * ureg.millimeter and outer_diameter <= 30 * ureg.millimeter:
            s = 30 * ureg.millimeter
        else:
            s = 100 * ureg.millimeter
        return (math.pi / 4) * (s ** 2 - outer_diameter ** 2)


    def initialize_edge_physical_attributes(self,
                                            graph: nx.DiGraph(),
                                            operation_point: str = "design_operation_point") -> nx.DiGraph():
        """
        Add new physical attributes for nodes for the calculation and dimension of the heating system.
        Args:
            graph (): Heating Graph
            operation_point (): Operation Point in the system

        Returns:
            returns a graph with initialised values of the edges
        """
        for edge in graph.edges():
            if operation_point not in graph.edges[edge]:
                graph.edges[edge][operation_point] = {}
            # variables
            graph.edges[edge][operation_point]["pressure_loss"]  = 0.0 * 10 ** 5 * ureg.pascal
            graph.edges[edge][operation_point]["inner_diameter"] = 0.0 * ureg.meter
            graph.edges[edge][operation_point]["calculate_inner_diameter"] = 0.0 * ureg.meter
            graph.edges[edge][operation_point]["outer_diameter"] = 0.0 * ureg.meter
            graph.edges[edge][operation_point]["heat_flow"] = 0.0 * ureg.kilowatt
            graph.edges[edge][operation_point]["mass_flow"] = 0.0 *  (ureg.kilogram / ureg.seconds)
            graph.edges[edge][operation_point]["volume_flow"] = 0.0 * (ureg.meter ** 3 / ureg.seconds)
            graph.edges[edge][operation_point]["pipe_friction_resistance"] = 0.0 *(ureg.Pa / ureg.m)
            graph.edges[edge][operation_point]["pipe_insulation"] = 0.0  * ureg.meter
            graph.edges[edge][operation_point]["density"] = 0.0 * (ureg.kilogram / ureg.meter ** 3)
            # parameter
            graph.edges[edge][operation_point]["material"] = None
            graph.edges[edge][operation_point]["maximal_velocity"] = self.maximal_velocity *( ureg.meter/ureg.seconds)
            graph.edges[edge][operation_point]["length"] = graph.edges[edge]["length"] * ureg.meter
        return graph



    def initialize_node_physical_attributes(self,
                                            graph: nx.DiGraph(),
                                            operation_point: str = "design_operation_point") -> nx.DiGraph():
        """
        Add new physical attributes for nodes for the calculation and dimension of the heating system.
        Variables:
        - max_velocity [m/s]
        - velocity [m/s]
        - heat_flow [kW]
        - mass_flow [kg/s]
        - volume_flow [m^3/s]
        - norm_indoor_temperature [K]
        - pressure_in [Pa]
        - pressure_out [Pa]
        - pressure_loss [Pa]
        - coefficient_resistance [-]
        Parameter:
        Args:
            graph ():
        Returns:
            returns a graph with initialised values of the nodes
        """
        for node, data in graph.nodes(data=True):
            if operation_point not in graph.nodes[node]:
                graph.nodes[node][operation_point] = {}
            # variables
            graph.nodes[node][operation_point]["max_velocity"] = self.maximal_velocity
            graph.nodes[node][operation_point]["mass_flow"] = 0.0 * (ureg.kilogram / ureg.second)
            graph.nodes[node][operation_point]["heat_flow"] = 0.0 * ureg.kilowatt
            graph.nodes[node][operation_point]["volume_flow"] = 0.0 * (ureg.meter ** 3 / ureg.second)
            graph.nodes[node][operation_point]["pressure_in"] = 1.0 * 10 ** 5 * ureg.pascal
            graph.nodes[node][operation_point]["pressure_out"] = 1.0 * 10 ** 5 * ureg.pascal
            graph.nodes[node][operation_point]["pressure_loss"] = 0.0 * 10 ** 5 * ureg.pascal
            # parameter
            graph.nodes[node][operation_point]["head"] = 0.0
            graph.nodes[node][operation_point]["norm_indoor_temperature"] = (22 + 273.15) * ureg.kelvin
            graph.nodes[node][operation_point]["coefficient_resistance"] = 0.0 * ureg.dimensionless
        return graph







    @staticmethod
    def remove_node_attributes(graph: nx.DiGraph(),
                               attributes: list = None) -> nx.DiGraph():
        """
        Remove
        Args:
            graph ():
            attributes ():

        Returns:

        """
        for node, data in graph.nodes(data=True):
            if data["node_type"] in attributes:
                for attr in attributes:
                    if attr in data["node_type"]:
                        data["node_type"] = None
        return graph

    def number_delivery_nodes_each_room(self,
                                        graph: nx.DiGraph(),
                                        component_type: str = "radiator") -> nx.DiGraph():
        """
        Calculates the number of deliveries per room.
        The total heat requirement is then divided between the number of radiators.
        Args:
            component_type (): type of delivery component/system in distribution system (radiator/ underfloor_heating)
            graph (): nx:Graph()
        Returns:
            Update delivery graph with the number of delivery components in each room

        """
        delivery_nodes_counter = {}
        for node, data in graph.nodes(data=True):
            if component_type == data["component_type"]:
                room_id = data["belongs_to_room"][0]
                if room_id in delivery_nodes_counter:
                    delivery_nodes_counter[room_id] += 1
                else:
                    delivery_nodes_counter[room_id] = 1
        for node, data in graph.nodes(data=True):
            if component_type == data["component_type"] :
                for room_id in delivery_nodes_counter:
                    if room_id in data["belongs_to_room"]:
                        data["delivery_number"] = delivery_nodes_counter[room_id]
        return graph




