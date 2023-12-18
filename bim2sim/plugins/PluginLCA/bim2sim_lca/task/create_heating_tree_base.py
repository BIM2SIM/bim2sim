from bim2sim.tasks.base import ITask

import networkx as nx
from pathlib import Path



class CreateHeatingTreeBase(ITask):
    """short docs.

    longs docs.

    Args:
        ...
    Returns:
        ...
    """

    reads = ('ifc_files', 'elements')
    touches = ('...', )
    final = True

    def run(self,G , elements):
        self.create_heating_circle(G, elements)
        return elements,


    def create_heating_circle(self,
                              G: nx.Graph(),
                              grid_type: str,
                              type_delivery: list = ["window"],
                              one_pump_flag: bool = False):

        """
        Erstelle Endpunkte

        """

        delivery_forward_nodes, delivery_backward_nodes, forward_backward_edge = self.get_delivery_nodes(G=G,
                                                                                                         type_delivery=type_delivery)
        """
        Erstelle Anfangspunkte und verbinde mit Graph

        """
        nodes_forward = ["center_wall_forward",
                         "snapped_nodes",
                         "window",
                         "radiator_forward",
                         "Verteiler",
                         "door"]
        subgraph_nodes_forward = [node for node, data in G.nodes(data=True) if set(data["type"]) & set(nodes_forward)]
        forward_graph = G.subgraph(subgraph_nodes_forward)
        self.check_graph(G=forward_graph, type="forward_graph")
        forward_graph, source_forward_list = self.get_source_nodes(G=forward_graph,
                                                                   points=self.source_data,
                                                                   floor_dict=self.building_data,
                                                                   type="Verteiler",
                                                                   connect_type_edges=["center_wall_forward"],
                                                                   type_connect_node=["center_wall_forward"],
                                                                   neighbor_nodes_collision_type=[
                                                                       "center_wall_forward"],
                                                                   edge_snapped_node_type="center_wall_forward",
                                                                   remove_type_node=["center_wall_forward"],
                                                                   grid_type="forward",
                                                                   new_edge_type="center_wall_forward",
                                                                   same_type_flag=True,
                                                                   element_belongs_to_flag=False)
        self.save_networkx_json(G=forward_graph,
                                type_grid=f"delivery_points",
                                file=Path(self.working_path, self.ifc_model,
                                          f"heating_circle_floor_delivery_points.json"))
        #self.visulize_networkx(G=forward_graph, type_grid="sources")
        # plt.show()
        self.check_graph(G=forward_graph, type="forward_graph")
        ff_graph_list = []
        # pro Etage
        for i, floor in enumerate(self.building_data):
            print(f"Calculate steiner tree {floor}_{i}")
            # Pro Delivery Point pro Etage
            element_nodes_forward = []
            element_nodes_backward = []
            for delivery_node in delivery_forward_nodes:
                if forward_graph.nodes[delivery_node]["floor_belongs_to"] == floor:
                    element_nodes_forward.append(delivery_node)
            for source_node in source_forward_list:
                if forward_graph.nodes[source_node]["floor_belongs_to"] == floor:
                    element_nodes_forward.append(source_node)

            f_st, forward_total_length = self.steiner_tree(graph=forward_graph,
                                                           term_points=element_nodes_forward,
                                                           grid_type="forward")

            if forward_total_length != 0 and forward_total_length is not None:
                end_node = ["radiator_forward"]
                end_nodes = [n for n, attr in f_st.nodes(data=True) if
                             any(t in attr.get("type", []) for t in end_node)]
                f_st = self.reduce_path_nodes(G=f_st,
                                              color="red",
                                              start_nodes=[source_forward_list[i]],
                                              end_nodes=end_nodes)
                self.save_networkx_json(G=f_st,
                                        type_grid=f"heating_circle_floor_{source_forward_list[i]}",
                                        file=Path(self.working_path, self.ifc_model,
                                                  f"heating_circle_floor_{source_forward_list[i]}.json"))
                #self.visulize_networkx(G=forward_graph, type_grid="Building")
                #self.visulize_networkx(G=f_st, title="Steinerbaumpfad von den Start- zu den Endknoten",
                #                       type_grid="Vorlaufkreislauf")
                f_st = self.directed_graph(G=f_st, source_nodes=source_forward_list[i], grid_type=grid_type)
                self.visulize_networkx(G=f_st, title="Gerichterer Graph des Steinerbaumpfad",
                                       type_grid="Vorlaufkreislauf")
                # plt.show()

                self.check_directed_graph(G=f_st, type_graph=grid_type)
                ff_graph_list.append(f_st)

        f_st = self.add_graphs(graph_list=ff_graph_list)
        # Löscht überflüssige Knoten attribute
        f_st = self.remove_attributes(G=f_st, attributes=["center_wall_forward", "snapped_nodes"])
        # Add rise tube

        f_st = self.add_rise_tube(G=f_st)
        self.visulize_networkx(G=f_st, title="Vollständiger Vorkreislauf des Heizungsystems",
                               type_grid="Vorlaufkreislauf")
        self.check_graph(G=f_st, type="forward")
        # Richte Forward Graphen
        f_st = self.directed_graph(G=f_st, source_nodes=source_forward_list[0], grid_type=grid_type)
        f_st = self.update_graph(G=f_st, grid_type="forward", color="red")
        f_st = self.index_strang(G=f_st)
        # Erstelle Backward Circle
        b_st = self.create_backward(G=f_st, grid_type="backward", offset=1.0, color="blue")

        # Füge Komponenten hinzu
        composed_graph = nx.disjoint_union(f_st, b_st)
        self.visulize_networkx(G=composed_graph, title="Vollständiger Vor- und Rückkreislauf des Heizungsystems",
                               type_grid="Vorlaufkreislauf")
        composed_graph = self.connect_sources(G=composed_graph,
                                              type_edge="source",
                                              grid_type="connection",
                                              color="orange")
        composed_graph = self.connect_forward_backward(G=composed_graph,
                                                       color="orange",
                                                       edge_type="radiator",
                                                       grid_type="connection",
                                                       type_delivery=["radiator_forward", "radiator_backward"])

        self.visulize_networkx(G=composed_graph, title="Geschlossener Heizkreislauf des Heizungsystems",
                               type_grid="Vorlaufkreislauf")
        # composed_graph = f_st

        composed_graph = self.add_component_nodes(G=composed_graph, one_pump_flag=one_pump_flag)

        self.visulize_networkx(G=composed_graph, title="Geschlossener Heizkreislauf mit Komponenten des Heizungsystems",
                               type_grid="Vorlaufkreislauf")

        # self.visulize_networkx(G=composed_graph, type_grid="Kreislauf")
        self.save_networkx_json(G=composed_graph, file=self.network_heating_json, type_grid="heating_circle")
        # plt.show()

        return composed_graph



    def steiner_tree(self, graph: nx.Graph(), term_points, grid_type: str = "forward", color: str = "red"):
        """
        Args:
            graph ():
            circulation_direction ():
            floor_height ():
        # term_points = sorted([n for n, data in graph.nodes(data=True) if data["type"] in {"radiator", "source"} ])
        Returns:
        """
        steinerbaum = nx.algorithms.approximation.steinertree.steiner_tree(G=graph,
                                                                           weight="length",
                                                                           terminal_nodes=term_points,
                                                                           method="kou")
        total_length = sum([edge[2]['length'] for edge in steinerbaum.edges(data=True)])
        print(f"Steiner Tree: {grid_type} {total_length}")
        steinerbaum.graph["grid_type"] = grid_type
        # Farbe der Kanten ändern
        edge_attributes = {(u, v): {"color": color} for u, v in graph.edges()}
        nx.set_edge_attributes(graph, edge_attributes)

        return steinerbaum, total_length

    def get_source_nodes(self,
                         G: nx.Graph(),
                         points,
                         floor_dict: dict,
                         type,
                         connect_type_edges: list,
                         type_connect_node: list,
                         neighbor_nodes_collision_type: list,
                         edge_snapped_node_type: str,
                         remove_type_node: list,
                         grid_type: str,
                         new_edge_type: str,
                         same_type_flag: bool = True,
                         element_belongs_to_flag: bool = False
                         ):
        """
        # Source Points
        # start_point = ((4.040, 5.990, 0), (4.040, 5.990, 2.7))
        Args:
            G ():
            points ():
            delivery_forward_points ():
        Returns:
        """
        # Pro Etage Source Knoten definieren
        print("Add Source Nodes")
        source_list = []
        source_dict = self.define_source_node_per_floor(floor_dict=floor_dict,
                                                        color="green",
                                                        type_node=type,
                                                        start_source_point=points)
        G = G.copy()
        # Erstellen der Source Knoten

        for floor in source_dict:
            pos = source_dict[floor]["pos"]
            color = source_dict[floor]["color"]
            type = source_dict[floor]["type_node"]
            element = source_dict[floor]["type_node"]
            G, source_node = self.create_nodes(G=G,
                                               points=pos,
                                               color="red",
                                               grid_type=grid_type,
                                               type_node=type,
                                               element=element,
                                               belongs_to=floor,
                                               direction="y",
                                               update_node=True,
                                               floor_belongs_to=floor)
            source_list.append(source_node)

        G, nodes = self.connect_nodes_with_grid(  # General
            G=G,
            node_list=source_list,
            color="grey",
            # filter_edges
            all_edges_flag=False,
            all_edges_floor_flag=False,
            same_type_flag=same_type_flag,
            belongs_to_floor=None,
            element_belongs_to_flag=element_belongs_to_flag,
            connect_type_edges=connect_type_edges,
            # nearest_edges
            top_z_flag=False,
            bottom_z_flag=False,
            pos_x_flag=True,
            neg_x_flag=True,
            pos_y_flag=True,
            neg_y_flag=True,
            tol_value=0.0,
            # create_snapped_nodes
            update_node=True,
            # check_collision
            disjoint_flag=False,
            intersects_flag=True,
            within_flag=False,
            col_tolerance=0.1,
            collision_type_node=["space"],
            collision_flag=False,
            # check_neighbour_nodes_collision
            type_node=type_connect_node,
            no_neighbour_collision_flag=False,
            neighbor_nodes_collision_type=neighbor_nodes_collision_type,
            # create_edge_snapped_nodes
            edge_snapped_node_type=edge_snapped_node_type,
            remove_type_node=remove_type_node,
            grid_type=grid_type,
            new_edge_type=new_edge_type,
            create_snapped_edge_flag=True)
        self.check_graph(G=G, type=type)
        return G, source_list



    def check_graph(self, G, type):
        if nx.is_connected(G) is True:
            print(f"{Fore.BLACK + Back.GREEN} {type} Graph is connected.")
            return G
        else:
            print(f"{Fore.BLACK + Back.RED} {type} Graph is not connected.")
            GeometryBuildingsNetworkx.visulize_networkx(G=G,
                                                        type_grid=type)
            for node in G.nodes():
                if nx.is_isolate(G, node) is True:
                    print("node", node, "is not connected.")
                    print(f'{G.nodes[node]["pos"]} with type {G.nodes[node]["type"]}')
            # Bestimme die verbundenen Komponenten
            components = list(nx.connected_components(G))
            # Gib die nicht miteinander verbundenen Komponenten aus
            print("Not Conntected Components")
            G = self.kit_grid(G=G)
            if nx.is_connected(G) is True:
                print(f"{Fore.BLACK + Back.GREEN} {type} Graph is connected.")
                GeometryBuildingsNetworkx.visulize_networkx(G=G, type_grid=type)
                # plt.show()
                return G
            else:
                print(f"{Fore.BLACK + Back.RED} {type} Graph is not connected.")
                GeometryBuildingsNetworkx.visulize_networkx(G=G, type_grid=type)
                plt.show()
                exit(1)