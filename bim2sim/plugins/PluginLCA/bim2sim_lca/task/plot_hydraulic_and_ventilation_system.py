import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import json
import networkx as nx


from bim2sim.tasks.base import ITask




class PlotHydraulicVentilationGraphs(ITask):
    """Exports a plot including the hydraulic and ventilation system"""

    reads = ()
    touches = ()

    def run(self):

        z_values_ventilation = [-0.3, 2.7, 5.7, 8.7]
        z_values_hydraulic = [-3.0, 0.0, 3.0, 6.0]

        self.load_graphs(z_values_ventilation, z_values_hydraulic)

        self.plot_3d_graph_building(self.floor_supply_graphs, self.floor_exhaust_graphs, self.shaft_supply_graph,
                                    self.shaft_exhaust_graph, self.heating_graph)

        for i in range(len(z_values_hydraulic)):
            self.plot_3d_graph_floor(self.floor_supply_graphs[i], self.floor_exhaust_graphs[i],
                                     self.floor_heating_graphs[i], z_values_hydraulic[i])



    def load_graphs(self, z_values_ventilation, z_values_hydraulic):
        self.floor_supply_graphs = []
        self.floor_exhaust_graphs = []
        self.floor_heating_graphs = []

        for z_value in z_values_ventilation:
            filepath_supply = self.paths.export / "ventilation system" / "supply air" / f"supply_air_floor_Z_{z_value}.json"
            filepath_exhaust = self.paths.export / "ventilation system" / "exhaust air" / f"exhaust_air_floor_Z_{z_value}.json"

            with open(filepath_supply, "r") as file:
                json_data = json.load(file)
                self.floor_supply_graphs.append(nx.node_link_graph(json_data))

            with open(filepath_exhaust, "r") as file:
                json_data = json.load(file)
                self.floor_exhaust_graphs.append(nx.node_link_graph(json_data))

        for z_value in z_values_hydraulic:
            filepath_hydraulic = self.paths.export / "hydraulic system" / f"heating_circle_floor_Z_{z_value}.json"

            with open(filepath_hydraulic, "r") as file:
                json_data = json.load(file)
                self.floor_heating_graphs.append(nx.node_link_graph(json_data))

        filepath_supply_shaft = self.paths.export / "ventilation system" / "supply air" / "supply_air_shaft.json"
        filepath_exhaust_shaft = self.paths.export / "ventilation system" / "exhaust air" / "exhaust_air_shaft.json"
        filepath_heating_circle = self.paths.export / "hydraulic system" / "heating_circle.json"

        with open(filepath_supply_shaft, "r") as file:
            json_data = json.load(file)
            self.shaft_supply_graph = nx.node_link_graph(json_data)

        with open(filepath_exhaust_shaft, "r") as file:
            json_data = json.load(file)
            self.shaft_exhaust_graph = nx.node_link_graph(json_data)

        with open(filepath_heating_circle, "r") as file:
            json_data = json.load(file)
            self.heating_graph = nx.node_link_graph(json_data)



    def plot_3d_graph_floor(self, graph_ventilation_supply_air, graph_ventilation_exhaust_air,
                            graph_hydraulic_heating_circle, floor):
        # Initialize the 3D plot
        fig = plt.figure(figsize=(10, 10))
        ax = fig.add_subplot(111, projection='3d')

        # Draw both graphs
        self.draw_ventilation_graph(ax, graph_ventilation_supply_air, 'blue', 'blue')
        self.draw_ventilation_graph(ax, graph_ventilation_exhaust_air, 'orange', 'orange')
        self.draw_hydraulic_graph(ax, graph_hydraulic_heating_circle, 'red', 'red')

        # Axis labels and title
        ax.set_xlabel('X-Achse in m')
        ax.set_ylabel('Y-Achse in m')
        ax.set_zlabel('Z-Achse in m')
        ax.set_title("Hydraulik + Lüftungssystem Gebäude")
        # Create custom legends
        legend_elements = [
            Line2D([0], [0], marker='o', color='w', markerfacecolor='blue', markersize=10, label='Zuluft'),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='orange', markersize=10, label='Abluft'),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='red', markersize=10, label='Radiator')]
        ax.legend(handles=legend_elements)
        plt.axis('equal')

        directory_path = self.paths.export / 'system plots'
        directory_path.mkdir(parents=True, exist_ok=True)

        filepath = directory_path / f"system_floor_Z_{floor}.png"
        plt.savefig(filepath)

        #plt.show()


    def plot_3d_graph_building(self, graph_list_ventilation_supply_air, graph_list_ventilation_exhaust_air,
                               graph_shaft_ventilation_supply_air, graph_shaft_ventilation_exhaust_air,
                               graph_hydraulic_heating_circle):
        # Initialize the 3D plot
        fig = plt.figure(figsize=(10, 10))
        ax = fig.add_subplot(111, projection='3d')

        # Draw both graphs
        for graph in graph_list_ventilation_supply_air:
            self.draw_ventilation_graph(ax, graph, 'blue', 'blue')  # Colors for the first graph
        for graph in graph_list_ventilation_exhaust_air:
            self.draw_ventilation_graph(ax, graph, 'orange', 'orange')  # Colors for the second graph
        self.draw_ventilation_graph(ax, graph_shaft_ventilation_supply_air, 'green', 'green')
        self.draw_ventilation_graph(ax, graph_shaft_ventilation_exhaust_air, 'green', 'green')

        self.draw_hydraulic_graph(ax, graph_hydraulic_heating_circle, 'red', 'red')  # Colors for the second graph

        # Axis labels and title
        ax.set_xlabel('X-Achse in m')
        ax.set_ylabel('Y-Achse in m')
        ax.set_zlabel('Z-Achse in m')
        ax.set_title("Hydraulik + Lüftungssystem Gebäude")
        # Create custom legends
        legend_elements = [
            Line2D([0], [0], marker='o', color='w', markerfacecolor='blue', markersize=10, label='Zuluft'),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='orange', markersize=10, label='Abluft'),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='red', markersize=10, label='Radiator')]
        ax.legend(handles=legend_elements)
        plt.axis('equal')

        directory_path = self.paths.export / 'system plots'
        directory_path.mkdir(parents=True, exist_ok=True)

        filepath = directory_path / f"system.png"
        plt.savefig(filepath)

        #plt.show()



    # Function to draw a graph
    def draw_ventilation_graph(self, ax, graph, color_nodes, color_edges):
        pos = {node: (node[0], node[1], node[2]) for node in graph.nodes()}
        for node, node_color in nx.get_node_attributes(graph, 'color').items():
            # Modified to draw nodes with weight > 0 in specified color, otherwise no color or gray
            if node_color == "green":
                color = "green"
            elif node_color == "red":
                color = None
            else:
                color = color_nodes
            if color:  # Draw only if color is specified (nodes with weight > 0 or if changed to 'gray')
                ax.scatter(*node, color=color, label='_nolegend_')
        for edge in graph.edges():
            start, end = edge
            x_start, y_start, z_start = pos[start]
            x_end, y_end, z_end = pos[end]
            ax.plot([x_start, x_end], [y_start, y_end], [z_start, z_end], color=color_edges, label='_nolegend_')



    # Function to draw a graph
    def draw_hydraulic_graph(self, ax, graph, color_nodes, color_edges):
        pos = {node[0]: (node[1]['pos'][0], node[1]['pos'][1], node[1]['pos'][2]) for node in graph.nodes(data=True)}
        for node in graph.nodes(data=True):
            node_pos = (node[1]['pos'][0], node[1]['pos'][1], node[1]['pos'][2])
            # Modified to draw nodes with weight > 0 in specified color, otherwise no color or gray
            if "radiator_forward" in node[1]['type']:
                color = color_nodes
            elif "Verteiler" in node[1]['type']:
                color = "green"
            else:
                color = None  # Change to 'gray' if you want to visualize these nodes without significant color
            if color:  # Draw only if color is specified (nodes with weight > 0 or if changed to 'gray')
                ax.scatter(*node_pos, color=color, label='_nolegend_')
        for edge in graph.edges():
            start, end = edge
            x_start, y_start, z_start = pos[start]
            x_end, y_end, z_end = pos[end]
            ax.plot([x_start, x_end], [y_start, y_end], [z_start, z_end], color=color_edges, label='_nolegend_')


