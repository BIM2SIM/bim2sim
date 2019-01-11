import networkx as nx
import matplotlib.pyplot as plt

from bim2sim.ifc2python.hvac.logic.pipestrand import PipeStrand

# create demo graph
G = nx.DiGraph()
G.add_edge('a', 15)
G.add_edge(1, 2)
G.add_edge(6, 20)
G.add_edge(3, 4)
G.add_edge(4, 5)
G.add_edge(20, 21)
G.add_edge(21, 20)
G.add_edge(11, 12)
G.add_edge(5, 6)
G.add_edge(2, 7)
G.add_edge(21, 22)
G.add_edge(7, 8)
G.add_edge(8, 9)
G.add_edge(2, 3)
G.add_edge(3, 2)
G.add_edge(22, 23)
G.add_edge(23, 24)
G.add_edge(9, 10)
G.add_edge(10, 11)
G.add_edge(9, 13)
G.add_edge(13, 'a')
G.add_edge(12,25)
G.add_edge(15,25)
G.add_edge(25,1)


nx.set_node_attributes(G, [], 'contracted_nodes')
for node in G.nodes():
    nodes_nb = list(set(nx.all_neighbors(G, node)) - set(
        G.node[node]['contracted_nodes']) - {node})
    if len(nodes_nb) == 2:  # add if is connection_element
        for node_nb in nodes_nb:
            nodes_nb_nb = list(set(nx.all_neighbors(G, node_nb)) - set(
                G.node[node_nb]['contracted_nodes']) - {node_nb})
            if len(nodes_nb_nb) <= 2:  # add if is connection_element
                G.node[node_nb]['contracted_nodes'] = G.node[node_nb][
                                                          'contracted_nodes'] \
                                                      + [node]
                print(G.node[node]['contracted_nodes'])
                G = nx.contracted_nodes(G, node_nb, node)  # merge node into
                break


nx.draw(G, with_labels=True)
plt.draw()
plt.show()
