"""Module for loading ifc files

Holds logic for target simulation independent file parsing, checking, and data enrichment
"""
import os
import logging
import typing

import ifcopenshell
from bim2sim.kernel.units import parse_ifc
import math
from collections.abc import Iterable


def load_ifc(path):
    logger = logging.getLogger('bim2sim')
    logger.info("Loading IFC '%s'", path)
    if not os.path.exists(path):
        raise IOError("Path '%s' does not exist"%(path))
    ifc_file = ifcopenshell.open(path)
    return ifc_file


def propertyset2dict(propertyset, ifc_units: dict):
    """Converts IfcPropertySet to python dict"""
    propertydict = {}
    if hasattr(propertyset, 'HasProperties'):
        for prop in propertyset.HasProperties:
            if hasattr(prop, 'Unit'):
                unit = parse_ifc(prop.Unit) if prop.Unit else None
            else:
                unit = None
            if prop.is_a() == 'IfcPropertySingleValue':
                if prop.NominalValue is not None:
                    unit = ifc_units.get(prop.NominalValue.is_a()) if not unit else unit
                    if unit:
                        propertydict[prop.Name] = prop.NominalValue.wrappedValue * unit
                    else:
                        propertydict[prop.Name] = prop.NominalValue.wrappedValue
            elif prop.is_a() == 'IfcPropertyListValue':
                # TODO: Unit conversion
                values = []
                for value in prop.ListValues:
                    unit = ifc_units.get(value.is_a()) if not unit else unit
                    if unit:
                        values.append(value.wrappedValue * unit)
                    else:
                        values.append(value.wrappedValue)
                propertydict[prop.Name] = values
            elif prop.is_a() == 'IfcPropertyBoundedValue':
                # TODO: Unit conversion
                propertydict[prop.Name] = (prop, prop)
                raise NotImplementedError("Property of type '%s'"%prop.is_a())
            elif prop.is_a() == 'IfcPropertyEnumeratedValue':
                # TODO: Unit conversion
                values = []
                for value in prop.EnumerationValues:
                    unit = ifc_units.get(value.is_a()) if not unit else unit
                    if unit:
                        values.append(value.wrappedValue * unit)
                    else:
                        values.append(value.wrappedValue)
                propertydict[prop.Name] = values
            else:
                raise NotImplementedError("Property of type '%s'"%prop.is_a())
    elif hasattr(propertyset, 'Quantities'):
        for prop in propertyset.Quantities:
            unit = parse_ifc(prop.Unit) if prop.Unit else None
            for attr, p_value in vars(prop).items():
                if attr.endswith('Value'):
                    if p_value is not None:
                        if unit:
                            propertydict[prop.Name] = p_value * unit
                        else:
                            propertydict[prop.Name] = p_value
                        break
    elif hasattr(propertyset, 'Properties'):
        for prop in propertyset.Properties:
            unit = parse_ifc(prop.Unit) if prop.Unit else None
            if prop.is_a() == 'IfcPropertySingleValue':
                if prop.NominalValue is not None:
                    unit = ifc_units.get(prop.NominalValue.is_a()) if not unit else unit
                    if unit:
                        propertydict[prop.Name] = prop.NominalValue.wrappedValue * unit
                    else:
                        propertydict[prop.Name] = prop.NominalValue.wrappedValue
            elif prop.is_a() == 'IfcPropertyListValue':
                # TODO: Unit conversion
                values = []
                for value in prop.ListValues:
                    unit = ifc_units.get(value.is_a()) if not unit else unit
                    values.append(value.wrappedValue * unit)
                propertydict[prop.Name] = values
            elif prop.is_a() == 'IfcPropertyBoundedValue':
                # TODO: Unit conversion
                propertydict[prop.Name] = (prop, prop)
                raise NotImplementedError("Property of type '%s'"%prop.is_a())
            else:
                raise NotImplementedError("Property of type '%s'"%prop.is_a())

    return propertydict


def get_layers_ifc(element):
    dict = []
    relation = 'RelatingMaterial'
    assoc_list = getIfcAttribute(element.ifc, "HasAssociations")
    for assoc in assoc_list:
        association = getIfcAttribute(assoc, relation)
        if association is not None:
            layer_list = None
            if association.is_a('IfcMaterial'):
                layer_list = [association]
            elif hasattr(association, 'ForLayerSet'):
                layer_list = association.ForLayerSet.MaterialLayers
            elif hasattr(association, 'Materials'):
                layer_list = association.Materials
            # TODO is this ifc4 conform? or just a workaround
            elif hasattr(association, 'MaterialLayers'):
                layer_list = association.MaterialLayers
            if isinstance(layer_list, Iterable):
                for layer in layer_list:
                    dict.append(layer)
    return dict


def getElementByGUID(ifcfile, guid):
    element = ifcfile.by_guid(guid)
    return element


def getIfcAttribute(ifcElement, attribute):
    """
    Fetches non-empty attributes (if they exist).
    """
    try:
        return getattr(ifcElement, attribute)
    except AttributeError:
        pass


def get_Property_Set(PropertySetName, element):
    """
    This function searches an elements PropertySets for the defined
    PropertySetName. If the PropertySet is found the function will return a
    dict with the properties and their values. If the PropertySet is not
    found the function will return None

    :param element: The element in which you want to search for the PropertySet
    :param PropertySetName: Name of the PropertySet you are looking for
    :return:
    """
    # TODO: Unit conversion
    AllPropertySetsList = element.IsDefinedBy
    property_set = next((item for item in AllPropertySetsList if
                         item.RelatingPropertyDefinition.Name == PropertySetName), None)
    if hasattr(property_set, 'RelatingPropertyDefinition'):
        return propertyset2dict(property_set.RelatingPropertyDefinition)


def get_property_sets(element, ifc_units):
    """Returns all PropertySets of element

    :param element: The element in which you want to search for the PropertySets
    :return: dict(of dicts)
    """
    # TODO: Unit conversion
    property_sets = {}
    if hasattr(element, 'IsDefinedBy'):
        for defined in element.IsDefinedBy:
            property_set_name = defined.RelatingPropertyDefinition.Name
            property_sets[property_set_name] = propertyset2dict(
                defined.RelatingPropertyDefinition, ifc_units)
    elif hasattr(element, 'Material'):
        for defined in element.Material.HasProperties:
            property_set_name = defined.Name
            property_sets[property_set_name] = propertyset2dict(
                defined, ifc_units)
    elif element.is_a('IfcMaterial'):
        for defined in element.HasProperties:
            property_set_name = defined.Name
            property_sets[property_set_name] = propertyset2dict(
                defined, ifc_units)

    return property_sets


def get_type_property_sets(element, ifc_units):
    """Returns all PropertySets of element's types

    :param element: The element in which you want to search for the PropertySets
    :return: dict(of dicts)"""
    # TODO: use guids to get type propertysets (they are userd by many entitys)
    property_sets = {}
    if hasattr(element, 'IsTypedBy'):
        for defined_type in element.IsTypedBy:
            for propertyset in defined_type.RelatingType.HasPropertySets:
                property_sets[propertyset.Name] = propertyset2dict(
                    propertyset, ifc_units)

    return property_sets


def get_quantity_sets(element):
    """Returns all QuantitySets of element"""

    quantity_sets = {}
    for defined_type in element.IsTypedBy:
        for quantityset in defined_type.RelatingType.Quantities:
            quantity_sets[quantityset.Name] = propertyset2dict(
                quantityset, ifc_units)

    return quantity_sets

def getGUID(ifcElement):
    """
    Returns the global id of the IFC element
    """
    try:
        return getattr(ifcElement, 'GlobalId')
    except TypeError:
        pass


def get_predefined_type(ifcElement) -> typing.Union[str, None]:
    """Returns the predifined type of the IFC element"""
    try:
        predefined_type = getattr(ifcElement, 'PredefinedType')
        # todo cache "USERDEFINED" and check where information is stored
        if predefined_type == "NOTDEFINED":
            predefined_type = None
        return predefined_type
    except AttributeError:
        return None


def getElementType(ifcElement):
    """Return the ifctype of the IFC element"""
    try:
        return ifcElement.wrapped_data.is_a()
    except TypeError:
        pass


def checkIfcElementType(ifcElement, ifcType):
    """Checks for matching IFC element types."""
    if getIfcAttribute(ifcElement, 'is_a'):
        return ifcElement.is_a() == ifcType


def getHierarchicalParent(ifcElement):
    """Fetch the first structural parent element."""
    parent = getIfcAttribute(ifcElement, 'Decomposes')
    if parent:
        return parent[0].RelatingObject
    # ... try again for voids:
    parent = getIfcAttribute(ifcElement, 'VoidsElements')
    if parent:
        return parent[0].RelatingBuildingElement


def getHierarchicalChildren(ifcElement):
    """Fetch the child elements from the first structural aggregation."""
    children = getIfcAttribute(ifcElement, 'IsDecomposedBy')
    if children:
        return children[0].RelatedObjects
    # ... try again for voids:
    children = getIfcAttribute(ifcElement, 'HasOpenings')
    if children:
        # just get the voids, not the relations
        return [i.RelatedOpeningElement for i in children]


def getSpatialParent(ifcElement):
    """Fetch the first spatial parent element."""
    parent = getIfcAttribute(ifcElement, 'ContainedInStructure')
    if parent:
        return parent[0].RelatingStructure


def getSpatialChildren(ifcElement):
    """Fetch the child elements from the first spatial structure."""
    children = getIfcAttribute(ifcElement, 'ContainsElements')
    if children:
        return children[0].RelatedElements


def getSpace(ifcElement):
    """Find the space for this element."""
    if ifcElement:
        # direct spatial child elements in space
        parent = getSpatialParent(ifcElement)
        if checkIfcElementType(parent, 'IfcSpace'):
            return parent
        else:
            # hierachically nested building elements
            parent = getHierarchicalParent(ifcElement)
            if checkIfcElementType(parent, 'IfcSpace'):
                return parent
            else:
                return getSpace(parent)


def getStorey(ifcElement):
    """Find the building storey for this element."""
    if ifcElement:
        # direct spatial child elements in space or storey
        parent = getSpatialParent(ifcElement)
        if checkIfcElementType(parent, 'IfcBuildingStorey'):
            return parent
        elif checkIfcElementType(parent, 'IfcSpace'):
            return getStorey(parent)
        else:
            # hierachically nested building elements
            parent = getHierarchicalParent(ifcElement)
            if checkIfcElementType(parent, 'IfcBuildingStorey'):
                return parent
            else:
                return getStorey(parent)


def getBuilding(ifcElement):
    """Find the building for this element."""
    if ifcElement:
        # direct spatial child elements outside of storey
        parent = getSpatialParent(ifcElement)
        if checkIfcElementType(parent, 'IfcBuilding'):
            return parent
        else:
            storey = getStorey(ifcElement)
            if storey:
                # part of building storey
                parent = getHierarchicalParent(storey)
            else:
                # hierarchical child elements outside of storey
                parent = getHierarchicalParent(ifcElement)
            # ... and finally check and return or start recursion
            if checkIfcElementType(parent, 'IfcBuilding'):
                return parent
            else:
                return getBuilding(parent)


def getSite(ifcElement):
    """Find the building site for this element."""
    if ifcElement:
        # direct spatial child elements outside of building
        parent = getSpatialParent(ifcElement)
        if checkIfcElementType(parent, 'IfcSite'):
            return parent
        else:
            building = getBuilding(ifcElement)
            if building:
                # part of building
                parent = getHierarchicalParent(building)
            else:
                # hierarchical child elements outside of building
                parent = getHierarchicalParent(ifcElement)
            # ... and finally check and return or start recursion
            if checkIfcElementType(parent, 'IfcSite'):
                return parent
            else:
                return getSite(parent)


def getProject(ifcElement):
    """Find the project/root for this element."""
    if ifcElement:
        # the project might be the hierarchical parent of the site ...
        site = getSite(ifcElement)
        parent = getHierarchicalParent(site)
        if checkIfcElementType(parent, 'IfcProject'):
            return parent
        else:
            # ... or of the building (no site defined) ...
            building = getBuilding(ifcElement)
            parent = getHierarchicalParent(site)
            if checkIfcElementType(parent, 'IfcProject'):
                return parent
        # ... or the parent of an IfcSpatialZone, which is non-hierarchical.


def getTrueNorth(ifcElement):
    """Find the true north in degree of this element, 0 °C means positive
    Y-axis. 45 °C Degree means middle between X- and Y-Axis"""
    project = getProject(ifcElement)
    try:
        true_north = project.RepresentationContexts[0].TrueNorth.DirectionRatios
    except AttributeError:
        true_north = [0, 1]
    angle_true_north = math.degrees(math.atan(true_north[0] / true_north[1]))
    return angle_true_north


def convertToSI(ifcUnit, value):
    """Return the value in basic SI units, conversion according to ifcUnit."""
    # IfcSIPrefix values
    ifcSIPrefix = {
                    'EXA': 1e18,
                    'PETA': 1e15,
                    'TERA': 1e12,
                    'GIGA': 1e9,
                    'MEGA': 1e6,
                    'KILO': 1e3,
                    'HECTO': 1e2,
                    'DECA': 1e1,
                    'DECI': 1e-1,
                    'CENTI': 1e-2,
                    'MILLI': 1e-3,
                    'MICRO': 1e-6,
                    'NANO': 1e-9,
                    'PICO': 1e-12,
                    'FEMTO': 1e-15,
                    'ATTO': 1e-18
                    }

    if checkIfcElementType(ifcUnit, 'IfcSIUnit'):
        # just check the prefix to normalize the values
        prefix = ifcUnit.Prefix
        if prefix:
            return value * ifcSIPrefix[prefix]
        else:
            return value
    elif checkIfcElementType(ifcUnit, 'IfcConversionBasedUnit'):
        factor = ifcUnit.ConversionFactor.ValueComponent.wrappedValue
        return value * factor

def summary(ifcelement):
    txt = "** Summary **\n"
    for k, v in ifcelement.get_info().items():
        txt += "%s: %s\n"%(k, v)

    # "HasAssignments", "ContainedInStructure", "IsTypedBy", "HasAssociations"
    relations = ("HasPorts", "IsDefinedBy", )
    for rel in relations:
        attr = getattr(ifcelement, rel)
        if attr:
            txt += "%s:\n"%(rel)
            for item in attr:
                if item.is_a() == 'IfcRelDefinesByProperties':
                    pset = item.RelatingPropertyDefinition
                    txt += " - %s\n"%(pset.Name)
                    for prop in pset.HasProperties:
                        txt += "    - %s\n"%(prop)
                else:
                    txt += " - %s\n"%(item)

    #for attrname in dir(ifcelement):
    #    if attrname.startswith('__'):
    #        continue
    #    value = getattr(ifcelement, attrname)
    #    if not value:
    #        continue
    #    txt += "\n%s:%s"%(attrname, value)

    return txt


def used_properties(ifc_file):
    """Filters given IFC for propertysets
   returns a dictonary with related ifctypes as keys and lists of usered propertysets as values"""
    props = ifc_file.by_type("IFCPROPERTYSET")
    tuples = []
    for prop in props:
        for occ in prop.DefinesOccurrence:
            for ro in occ.RelatedObjects:
                tuples.append((ro.is_a(), prop.Name))
    tuples = set(tuples)
    types = set(tup[0] for tup in tuples)
    type_dict = {typ:[] for typ in types}
    for tup in tuples:
        type_dict[tup[0]].append(tup[1])
    return type_dict

