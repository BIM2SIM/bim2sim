import os
import logging

from bim2sim.ifc2python import ifc2python

# TODO: Ports, Connections

class Port():
    """"""

    def __init__(self, name, parent):

        self.name = name
        self.parent = parent

        self.connections = []

    def connect(self, other):
        """Connect this interface to another interface"""
        assert isinstance(other, self.__class__), "Can't connect interfaces of different classes."
        self.connections.append(other)

    def __repr__(self):
        return "<%s (%s)>"%(self.__class__.__name__, self.name)

class Element():
    """Base class for IFC model representation"""

    ifc_type = None
    ifc_classes = {}
    dummy = None

    def __init__(self, ifc):
        self.logger = logging.getLogger(__name__)
        self.ifc = ifc
        self.GUID = ifc.GlobalId
        self.name = ifc.Name

        self.ports = [] #TODO

    @staticmethod
    def _init_factory():
        """initialize lookup for factory"""
        logger = logging.getLogger(__name__)
        conflict = False
        for cls in Element.__subclasses__():
            if cls.ifc_type is None:
                conflict = True
                logger.error("Invalid ifc_type (%s) in '%s'", cls.ifc_type, cls.__name__)
            elif cls.ifc_type in Element.ifc_classes:
                conflict = True
                logger.error("Conflicting ifc_types (%s) in '%s' and '%s'", \
                    cls.ifc_type, cls.__name__, Element.ifc_classes[cls.ifc_type])
            elif cls.__name__ == "Dummy":
                Element.dummy = cls
            elif not cls.ifc_type.lower().startswith("ifc"):
                conflict = True
                logger.error("Invalid ifc_type (%s) in '%s'", cls.ifc_type, cls.__name__)
            else:
                Element.ifc_classes[cls.ifc_type] = cls

        if conflict:
            raise AssertionError("Conflict(s) in Models. (See log for details).")

        #Model.dummy = Model.ifc_classes['any']

        logger.debug("IFC model factory intitialized with %d models:", len(Element.ifc_classes))
        for model in Element.ifc_classes.keys():
            logger.debug("- %s", model)

    @staticmethod
    def factory(ifc_element):
        """Create model depending on ifc_element"""

        if not Element.ifc_classes:
            Element._init_factory()

        ifc_type = ifc_element.get_info()['type'] # TODO: should be accessible directly by ifc_element??
        cls = Element.ifc_classes.get(ifc_type, Element.dummy)
        #if cls is Model.dummy:
        #    logger = logging.getLogger(__name__)
        #    logger.warning("Did not found matching class for %s", ifc_type)

        return cls(ifc_element)

    @property
    def ifc_type(self):
        return self.__class__.ifc_type

    def getifcattribute(self, attribute):
        """
        Fetches non-empty attributes (if they exist).
        """
        try:
            return getattr(self.ifc, attribute)
        except AttributeError:
            pass

    def getpropertysets(self, propertysetname):
        return ifc2python.get_Property_Sets(propertysetname, self.ifc)

    def gethierarchicalparent(self):
        return ifc2python.getHierarchicalParent(self.ifc)

    def gethierarchicalchildren(self):
        return ifc2python.getHierarchicalChildren(self.ifc)

    def getspartialparent(self):
        return ifc2python.getSpatialParent(self.ifc)

    def getspartialchildren(self):
        return ifc2python.getSpatialChildren(self.ifc)

    def getspace(self):
        return ifc2python.getSpace(self.ifc)

    def getstorey(self):
        return ifc2python.getStorey(self.ifc)

    def getbuilding(self):
        return ifc2python.getBuilding(self.ifc)

    def getsite(self):
        return ifc2python.getSite(self.ifc)

    def getproject(self):
        return ifc2python.getProject(self.ifc)

    def __repr__(self):
        return "<%s (%s)>"%(self.__class__.__name__, self.name)



class Dummy(Element):

    #ifc_type = 'any'

    def __init__(self, ifc):
        super().__init__(ifc)
        
        self._ifc_type = ifc.get_info()['type']

    @property
    def ifc_type(self):
        return self._ifc_type

