"""Definition for basic representations of IFC elements"""

import logging
import numpy as np

from bim2sim.ifc2python import ifc2python

# TODO: Ports, Connections

class Port():
    """"""

    def __init__(self, parent, ifcport):

        # self.name = name
        # todo @christian: if we have the ifcguid as
        #  unique id, to we need a name as well?
        self.parent = parent
        self.ifc_port = ifcport
        self.connections = []

    def connect(self, other):
        """Connect this interface to another interface"""
        assert isinstance(other, self.__class__), "Can't connect interfaces of different classes."
        self.connections.append(other)

    @property
    def position(self):
        """returns absolute position"""
        raise NotImplementedError # TODO
        rel = np.array(self.ifc_port.ObjectPlacement.RelativePlacement.Location.Coordinates)
        rel_to = np.array(self.ifc_port.ObjectPlacement.PlacementRelTo.RelativePlacement.Location.Coordinates)
        return

    def __repr__(self):
        return "<%s (%s)>"%(self.__class__.__name__, self.name)

class Element():
    """Base class for IFC model representation"""

    _ifc_type = None
    _ifc_classes = {}
    dummy = None

    def __init__(self, ifc):
        self.logger = logging.getLogger(__name__)
        self.ifc = ifc
        self.guid = ifc.GlobalId
        self.name = ifc.Name

        self.ports = [] #TODO

    def add_ports(self):
        element_port_connections = self.ifc.HasPorts
        for element_port_connection in element_port_connections:
            self.ports.append(Port(self, element_port_connection.RelatingPort))

    @staticmethod
    def _init_factory():
        """initialize lookup for factory"""
        logger = logging.getLogger(__name__)
        conflict = False
        for cls in Element.__subclasses__():
            if cls.ifc_type is None:
                conflict = True
                logger.error("Invalid ifc_type (%s) in '%s'", cls.ifc_type, cls.__name__)
            elif cls.ifc_type in Element._ifc_classes:
                conflict = True
                logger.error("Conflicting ifc_types (%s) in '%s' and '%s'", \
                    cls.ifc_type, cls.__name__, Element._ifc_classes[cls.ifc_type])
            elif cls.__name__ == "Dummy":
                Element.dummy = cls
            elif not cls.ifc_type.lower().startswith("ifc"):
                conflict = True
                logger.error("Invalid ifc_type (%s) in '%s'", cls.ifc_type, cls.__name__)
            else:
                Element._ifc_classes[cls.ifc_type] = cls

        if conflict:
            raise AssertionError("Conflict(s) in Models. (See log for details).")

        #Model.dummy = Model.ifc_classes['any']

        logger.debug("IFC model factory intitialized with %d models:", len(Element._ifc_classes))
        for model in Element._ifc_classes:
            logger.debug("- %s", model)

    @staticmethod
    def factory(ifc_element):
        """Create model depending on ifc_element"""

        if not Element._ifc_classes:
            Element._init_factory()

        ifc_type = ifc_element.is_a()
        cls = Element._ifc_classes.get(ifc_type, Element.dummy)
        #if cls is Model.dummy:
        #    logger = logging.getLogger(__name__)
        #    logger.warning("Did not found matching class for %s", ifc_type)

        return cls(ifc_element)

    @property
    def ifc_type(self):
        """Returns IFC type"""
        return self.__class__._ifc_type

    @property
    def position(self):
        """returns absolute position"""
        raise NotImplementedError # TODO

    def get_ifc_attribute(self, attribute):
        """
        Fetches non-empty attributes (if they exist).
        """
        try:
            return getattr(self.ifc, attribute)
        except AttributeError:
            pass

    def get_propertysets(self, propertysetname):
        return ifc2python.get_Property_Sets(propertysetname, self.ifc)

    def get_hierarchical_parent(self):
        return ifc2python.getHierarchicalParent(self.ifc)

    def get_hierarchical_children(self):
        return ifc2python.getHierarchicalChildren(self.ifc)

    def get_spartial_parent(self):
        return ifc2python.getSpatialParent(self.ifc)

    def get_spartial_children(self):
        return ifc2python.getSpatialChildren(self.ifc)

    def get_space(self):
        return ifc2python.getSpace(self.ifc)

    def get_storey(self):
        return ifc2python.getStorey(self.ifc)

    def get_building(self):
        return ifc2python.getBuilding(self.ifc)

    def get_site(self):
        return ifc2python.getSite(self.ifc)

    def get_project(self):
        return ifc2python.getProject(self.ifc)

    def __repr__(self):
        return "<%s (%s)>"%(self.__class__.__name__, self.name)



class Dummy(Element):
    """Dummy for all unknown elements"""
    #ifc_type = 'any'

    def __init__(self, ifc):
        super().__init__(ifc)

        self._ifc_type = ifc.get_info()['type']

    @property
    def ifc_type(self):
        return self._ifc_type

