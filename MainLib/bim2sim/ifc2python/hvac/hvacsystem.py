""" This module holds a HVACSystem object which is represented by a graph
network
where each node represents a hvac-component
"""
import networkx as nx
from os.path import dirname

import numpy as np
import ifcopenshell
import matplotlib.pyplot as plt
from bim2sim.ifc2python import ifc2python
from bim2sim.ifc2python.hvac.hvac_specific_functions import \
    create_object_from_ifc
from bim2sim.ifc2python.hvac.logic.pipestrand import PipeStrand

# todo: get ifc file from top function bim2sim
IfcFile = ifcopenshell.open(
    dirname(dirname(dirname(dirname(dirname((__file__)))))) +
    '/ExampleFiles/KM_DPM_Vereinshaus_Gruppe62_Heizung_DTV_all_Spaceheaters'
    '.ifc')

class HVACSystem(object):
    def __init__(self):
        self.hvac_graph = None
        self.create_hvac_network()
        # self.draw_hvac_network()
        self.reduce_strangs()

    def create_hvac_network(self,
                            element_types=None):
        """
        This function defines the hvac as graph network, each element is
        represented by a node. The nodes are connected by the geometrical
        positions of their ports.
        """




        if element_types is None:
            element_types = ['IfcSpaceHeater',
                             'IfcPipeFitting',
                             'IfcPipeSegment',
                             'IfcTank',
                             'IfcBoiler']
        DG = nx.DiGraph()
        parts = {}
        # all absolute coordinates of the ports are calculated and saved
        # in the parts dict
        for element_type in element_types:
            elements = IfcFile.by_type(element_type)
            for element in elements:
                try:
                    a = element.ObjectPlacement.RelativePlacement
                    x1 = a.RefDirection.DirectionRatios[0]
                    x2 = a.RefDirection.DirectionRatios[1]
                    x3 = a.RefDirection.DirectionRatios[2]
                    x = np.array([x1, x2, x3])
                    z1 = a.Axis.DirectionRatios[0]
                    z2 = a.Axis.DirectionRatios[1]
                    z3 = a.Axis.DirectionRatios[2]
                    z = np.array([z1, z2, z3])
                except:
                    x = np.array([1, 0, 0])
                    z = np.array([0, 0, 1])

                y = np.cross(z, x)
                DG.add_node(element,
                            type=ifc2python.getElementType(element), oid=element.id())

                element_port_connections = element.HasPorts
                ports = {}
                for element_port_connection in element_port_connections:
                    b = element.ObjectPlacement.RelativePlacement.Location\
                        .Coordinates
                    c = element_port_connection.RelatingPort.ObjectPlacement\
                        .RelativePlacement.Location.Coordinates
                    coordinate = []
                    i = 0
                    while i <= 2:
                        coordinate.append(
                            b[i] + x[i] * c[0] + y[i] * c[1] + z[i] * c[2])
                        i += 1
                        ports[
                            element_port_connection.RelatingPort] = \
                            coordinate

                    parts[element] = ports

        for key1, value1 in parts.items():
            for key3, value3 in value1.items():
                for key2, value2 in parts.items():
                    for key4, value4 in value2.items():
                        j = 1
                        if key3 == key4:
                            continue
                        if abs(value3[0] - value4[0]) <= j and abs(value3[1] - value4[1]) <= j \
                                and \
                                abs(value3[2] - value4[2]) <= j:
                            DG.add_edge(key1, key2)
                            break


        self.hvac_graph = DG
        print(DG.number_of_nodes())


    def reduce_strangs(self):
        """""
          This function creates all strands. Each strand starts with an element that has 3 or more ports. Each strand
          finishes with an element that has 3 or more ports or with an IFCAIRTERMINAL. For each strand a list with the 
          elements of the strand is created. 
          """""
        #t = 1
        #s = 0
        #u = 0
        graph = self.hvac_graph
        element_types = ['IFCPIPEFITTING', 'IFCPIPESEGMENT']
        pipelist = []
        for element_type in element_types:
            elements = IfcFile.by_type(element_type)
            for element in elements:
                pipelist.append(element)

        SG = graph.subgraph(pipelist)
        graph1 = SG
        FG = nx.compose(graph, SG)
        for node in SG.nodes:
            if len(node.HasPorts) >= 3:
                neighbors_source_node = list(SG.neighbors(node))
                # print("neuer Knoten")
                for neighbor_source_node in neighbors_source_node:
                    node_before = node
                    # print("neuer Strang")
                    strangliste = []
                    # strangliste.append(node) # dont add node to strand its not
                    # part of it

                    while True:
                        # strangliste.append(neighbor_source_node)
                        neighbors_new_node = list(SG.neighbors(neighbor_source_node))
                        if len(neighbors_new_node) == 2:
                            strangliste.append(neighbor_source_node)
                            neighbors_new_node.remove(node_before)
                            node_before = neighbor_source_node
                            neighbor_source_node = neighbors_new_node[0]
                            # node_before = neighbor_source_node
                        else:
                            x = PipeStrand()
                            x.calc_length(strangliste=strangliste)
                            x.calc_median_diameter(strangliste=strangliste)
                            #FG.add_node(t)
                            #FG.add_edge(s, t)
                            #FG.add_edge(t, u)
                            #print(x)
                            FG.add_node(x)
                            # for j in strangliste:
                                 #print(len(j.HasPorts))
                                # if len(j.HasPorts) == 3:
                                #     print(j)
                            FG.remove_nodes_from(strangliste)
                            FG.add_edge(node, x)
                            FG.add_edge(x, neighbor_source_node)
                            #t += 1
                            break

        print(FG.number_of_nodes())
        print(FG.number_of_edges())
        #print(t)
        # print(FG.number_of_edges())
        # a = FG.nodes()
        # b = FG.edges()
        # print(a)
        # print(b)

        #todo add                 create_object_from_ifc(ifc_element=element)

    def draw_hvac_network(self):
        labels = nx.get_node_attributes(self.hvac_graph, 'oid')
        nx.draw(self.hvac_graph, labels=labels, node_size=3, font_size=6,
                with_labels=True)
        plt.draw() 
        plt.show()



if __name__ == '__main__':
    test = HVACSystem()
