
import importlib

from bim2sim.ifc2python import ifc2python


def create_object_from_ifc(ifc_element):
    """
    Creating an hvac_object by the corresponding ifc_element
    :param ifc_element:
    :return: object of class corresponding to the ifc_element
    """
    ifc_type = ifc2python.getElementType(ifc_element)
    class_dict = {
        "IfcBoiler": ['bim2sim.ifc2python.hvac.logic.boiler',
                      'Boiler'],
        "IfcSpaceHeater": [
            'bim2sim.ifc2python.hvac.logic.spaceheater',
            'SpaceHeater'],
        "IfcTank": [
            'bim2sim.ifc2python.hvac.logic.storage_device',
            'StorageDevice'],
        "PipeStrand": [
            'bim2sim.ifc2python.hvac.logic.pipestrand',
            'PipeStrand']
    }
    module = importlib.import_module(
        class_dict[ifc_type][0])
    class_ = getattr(module, class_dict[ifc_type][1])
    instance = class_()
    instance.IfcGUID = ifc2python.getGUID(ifc_element)
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
