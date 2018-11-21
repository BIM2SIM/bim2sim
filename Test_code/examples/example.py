#!/usr/bin/env python
# -*- coding: utf-8 -*-
import ifcopenshell
import os
from collections import OrderedDict


IfcFile = ifcopenshell.open(os.path.dirname(__file__) +'/ifc_testfiles/KM_DPM_Vereinshaus_Gruppe62_Heizung_DTV_Spaceheater.ifc')

# get some information from the current ifc file
print(ifcopenshell.file().schema)
print(ifcopenshell.version)

def get_Property_Sets(element, PropertySetName):
    """
    This function searches an elements PropertySets for the defined
    PropertySetName. If the PropertySet is found the function will return a
    dict with the properties and their values. If the PropertySet is not
    found the function will return None

    :param element: The element in which you want to search for the PropertySet
    :param PropertySetName: Name of the PropertySet you are looking for
    :return:
    """
    AllPropertySetsList = element.IsDefinedBy
    # find the first PropertySet that matches PropertySetName, if there are
    # multiple ones with the same name they will also have same content
    PropertySet = next((item for item in AllPropertySetsList if
         item.RelatingPropertyDefinition.Name == PropertySetName), None)
    Properties = PropertySet.RelatingPropertyDefinition.HasProperties
    if PropertySet is not None:
        Propertydict = {}
        for Property in Properties:
            Propertydict[Property.Name] = Property.NominalValue.wrappedValue
        return Propertydict
    else:
        return None

def build_hydraulic(file):
    """
    This function creates the hydraulic system based on the ifc data.
    It works by starting with the space heaters, because these are defined
    endpoints of every hydraulic strand.

    :param file:
    :return:
    """
    # create and merge space heaters
    spaceheaters = IfcFile.by_type('IfcSpaceHeater')
    # the following have to be done for every spaceheater
    spaceheater_example = spaceheaters[0]
    #print(spaceheater_example)
    # get connections between element (spaceheater) and port
    element_port_connections = spaceheater_example.HasPorts
    for element_port_connection in element_port_connections:
    # check if connected port is Sink or Source
        # Sink means Flow circuit:
        FlowCircuit = OrderedDict()
        if element_port_connection.RelatingPort.FlowDirection=='SINK':
            port_port_connection = \
                element_port_connection.RelatingPort.ConnectedTo[0]
            next_port = port_port_connection.RelatedPort
            next_element = next_port.ContainedIn[0].RelatedElement
            print(next_element)
            Abmessungen = get_Property_Sets(next_element, 'Abmessungen')
            FlowCircuit[next_element] = Abmessungen
            print(FlowCircuit)

            #Todo find abmessungen from pipe
        # Source means Return circuit
        else:
            port_port_connection = \
                element_port_connection.RelatingPort.ConnectedFrom


build_hydraulic(IfcFile)

## below are some old code snippets for testing

# def get_port_from_element(file, object):
#     PortElementConnections = object.HasPorts
#     for PortElementConnection in PortElementConnections:
#         print(PortElementConnection)
#         if len(PortElementConnection.RelatingPort) > 0:
#             portid = PortElementConnection.RelatingPort.GlobalId
#             #Port = PortElementConnection.RelatingPort.ContainedIn[0].GlobalId
#             # ConnectedFrom = PortElementConnection.RelatingPort.ConnectedFrom[0].RelatedPort.GlobalId
#             # ConnectedTo = PortElementConnection.RelatingPort.ConnectedFrom[0].RelatingPort.GlobalId
#             port = file.by_guid(portid)
#             print(port)

#
#
# boiler = IfcFile.by_type('IFCBoiler')[0]
# get_port_from_element(IfcFile,boiler)
#
# ## Get Next Element from Port
# port =IfcFile.by_guid('0f2u$Wo6zAqgPzma_gQCUd')
# print(port)

# for port in ports:
#     print(port)
#     # print(port.Description)
#     print('test')
#
# def get_properties_by_id(file, id):
#     object = file.by_id(id)
#     for PropertySet in object.IsDefinedBy[1:-1]:  # first one is type defined by
#         PropertyId = PropertySet.RelatingPropertyDefinition[0]
#         Propertys = file.by_id(PropertyId).HasProperties
#         for Property in Propertys:
#             print(Property.Name+str(': ') +
#                   str(Property.NominalValue.wrappedValue))
#
# get_properties_by_id(IfcFile, 395)
#
# #boiler = IfcFile.by_id(414)
# #boilertype = IfcFile.by_id(414)
#
# #print(boiler)
# print(boilertype)