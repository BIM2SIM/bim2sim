import networkx as nx
import matplotlib.pyplot as plt

# create demo graph
G = nx.DiGraph()
a = 'a'
b = 'b'
c = 'c'
d = 'd'
e = 'e'
f = 'f'
g = 'g'
h = 'h'
x = 'x'
y = 'y'
G.add_edge(a, b)
G.add_edge(b, c)
G.add_edge(d, e)
G.add_edge(e, f)
G.add_edge(c, h)
G.add_node(g)
G.add_node(x)
G.add_node(y)
G = nx.contracted_nodes(G, a, y)
G = nx.contracted_nodes(G, g, a)
G = nx.contracted_nodes(G, g, d)
G = nx.contracted_nodes(G, g, h)


# G = nx.contracted_nodes(G, c, d)

# print(G.has_node(x))


# print(value['contraction'])
# cycles=nx.find_cycle(G)
def get_contractions(node):
    """
    Returns a list of contracted nodes for the passed node.
    :param node:
    :return:
    """
    node = G.node[node]
    inner_nodes = []
    for contraction in node['contraction'].keys():
        inner_nodes.append(contraction)
    return inner_nodes
# print(get_contractions(g))

# cycles = nx.cycle_basis(G.to_undirected())
# for cycle in cycles:
#     print(cycle)
#
nx.draw(G, with_labels=True)
plt.draw()
plt.show()