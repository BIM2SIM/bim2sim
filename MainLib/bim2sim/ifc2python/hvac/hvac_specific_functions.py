
import importlib

from bim2sim.ifc2python import ifc2python
from bim2sim.ifc2python.hvac.logic.hvac_objects import Boiler, SpaceHeater, \
    StorageDevice, Pipe, Valve, GenericDevice
import networkx as nx
from bim2sim.ifc2python.hvac.logic.energy_conversion_device \
    import EnergyConversionDevice


def all_neighbors(graph, node):
    neighbors = list(
        set(nx.all_neighbors(graph, node)) -
        set(graph.node[node]['contracted_nodes']) - {node}
    )
    return neighbors


def create_generic_objects(graph, node):
    """
    Creating an hvac_object by the corresponding ifc_element
    :param node:
    :return: object of class corresponding to the ifc_element
    """

    object_type = ifc2python.getElementType(node)
    if object_type == "IfcBoiler":
        instance = Boiler()
        instance.IfcGUID = ifc2python.getGUID(node)
    elif object_type == "IfcTank":
        instance = StorageDevice()
    elif object_type == "IfcSpaceHeater":
        instance = SpaceHeater()
    elif object_type in ("IfcPipeFitting", "IfcPipeSegment"):
        if len(all_neighbors(graph, node)) > 2:
            instance = Valve()
        else:
            instance = Pipe()
    elif object_type == "IfcUnitaryEquipment":
        instance = EnergyConversionDevice()
    else:
        instance = GenericDevice

    instance.IfcGUID = [ifc2python.getGUID(node)] + list(map(ifc2python.getGUID,
                                                        graph.node[node][
                                                            'contracted_nodes']))
    return instance


def connect_elements_by_coordinates(graph, parts, threshold):
    """
    Connects the ifc elements of the parts dict to each other by taking the
    geometrical position of the ports into account. The threshold value
    determines how far apart the ports may be from each other so that a
    connection is still established.

    Parameters
    ----------


    graph : Graph object from networkx
        Graph that displays the hvac network
    parts : dict
        Dictionary holding all ifc elements of the hvac network
    threshold : float
        Value to specify how far apart the ports may be from each other so that
        a connection is still established.
    """
    for element1, ports1 in parts.items():
        for port1 in ports1.values():
            for element2, ports2 in parts.items():
                for port2 in ports2.values():
                    if element1 == element2:
                        continue

                    distance = list((abs(coord1 - coord2)
                                     for (coord1, coord2)
                                     in zip(port1['coordinate'],
                                            port2['coordinate'])))
                    if all(diff <= threshold for diff in distance):
                        if port1['flow_direction'] == 'SOURCE' and \
                                port2['flow_direction'] == 'SINK':
                            graph.add_edge(element1, element2)
                        elif port1['flow_direction'] == 'SINK' and \
                                port2['flow_direction'] == 'SOURCE':
                            graph.add_edge(element2, element1)
                        elif port1['flow_direction'] == 'SOURCEANDSINK' or \
                                port2['flow_direction'] == 'SOURCEANDSINK':
                            graph.add_edge(element1, element2)
                            graph.add_edge(element2, element1)
                        else:
                            continue
    return graph


def connect_generic_objects():
    pass