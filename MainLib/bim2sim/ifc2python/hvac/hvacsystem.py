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

# todo: get ifc file from top function bim2sim
IfcFile = ifcopenshell.open(
    dirname(dirname(dirname(dirname(dirname((__file__)))))) +
    '/ExampleFiles/KM_DPM_Vereinshaus_Gruppe62_Heizung_DTV_all_Spaceheaters'
    '.ifc')

class HVACSystem(object):
    def __init__(self):
        self.hvac_graph = None
        self.create_hvac_network()
        self.draw_hvac_network()
        #self.reduce_strangs()

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
                            type=ifc2python.getGUID(element))

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
                        j = 0
                        value3[0] = round(value3[0], j)
                        value3[1] = round(value3[1], j)
                        value3[2] = round(value3[2], j)
                        value4[0] = round(value4[0], j)
                        value4[1] = round(value4[1], j)
                        value4[2] = round(value4[2], j)
                        if key3 == key4:
                            continue
                        if value3[0] == value4[0] and value3[1] == value4[1] \
                                and \
                                value3[2] == value4[2]:
                            DG.add_edge(key1, key2)
                            break


        self.hvac_graph = DG


    def reduce_strangs(self):
        graph = self.hvac_graph
        for node in graph.nodes:
            ifctype = ifc2python.getElementType(node)
            #todo solve problem with logic
            boolean1 = len(node.HasPorts) >= 3
            boolean2 = ifctype == 'IfcPipeFitting'
            if (len(node.HasPorts) >= 3 and ifctype == 'IfcPipeSegment') or \
                    (len(node.HasPorts) >= 3 and ifctype == 'IfcPipeFitting'):
                g = graph.neighbors(node)
                #print("neuer Knoten")
                for new_startingpoint in g:
                    n = new_startingpoint
                    strangliste = []
                    strangliste.append(node)
                    strangliste.append(new_startingpoint)
                    #print("neuer Strang")
                    # h = DG.neighbors(new_startingpoint)
                    # next_point = new_startingpoint
                    while True:
                        h = graph.neighbors(n)
                        for next_point in h:
                            if next_point == n or next_point == node:
                                continue
                            else:
                                if next_point not in strangliste:
                                    strangliste.append(next_point)
                                    # h = DG.neighbors(next_point)
                                    n = next_point
                                    # h = DG.neighbors(n)
                                    if len(next_point.HasPorts) >= 3:
                                        # print(strangliste)
                                        break
                                if next_point in strangliste:
                                    continue
                        #print(strangliste)
                        break

        #todo add                 create_object_from_ifc(ifc_element=element)

    def draw_hvac_network(self):
        labels = nx.get_node_attributes(self.hvac_graph,'type')
        nx.draw(self.hvac_graph, labels=labels, node_size=3, font_size=6,
                with_labels=True)
        plt.draw()
        plt.show()



if __name__ == '__main__':
    test = HVACSystem()
