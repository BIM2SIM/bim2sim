"""Definition for basic representations of IFC elements"""

import logging
from json import JSONEncoder
import itertools
import re

import numpy as np

from bim2sim.decorators import cached_property
from bim2sim.kernel import ifc2python, attribute
from bim2sim.decision import Decision
from bim2sim.task.common.common_functions import angle_equivalent, vector_angle
from bim2sim.kernel.finder import TemplateFinder

logger = logging.getLogger(__name__)


class ElementError(Exception):
    """Error in Element"""


class NoValueError(ElementError):
    """Value is not available"""


class ElementEncoder(JSONEncoder):
    """Encoder class for Element"""

    # TODO: make Elements serializable and deserializable.
    # Ideas: guid to identify, (factory) method to (re)init by guid
    # mayby weakref to other elements (Ports, connections, ...)

    def default(self, o):
        if isinstance(o, Element):
            return "<Element(%s)>" % (o.guid)
        return JSONEncoder.default()


class Root(metaclass=attribute.AutoAttributeNameMeta):
    """Most basic class

    keeps track of created instances and guids"""
    objects = {}
    _id_counter = 0

    def __init__(self, guid=None):
        self.guid = guid or self.get_id()
        Root.objects[self.guid] = self
        self.related_decisions = []
        self.attributes = attribute.AttributeManager(bind=self)

    def __hash__(self):
        return hash(self.guid)

    def calc_position(self):
        """Returns position (calculation may be expensive)"""
        return None

    def calc_orientation(self):
        """Returns position (calculation may be expensive)"""
        return None

    @cached_property
    def position(self):
        """Position calculated only once by calling calc_position"""
        return self.calc_position()

    @cached_property
    def orientation(self):
        return self.calc_orientation()

    @staticmethod
    def get_id(prefix=""):
        prefix_length = len(prefix)
        if prefix_length > 8:
            raise AttributeError("Max prefix length is 8!")
        Root._id_counter += 1
        return "{0:0<8s}{1:0>14d}".format(prefix, Root._id_counter)

    @staticmethod
    def get_object(guid):
        """Get Root object instance with given guid

        :returns: None if object with guid was not instanciated"""
        return Root.objects.get(guid)

    def request(self, name):
        self.attributes.request(name)

    def solve_requested_decisions(self=None):
        """Solve all requested decisions.
        If called by instance, all instance related decisions are solved
        else all decisions of all instances are solved."""
        if not self:
            # called from class
            related_decisions = []
            for obj in Root.objects.values():
                related_decisions.extend(obj.related_decisions)
            Decision.decide_collected(collection=set(related_decisions))
        else:
            # called from instance
            Decision.decide_collected(collection=self.related_decisions)

    def discard(self):
        """Remove from tracked objects. Related decisions are also discarded."""
        del Root.objects[self.guid]
        for d in self.related_decisions:
            d.discard()


class IFCBased(Root):
    """Mixin for all IFC representating classes"""
    ifc_type = None
    predefined_type = None
    _ifc_classes = {}
    pattern_ifc_type = []
    finder = TemplateFinder()

    def __init__(self, ifc, *args, **kwargs):
        if hasattr(ifc, 'GlobalId'):
            super().__init__(*args, guid=ifc.GlobalId, **kwargs)
        # subelement can be an ifc instance that doesnt have a GlobalId
        else:
            super().__init__(*args, guid=self.get_id(type(self).__name__), **kwargs)

        self.ifc = ifc
        # todo to reduce decision querys we should only do this for needed names like Building or projectname
        if ifc is not None:
            if ifc.Name is not None:
                if len(ifc.Name) > 0:
                    self.name = ifc.Name
                else:
                    self.name = input("Please enter name for the instance %s"
                                      % type(self).__name__)
        self.predefined_type = ifc2python.get_predefined_type(ifc)
        self.enrichment = {}
        self._propertysets = None
        self._type_propertysets = None

        self._decision_results = {}

    def calc_position(self):
        """returns absolute position"""
        if hasattr(self.ifc, 'ObjectPlacement'):
            absolute = np.array(self.ifc.ObjectPlacement.RelativePlacement.Location.Coordinates)
            placementrel = self.ifc.ObjectPlacement.PlacementRelTo
            while placementrel is not None:
                absolute += np.array(placementrel.RelativePlacement.Location.Coordinates)
                placementrel = placementrel.PlacementRelTo
        else:
            absolute = None

        return absolute

    def calc_orientation(self):
        # ToDO: true north angle
        switcher = {'Slab': -1,
                    'Roof': -1,
                    'Floor': -2,
                    'GroundFloor': -2}
        value = switcher.get(self.__class__.__name__, 'continue')
        if value != 'continue':
            return value

        list_angles = {}
        placementrel = self.ifc.ObjectPlacement
        while placementrel is not None:
            if placementrel.RelativePlacement.RefDirection is not None:
                o2 = placementrel.RelativePlacement.RefDirection.DirectionRatios
                list_angles[placementrel.PlacesObject[0].GlobalId] = vector_angle(o2)
            else:
                list_angles[placementrel.PlacesObject[0].GlobalId] = None
            placementrel = placementrel.PlacementRelTo

        # relative vector + absolute vector
        if len(list_angles) == 1:
            if list_angles[next(iter(list_angles))] is None:
                return -90
                # return 0

        ang_sum = 0

        self_class = type(self).__name__

        if all(value is None for value in list_angles.values()) and self_class in ['Wall', 'OuterWall', 'InnerWall']:
            return 0

        for key in list_angles:
            guid = key
            ang = list_angles[key]
            relative_element = self.get_object(guid)
            if relative_element is None:
                if ang is not None:
                    ang_sum += ang
                continue
            else:
                if relative_element is self:
                    if ang is not None:
                        ang_sum += ang
                    continue
                else:
                    relative_class = type(relative_element).__name__
                    if self_class in ['Window', 'Door'] and relative_class in ['Wall', 'OuterWall', 'InnerWall']:
                        return relative_element.orientation

                    new_ang = relative_element.orientation
                    if new_ang is not None:
                        ang_sum += new_ang
                        break

        if ang_sum is None:
            return None
        # specific case windows
        if self.ifc_type == 'IfcWindow':
            ang_sum += 180

        # angle between 0 and 360
        return angle_equivalent(ang_sum)

    def get_ifc_attribute(self, attribute):
        """
        Fetches non-empty attributes (if they exist).
        """
        return getattr(self.ifc, attribute, None)

    def get_propertyset(self, propertysetname):
        return ifc2python.get_Property_Set(propertysetname, self.ifc)

    def get_propertysets(self):
        if self._propertysets is None:
            self._propertysets = ifc2python.get_property_sets(self.ifc)
        return self._propertysets

    def get_type_propertysets(self):
        if self._type_propertysets is None:
            self._type_propertysets = ifc2python.get_type_property_sets(self.ifc)
        return self._type_propertysets

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

    def get_true_north(self):
        return ifc2python.getTrueNorth(self.ifc)

    def summary(self):
        return ifc2python.summary(self.ifc)

    def search_property_hierarchy(self, propertyset_name):
        """Search for property in all related properties in hierarchical order.

        1. element's propertysets
        2. element type's propertysets"""

        p_set = None
        p_sets = self.get_propertysets()
        try:
            p_set = p_sets[propertyset_name]
        except KeyError:
            pass
        else:
            return p_set

        pt_sets = self.get_type_propertysets()
        try:
            p_set = pt_sets[propertyset_name]
        except KeyError:
            pass
        else:
            return p_set
        return p_set

    def inverse_properties(self):
        """Generator yielding tuples of PropertySet name and Property name"""
        for p_set_name, p_set in self.get_propertysets().items():
            for p_name in p_set.keys():
                yield (p_set_name, p_name)

    def filter_properties(self, patterns):
        """filter all properties by re pattern

        :returns: list of tuple(propertyset_name, property_name, match)"""
        matches = []
        for propertyset_name, property_name in self.inverse_properties():
            for pattern in patterns:
                match = re.match(pattern, property_name)
                if match:
                    matches.append((propertyset_name, property_name, match))
        return matches

    @classmethod
    def filter_for_text_fracments(cls, ifc_element, optional_locations: list = None):
        """Filter for text fracments in the ifc_element to identify the ifc_element."""
        results = []
        hits = [p.search(ifc_element.Name) for p in cls.pattern_ifc_type]
        # hits.extend([p.search(ifc_element.Description or '') for p in cls.pattern_ifc_type])
        hits = [x for x in hits if x is not None]
        if any(hits):
            logger = logging.getLogger('IFCModelCreation')
            logger.info("Identified %s through text fracments in name. Criteria: %s", cls.ifc_type, hits)
            results.append(hits[0][0])
            # return hits[0][0]
        if optional_locations:
            for loc in optional_locations:
                hits = [p.search(ifc2python.get_Property_Set(loc, ifc_element) or '') for p in cls.pattern_ifc_type
                        if ifc2python.get_Property_Set(loc, ifc_element)]
                hits = [x for x in hits if x is not None]
                if any(hits):
                    logger = logging.getLogger('IFCModelCreation')
                    logger.info("Identified %s through text fracments in %s. Criteria: %s", cls.ifc_type, loc, hits)
                    results.append(hits[0][0])
        return results if results else ''

    def get_exact_property(self, propertyset_name, property_name):
        """Returns value of property specified by propertyset name and property name

        :Raises: AttributeError if property does not exist"""
        self.search_property_hierarchy(propertyset_name)
        try:
            p_set = self.search_property_hierarchy(propertyset_name)
            value = p_set[property_name]
        except (AttributeError, KeyError, TypeError):
            raise NoValueError("Property '%s.%s' does not exist" % (
                propertyset_name, property_name))
        return value

    def get_exact_association(self, propertyset_name, property_name):
        """Returns value of property specified by propertyset name and property name

        :Raises: AttriebuteError if property does not exist"""
        try:
            p_set = self.search_property_hierarchy(propertyset_name)
            value = p_set[property_name]
        except (AttributeError, KeyError, TypeError):
            raise NoValueError("Property '%s.%s' does not exist" % (
                propertyset_name, property_name))
        return value

    def select_from_potential_properties(self, patterns, name,
                                         collect_decisions):
        """Ask user to select from all properties matching patterns"""

        matches = self.filter_properties(patterns)
        if matches:
            values = []
            choices = []
            for propertyset_name, property_name, match in matches:
                value = self.get_exact_property(propertyset_name, property_name)
                values.append(value)
                choices.append((propertyset_name, property_name))
                # print("%s.%s = %s"%(propertyset_name, property_name, value))

            # TODO: Decision: save for all following elements of same class (
            #  dont ask again?)
            # selected = (propertyset_name, property_name, value)

            distinct_values = set(values)
            if len(distinct_values) == 1:
                # multiple sources but common value
                return distinct_values.pop()
            else:
                self.logger.warning('Found multiple values for attributes %s of instance %s' % (
                    ', '.join((str((m[0], m[1])) for m in matches)), self))
                return distinct_values

        return None
        #     # TODO: Decision with id, key, value
        #     decision = DictDecision("Multiple possibilities found",
        #                             choices=dict(zip(choices, values)),
        #                             output=self.attributes,
        #                             output_key=name,
        #                             global_key="%s_%s.%s" % (self.ifc_type,
        #                             self.guid, name),
        #                             allow_skip=True, allow_load=True,
        #                             allow_save=True,
        #                             collect=collect_decisions,
        #                             quick_decide=not collect_decisions)
        #
        #     if collect_decisions:
        #         raise PendingDecisionError()
        #
        #     return decision.value
        # raise NoValueError("No matching property for %s" % (patterns))

    def __repr__(self):
        return "<%s (%s)>" % (self.__class__.__name__, self.name)


class BaseElement(Root):
    """Base class for all elements with ports"""
    objects = {}
    default_materials = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        BaseElement.objects[self.guid] = self
        self.logger = logging.getLogger(__name__)
        self.aggregation = None
        self.attributes = attribute.AttributeManager(bind=self)
        self.thermal_zones = []
        self.ports = []
        self.space_boundaries = []
        self.storeys = []

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
        """Get element instance with given guid

        :returns: None if element with guid was not instanciated"""
        return BaseElement.objects.get(guid)

    def discard(self):
        super().discard()
        del self.objects[self.guid]

    def is_generator(self):
        return False

    def is_consumer(self):
        return False

    def __repr__(self):
        return "<%s (ports: %d)>" % (self.__class__.__name__, len(self.ports))


class BasePort(Root):
    """Basic port"""
    objects = {}

    def __init__(self, parent, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent = parent
        self.connection = None
        BasePort.objects[self.guid] = self

        self._flow_master = False
        self._flow_direction = None
        self._flow_side = None

    @staticmethod
    def get_port(guid):
        """Get port instance with given guid

        :returns: None if port with guid was not instanciated"""
        return BasePort.objects.get(guid)

    def connect(self, other):
        """Connect this interface bidirectional to another interface"""
        assert isinstance(other, BasePort), "Can't connect interfaces" \
                                            " of different classes."
        # if self.flow_direction == 'SOURCE' or \
        #         self.flow_direction == 'SOURCEANDSINK':
        if self.connection and self.connection is not other:
            raise AttributeError("Port is already connected!")
        if other.connection and other.connection is not self:
            raise AttributeError("Other port is already connected!")
        self.connection = other
        other.connection = self

    def disconnect(self):
        """remove connection between self and other port"""
        other = self.connection
        if other:
            self.connection = None
            other.disconnect()

    def is_connected(self):
        """Returns truth value of port's connection"""
        return bool(self.connection)

    @property
    def flow_master(self):
        """Lock flow direction for port"""
        return self._flow_master

    @flow_master.setter
    def flow_master(self, value: bool):
        self._flow_master = value

    @property
    def flow_direction(self):
        """Flow direction of port

        -1 = medium flows into port
        1 = medium flows out of port
        0 = medium flow undirected
        None = flow direction unknown"""
        return self._flow_direction

    @flow_direction.setter
    def flow_direction(self, value):
        if self._flow_master:
            raise AttributeError("Can't set flow direction for flow master.")
        if value not in (-1, 0, 1, None):
            raise AttributeError("Invalid value. Use one of (-1, 0, 1, None).")
        self._flow_direction = value

    @property
    def verbose_flow_direction(self):
        """Flow direction of port"""
        if self.flow_direction == -1:
            return 'SINK'
        if self.flow_direction == 0:
            return 'SINKANDSOURCE'
        if self.flow_direction == 1:
            return 'SOURCE'
        return 'UNKNOWN'

    @property
    def flow_side(self):
        """VL(1), RL(-1), UNKNOWN(0)"""
        if self._flow_side is None:
            self._flow_side = self.determine_flow_side()
        return self._flow_side

    @flow_side.setter
    def flow_side(self, value):
        if value not in (-1, 0, 1):
            raise ValueError("allowed values for flow_side are 1, 0, -1")
        previous = self._flow_side
        self._flow_side = value
        if previous:
            if previous != value:
                logger.info("Overwriting flow_side for %r with %s" % (self, self.verbose_flow_side))
        else:
            logger.debug("Set flow_side for %r to %s" % (self, self.verbose_flow_side))

    @property
    def verbose_flow_side(self):
        if self.flow_side == 1:
            return "VL"
        if self.flow_side == -1:
            return "RL"
        return "UNKNOWN"

    def determine_flow_side(self):
        return 0

    def discard(self):
        super().discard()
        del BasePort.objects[self.guid]

    def __repr__(self):
        if self.parent:
            try:
                idx = self.parent.ports.index(self)
                return "<%s #%d of %s)>" % (
                    self.__class__.__name__, idx, self.parent)
            except ValueError:
                return "<%s (broken parent: %s)>" % (
                    self.__class__.__name__, self.parent)
        return "<%s (*abandoned*)>" % (self.__class__.__name__)

    def __str__(self):
        return self.__repr__()[1:-2]


class Port(BasePort, IFCBased):
    """Port of Element"""
    vl_pattern = re.compile('.*vorlauf.*', re.IGNORECASE)  # TODO: extend pattern
    rl_pattern = re.compile('.*rücklauf.*', re.IGNORECASE)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.groups = {assg.RelatingGroup.ObjectType
                       for assg in self.ifc.HasAssignments}

        if self.ifc.FlowDirection == 'SOURCE':
            self.flow_direction = 1
        elif self.ifc.FlowDirection == 'SINK':
            self.flow_direction = -1
        elif self.ifc.FlowDirection == 'SINKANDSOURCE':
            self.flow_direction = 0

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

        if all(coordinates == np.array([0, 0, 0])):
            logger = logging.getLogger('IFCQualityReport')
            logger.info("Suspect position [0, 0, 0] for %s", self)
        return coordinates

    def determine_flow_side(self):
        """Check groups for hints of flow_side and returns flow_side if hints are definitely"""
        vl = None
        rl = None
        if self.parent.is_generator():
            if self.flow_direction == 1:
                vl = True
            elif self.flow_direction == -1:
                rl = True
        elif self.parent.is_consumer():
            if self.flow_direction == 1:
                rl = True
            elif self.flow_direction == -1:
                vl = True
        if not vl:
            vl = any(filter(self.vl_pattern.match, self.groups))
        if not rl:
            rl = any(filter(self.rl_pattern.match, self.groups))

        if vl and not rl:
            return 1
        if rl and not vl:
            return -1
        return 0


class SubElement(BaseElement, IFCBased):
    _ifc_classes = {}

    dummy = None
    conditions = []
    # todo move this to upper class?
    instances = {}

    def __init__(self, *args, tool=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._tool = tool
        self.parent = None

    @classmethod
    def _init_factory(cls):
        """initialize lookup for factory"""
        logger = logging.getLogger(__name__)
        conflict = False
        all_subclasses = cls.get_all_subclasses(cls)
        if Element in all_subclasses:
            all_subclasses.pop(all_subclasses.index(Element))
        for cls_selected in all_subclasses:
            if not isinstance(cls_selected.ifc_type, list):
                ifc_types = [cls_selected.ifc_type]
            else:
                ifc_types = cls_selected.ifc_type
            for ifc_type in ifc_types:
                if ifc_type is None:
                    conflict = True
                    logger.error("Invalid ifc_type (%s) in '%s'", ifc_type,
                                 cls_selected.__name__)
                elif ifc_type in cls._ifc_classes:
                    conflicting_cls = cls._ifc_classes[ifc_type]
                    if not issubclass(cls_selected, conflicting_cls):
                        conflict = True
                        logger.error(
                            "Conflicting ifc_types (%s) in '%s' and '%s'",
                            ifc_type, cls_selected.__name__,
                            cls._ifc_classes[ifc_type])
                elif cls_selected.__name__ == "Dummy":
                    cls.dummy = cls_selected
                elif not ifc_type.lower().startswith("ifc"):
                    conflict = True
                    logger.error("Invalid ifc_type (%s) in '%s'", ifc_type,
                                 cls_selected.__name__)
                else:
                    cls._ifc_classes[ifc_type] = cls_selected

        if conflict:
            raise AssertionError(
                "Conflict(s) in Models. (See log for details).")

        # Model.dummy = Model.ifc_classes['any']
        if not cls._ifc_classes:
            raise ElementError(
                "Failed to initialize Element factory. No elements found!")

        model_txt = "\n".join(
            " - %s" % (model) for model in cls._ifc_classes)
        logger.debug("IFC model factory initialized with %d ifc classes:\n%s",
                     len(cls._ifc_classes), model_txt)

    @classmethod
    def factory(cls, ifc_element, alternate_ifc_type=None, tool=None):
        """Create model depending on ifc_element"""
        if not cls._ifc_classes:
            cls._init_factory()

        ifc_type = ifc_element.is_a() \
            if not alternate_ifc_type or alternate_ifc_type == ifc_element.is_a() \
            else alternate_ifc_type
        cls_selected = cls._ifc_classes.get(ifc_type, cls.dummy)

        prefac = cls_selected(ifc=ifc_element, tool=tool)
        if cls_selected is cls.dummy:
            logger = logging.getLogger(__name__)
            logger.warning("Did not found matching class for %s", ifc_type)
            return prefac

        for sub_cls in cls.get_all_subclasses(cls_selected):
            requirements = cls.get_class_requirements(sub_cls)
            match = True
            for req, value in requirements.items():
                on_ifc = getattr(prefac, req)
                if on_ifc != value:
                    match = False
                    break
            if match is True:
                prefac = sub_cls(ifc=ifc_element, tool=tool)
                break
        if type(prefac).__name__ not in cls.instances:
            cls.instances[type(prefac).__name__] = {prefac.guid: prefac}
        else:
            if prefac.guid not in cls.instances[type(prefac).__name__]:
                cls.instances[type(prefac).__name__][prefac.guid] = prefac
        return prefac

    @staticmethod
    def get_all_subclasses(cls):
        all_subclasses = []

        for subclass in cls.__subclasses__():
            if subclass not in all_subclasses:
                all_subclasses.append(subclass)
                all_subclasses.extend(cls.get_all_subclasses(subclass))

        return all_subclasses

    @staticmethod
    def get_dict_subclasses(cls):
        all_subclasses = {}

        for subclass in cls.__subclasses__():
            if subclass.__name__ not in all_subclasses:
                all_subclasses[subclass.__name__] = subclass
                all_subclasses.update(cls.get_dict_subclasses(subclass))

        return all_subclasses


    @staticmethod
    def get_class_requirements(cls):
        requirements = {}
        if cls.predefined_type is not None:
            requirements['predefined_type'] = cls.predefined_type
        if hasattr(cls, 'special_argument'):
            requirements.update(cls.special_argument)

        return requirements

    @classmethod
    def get_class_instances(cls, instance_class):
        if isinstance(instance_class, str):
            return list(cls.instances[instance_class].values())
        else:
            return list(cls.instances[instance_class.__name__].values())

    def validate(self):
        """"Check if standard parameter are in valid range"""
        for cond in self.conditions:
            if not cond.check(self):
                self.logger.warning("%s validation (%s) failed for %s", self.ifc_type, cond.name, self.guid)
                return False
        return True

    @property
    def source_tool(self):
        """Name of tool that the parent has been created with"""
        if hasattr(self.parent, 'source_tool'):
            self._tool = self.parent.source_tool
        return self._tool

    def __repr__(self):
        return "<%s (guid=%s)>" % (self.__class__.__name__, self.guid)

    def __str__(self):
        return "%s" % self.__class__.__name__


class Element(SubElement):
    """Base class for IFC model representation

    WARNING: getting an not defined attribute from instances of Element will
    return None (from finder) instead of rasing an AttributeError"""
    _ifc_classes = {}

    dummy = None
    conditions = []
    _source_tool = None

    def __init__(self, *args, tool=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._tool = tool
        self._add_ports()
        del self.parent
        # TODO: set flow_side based on ifc (no official property, but revit (HLS) and tricad (TRICAS-MS) provide it)

    def _add_ports(self):
        # has no ports option
        try:
            for nested in self.ifc.IsNestedBy:
                # valid for IFC for Revit v19.2.0.0
                for element_port_connection in nested.RelatedObjects:
                    if element_port_connection.is_a() == 'IfcDistributionPort':
                        self.ports.append(Port(parent=self, ifc=element_port_connection))
                    else:
                        self.logger.warning("Not included %s as Port in %s", element_port_connection.is_a(), self)
        except AttributeError:
            pass
        # valid for IFC for Revit v19.1.0.0
        element_port_connections = getattr(self.ifc, 'HasPorts', [])
        for element_port_connection in element_port_connections:
            self.ports.append(Port(parent=self, ifc=element_port_connection.RelatingPort))

    @property
    def source_tool(self):
        """Name of tool the ifc has been created with"""
        if not self.__class__._source_tool:
            self.__class__._source_tool = self.get_project().OwnerHistory.OwningApplication.ApplicationFullName
        return self.__class__._source_tool

    @property
    def neighbors(self):
        """Directly connected elements"""
        neighbors = []
        for port in self.ports:
            neighbors.append(port.connection.parent)
        return neighbors

    def __repr__(self):
        return "<%s (ports: %d, guid=%s)>" % (
            self.__class__.__name__, len(self.ports), self.guid)

    def __str__(self):
        return "%s" % self.__class__.__name__


class Dummy(Element):
    """Dummy for all unknown elements"""

    # ifc_type = 'any'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._ifc_type = self.ifc.get_info()['type']

    @property
    def ifc_type(self):
        return self._ifc_type

    def __str__(self):
        return "Dummy '%s'" % self.name
