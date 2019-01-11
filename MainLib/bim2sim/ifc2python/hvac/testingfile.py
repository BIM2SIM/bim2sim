import networkx as nx
import matplotlib.pyplot as plt

from bim2sim.ifc2python.hvac.logic.pipestrand import PipeStrand

# create demo graph

# def create_pipe_strands(graph):
#
#     def get_keys(dict, keys_list):
#         if isinstance(dict, type(dict)):
#             keys_list += dict.keys()
#             test = dict.values()
#             map(lambda x: get_keys(x, keys_list), dict.values())
#         # elif isinstance(dl, type(list)):
#         #     map(lambda x: get_keys(x, keys_list), dl)
#     dict = nx.get_node_attributes(graph,'contraction')
#     keys_list = []
#     get_keys(dict, keys_list)
#     print(keys_list)

G = nx.DiGraph()
G.add_edge('a',15)
G.add_edge(1,2)
G.add_edge(6,20)
G.add_edge(3,4)
G.add_edge(4,5)
G.add_edge(20,21)
G.add_edge(21,20)
G.add_edge(11,12)
G.add_edge(5,6)
G.add_edge(2,7)
G.add_edge(21,22)
G.add_edge(7,8)
G.add_edge(8,9)
G.add_edge(2,3)
G.add_edge(3,2)
G.add_edge(22,23)
G.add_edge(23,24)
G.add_edge(9,10)
G.add_edge(10,11)
G.add_edge(9,13)
G.add_edge(13,'a')
# for node in G.nodes():
#     print('node: '+str(node) +' neighbor: '+ str(list(nx.neighbors(G, node))))
# nx.draw(G, with_labels=True)
# plt.draw()
# plt.show()
nx.set_node_attributes(G, [], 'contracted_nodes')

# merge directed nodes
outdeg = G.out_degree()
indeg = G.in_degree()
outdeg_1_nodes = [n for (n, deg) in outdeg if deg == 1]
indeg_1_nodes = [n for (n, deg) in indeg if deg == 1]
reducable_nodes = list(set(outdeg_1_nodes).intersection(indeg_1_nodes))
for reducable_node in reducable_nodes:
    neighbor_node = list(nx.neighbors(G, reducable_node))[0]
    if neighbor_node in reducable_nodes:
        G.node[neighbor_node]['contracted_nodes'] = G.node[reducable_node][
            'contracted_nodes'] + [reducable_node]
        if reducable_node not in G.node[neighbor_node]['contracted_nodes']:
            G.node[neighbor_node]['contracted_nodes'].append(reducable_node)
        G = nx.contracted_nodes(G, neighbor_node, reducable_node)

# merge bidirectional nodes
outdeg_2_nodes = [n for (n, deg) in outdeg if deg == 2]
indeg_2_nodes = [n for (n, deg) in indeg if deg == 2]
reducable_nodes = list(set(outdeg_2_nodes).intersection(indeg_2_nodes))
neighbor_2_nodes = []
for node in G.nodes():
    if len(list(nx.all_neighbors(G,node))) == 2:
        neighbor_2_nodes.append(node)
reducable_nodes = list(set(reducable_nodes).intersection(neighbor_2_nodes))
print(reducable_nodes)
print('Reduced:')
# for node in G.nodes():
#     print('node: '+str(node) +' neighbor: '+ str(list(nx.neighbors(G, node))))


nx.draw(G, with_labels=True)
plt.draw()
plt.show()
print('done')
