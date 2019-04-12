import networkx as nx
import matplotlib.pyplot as plt

# create demo graph
G = nx.DiGraph()
a = 1
b = 2
c = 3
d = 4
e = 5
f = 6
g = 7
h = 8
G.add_edge(a, b)
G.add_edge(b, c)
G.add_edge(d, e)
G.add_edge(e, f)
G.add_node(g)
G.add_edge(d,h)
G = nx.contracted_nodes(G, a, f)
G = nx.contracted_nodes(G, a, g)
G = nx.contracted_nodes(G, c, d)


# print(G.has_node(x))

# print(get_contractions(G.node[a]))
# print(value['contraction'])
# cycles=nx.find_cycle(G)

# cycles = nx.cycle_basis(G.to_undirected())
# for cycle in cycles:
#     print(cycle)
#
nx.draw(G, with_labels=True)
plt.draw()
plt.show()