from pint import Quantity
import matplotlib.pyplot as plt
import numpy as np
import networkx as nx


def arrow3D(ax, x, y, z, dx, dy, dz, length, arrowstyle="-|>", color="black"):
    """

    Args:
        ax ():
        x ():
        y ():
        z ():
        dx ():
        dy ():
        dz ():
        length ():
        arrowstyle ():
        color ():
    """
    if length != 0:
        arrow = 0.1 / length
    else:
        arrow = 0.1 / 0.0001

    if isinstance(arrow, Quantity):
        arrow = arrow.magnitude
    ax.quiver(x, y, z, dx, dy, dz, color=color, arrow_length_ratio=arrow)


def visulize_networkx(G,
                      type_grid,
                      title: str = None, ):
    """
    [[[0.2 4.2 0.2]
        [0.2 0.2 0.2]]
    Args:
        G ():

    """

    # node_xyz = np.array(sorted(nx.get_node_attributes(G, "pos").values()))
    fig = plt.figure()
    ax = fig.add_subplot(111, projection="3d")
    node_xyz = np.array(sorted(nx.get_node_attributes(G, "pos").values(), key=lambda x: (x[0], x[1], x[2])))
    node_colors = nx.get_node_attributes(G, "color")
    node_colors_list = [node_colors[node] for node in G.nodes()]
    # ax.scatter(*node_xyz.T, s=50, ec="w")
    # ax.scatter(*node_xyz.T, s=50, ec="w", c=node_colors_list)
    used_labels = set()
    for node, data in G.nodes(data=True):
        pos = np.array(data["pos"])
        color = data["color"]
        s = 50
        if set(["Verteiler", "radiator_forward"]) & set(data["node_type"]):
            label = set(["Verteiler", "radiator_forward"]) & set(data["node_type"])
            label = list(label)[0]
            s = 50
        else:
            s = 10
            label = None
        if label not in used_labels:
            used_labels.add(label)
            ax.scatter(*pos, s=s, ec="w", c=color, label=label)
        else:
            ax.scatter(*pos, s=s, ec="w", c=color)

    if G.is_directed():
        for u, v in G.edges():
            edge = np.array([(G.nodes[u]['pos'], G.nodes[v]['pos'])])
            direction = edge[0][1] - edge[0][0]
            # ax.quiver(*edge[0][0], *direction, color=G.edges[u, v]['color'])
            length = G.edges[u, v]['length']

            arrow3D(ax, *edge[0][0], *direction, arrowstyle="-|>",
                                              color=G.edges[u, v]['color'],
                                              length=length)
    else:
        for u, v in G.edges():
            edge = np.array([(G.nodes[u]['pos'], G.nodes[v]['pos'])])
            ax.plot(*edge.T, color=G.edges[u, v]['color'])
            # ax.plot(*edge.T, color="red")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_zlabel("z")
    ax.set_xlim(0, 43)
    # Achsenlimits festlegen
    ax.set_xlim(node_xyz[:, 0].min(), node_xyz[:, 0].max())
    ax.set_ylim(node_xyz[:, 1].min(), node_xyz[:, 1].max())
    ax.set_zlim(node_xyz[:, 2].min(), node_xyz[:, 2].max())
    ax.set_box_aspect([3, 1.5, 1])
    # ax.set_box_aspect([1, 1, 1])
    ax.legend()
    if title is None:
        plt.title(f'Gebäudegraph vom Typ {type_grid}')
    else:

        plt.title(title)
    fig.tight_layout()
    plt.show()

def visualzation_networkx_3D(self, G, minimum_trees: list, type_grid: str):

    """

    Args:
        G ():
        minimum_trees ():
    """
    fig = plt.figure()
    ax = fig.add_subplot(111, projection="3d")
    # Graph Buildings G
    node_xyz = np.array(sorted(nx.get_node_attributes(G, "pos").values()))
    ax.scatter(*node_xyz.T, s=1, ec="w")
    for u, v in G.edges():
        edge = np.array([(G.nodes[u]['pos'], G.nodes[v]['pos'])])
        ax.plot(*edge.T, color=G.edges[u, v]['color'])

    # Graph Steiner Tree
    for minimum_tree in minimum_trees:
        for u, v in minimum_tree.edges():
            edge = np.array([(minimum_tree.nodes[u]['pos'], minimum_tree.nodes[v]['pos'])])
            if minimum_tree.graph["grid_type"] == "forward":
                ax.plot(*edge.T, color="magenta")
            else:
                ax.plot(*edge.T, color="blue")

        node_xyz = np.array(
            sorted([data["pos"] for n, data in minimum_tree.nodes(data=True) if {"radiator"} in set(data["type"])]))
        if len(node_xyz) > 0 and node_xyz is not None:
            ax.scatter(*node_xyz.T, s=10, ec="red")
        node_xyz = np.array(sorted([data["pos"][0] for n, data in minimum_tree.nodes(data=True) if
                                    set(data["type"]) not in {"heat_source"} and {"radiator"}]))
        # node_xyz = np.array(sorted([data["pos"][0] for n, data in minimum_tree.nodes(data=True) if "pos" in data]))
        if len(node_xyz) > 0 and node_xyz is not None:
            ax.scatter(node_xyz.T[0], node_xyz.T[1], node_xyz.T[2], s=100, ec="yellow")
    """for minimum_tree in minimum_trees:
        edge_xyz = np.array([(minimum_tree.nodes[u]['pos'], minimum_tree.nodes[v]['pos']) for u, v in minimum_tree.edges()])
        if len(edge_xyz) > 0 or edge_xyz is not None:
            for vizedge in edge_xyz:
                if minimum_tree.graph["grid_type"] == "forward":
                    ax.plot(*vizedge.T, color="tab:red")
                else:
                    ax.plot(*vizedge.T, color="blue")"""
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_zlabel("z")
    plt.title(f'Graphennetzwerk vom typ {type_grid}')
    fig.tight_layout()