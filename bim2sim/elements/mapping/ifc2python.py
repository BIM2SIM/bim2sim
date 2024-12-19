"""Module to convert ifc data from to python data"""
from __future__ import annotations

import logging
import math
import os
from collections.abc import Iterable
from typing import Optional, Union, TYPE_CHECKING, Any

import ifcopenshell
from ifcopenshell import entity_instance, file, open as ifc_open, guid
from pathlib import Path

from bim2sim.elements.mapping.units import parse_ifc

if TYPE_CHECKING:
    from bim2sim.elements.base_elements import ProductBased

logger = logging.getLogger(__name__)


def load_ifc(path: Path) -> file:
    """loads the ifc file using ifcopenshell and returns the ifcopenshell
    instance

    Args:
        path: Path to ifc file location

    Returns:
        ifc_file: ifcopenshell file object
    """
    logger = logging.getLogger('bim2sim')
    if not isinstance(path, Path):
        try:
            path = Path(path)
        except:
            raise ValueError(f"Can't convert given path {path} to pathlib"
                             f" object")
    logger.info(f"Loading IFC {path.name} from {path}")
    if not os.path.exists(path):
        raise IOError("Path '%s' does not exist"%(path))
    try:
        ifc_file = ifc_open(path)
    except Exception as ex:
        logger.error(f"Loading IFC raised the following error: {ex}")
        raise RuntimeError("bim2sim canceled due to invalid IFC schema")
    return ifc_file


def reset_guids(ifc_file) -> file:
    all_elements = ifc_file.by_type('IfcRoot')
    for element in all_elements:
        element.GlobalId = guid.new()
    return ifc_file


def property_set2dict(property_set: entity_instance,
                      ifc_units: Optional[dict]) -> dict:
    """Converts IfcPropertySet and IfcQuantitySet to python dict

    Takes all IfcPropertySet and IfcQuantitySet properties and quantities of the
     given IfcPropertySet or IfcQuantitySet and converts them into a dictionary.
    Also takes care of setting the correct unit to every property/quantity by
    using the units defined in the IFC.

    Args:
        property_set: IfcPropertySet entity from ifcopenshell
        ifc_units: dict with key ifc unit definition and value pint unit
    Returns:
        property_dict: dict with key name of the property/quantity and value
            the property/quantity value as pint quantity if available
    """

    def add_quantities_to_dict(quantity):
        quantity_unit = parse_ifc(quantity.Unit) if quantity.Unit else None
        if not quantity_unit:
            if prop.is_a() == 'IfcQuantityLength':
                quantity_unit = ifc_units.get('ifclengthmeasure')
            elif prop.is_a() == 'IfcQuantityArea':
                quantity_unit = ifc_units.get('ifcareameasure')
            elif prop.is_a() == 'IfcQuantityCount':
                quantity_unit = ifc_units.get('ifccountmeasure')
            elif prop.is_a() == 'IfcQuantityTime':
                quantity_unit = ifc_units.get('ifctimemeasure')
            elif prop.is_a() == 'IfcQuantityVolume':
                quantity_unit = ifc_units.get('ifcvolumemeasure')
            elif prop.is_a() == ' IfcQuantityWeight':
                quantity_unit = ifc_units.get('ifcmassmeasure')

        for attr, p_value in vars(quantity).items():
            if attr.endswith('Value'):
                if p_value is not None:
                    if quantity_unit:
                        property_dict[quantity.Name] = p_value * quantity_unit
                    else:
                        property_dict[quantity.Name] = p_value
                    break

    def add_property_to_dict(prop):
        if hasattr(prop, 'Unit'):
            property_unit = parse_ifc(prop.Unit) if prop.Unit else None
        else:
            property_unit = None
        if prop.is_a() == 'IfcPropertySingleValue':
            if prop.NominalValue is not None:
                property_unit = ifc_units.get(prop.NominalValue.is_a().lower())\
                    if not property_unit else property_unit
                if property_unit:
                    property_dict[prop.Name] = \
                        prop.NominalValue.wrappedValue * property_unit
                else:
                    property_dict[prop.Name] = prop.NominalValue.wrappedValue
        elif prop.is_a() == 'IfcPropertyListValue':
            values = []
            for value in prop.ListValues:
                property_unit = ifc_units.get(value.is_a().lower())\
                    if not property_unit else property_unit
                if property_unit:
                    values.append(value.wrappedValue * property_unit)
                else:
                    values.append(value.wrappedValue)
            property_dict[prop.Name] = values
        elif prop.is_a() == 'IfcPropertyBoundedValue':
            # TODO: value.UpperBoundValue and value.LowerBoundValue not used
            value = prop.SetPointValue
            if value:
                property_unit = ifc_units.get(value.is_a().lower()) \
                    if not property_unit else property_unit
                if property_unit:
                    property_dict[prop.Name] = value * property_unit
                else:
                    property_dict[prop.Name] = value
        elif prop.is_a() == 'IfcPropertyEnumeratedValue':
            values = []
            for value in prop.EnumerationValues:
                property_unit = ifc_units.get(value.is_a().lower())\
                    if not property_unit else property_unit
                if property_unit:
                    values.append(value.wrappedValue * property_unit)
                else:
                    values.append(value.wrappedValue)
            property_dict[prop.Name] = values
        else:
            raise NotImplementedError("Property of type '%s'"%prop.is_a())

    property_dict = {}
    if hasattr(property_set, 'HasProperties') and\
            getattr(property_set, 'HasProperties') is not None:
        for prop in property_set.HasProperties:
            # IfcComplexProperty
            if hasattr(prop, 'HasProperties') and \
                    getattr(prop, 'HasProperties') is not None:
                for property in prop.HasProperties:
                    add_property_to_dict(property)
            else:
                add_property_to_dict(prop)

    elif hasattr(property_set, 'Quantities') and\
            getattr(property_set, 'Quantities') is not None:
        for prop in property_set.Quantities:
            # IfcPhysicalComplexQuantity
            if hasattr(prop, 'HasQuantities') and \
                    getattr(prop, 'HasQuantities') is not None:
                for quantity in prop.HasQuantities:
                    add_quantities_to_dict(quantity)
            else:
                add_quantities_to_dict(prop)
    elif hasattr(property_set, 'Properties') and\
            getattr(property_set, 'Properties') is not None:
        for prop in property_set.Properties:
            property_unit = parse_ifc(prop.Unit) if prop.Unit else None
            if prop.is_a() == 'IfcPropertySingleValue':
                if prop.NominalValue is not None:
                    property_unit = ifc_units.get(prop.NominalValue.is_a().lower())\
                        if not property_unit else property_unit
                    if property_unit:
                        property_dict[prop.Name] = \
                            prop.NominalValue.wrappedValue * property_unit
                    else:
                        property_dict[prop.Name] = \
                            prop.NominalValue.wrappedValue
            elif prop.is_a() == 'IfcPropertyListValue':
                values = []
                for value in prop.ListValues:
                    property_unit = ifc_units.get(value.is_a().lower()) \
                        if not property_unit else property_unit
                    values.append(value.wrappedValue * property_unit)
                property_dict[prop.Name] = values
            elif prop.is_a() == 'IfcPropertyBoundedValue':
                # TODO: value.UpperBoundValue and value.LowerBoundValue not used
                value = prop.SetPointValue
                if value:
                    property_unit = ifc_units.get(value.is_a().lower()) \
                        if not property_unit else property_unit
                    if property_unit:
                        property_dict[prop.Name] = value * property_unit
                    else:
                        property_dict[prop.Name] = value
    return property_dict


def get_layers_ifc(element: Union[entity_instance, ProductBased]):
    # TODO only used for check, maybe we can use functions of base_tasks.py instead
    """
    Returns layers information of an element as list. It can be applied to
    an IFCProduct directly or a Bim2Sim Instance. This only used to pre instance
    creation check of IFC file now.
    Args:
        element: ifcopenshell instance or bim2sim Instance

    Returns:
        layers_list: list of all organized layers with all material information
    """
    layers_list = []
    relation = 'RelatingMaterial'
    ifc_instance = element.ifc if hasattr(element, 'ifc') else element
    assoc_list = getIfcAttribute(ifc_instance, "HasAssociations") if \
        hasattr(ifc_instance, 'HasAssociations') else []
    for assoc in assoc_list:
        association = getIfcAttribute(assoc, relation)
        if association is not None:
            layer_list = None
            if association.is_a('IfcMaterial'):
                layer_list = [association]
            # IfcMaterialLayerSetUsage
            elif hasattr(association, 'ForLayerSet'):
                layer_list = association.ForLayerSet.MaterialLayers
            # single IfcMaterial
            elif hasattr(association, 'Materials'):
                layer_list = association.Materials
            elif hasattr(association, 'MaterialLayers'):
                layer_list = association.MaterialLayers
            elif hasattr(association, 'MaterialConstituents'):
                layer_list = [Constituent.Material for Constituent in
                              association.MaterialConstituents]
            elif hasattr(association, 'MaterialProfiles'):
                layer_list = [profile.Material for profile in
                              association.MaterialProfiles]

            if isinstance(layer_list, Iterable):
                for layer in layer_list:
                    layers_list.append(layer)
    return layers_list


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


def get_property_set_by_name(property_set_name: str, element: entity_instance,
                             ifc_units: dict) -> dict:
    """Try to find a IfcPropertySet for a given ifc instance by it's name.

    This function searches an elements PropertySets for the defined
    PropertySetName. If the PropertySet is found the function will return a
    dict with the properties and their values. If the PropertySet is not
    found the function will return None

    Args:
        property_set_name: Name of the PropertySet you are looking for
        element: ifcopenshell element to search for PropertySet
        ifc_units: dict with key ifc unit definition and value pint unit
    Returns:
        property_set: dict with key name of the property/quantity and value
            the property/quantity value as pint quantity if available if found
    """
    property_dict = None
    all_property_sets_list = element.IsDefinedBy
    preselection = [item for item in all_property_sets_list
        if hasattr(item, 'RelatingPropertyDefinition')]
    property_set = next(
        (item for item in preselection if
         item.RelatingPropertyDefinition.Name == property_set_name), None)
    if hasattr(property_set, 'RelatingPropertyDefinition'):
        property_dict = property_set2dict(
            property_set.RelatingPropertyDefinition, ifc_units)
    return property_dict


def get_property_sets(element: entity_instance, ifc_units: dict) -> dict:
    """Returns all PropertySets of element


    Args:
        element: The element in which you want to search for the PropertySets
        ifc_units: dict holding all unit definitions from ifc_units

    Returns:
         dict of dicts for each PropertySet. Each dict with key property name
          and value its value

    """
    property_sets = {}
    if hasattr(element, 'IsDefinedBy') and\
            getattr(element, 'IsDefinedBy') is not None:
        for defined in element.IsDefinedBy:
            property_set_name = defined.RelatingPropertyDefinition.Name
            property_sets[property_set_name] = property_set2dict(
                defined.RelatingPropertyDefinition, ifc_units)
    elif hasattr(element, 'Material') and\
            getattr(element, 'Material') is not None:
        for defined in element.Material.HasProperties:
            property_set_name = defined.Name
            property_sets[property_set_name] = property_set2dict(
                defined, ifc_units)
    elif element.is_a('IfcMaterial'):
        for defined in element.HasProperties:
            property_set_name = defined.Name
            property_sets[property_set_name] = property_set2dict(
                defined, ifc_units)

    return property_sets


def get_type_property_sets(element, ifc_units):
    """Returns all PropertySets of element's types

    :param element: The element in which you want to search for the PropertySets
    :return: dict(of dicts)"""
    # TODO: use guids to get type property_sets (they are userd by many entitys)
    property_sets = {}
    if hasattr(element, 'IsTypedBy') and\
            getattr(element, 'IsTypedBy') is not None:
        for defined_type in element.IsTypedBy:
            for property_set in defined_type.RelatingType.HasPropertySets:
                property_sets[property_set.Name] = property_set2dict(
                    property_set, ifc_units)

    return property_sets


def get_quantity_sets(element, ifc_units):
    """Returns all QuantitySets of element"""

    quantity_sets = {}
    if hasattr(element, 'IsTypedBy') and \
            getattr(element, 'IsTypedBy') is not None:
        for defined_type in element.IsTypedBy:
            for quantityset in defined_type.RelatingType.Quantities:
                quantity_sets[quantityset.Name] = property_set2dict(
                    quantityset, ifc_units)

    return quantity_sets


def get_guid(ifcElement):
    """
    Returns the global id of the IFC element
    """
    try:
        return getattr(ifcElement, 'GlobalId')
    except TypeError:
        pass


def get_predefined_type(ifcElement) -> Union[str, None]:
    """Returns the predefined type of the IFC element"""
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


def get_true_north(ifcElement: entity_instance):
    """Find the true north in degree of this element, 0 °C means positive
    Y-axis. 45 °C Degree means middle between X- and Y-Axis"""
    project = getProject(ifcElement)
    try:
        true_north = project.RepresentationContexts[0].TrueNorth.DirectionRatios
    except AttributeError as er:
        logger.warning(f"Not able to calculate true north of IFC element "
                       f"{ifcElement} due to error: {er}")
        true_north = [0, 1]
    angle_true_north = math.degrees(math.atan(true_north[0] / true_north[1]))
    return angle_true_north


def get_ports(element: entity_instance) -> list[Any]:
    """Get all ports for new and old IFC definition of ports.

    Args:
        element: ifcopenshell element to check for ports
    Returns:
        ports: list of all ports connected to the element
    """
    ports = []
    # new IfcStandard with IfcRelNests
    ports_nested = list(getattr(element, 'IsNestedBy', []))
    # old IFC standard with IfcRelConnectsPortToElement
    ports_connects = list(getattr(element, 'HasPorts', []))

    for nested in ports_nested:
        for port_connection in nested.RelatedObjects:
            ports.append(port_connection)

    for connected in ports_connects:
        ports.append(connected.RelatingPort)

    return ports


def get_ports_connections(element_port: entity_instance) -> list[Any]:
    """Get all connected ports to a given port.

    Args:
        element_port: ifcopenshell port element to check for connections
    Returns:
        connected_ports: list of all ports connected to given element_port
    """
    connected_ports = \
        [conn.RelatingPort for conn in element_port.ConnectedFrom] + \
        [conn.RelatedPort for conn in element_port.ConnectedTo]
    return connected_ports


def get_ports_parent(element: entity_instance) -> list[Any]:
    """Get the parent of given port for new and old Ifc definitions of ports.

    Args:
        element: ifcopenshell port element which parents are searched
    Returns:
        parents: list of ifcopenshell elements that are parent of the port
    """
    parents = []
    parent_nested = list(getattr(element, 'Nests', []))
    for nest in parent_nested:
        parents.append(nest.RelatingObject)
    return parents


def convertToSI(ifcUnit, value):
    # TODO not used anywhere. Remove?
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
    """Filters given IFC for property_sets.

    Returns a dictionary with related ifc types as keys and lists of used
    propertysets as values"""
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
