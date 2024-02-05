import networkx as nx

from bim2sim.tasks.base import ITask
import math
from bim2sim.elements.mapping.units import ureg
import pandas as pd
from pathlib import Path


class ExportLCAHeating(ITask):
    """short docs.

    longs docs.

    Args:
        ...
    Returns:
        ...
    """

    reads = ('calculate_heating_graph_list',)
    final = True



    def __init__(self, playground):
        super().__init__(playground)

    def run(self, calculate_heating_graph_list):

        for calculate_heating_graph in calculate_heating_graph_list:
            excel_file = Path(self.paths.export, f"lca_heating_material_{calculate_heating_graph.graph['temperature_niveau']}.xlsx")
            self.create_bom_edges(graph=calculate_heating_graph,
                                  sheet_name="pipe",
                                  filename=excel_file)
            component_list = self.write_value_list(calculate_heating_graph)
            number_component_duit = self.write_number_component_list(calculate_heating_graph)
            self.create_bom_nodes(filename=Path(excel_file), bom=component_list, sheet_name = 'Werte')
            self.create_bom_nodes(filename=Path(excel_file), bom=number_component_duit, sheet_name='Komponenten')


    def create_bom_nodes(self, filename, bom, sheet_name:str = 'Komponenten' ):
        df_new_sheet = pd.DataFrame.from_dict(bom, orient='index')
        with pd.ExcelWriter(filename, mode='a', engine='openpyxl') as writer:
            # Schreiben Sie das neue Sheet in die Excel-Datei
            df_new_sheet.to_excel(writer, sheet_name=sheet_name)
        # Bestätigung, dass das Sheet hinzugefügt wurde
        self.logger.info(f"The new sheet {filename} has been successfully added to the Excel file.")

    def create_bom_edges(self, graph: nx.DiGraph(),
                         filename,
                         sheet_name,
                         operation_point: str = "design_operation_point"):
        bom_edges = {}  # Stückliste für Kanten (Rohre)
        total_mass = 0  # Gesamtmasse der Kanten (Rohre)
        total_length = 0
        total_flow = 0
        total_dammung = 0
        for u, v in graph.edges():
            length = graph.edges[u, v][operation_point]['length']
            inner_diameter = graph.edges[u, v][operation_point]['inner_diameter']
            outer_diameter = graph.edges[u, v][operation_point]['outer_diameter']
            insulation = graph.edges[u, v][operation_point]['pipe_insulation']
            density = graph.edges[u, v][operation_point]['density']
            material = graph.edges[u, v][operation_point]['material']
            m_flow = graph.nodes[u][operation_point]['mass_flow']
            # Berechne die Materialmenge basierend auf den Kantenattributen (Beispielberechnung)
            material_quantity = ((length * (math.pi / 4) * (
                        outer_diameter ** 2 - inner_diameter ** 2)) * density).to_base_units()
            # material_dammung = ((length *(math.pi/4) * (dammung**2 - outer_diameter**2)) *  55.0 *(ureg.kg/ureg.meter**3)).to_base_units()
            material_dammung = ((length * insulation * 55.0 * (ureg.kg / ureg.meter ** 3))).to_base_units()
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

    def write_value_list(self,
                         graph: nx.DiGraph(),
                         operation_point: str = "design_operation_point") -> dict:
        bom = {}
        for node, data in graph.nodes(data=True):
            if node not in bom:
                bom[node] = {}
            if data["component_type"] == self.playground.sim_settings.distribution_system_type or data["component_type"]=="pump":
                if "component_type" in data:
                    bom[node]["component_type"] = data["component_type"]
                if "material" in data:
                    bom[node]["material"] = data["material"]
                if "model" in data:
                    bom[node]["model"] = data["model"]
                if "material_mass" in data:
                    bom[node]["material_mass"] = data["material_mass"]
                if "length" in data:
                    bom[node]["length"] = data["length"]
                if "norm_heat_flow_per_length" in data:
                    bom[node]["norm_heat_flow_per_length"] = data["norm_heat_flow_per_length"]
                if operation_point in data:
                    if "heat_flow" in data[operation_point]:
                        bom[node]["heat_flow"] = data[operation_point]["heat_flow"]
                    if "norm_indoor_temperature" in data[operation_point]:
                        bom[node]["norm_indoor_temperature"] = data[operation_point]["norm_indoor_temperature"]
                    if "power" in data[operation_point]:
                        bom[node]["power"] = data[operation_point]["power"]
                    if "head" in data[operation_point]:
                        bom[node]["head"] = data[operation_point]["head"]

        return bom

    def  write_number_component_list(self, graph: nx.DiGraph()) -> dict:
        bom = {}
        for node,data  in graph.nodes(data=True):
            component = data["component_type"]
            if component not in bom:
                bom[component] = 1
            else:
                bom[component] = bom[component] + 1
        return bom