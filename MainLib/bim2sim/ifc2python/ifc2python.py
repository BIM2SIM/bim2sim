'''Module for loading ifc files

Holds logic for target simulation independent file parsing, checking, and data enrichment
'''
import ifcopenshell

# various functions to get additional information on building elements ...
#
def getIfcAttribute(ifcElement, attribute):
    '''Fetches non-empty attributes (if they exist).'''
    try:
        return getattr(ifcElement, attribute)
    except AttributeError:
        pass


def checkIfcElementType(ifcElement, ifcType):
    '''Checks for matching IFC element types.'''
    if getIfcAttribute(ifcElement, 'is_a'):
        return ifcElement.is_a() == ifcType


def getHierarchicalParent(ifcElement):
    '''Fetch the first structural parent element.'''
    parent = getIfcAttribute(ifcElement, 'Decomposes')
    if parent:
        return parent[0].RelatingObject
    # ... try again for voids:
    parent = getIfcAttribute(ifcElement, 'VoidsElements')
    if parent:
        return parent[0].RelatingBuildingElement


def getHierarchicalChildren(ifcElement):
    '''Fetch the child elements from the first structural aggregation.'''
    children = getIfcAttribute(ifcElement, 'IsDecomposedBy')
    if children:
        return children[0].RelatedObjects
    # ... try again for voids:
    children = getIfcAttribute(ifcElement, 'HasOpenings')
    if children:
        # just get the voids, not the relations
        return [i.RelatedOpeningElement for i in children]


def getSpatialParent(ifcElement):
    '''Fetch the first spatial parent element.'''
    parent = getIfcAttribute(ifcElement, 'ContainedInStructure')
    if parent:
        return parent[0].RelatingStructure


def getSpatialChildren(ifcElement):
    '''Fetch the child elements from the first spatial structure.'''
    children = getIfcAttribute(ifcElement, 'ContainsElements')
    if children:
        return children[0].RelatedElements


def getSpace(ifcElement):
    '''Find the space for this element.'''
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
    '''Find the building storey for this element.'''
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
    '''Find the building for this element.'''
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
    '''Find the building site for this element.'''
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
    '''Find the project/root for this element.'''
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


def convertToSI(ifcUnit, value):
    '''Return the value in basic SI units, conversion according to ifcUnit.'''
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
