import logging
import pickle
import re
from json import JSONEncoder
from typing import Union, Iterable, Dict, List, Tuple, Type, Optional, Any

import numpy as np
import ifcopenshell.geom
from ifcopenshell import guid

from bim2sim.elements.aggregation import AggregationMixin
from bim2sim.kernel.decision import Decision, DecisionBunch
from bim2sim.kernel import IFCDomainError
from bim2sim.elements.mapping import condition, attribute, ifc2python
from bim2sim.elements.mapping.finder import TemplateFinder, SourceTool
from bim2sim.elements.mapping.units import ureg
from bim2sim.utilities.common_functions import angle_equivalent, vector_angle, \
    remove_umlaut
from bim2sim.utilities.pyocc_tools import PyOCCTools
from bim2sim.utilities.types import IFCDomain, AttributeDataSource

logger = logging.getLogger(__name__)
quality_logger = logging.getLogger('bim2sim.QualityReport')
settings_products = ifcopenshell.geom.main.settings()
settings_products.set(settings_products.USE_PYTHON_OPENCASCADE, True)


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

    def validate_creation(self) -> bool:
        """Check if current instance is valid"""
        raise NotImplementedError

    def validate_attributes(self) -> dict:
        """Check if attributes are valid"""
        return {}

    def _calc_position(self, name) -> np.array:
        """Returns position (calculation may be expensive)"""
        return None

    position = attribute.Attribute(
        description='Position of element',
        functions=[_calc_position]
    )

    @staticmethod
    def get_id(prefix=""):
        prefix_length = len(prefix)
        if prefix_length > 10:
            raise AttributeError("Max prefix length is 10!")
        Element._id_counter += 1
        return "{0:0<8s}{1:0>14d}".format(prefix, Element._id_counter)

    @staticmethod
    def get_object(guid):
        """Get Element object instance with given guid

        :returns: None if object with guid was not instanciated"""
        raise AssertionError("Obsolete method. "
                             "Don't rely on global Element.objects. "
                             "Use e.g. elements from tasks/playground.")

    def request(self, name, external_decision: Decision = None) \
            -> Union[None, Decision]:
        """Request the elements attribute.

        Args:
            name: Name of attribute
            external_decision: Decision to use instead of default decision
        """
        return self.attributes.request(name, external_decision)

    def reset(self, name, data_source=AttributeDataSource.manual_overwrite):
        """Reset the attribute of the element.

        Args:
            name: attribute name
            data_source (object): data source of the attribute
        """

        return self.attributes.reset(name, data_source)

    def source_info(self) -> str:
        """Get informative string about source of Element."""
        return ''

    @classmethod
    def get_pending_attribute_decisions(
            cls, elements: Iterable['Element']) -> DecisionBunch:
        """Get all requested decisions of attributes and functions of attributes
        to afterwards calculate said attribute.

        all decisions related to given elements are yielded.
        all attributes functions are used to calculate the remaining attributes
        """

        all_attr_decisions = DecisionBunch()
        for inst in elements:
            bunch = inst.attributes.get_decisions()
            all_attr_decisions.extend(bunch)

        # sort decisions to preserve order
        all_attr_decisions.sort(key=lambda d: d.global_key)
        yield all_attr_decisions

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
                 ifc_units: dict = None,
                 ifc_domain: IFCDomain = None,
                 **kwargs):
        super().__init__(*args, **kwargs)

        self.ifc = ifc
        self.predefined_type = ifc2python.get_predefined_type(ifc)
        self.ifc_domain = ifc_domain
        self.finder = finder
        self.ifc_units = ifc_units
        self.source_tool: SourceTool = None

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

    @classmethod
    def pre_validate(cls, ifc) -> bool:
        """Check if ifc meets conditions to create element from it"""
        raise NotImplementedError

    def _calc_position(self, name):
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

    def _get_name_from_ifc(self, name):
        ifc_name = self.get_ifc_attribute('Name')
        if ifc_name:
            return remove_umlaut(ifc_name)

    name = attribute.Attribute(
        description="Name of element based on IFC attribute.",
        functions=[_get_name_from_ifc]
    )

    def get_ifc_attribute(self, attribute):
        """
        Fetches non-empty attributes (if they exist).
        """
        return getattr(self.ifc, attribute, None)

    def get_propertyset(self, propertysetname):
        return ifc2python.get_property_set_by_name(
            propertysetname, self.ifc, self.ifc_units)

    def get_propertysets(self):
        if self._propertysets is None:
            self._propertysets = ifc2python.get_property_sets(
                self.ifc, self.ifc_units)
        return self._propertysets

    def get_type_propertysets(self):
        if self._type_propertysets is None:
            self._type_propertysets = ifc2python.get_type_property_sets(
                self.ifc, self.ifc_units)
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
        return ifc2python.get_true_north(self.ifc)

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

        :returns: list of tuple(propertyset_name, property_name, match_graph)"""
        matches = []
        for propertyset_name, property_name in self.inverse_properties():
            for pattern in patterns:
                match = re.match(pattern, property_name)
                if match:
                    matches.append((propertyset_name, property_name, match))
        return matches

    @classmethod
    def filter_for_text_fragments(
            cls, ifc_element, ifc_units: dict, optional_locations: list = None):
        """Filter for text fragments in the ifc_element to identify the ifc_element."""
        results = []
        hits = [p.search(ifc_element.Name) for p in cls.pattern_ifc_type]
        # hits.extend([p.search(ifc_element.Description or '') for p in cls.pattern_ifc_type])
        hits = [x for x in hits if x is not None]
        if any(hits):
            quality_logger.info("Identified %s through text fracments in name. Criteria: %s", cls.ifc_type, hits)
            results.append(hits[0][0])
            # return hits[0][0]
        if optional_locations:
            for loc in optional_locations:
                hits = [p.search(ifc2python.get_property_set_by_name(
                    loc, ifc_element, ifc_units) or '')
                        for p in cls.pattern_ifc_type
                        if ifc2python.get_property_set_by_name(
                        loc, ifc_element, ifc_units)]
                hits = [x for x in hits if x is not None]
                if any(hits):
                    quality_logger.info("Identified %s through text fracments in %s. Criteria: %s", cls.ifc_type, loc, hits)
                    results.append(hits[0][0])
        return results if results else ''

    def get_exact_property(self, propertyset_name: str, property_name: str):
        """Returns value of property specified by propertyset name and property name

        :Raises: AttributeError if property does not exist"""
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
                quality_logger.warning('Found multiple values for attributes %s of instance %s' % (
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

    def source_info(self) -> str:
        return f'{self.ifc_type}:{self.guid}'


class RelationBased(IFCBased):
    conditions = []

    def __repr__(self):
        return "<%s (guid: %s)>" % (self.__class__.__name__, self.guid)

    def __str__(self):
        return "%s" % self.__class__.__name__


class RelationBased(IFCBased):

    pass


class ProductBased(IFCBased):
    """Elements based on IFC products.

    Args:
        material: material of the element
        material_set: dict of material and fraction [0, 1] if multiple materials
    """
    domain = 'GENERAL'
    key: str = ''
    key_map: Dict[str, 'Type[ProductBased]'] = {}
    conditions = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aggregation = None
        self.ports = self.get_ports()
        self.material = None
        self.material_set = {}
        self.cost_group = self.calc_cost_group()

    def __init_subclass__(cls, **kwargs):
        # set key for each class
        cls.key = f'{cls.domain}-{cls.__name__}'
        cls.key_map[cls.key] = cls

    def get_ports(self):
        return []

    def get_better_subclass(self) -> Union[None, Type['IFCBased']]:
        """Returns alternative subclass of current object.
        CAUTION: only use this if you can't know the result before instantiation
         of base class

        Returns:
            object: subclass of ProductBased or None"""
        return None

    @property
    def neighbors(self):
        """Directly connected elements"""
        neighbors = []
        for port in self.ports:
            if port.connection:
                neighbors.append(port.connection.parent)
        return neighbors

    def validate_creation(self):
        """"Validate the element creation in two steps.
        1. Check if standard parameter are in valid range.
        2. Check if number of ports are equal to number of expected ports
        (only for HVAC).
        """
        for cond in self.conditions:
            if cond.critical_for_creation:
                value = getattr(self, cond.key)
                # don't prevent creation if value is not existing
                if value:
                    if not cond.check(self, value):
                        logger.warning("%s validation (%s) failed for %s", self.ifc_type, cond.name, self.guid)
                        return False
        if not self.validate_ports():
            logger.warning("%s has %d ports, but %s expected for %s", self.ifc_type, len(self.ports),
                           self.expected_hvac_ports, self.guid)
            return False
        return True

    def validate_attributes(self) -> dict:
        """Check if all attributes are valid, returns dict with key = attribute
        and value = True or False"""
        results = {}
        for cond in self.conditions:
            if not cond.critical_for_creation:
                # todo
                pass
        #         if not cond.check(self):
        #             logger.warning("%s validation (%s) failed for %s",
        #                            self.ifc_type, cond.name, self.guid)
        #             return False
        # return True
        return results

    def validate_ports(self):
        return True

    def __repr__(self):
        return "<%s>" % self.__class__.__name__

    def calc_cost_group(self) -> Optional[int]:
        """Calculate the cost group according to DIN276"""
        return None

    def calc_volume_from_ifc_shape(self):
        # todo use more efficient iterator to calc all shapes at once
        #  with multiple cores:
        #  https://wiki.osarch.org/index.php?title=IfcOpenShell_code_examples
        if hasattr(self.ifc, 'Representation'):
            try:
                shape = ifcopenshell.geom.create_shape(
                            settings_products, self.ifc).geometry
                vol = PyOCCTools.get_shape_volume(shape)
                vol = vol * ureg.meter ** 3
                return vol
            except:
                logger.warning(f"No calculation of geometric volume possible "
                               f"for {self.ifc}.")

    def _get_volume(self, name):
        if hasattr(self, "net_volume"):
            if self.net_volume:
                vol = self.net_volume
                return vol
        vol = self.calc_volume_from_ifc_shape()
        return vol

    volume = attribute.Attribute(
        description="Volume of the attribute",
        functions=[_get_volume],
    )

    def __str__(self):
        return "<%s>" % (self.__class__.__name__)


class Port(RelationBased):
    """Basic port"""

    def __init__(self, parent, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent: ProductBased = parent
        self.connection = None

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


class Material(ProductBased):
    guid_prefix = 'Material_'
    key: str = 'Material'
    ifc_types = {
        'IfcMaterial': ["*"]
    }
    name = ''

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parents: List[ProductBased] = []

    @staticmethod
    def get_id(prefix=""):
        prefix_length = len(prefix)
        if prefix_length > 10:
            raise AttributeError("Max prefix length is 10!")
        ifcopenshell_guid = guid.new()[prefix_length + 1:]
        return f"{prefix}{ifcopenshell_guid}"

    conditions = [
        condition.RangeCondition('spec_heat_capacity',
                                 0 * ureg.kilojoule / (ureg.kg * ureg.K),
                                 5 * ureg.kilojoule / (ureg.kg * ureg.K),
                                 critical_for_creation=False),
        condition.RangeCondition('density',
                                 0 * ureg.kg / ureg.m ** 3,
                                 50000 * ureg.kg / ureg.m ** 3,
                                 critical_for_creation=False),
        condition.RangeCondition('thermal_conduc',
                                 0 * ureg.W / ureg.m / ureg.K,
                                 100 * ureg.W / ureg.m / ureg.K,
                                 critical_for_creation=False),
        condition.RangeCondition('porosity',
                                 0 * ureg.dimensionless,
                                 1 * ureg.dimensionless, True,
                                 critical_for_creation=False),
        condition.RangeCondition('solar_absorp',
                                 0 * ureg.percent,
                                 1 * ureg.percent, True,
                                 critical_for_creation=False),
                 ]

    spec_heat_capacity = attribute.Attribute(
        default_ps=("Pset_MaterialThermal", "SpecificHeatCapacity"),
        # functions=[get_from_template],
        unit=ureg.kilojoule / (ureg.kg * ureg.K)
    )

    density = attribute.Attribute(
        default_ps=("Pset_MaterialCommon", "MassDensity"),
        unit=ureg.kg / ureg.m ** 3
    )

    thermal_conduc = attribute.Attribute(
        default_ps=("Pset_MaterialThermal", "ThermalConductivity"),
        unit=ureg.W / (ureg.m * ureg.K)
    )

    porosity = attribute.Attribute(
        default_ps=("Pset_MaterialCommon", "Porosity"),
        unit=ureg.dimensionless
    )

    # todo is percent the correct unit? (0-1)
    solar_absorp = attribute.Attribute(
        # default_ps=('Pset_MaterialOptical', 'SolarTransmittance'),
        default=0.7,
        unit=ureg.percent
    )

    def __repr__(self):
        if self.name:
            return "<%s %s>" % (self.__class__.__name__, self.name)
        else:
            return "<%s>" % self.__class__.__name__


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

    To understand the concept of the factory class, we refer to this article:
    https://refactoring.guru/design-patterns/factory-method/python/example

    Example:
        factory = Factory([Pipe, Boiler], dummy)
        ele = factory(some_ifc_element)
        """

    def __init__(
            self,
            relevant_elements: set[ProductBased],
            ifc_units: dict,
            ifc_domain: IFCDomain,
            finder: Union[TemplateFinder, None] = None,
            dummy=Dummy):
        self.mapping, self.blacklist, self.defaults = self.create_ifc_mapping(relevant_elements)
        self.dummy_cls = dummy
        self.ifc_domain = ifc_domain
        self.finder = finder
        self.ifc_units = ifc_units

    def __call__(self, ifc_entity, *args, ifc_type: str = None, use_dummy=True,
                 **kwargs) -> ProductBased:
        """Run factory to create element instance.

        Calls self.create() function but before checks which element_cls is the
        correct mapping for the given ifc_entity.

        Args:
            ifc_entity: IfcOpenShell entity
            args: additional args passed to element
            ifc_type: ify type to create element for.
                defaults to ifc_entity.is_a()
            use_dummy: use dummy class if nothing is found
            kwargs: additional kwargs passed to element
        Raises:
            LookupError: if no element found and use_dummy = False
        Returns:
            element: created element instance
        """
        _ifc_type = ifc_type or ifc_entity.is_a()
        predefined_type = ifc2python.get_predefined_type(ifc_entity)
        element_cls = self.get_element(_ifc_type, predefined_type)
        if not element_cls:
            if use_dummy:
                element_cls = self.dummy_cls
            else:
                raise LookupError(f"No element found for {ifc_entity}")
        # TODO # 537 Put this to a point where it makes sense, return None is no
        #  solution
        if hasattr(element_cls, 'from_ifc_domains'):
            if self.ifc_domain not in element_cls.from_ifc_domains:
                logger.warning(
                    f"Element has {self.ifc_domain} but f{element_cls.__name__}"
                    f" will only be created for IFC files of domain "
                    f"{element_cls.from_ifc_domains}.")
                raise IFCDomainError(
                    f"Element has {self.ifc_domain} but f{element_cls.__name__}"
                    f" will only be created for IFC files of domain "
                    f"{element_cls.from_ifc_domains}")

        element = self.create(element_cls, ifc_entity, *args, **kwargs)
        return element

    def create(self, element_cls, ifc_entity, *args, **kwargs):
        """Create Element from class and ifc"""
        # instantiate element

        element = element_cls.from_ifc(
            ifc_entity, ifc_domain=self.ifc_domain, finder=self.finder,
            ifc_units=self.ifc_units, *args, **kwargs)
        # check if it prefers to be sth else
        better_cls = element.get_better_subclass()
        if better_cls:
            logger.info("Creating %s instead of %s", better_cls, element_cls)
            element = better_cls.from_ifc(
                ifc_entity,
                ifc_domain=self.ifc_domain,
                finder=self.finder,
                ifc_units=self.ifc_units,
                *args, **kwargs)
        return element

    def get_element(self, ifc_type: str, predefined_type: Union[str, None]) -> \
            Union[ProductBased, None]:
        """Get element class by ifc type and predefined type"""
        if predefined_type:
            key = (ifc_type.lower(), predefined_type.upper())
            # 1. go over normal list, if found match_graph --> return
            element = self.mapping.get(key)
            if element:
                return element
            # 2. go over negative list, if found match_graph --> not existing
            if key in self.blacklist:
                return None
        # 3. go over default list, if found match_graph --> return
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

        WARNING: ifc_type is always converted to lower case
        and predefined types to upper case

        Returns:
            mapping: dict of ifc_type and predefined_type to element class
            blacklist: list of ifc_type which will not be taken into account
            default: dict of ifc_type to element class
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
                           "representing Element class. There will be no "
                           "match if predefined type is not provided.\n%s",
                           no_default)
        return mapping, blacklist, default


class SerializedElement:
    """Serialized version of an element.

    This is a workaround as we can't serialize elements due to the usage of
    IfcOpenShell which uses unpickable swigPy objects. We just store the most
    important information which are guid, element_type, storeys, aggregated
    elements and the attributes from the attribute system."""
    def __init__(self, element):
        self.guid = element.guid
        self.element_type = element.__class__.__name__
        for attr_name, attr_val in element.attributes.items():
            # assign value directly to attribute without status
            # make sure to get the value
            value = getattr(element, attr_name)
            if self.is_picklable(value):
                setattr(self, attr_name, value)
            else:
                logger.info(
                    f"Attribute {attr_name} will not be serialized, as it's "
                    f"not pickleable")
        if hasattr(element, "space_boundaries"):
            self.space_boundaries = [bound.guid for bound in
                                     element.space_boundaries]
        if hasattr(element, "storeys"):
            self.storeys = [storey.guid for storey in element.storeys]
        if issubclass(element.__class__, AggregationMixin):
            self.elements = [ele.guid for ele in element.elements]

    @staticmethod
    def is_picklable(value: Any) -> bool:
        """Determines if a given value is picklable.

        This method attempts to serialize the provided value using the `pickle` module.
        If the value can be successfully serialized, it is considered picklable.

        Args:
            value (Any): The value to be tested for picklability.

        Returns:
            bool: True if the value is picklable, False otherwise.
        """
        try:
            pickle.dumps(value)
            return True
        except (pickle.PicklingError, TypeError):
            return False

    def __repr__(self):
        return "<serialized %s (guid: '%s')>" % (
            self.element_type, self.guid)
