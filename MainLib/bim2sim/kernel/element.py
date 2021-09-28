"""Definition for basic representations of IFC elements"""
# from __future__ import annotations
import json
import logging
from json import JSONEncoder
import re
from pathlib import Path
from typing import Union, Set, Iterable, Dict, List, Tuple, Type, Generator

import numpy as np

import bim2sim
from bim2sim.decorators import cached_property
from bim2sim.kernel import ifc2python, attribute
from bim2sim.decision import Decision, DecisionBunch
from bim2sim.utilities.common_functions import angle_equivalent, vector_angle
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
            return "<Element(%s)>" % o.guid
        return JSONEncoder.default()


class Element(metaclass=attribute.AutoAttributeNameMeta):
    """Most basic class"""
    guid_prefix = ''
    _id_counter = 0

    def __init__(self, guid=None, **kwargs):
        self.guid = guid or self.get_id(self.guid_prefix)
        # self.related_decisions: List[Decision] = []
        self.attributes = attribute.AttributeManager(bind=self)

        # set attributes based on kwargs
        for kw, arg in kwargs.items():
            if kw in self.attributes:  # allow only attributes
                setattr(self, kw, arg)
            else:
                raise AttributeError(f"Unused argument in kwargs: {kw}: {arg}")

    def __hash__(self):
        return hash(self.guid)

    def validate(self) -> bool:
        """Check if current instance is valid"""
        raise NotImplementedError

    def calc_position(self) -> np.array:
        """Returns position (calculation may be expensive)"""
        return None

    def calc_orientation(self) -> np.array:
        """Returns position (calculation may be expensive)"""
        return None

    @cached_property
    def position(self) -> np.array:
        """Position calculated only once by calling calc_position"""
        return self.calc_position()

    @cached_property
    def orientation(self) -> np.array:
        return self.calc_orientation()

    @staticmethod
    def get_id(prefix=""):
        prefix_length = len(prefix)
        if prefix_length > 8:
            raise AttributeError("Max prefix length is 8!")
        Element._id_counter += 1
        return "{0:0<8s}{1:0>14d}".format(prefix, Element._id_counter)

    @staticmethod
    def get_object(guid):
        """Get Element object instance with given guid

        :returns: None if object with guid was not instanciated"""
        raise AssertionError("Obsolete method. "
                             "Don't rely on global Element.objects. "
                             "Use e.g. instances from task/playground.")

    def request(self, name, external_decision: Decision = None) \
            -> Union[None, Decision]:
        """Request attribute
        :param name: Name of attribute
        :param external_decision: Decision to use instead of default decision
        """
        return self.attributes.request(name, external_decision)

    @classmethod
    def get_pending_attribute_decisions(
            cls, instances: Iterable['Element'] = None) -> DecisionBunch:
        """Get all requested decisions of attributes.

        all decisions related to given instances are returned"""
        # if not self or not isinstance(self, Element):
        # called from class
        decisions = DecisionBunch()
        for inst in instances:
            for bunch in inst.attributes.get_decisions():
                decisions.extend(bunch)
        # else:
        #     # called from instance
        #     if instances:
        #         raise AssertionError(
        #             "Only use instances argument on call from class")
        #     decisions = self.attributes.get_decisions()
        return decisions

    @classmethod
    def full_reset(cls):
        raise AssertionError("Obsolete method. not required any more.")


class IFCBased(Element):
    """Element with instantiation from ifc and related methods.

        Attributes:
        ifc: IfcOpenShell element instance
        ifc_types: Dict with ifc_type as key and list of predifined types that
        fit to the class as values.
        Special values for predifined types:
            '*' all which are not overwritten in other classes predfined types.
            '-Something'  start with minus to exclude

        For example:
        {'IfcSlab': ['*', '-SomethingSpecialWeDontWant', 'BASESLAB']}
        {'IfcRoof': ['FLAT_ROOF', 'SHED_ROOF',...],
         'IfcSlab': ['ROOF']}"""

    ifc_types: Dict[str, List[str]] = None
    pattern_ifc_type = []

    def __init__(self, *args,
                 ifc=None,
                 finder: TemplateFinder = None,
                 **kwargs):
        super().__init__(*args, **kwargs)

        self.ifc = ifc
        self.predefined_type = ifc2python.get_predefined_type(ifc)
        self.finder = finder
        self._source_tool: str = None

        # TBD
        self.enrichment = {}  # TODO: DJA
        self._propertysets = None
        self._type_propertysets = None
        self._decision_results = {}

    @classmethod
    def ifc2args(cls, ifc) -> Tuple[tuple, dict]:
        """Extract init args and kwargs from ifc"""
        guid = getattr(ifc, 'GlobalId', None)
        kwargs = {'guid': guid, 'ifc': ifc}
        return (), kwargs

    @classmethod
    def from_ifc(cls, ifc, *args, **kwargs):
        """Factory method to create instance from ifc"""
        ifc_args, ifc_kwargs = cls.ifc2args(ifc)
        kwargs.update(ifc_kwargs)
        return cls(*(args + ifc_args), **kwargs)

    @property
    def ifc_type(self):
        if self.ifc:
            return self.ifc.is_a()

    @property
    def source_tool(self):  # TBD: this incl. Finder could live in Factory
        """Name of tool the ifc has been created with"""
        if not self._source_tool and self.ifc:
            self._source_tool = self.get_project().OwnerHistory.\
                OwningApplication.ApplicationFullName
        return self._source_tool

    @classmethod
    def pre_validate(cls, ifc) -> bool:
        """Check if ifc meets conditions to create element from it"""
        raise NotImplementedError

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

    def calc_orientation(self) -> np.array:
        # ToDO: true north angle
        # ToDO: we want a consistent return which is a absolute vector.
        ang_sum = 0
        placementrel = self.ifc.ObjectPlacement
        while placementrel is not None:
            if placementrel.RelativePlacement.RefDirection is not None:
                vector = placementrel.RelativePlacement.RefDirection.DirectionRatios
                ang_sum += vector_angle(vector)
            placementrel = placementrel.PlacementRelTo

        # relative vector + absolute vector
        # if len(list_angles) == 1:
        #     if list_angles[next(iter(list_angles))] is None:
        #         return -90
        #         # return 0

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
    def filter_for_text_fragments(cls, ifc_element, optional_locations: list = None):
        """Filter for text fragments in the ifc_element to identify the ifc_element."""
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

    def get_exact_property(self, propertyset_name: str, property_name: str):
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
                logger.warning('Found multiple values for attributes %s of instance %s' % (
                    ', '.join((str((m[0], m[1])) for m in matches)), self))
                return distinct_values

        return None
        #     # TODO: Decision with id, key, value
        #     decision = DictDecision("Multiple possibilities found",
        #                             choices=dict(zip(choices, values)),
        #                             output=self.attributes,
        #                             key=name,
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


class RelationBased(IFCBased):

    def __repr__(self):
        return "<%s (guid=%s)>" % (self.__class__.__name__, self.guid)

    def __str__(self):
        return "%s" % self.__class__.__name__


class ProductBased(IFCBased):
    """Elements based on IFC products."""
    domain = 'GENERAL'
    key: str = ''
    key_map: Dict[str, 'Type[ProductBased]'] = {}
    conditions = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aggregation = None
        self.ports = self.get_ports()

    def __init_subclass__(cls, **kwargs):
        # set key for each class
        cls.key = f'{cls.domain}-{cls.__name__}'
        cls.key_map[cls.key] = cls

    def get_ports(self):
        return []

    def get_better_subclass(self) -> Union[None, Type['ProductBased']]:
        """Returns alternative subclass of current object.

        CAUTION: only use this if you can't know the result before instantiation
         of base class
        :returns: subclass of ProductBased or None"""
        return None

    @property
    def neighbors(self):
        """Directly connected elements"""
        neighbors = []
        for port in self.ports:
            neighbors.append(port.connection.parent)
        return neighbors

    def is_generator(self):
        return False

    def is_consumer(self):
        return False

    def validate(self):
        """"Check if standard parameter are in valid range"""
        for cond in self.conditions:
            if not cond.check(self):
                logger.warning("%s validation (%s) failed for %s",
                               self.ifc_type, cond.name, self.guid)
                return False
        return True

    def __repr__(self):
        return "<%s (ports: %d)>" % (self.__class__.__name__, len(self.ports))


class Port(RelationBased):
    """Basic port"""

    def __init__(self, parent, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent: ProductBased = parent
        self.connection = None

    @property
    def source_tool(self):  # TBD: this incl. Finder could live in Factory
        """Name of tool that the parent has been created with"""
        return getattr(self.parent, 'source_tool')

    def connect(self, other):
        """Connect this interface bidirectional to another interface"""
        assert isinstance(other, Port), \
            "Can't connect interfaces of different classes."
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

    def __repr__(self):
        if self.parent:
            try:
                idx = self.parent.ports.index(self)
                return "<%s #%d of %s)>" % (
                    self.__class__.__name__, idx, self.parent)
            except ValueError:
                return "<%s (broken parent: %s)>" % (
                    self.__class__.__name__, self.parent)
        return "<%s (*abandoned*)>" % self.__class__.__name__

    def __str__(self):
        return self.__repr__()[1:-2]


class Dummy(ProductBased):
    """Dummy for all unknown elements"""

    ifc_types = {
        "IfcElementProxy": ['*']
    }

    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #
    #     self._ifc_type = self.ifc.get_info()['type']

    @property
    def ifc_type(self):
        return self._ifc_type

    def __str__(self):
        return "Dummy '%s'" % self.ifc_type


class Factory:
    """Element Factory for :class: `ProductBased`

    Example:
        factory = Factory([Pipe, Boiler], dummy)
        ele = factory(some_ifc_element)
        """

    def __init__(
            self, relevant_elements: List[ProductBased],
            finder_path: Union[str, Path, None] = None, dummy=Dummy):
        self.mapping, self.blacklist, self.defaults = \
            self.create_ifc_mapping(relevant_elements)
        self.dummy_cls = dummy
        self.finder = TemplateFinder()
        if finder_path:
            self.finder.load(finder_path)

    def __call__(self, ifc_entity, *args, ifc_type: str = None, use_dummy=True,
                 **kwargs) -> ProductBased:
        """Run factory to create element instance.

        :param ifc_entity: IfcOpenShell entity
        :param args: additional args passed to element
        :param ifc_type: ify type to create element for.
            defaults to ifc_entity.is_a()
        :param use_dummy: use dummy class if nothing is found
        :param kwargs: additional kwargs passed to element

        :raises LookupError: if no element found an use_dummy = False
        """
        _ifc_type = ifc_type or ifc_entity.is_a()
        predefined_type = ifc2python.get_predefined_type(ifc_entity)
        element_cls = self.get_element(_ifc_type, predefined_type)
        if not element_cls:
            if use_dummy:
                element_cls = self.dummy_cls
            else:
                raise LookupError(f"No element found for {ifc_entity}")

        element = self.create(element_cls, ifc_entity, *args, **kwargs)
        return element

    def create(self, element_cls, ifc_entity, *args, **kwargs):
        """Create Element from class and ifc"""
        # instantiate element
        element = element_cls.from_ifc(
            ifc_entity, finder=self.finder, *args, **kwargs)
        # check if it prefers to be sth else
        better_cls = element.get_better_subclass()
        if better_cls:
            logger.info("Creating %s instead of %s", better_cls, element_cls)
            element = better_cls.from_ifc(ifc_entity, finder=self.finder, *args, **kwargs)
        return element

    def get_element(self, ifc_type: str, predefined_type: Union[str, None]) -> \
            Union[ProductBased, None]:
        """Get element class by ifc type and predefined type"""
        if predefined_type:
            key = (ifc_type.lower(), predefined_type.upper())
            # 1. go over normal list, if found match --> return
            element = self.mapping.get(key)
            if element:
                return element
            # 2. go over negative list, if found match --> not existing
            if key in self.blacklist:
                return None
        # 3. go over default list, if found match --> return
        return self.defaults.get(ifc_type.lower())

    # def _get_by_guid(self, guid: str) -> Union[ProductBased, None]:
    #     """Get item from given guid created by this factory."""
    #     return self._objects.get(guid)
    #
    # def _get_by_cls(self, item_cls: Type[ProductBased]) -> List[ProductBased]:
    #     """Get list of child items from given class created by this factory."""
    #     return [item for item in self._objects.values()
    #             if isinstance(item, item_cls)]

    @staticmethod
    def create_ifc_mapping(elements: Iterable) -> Tuple[
        Dict[Tuple[str, str], ProductBased],
        List[Tuple[str, ProductBased]],
        Dict[str, ProductBased]
    ]:
        """Create mapping dict, blacklist and default dict from elements

        WARNING: ifc_type is always converted to lowe case
        and predefined types to upper case
        """
        # TODO: cover virtual elements e.g. Space Boundaries (not products)

        mapping = {}
        blacklist = []
        default = {}
        _all_ifc_types = set()

        for ele in elements:
            for ifc_type, tokens in ele.ifc_types.items():
                _all_ifc_types.add(ifc_type.lower())
                for token in tokens:
                    # create default dict where all stars are taken into account
                    # items 'IfcSlab': Slab
                    if token == '*':
                        if ifc_type in default:
                            raise NameError(f"Conflicting default ifc_types for {ifc_type}")  # TBD
                        default[ifc_type.lower()] = ele
                        # create blacklist where all - are taken into account
                        # items: ('IfcRoof', 'WeiredStuff')
                    elif token.startswith('-'):
                        blacklist.append((ifc_type.lower(), token[1:].upper()))
                        # create mapping dict
                        # items ('IfcSlab', 'Roof'): Roof
                    else:
                        mapping[(ifc_type.lower(), token.upper())] = ele

        # check ifc types without default
        no_default = _all_ifc_types - set(default)
        if no_default:
            logger.warning("The following ifc types have no default "
                           "representing Elemet class. There will be no match "
                           "if predefined type is not provided.\n%s",
                           no_default)

        return mapping, blacklist, default
