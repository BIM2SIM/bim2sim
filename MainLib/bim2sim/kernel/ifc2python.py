"""Module for loading ifc files

Holds logic for target simulation independent file parsing, checking, and data enrichment
"""
import os
import logging
import ifcopenshell
import math
import copy
import uuid
import inspect

def load_ifc(path):
    logger = logging.getLogger('bim2sim')
    logger.info("Loading IFC '%s'", path)
    if not os.path.exists(path):
        raise IOError("Path '%s' does not exist"%(path))
    ifc_file = ifcopenshell.open(path)
    return ifc_file

def propertyset2dict(propertyset):
    """Converts IfcPropertySet to python dict"""
    propertydict = {}
    if hasattr(propertyset, 'HasProperties'):
        props = propertyset.HasProperties
        for prop in props:
            unit = prop.Unit
            # TODO: Unit conversion
            if prop.is_a() == 'IfcPropertySingleValue':
                propertydict[prop.Name] = prop.NominalValue.wrappedValue
            elif prop.is_a() == 'IfcPropertyListValue':
                propertydict[prop.Name] = [value.wrappedValue for value in
                                           prop.ListValues]
            elif prop.is_a() == 'IfcPropertyBoundedValue':
                propertydict[prop.Name] = (prop, prop)
                raise NotImplementedError("Property of type '%s'" % prop.is_a())
            else:
                raise NotImplementedError("Property of type '%s'" % prop.is_a())
    elif hasattr(propertyset, 'Quantities'):
        quants = propertyset.Quantities
        for quant in quants:
            if quant.is_a() == 'IfcQuantityLength':
                propertydict[quant.Name] = quant.LengthValue
            elif quant.is_a() == 'IfcQuantityArea':
                propertydict[quant.Name] = quant.AreaValue
            elif quant.is_a() == 'IfcQuantityVolume':
                propertydict[quant.Name] = quant.VolumeValue
            elif quant.is_a() == 'IfcQuantityCount':
                propertydict[quant.Name] = quant.CountValue
            elif quant.is_a() == 'IfcQuantityTime':
                propertydict[quant.Name] = quant.TimeValue
            elif quant.is_a() == 'IfcQuantityWeight':
                propertydict[quant.Name] = quant.WeightValue
            # todo IfcQuantitySet? found in doku but not belonging value
            else:
                raise NotImplementedError("Quantity of type '%s'" %
                                          quant.is_a())

    return propertydict


def get_layers_ifc(element):
    dict = {}
    relation = 'RelatingMaterial'
    assoc_list = getIfcAttribute(element.ifc, "HasAssociations")
    for assoc in assoc_list:
        association = getIfcAttribute(assoc, relation)
        if association is not None:
            layer_list = association.ForLayerSet.MaterialLayers
            for count, layer in enumerate(layer_list):
                thickness = layer.LayerThickness
                material_name = layer.Material.Name
                dict[count] = [thickness, material_name]
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
    if property_set is not None:
        properties = property_set.RelatingPropertyDefinition.HasProperties
        propertydict = {}
        for Property in properties:
            propertydict[Property.Name] = Property.NominalValue.wrappedValue
        return propertydict
    else:
        return None


def get_property_sets(element):
    """Returns all PropertySets of element

    :param element: The element in which you want to search for the PropertySets
    :return: dict(of dicts)
    """
    # TODO: Unit conversion
    property_sets = {}
    for defined in element.IsDefinedBy:
        property_set_name = defined.RelatingPropertyDefinition.Name
        property_sets[property_set_name] = propertyset2dict(defined.RelatingPropertyDefinition)

    return property_sets

def get_type_property_sets(element):
    """Returns all PropertySets of element's types

    :param element: The element in which you want to search for the PropertySets
    :return: dict(of dicts)"""
    # TODO: use guids to get type propertysets (they are userd by many entitys)
    property_sets = {}
    for defined_type in element.IsTypedBy:
        for propertyset in defined_type.RelatingType.HasPropertySets:
            property_sets[propertyset.Name] = propertyset2dict(propertyset)

    return property_sets


def get_quantity_sets(element):
    """Returns all QuantitySets of element"""

    quantity_sets = {}
    for defined_type in element.IsTypedBy:
        for quantityset in defined_type.RelatingType.Quantities:
            quantity_sets[quantityset.Name] = propertyset2dict(quantityset)

    return quantity_sets

def getGUID(ifcElement):
    """
    Returns the global id of the IFC element
    """
    try:
        return getattr(ifcElement, 'GlobalId')
    except TypeError:
        pass

def get_predefined_type(ifcElement):
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
    X-axis. 45 °C Degree means middle between X- and Y-Axis"""
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


def get_all_property_sets(element):
    sets = {'Property_Sets': {},
            'Quantity_Sets': {}}

    for p_set in element.IsDefinedBy:
        if hasattr(p_set, 'RelatingPropertyDefinition'):
            name = p_set.RelatingPropertyDefinition.Name
            props = []
            if hasattr(p_set.RelatingPropertyDefinition, 'HasProperties'):
                for p in p_set.RelatingPropertyDefinition.HasProperties:
                    props.append(p.Name)
                sets['Property_Sets'][name] = props
            elif hasattr(p_set.RelatingPropertyDefinition, 'Quantities'):
                for p in p_set.RelatingPropertyDefinition.Quantities:
                    props.append(p.Name)
                sets['Quantity_Sets'][name] = props
    return sets


def get_property(element, property_set, property_name):
    data = None
    for PropertySet in element.IsDefinedBy:
        if PropertySet.RelatingPropertyDefinition.Name == property_set:
            if hasattr(PropertySet.RelatingPropertyDefinition, 'HasProperties'):
                for Property in PropertySet.RelatingPropertyDefinition.HasProperties:
                    if Property.Name == property_name:
                        data = Property
                        break
            if hasattr(PropertySet.RelatingPropertyDefinition, 'Quantities'):
                for Property in PropertySet.RelatingPropertyDefinition.Quantities:
                    if Property.Name == property_name:
                        data = Property
                        break

    return data


def get_set(element, property_set):
    data = None
    for PropertySet in element.IsDefinedBy:
        if PropertySet.RelatingPropertyDefinition.Name == property_set:
            data = PropertySet.RelatingPropertyDefinition

    return data


def ifc_instance_overwriter(element, property_set, property_name, value, ifc_file, target_path):
    """modifies the IfcProperty of a selected Instance, and creates a new ifc file with those changes"""
    ifc_switcher = {bool: 'IfcBoolean',
                    str: 'IfcText',
                    float: 'IfcReal',
                    int: 'IfcInteger'}
    quantity_switcher = {'Volume': ifc_file.createIfcQuantityVolume,
                         'Area': ifc_file.createIfcQuantityArea,
                         'Length': ifc_file.createIfcQuantityLength}

    owner_history = ifc_file.by_type("IfcOwnerHistory")[0]
    sets = get_all_property_sets(element)
    type_value_in_element = ifc_switcher.get(type(value))

    # quantity set overwrite
    if property_set in sets['Quantity_Sets']:
        # property overwrite:
        if property_name in sets['Quantity_Sets'][property_set]:
            property_to_edit = get_property(element, property_set, property_name)
            for attr, value in vars(property_to_edit).items():
                if attr.endswith('Value'):
                    attr_to_edit = attr
                    break
            setattr(property_to_edit, attr_to_edit, value)
        # new property
        else:
            set_to_edit = get_set(element, property_set)
            quantity_function = ifc_file.createIfcQuantityLength
            for dimension in quantity_switcher:
                if dimension in property_name:
                    quantity_function = quantity_switcher.get(dimension, ifc_file.createIfcQuantityLength)
                new_quantity = quantity_function(property_name, None, None, value)
                edited_quantities_set = list(set_to_edit.Quantities)
                edited_quantities_set.append(new_quantity)
                set_to_edit.Quantities = tuple(edited_quantities_set)
    # property set overwrite
    elif property_set in sets['Property_Sets']:
        # property overwrite:
        if property_name in sets['Property_Sets'][property_set]:
            property_to_edit = get_property(element, property_set, property_name)
            try:
                property_to_edit.NominalValue.wrappedValue = value
            except ValueError:  # double, boolean, etc error
                pass
        # new property
        else:
            set_to_edit = get_set(element, property_set)
            new_property = ifc_file.createIfcPropertySingleValue(
                property_name, None, ifc_file.create_entity(type_value_in_element, value),
                None)
            edited_properties_set = list(set_to_edit.HasProperties)
            edited_properties_set.append(new_property)
            set_to_edit.HasProperties = tuple(edited_properties_set)
    #new property set, new property
    else:
        new_property = ifc_file.createIfcPropertySingleValue(
            property_name, None, ifc_file.create_entity(type_value_in_element, value),
            None)
        new_properties_set = ifc_file.createIfcPropertySet(create_guid(), owner_history,
                                                           property_set, None, [new_property])
        ifc_file.createIfcRelDefinesByProperties(create_guid(), owner_history, None, None,
                                                 [element], new_properties_set)

    # ifc_file.write(target_path)


def create_guid():
    return ifcopenshell.guid.compress(uuid.uuid1().hex)


def get_source_tool(instance):
    source_tool = None
    if hasattr(instance, 'source_tool'):
        if instance.source_tool.startswith('Autodesk'):
            source_tool = 'Autodesk Revit 2019 (DEU)'
        elif instance.source_tool.startswith('ARCHICAD'):
            source_tool = 'ARCHICAD-64'
        else:
            instance.logger.warning('No source tool for the ifc file found')
    return source_tool

# def property_set_editer(PropertyList, element):
#     """returns the necessary parameters for the afterwards edition of a given property-set, property-name couple
#     * Property Set doesnt exists -> returns None
#     * Property doesnt exists -> returns property set
#     * Property exists -> return Property"""
#
#     PropertySetName = PropertyList[0]
#     PropertyName = PropertyList[1]
#     has_property_set = False
#     has_property = False
#     data = None
#     is_quantity = False
#     if 'Quantities' in PropertySetName:
#         is_quantity = True
#
#     AllPropertySetsList = element.IsDefinedBy
#     for PropertySet in AllPropertySetsList:
#         if PropertySet.RelatingPropertyDefinition.Name == PropertySetName:
#             has_property_set = True
#             if hasattr(PropertySet.RelatingPropertyDefinition, 'HasProperties'):
#                 data = PropertySet.RelatingPropertyDefinition
#                 is_quantity = False
#                 for Property in PropertySet.RelatingPropertyDefinition.HasProperties:
#                     if Property.Name == PropertyName:
#                         has_property = True
#                         data = Property
#                         break
#             if hasattr(PropertySet.RelatingPropertyDefinition, 'Quantities'):
#                 data = PropertySet.RelatingPropertyDefinition
#                 is_quantity = True
#                 for Property in PropertySet.RelatingPropertyDefinition.Quantities:
#                     if Property.Name == PropertyName:
#                         has_property = True
#                         data = Property
#                         break
#                 # property doesnt exist, returns set
#
#     return has_property_set, has_property, is_quantity, data
#
#
# def ifc_property_writer(instance, ifc_file):
#     """Check an ifc instance, whose properties have been modified,
#     and overwrite this changes on the ifc file"""
#
#     ifc_switcher = {bool: 'IfcBoolean',
#                     str: 'IfcText',
#                     float: 'IfcReal',
#                     int: 'IfcInteger'}
#     quantity_switcher = {'Volume': ifc_file.createIfcQuantityVolume,
#                          'Area': ifc_file.createIfcQuantityArea,
#                          'Length': ifc_file.createIfcQuantityLength}
#     owner_history = ifc_file.by_type("IfcOwnerHistory")[0]
#
#     # find properties and quantity sets
#     source_tool = get_source_tool(instance)
#     if source_tool is not None:
#         if instance.__class__.__name__ in instance.finder.templates[source_tool]:
#             default_ps = instance.finder.templates[source_tool][instance.__class__.__name__]['default_ps']
#             for key, def_ps in default_ps.items():
#                 if hasattr(instance, key):
#                     value_in_element = getattr(instance, key)
#                     type_value_in_element = ifc_switcher.get(type(value_in_element))
#                     if value_in_element is not None:
#                         has_set, has_property, is_quantity, property_to_edit = property_set_editer(def_ps, instance.ifc)
#                         if is_quantity:
#                             if has_property:
#                                 for attr, value in vars(property_to_edit).items():
#                                     if attr.endswith('Value'):
#                                         attr_to_edit = attr
#                                 setattr(property_to_edit, attr_to_edit, value_in_element)
#                             # new quantity creation
#                             else:
#                                 # property_creation function
#                                 quantity_function = ifc_file.createIfcQuantityLength
#                                 for dimension in quantity_switcher:
#                                     if dimension in def_ps[1]:
#                                         quantity_function = quantity_switcher.get(dimension)
#                                         break
#                                 new_quantity = quantity_function(def_ps[1], None, None, value_in_element)
#                                 if has_set:
#                                     edited_quantities_set = list(property_to_edit.Quantities)
#                                     edited_quantities_set.append(new_quantity)
#                                     property_to_edit.Quantities = tuple(edited_quantities_set)
#                                 else:
#                                     new_quantities_set = ifc_file.createIfcElementQuantity(create_guid(), owner_history,
#                                                                                            def_ps[0], None, None,
#                                                                                            [new_quantity])
#                                     ifc_file.createIfcRelDefinesByProperties(create_guid(), owner_history, None, None,
#                                                                              [instance.ifc], new_quantities_set)
#                         else:
#                             if has_property:
#                                 try:
#                                     property_to_edit.NominalValue.wrappedValue = value_in_element
#                                 except ValueError:  # double, boolean, etc error
#                                     pass
#                             # new property creation
#                             else:
#                                 new_property = ifc_file.createIfcPropertySingleValue(
#                                     def_ps[1], None, ifc_file.create_entity(type_value_in_element, value_in_element),
#                                     None)
#                                 if has_set:
#                                     edited_properties_set = list(property_to_edit.HasProperties)
#                                     edited_properties_set.append(new_property)
#                                     property_to_edit.HasProperties = tuple(edited_properties_set)
#                                 else:
#                                     new_properties_set = ifc_file.createIfcPropertySet(create_guid(), owner_history,
#                                                                                        def_ps[0], None, [new_property])
#                                     ifc_file.createIfcRelDefinesByProperties(create_guid(), owner_history, None, None,
#                                                                              [instance.ifc], new_properties_set)



# def material_editer(element):
#     material = ()
#
#     for i in element.HasAssociations:
#         if hasattr(i, 'RelatingMaterial'):
#             material = i.RelatingMaterial
#             material_switcher = {'Materials': None,
#                                  'MaterialConstituents': 'ToMaterialConstituentSet',
#                                  'ForLayerSet': 'MaterialLayers',
#                                  'MaterialLayers': None,
#                                  'ForProfileSet': 'MaterialProfiles',
#                                  'MaterialProfiles': None}
#
#             for k in material_switcher:
#                 if hasattr(i.RelatingMaterial, k):
#                     material = getattr(material, k)
#                     if type(material) is not tuple:
#                         material = getattr(material, material_switcher[k])
#                     break
#
#     if type(material) is not tuple and material is not None:
#         material = [material]
#         material = tuple(material)
#
#     return material

# def material_property_finder(PropertyList, material):
#     PropertySetName = PropertyList[0]
#     PropertyName = PropertyList[1]
#     has_property_set = False
#     has_property = False
#     data = None
#
#     if hasattr(material, 'HasProperties'):
#         for PropertySet in material.HasProperties:
#             if PropertySet.Name == PropertySetName:
#                 has_property_set = True
#                 if hasattr(PropertySet, 'Properties'):
#                     data = PropertySet.Properties
#                     for Property in PropertySet.Properties:
#                         if Property.Name == PropertyName:
#                             has_property = True
#                             data = Property
#                             break
#
#     return has_property_set, has_property, data


# def ifc_material_writer(instance, ifc_file):
#     """Check a material of an instance, whose properties have been modified,
#     and overwrite this changes on the ifc file"""
#
#     ifc_switcher = {bool: 'IfcBoolean',
#                     str: 'IfcText',
#                     float: 'IfcReal',
#                     int: 'IfcInteger'}
#     materials = material_editer(instance.ifc)
#     source_tool = get_source_tool(instance)
#
#     for i in materials:
#         material = i
#         if hasattr(i, 'Material'):
#             material = i.Material
#         if source_tool is not None:
#             default_ps = instance.finder.templates[source_tool]['Material']['default_ps']
#             for key, def_ps in default_ps.items():
#                 value_in_element = 2.455555 #'to further development'
#                 type_value_in_element = ifc_switcher.get(type(value_in_element))
#                 if value_in_element is not None:
#                     has_set, has_property, property_to_edit = material_property_finder(def_ps, material)
#                     if has_property:
#                         try:
#                             property_to_edit.NominalValue.wrappedValue = value_in_element
#                         except ValueError:  # double, boolean, etc error
#                             pass
#                     else:
#                         new_property = ifc_file.createIfcPropertySingleValue(
#                             def_ps[1], None, ifc_file.create_entity(type_value_in_element, value_in_element), None)
#                         if has_set:
#                             edited_properties_set = list(property_to_edit.Properties)
#                             edited_properties_set.append(new_property)
#                             property_to_edit.Properties = tuple(edited_properties_set)
#                         else:
#                             new_material_properties = ifc_file.createIfcMaterialProperties(
#                                 def_ps[0], None, [new_property])
#                             # edited_material_properties = list(material.HasProperties)
#                             # edited_material_properties.append(new_material_properties)
#                             # setattr(material, 'HasProperties', edited_material_properties)












