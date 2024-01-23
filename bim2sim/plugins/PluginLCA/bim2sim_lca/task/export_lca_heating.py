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

    reads = ('calculate_heating_graph',)
    final = True



    def __init__(self, playground):
        super().__init__(playground)

    def run(self, calculate_heating_graph):
        self.create_bom_edges(graph=calculate_heating_graph,
                              sheet_name="pipe",
                              filename=Path(self.paths.export, "lca_heating_material.xlsx"))
        component_list = self.write_component_list(calculate_heating_graph)
        print(component_list)
        self.create_bom_nodes(filename=Path(self.paths.export, "lca_heating_material.xlsx"), bom=component_list)


    def create_bom_nodes(self, filename, bom):
        df_new_sheet = pd.DataFrame.from_dict(bom, orient='index')
        with pd.ExcelWriter(filename, mode='a', engine='openpyxl') as writer:
            # Schreiben Sie das neue Sheet in die Excel-Datei
            df_new_sheet.to_excel(writer, sheet_name='Komponenten')
        print(df_new_sheet)
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

    def  write_component_list(self, graph: nx.DiGraph()) -> dict:
        bom = {}  # Stückliste (Komponente: Materialmenge)
        for node, data in graph.nodes(data=True):

            if "pump" == data["component_type"]:
                pass
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
        """for node,data  in G.nodes(data=True):
            print(data)
            component_type = G.nodes[node].get('type')
            for comp in component_type:
                if comp in bom:
                    bom[comp] += 1  # Erhöhe die Materialmenge für die Komponente um 1
                else:
                    bom[comp] = 1  # Initialisiere die Materialmenge für die Komponente mit 1"""

        return bom