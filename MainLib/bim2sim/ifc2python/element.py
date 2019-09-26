"""Definition for basic representations of IFC elements"""

import logging
from json import JSONEncoder
import itertools

import numpy as np

from bim2sim.decorators import cached_property
from bim2sim.ifc2python import ifc2python





class ElementError(Exception):
    """Error in Element"""


class ElementEncoder(JSONEncoder):
    """Encoder class for Element"""
    #TODO: make Elements serializable and deserializable.
    # Ideas: guid to identify, (factory) method to (re)init by guid
    # mayby weakref to other elements (Ports, connections, ...)

    def default(self, o):
        if isinstance(o, Element):
            return "<Element(%s)>"%(o.guid)
        return JSONEncoder.default()


class Root:
    """Most basic class

    keeps track of created instances and guids"""
    objects = {}
    _id_counter = 0

    def __init__(self, guid=None):
        self.guid = guid or self.get_id()
        Root.objects[self.guid] = self

    def __hash__(self):
        return hash(self.guid)

    def calc_position(self):
        """Returns position (calculation may be expensive)"""
        return None

    @cached_property
    def position(self):
        """Position

        calculated only once by calling calc_position"""
        return self.calc_position()

    @staticmethod
    def get_id(prefix=""):
        prefix_length = len(prefix)
        if prefix_length > 8:
            raise AttributeError("Max prefix legth is 8!")
        Root._id_counter += 1
        return "{0:0<8s}{1:0>14d}".format(prefix, Root._id_counter)

    @staticmethod
    def get_object(guid):
        """Returns object by guid"""
        return Root.objects.get(guid)


class IFCBased(Root):
    """Mixin for all IFC representating classes"""
    ifc_type = None
    _ifc_classes = {}

    def __init__(self, ifc, *args, **kwargs):
        super().__init__(*args, guid=ifc.GlobalId, **kwargs)
        self.ifc = ifc
        self.name = ifc.Name

    @property
    def ifc_type(self):
        """Returns IFC type"""
        return self.__class__.ifc_type

    def calc_position(self):
        """returns absolute position"""
        rel = np.array(self.ifc.ObjectPlacement.
                       RelativePlacement.Location.Coordinates)
        relto = np.array(self.ifc.ObjectPlacement.
                         PlacementRelTo.RelativePlacement.Location.Coordinates)
        return rel + relto

    def get_ifc_attribute(self, attribute):
        """
        Fetches non-empty attributes (if they exist).
        """
        return getattr(self.ifc, attribute, None)

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

    def summary(self):
        return ifc2python.summary(self.ifc)

    def __repr__(self):
        return "<%s (%s)>"%(self.__class__.__name__, self.name)


class BaseElement(Root):
    """Base class for all elements with ports"""
    objects = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        BaseElement.objects[self.guid] = self
        self.logger = logging.getLogger(__name__)
        self.ports = []
        self.aggregation = None

    def get_inner_connections(self):
        """Returns inner connections of Element

        by default each port is connected to each other port.
        Overwrite for other connections"""

        connections = []
        for port0, port1 in itertools.combinations(self.ports, 2):
            connections.append((port0, port1))
        return connections

    @staticmethod
    def get_element(guid):
        return BaseElement.objects.get(guid)

    def __repr__(self):
        return "<%s (ports: %d)>"%(self.__class__.__name__, len(self.ports))


class BasePort(Root):
    """Basic port"""
    objects = {}

    def __init__(self, parent, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent = parent
        self.connection = None
        BasePort.objects[self.guid] = self

    @staticmethod
    def get_port(guid):
        return BasePort.objects.get(guid)

    def connect(self, other):
        """Connect this interface bidirectional to another interface"""
        assert isinstance(other, BasePort), "Can't connect interfaces" \
                                                  " of different classes."
        # if self.flow_direction == 'SOURCE' or \
        #         self.flow_direction == 'SOURCEANDSINK':
        if self.connection:
            raise AttributeError("Port is already connected!")
        self.connection = other
        other.connection = self

    def is_connected(self):
        """Returns truth value of port's connection"""
        return bool(self.connection)

    def __repr__(self):
        if self.parent:
            try:
                idx = self.parent.ports.index(self)
                return "<%s (#%d, parent: %s)>"%(
                    self.__class__.__name__, idx, self.parent)
            except ValueError:
                return "<%s (broken parent: %s)>"%(
                    self.__class__.__name__, self.parent)
        return "<%s (*abandoned*)>"%(self.__class__.__name__)


class Port(BasePort, IFCBased):
    """Port of Element"""

    @cached_property
    def flow_direction(self):
        """returns the flow direction"""
        return self.ifc.FlowDirection

    def calc_position(self):
        """returns absolute position as np.array"""
        try:
            relative_placement = \
                self.parent.ifc.ObjectPlacement.RelativePlacement
            x_direction = np.array(relative_placement.RefDirection.DirectionRatios)
            z_direction = np.array(relative_placement.Axis.DirectionRatios)
        except AttributeError:
            x_direction = np.array([1, 0, 0])
            z_direction = np.array([0, 0, 1])
        y_direction = np.cross(z_direction, x_direction)
        directions = np.array((x_direction, y_direction, z_direction)).T
        port_coordinates_relative = \
            np.array(self.ifc.ObjectPlacement.RelativePlacement.Location.Coordinates)
        coordinates = self.parent.position + np.matmul(directions, port_coordinates_relative)

        return coordinates


class ElementMeta(type):
    """Metaclass or Element

    catches class creation and lists all properties (and subclasses) as findables
    for Element.finder. Class can use custom findables by providung the
    attribute 'findables'."""

    def __new__(cls, clsname, superclasses, attributedict):
        if clsname != 'Element':
            sc_element = [sc for sc in superclasses if sc is Element]
            if sc_element:
                findables = []
                overwrite = True
                for name, value in attributedict.items():
                    if name == 'findables':
                        overwrite = False
                        break
                    if isinstance(value, property):
                        findables.append(name)
                if overwrite:
                    attributedict['findables'] = tuple(findables)
        return type.__new__(cls, clsname, superclasses, attributedict)


class Element(BaseElement, IFCBased, metaclass=ElementMeta):
    """Base class for IFC model representation

    WARNING: getting an not defined attribute from instances of Element will
    return None (from finder) instead of rasing an AttributeError"""

    dummy = None
    finder = None
    findables = ()

    def __init__(self, *args, tool=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._tool = tool
        self._add_ports()

    def __getattr__(self, name):
        # user finder to get attribute
        if self.__class__.finder:
            return self.__class__.finder.find(self, name)
        return super().__getattr__(name)

    def __getattribute__(self, name):
        found = object.__getattribute__(self, name)
        if found is None:
            findables = object.__getattribute__(self, '__class__').findables
            if name in findables:
                # if None is returned ask finder for value
                # (on AttributeError __getattr__ is called anyway)
                try:
                    found = object.__getattribute__(self, '__getattr__')(name)
                except AttributeError:
                    pass
        return found

    def _add_ports(self):
        if not self.ifc.HasPorts:
            # valid for IFC for Revit v19.2.0.0
            element_port_connections = self.ifc.IsNestedBy[0].RelatedObjects
            for element_port_connection in element_port_connections:
                self.ports.append(Port(parent=self, ifc=element_port_connection))
        else:
            # valid for IFC for Revit v19.1.0.0
            element_port_connections = self.ifc.HasPorts
            for element_port_connection in element_port_connections:
                self.ports.append(Port(parent=self, ifc=element_port_connection.RelatingPort))

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
                logger.error("Conflicting ifc_types (%s) in '%s' and '%s'",
                    cls.ifc_type, cls.__name__, Element._ifc_classes[cls.ifc_type])
            elif cls.__name__ == "Dummy":
                Element.dummy = cls
            elif not cls.ifc_type.lower().startswith("ifc"):
                conflict = True
                logger.error("Invalid ifc_type (%s) in '%s'", cls.ifc_type,
                             cls.__name__)
            else:
                Element._ifc_classes[cls.ifc_type] = cls

        if conflict:
            raise AssertionError("Conflict(s) in Models. (See log for details).")

        #Model.dummy = Model.ifc_classes['any']
        if not Element._ifc_classes:
            raise ElementError("Failed to initialize Element factory. No elements found!")

        model_txt = "\n".join(" - %s"%(model) for model in Element._ifc_classes)
        logger.debug("IFC model factory initialized with %d ifc classes:\n%s",
                     len(Element._ifc_classes), model_txt)

    @staticmethod
    def factory(ifc_element, tool=None):
        """Create model depending on ifc_element"""

        if not Element._ifc_classes:
            Element._init_factory()

        ifc_type = ifc_element.is_a()
        cls = Element._ifc_classes.get(ifc_type, Element.dummy)
        if cls is Element.dummy:
            logger = logging.getLogger(__name__)
            logger.warning("Did not found matching class for %s", ifc_type)

        return cls(ifc=ifc_element, tool=tool)

    @property
    def source_tool(self):
        """Name of tool the ifc has been created with"""
        if not self._tool:
            self._tool = self.get_project().OwnerHistory.OwningApplication.ApplicationFullName
        return self._tool

    @property
    def neighbors(self):
        """Directly connected elements"""
        neighbors = []
        for port in self.ports:
            neighbors.append(port.connection.parent)
        return neighbors

    def __repr__(self):
        return "<%s (ports: %d, guid=%s)>"%(
            self.__class__.__name__, len(self.ports), self.guid)


class Dummy(Element):
    """Dummy for all unknown elements"""
    #ifc_type = 'any'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._ifc_type = self.ifc.get_info()['type']

    @property
    def ifc_type(self):
        return self._ifc_type

# import Element classes for Element.factory
import bim2sim.ifc2python.elements
