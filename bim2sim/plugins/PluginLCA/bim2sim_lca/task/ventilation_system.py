import bim2sim
import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.lines import Line2D
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


class DesignVentilationSystem(ITask):
    """Design of the LCA

    Annahmen:
    Inputs: IFC Modell, Räume,

    Args:
        instances: bim2sim elements
    Returns:
        instances: bim2sim
    """
    reads = ('graph_ventilation_duct_length_supply_air',
             'pressure_loss_supply_air',
             'database_rooms_supply_air',
             'database_distribution_network_supply_air',
             'graph_ventilation_duct_length_exhaust_air',
             'pressure_loss_exhaust_air',
             'database_rooms_exhaust_air',
             'database_distribution_network_exhaust_air')
    touches = ()

    def run(self,
            graph_ventilation_duct_length_supply_air,
            pressure_loss_supply_air,
            database_rooms_supply_air,
            database_distribution_network_supply_air,
            graph_ventilation_duct_length_exhaust_air,
            pressure_loss_exhaust_air,
            database_rooms_exhaust_air,
            database_distribution_network_exhaust_air
            ):
        print(graph_ventilation_duct_length_supply_air)

        self.logger.info("Plott 3D Graph")
        self.plot_3d_graphs(graph_ventilation_duct_length_supply_air, graph_ventilation_duct_length_exhaust_air)

    def plot_3d_graphs(self, graph_ventilation_duct_length_supply_air, graph_ventilation_duct_length_exhaust_air):
        # Initialize the 3D plot
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')

        # Function to draw a graph
        def draw_graph(graph, color_nodes, color_edges):
            pos = {node: (node[0], node[1], node[2]) for node in graph.nodes()}
            for node, weight in nx.get_node_attributes(graph, 'weight').items():
                color = color_nodes if weight > 0 else 'black'
                ax.scatter(*node, color=color,
                           label='_nolegend_')  # '_nolegend_' entfernt doppelte Einträge in der Legende
            for edge in graph.edges():
                start, end = edge
                x_start, y_start, z_start = pos[start]
                x_end, y_end, z_end = pos[end]
                ax.plot([x_start, x_end], [y_start, y_end], [z_start, z_end], color=color_edges, label='_nolegend_')

        # Draw both graphs
        draw_graph(graph_ventilation_duct_length_supply_air, 'blue', 'blue')  # Colors for the first graph
        draw_graph(graph_ventilation_duct_length_exhaust_air, 'orange', 'orange')  # Colors for the second graph

        # Axis labels and title
        ax.set_xlabel('X-Axis [m]')
        ax.set_ylabel('Y-Axis [m]')
        ax.set_zlabel('Z-Axis [m]')
        ax.set_title("3D Graph of Ventilation Ducts")

        # Create custom legends
        legend_elements = [
            Line2D([0], [0], marker='o', color='w', markerfacecolor='blue', markersize=10, label='Supply Air'),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='orange', markersize=10, label='Exhaust Air')]
        ax.legend(handles=legend_elements)

        plt.show()