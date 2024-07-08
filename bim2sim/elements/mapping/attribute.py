import logging
from functools import partial
from typing import Tuple, Iterable, Callable, Any, Union

import pint

from bim2sim.kernel.decision import RealDecision, Decision, \
    DecisionBunch
from bim2sim.elements.mapping.units import ureg

logger = logging.getLogger(__name__)
quality_logger = logging.getLogger('bim2sim.QualityReport')


class AutoAttributeNameMeta(type):
    """Detect setting on Attributes on class level and set name as given"""

    def __init__(cls, name, bases, namespace):
        super(AutoAttributeNameMeta, cls).__init__(name, bases, namespace)
        for name, obj in namespace.items():
            if isinstance(obj, Attribute):
                obj.name = name

    # def __setattr__(cls, name, value):
    #     if isinstance(value, Attribute):
    #         value.name = name
    #         print(name)
    #     return super().__setattr__(name, value)


class Attribute:
    """Descriptor of element attribute to get its value from various sources.

    value and status of attribute are stored in __dict__ of bound instance.
    Possible statuses are:
        UNKNOWN: default status at the beginning.
        REQUESTED: Attribute was already requested via a decision??.
        AVAILABLE: Attribute exists and is available.
        NOT_AVAILABLE: No way was found to obtain the attributes value.

    To find more about Descriptor objects follow the explanations on
    https://rszalski.github.io/magicmethods/#descriptor
    """
    STATUS_UNKNOWN = 'UNKNOWN'
    STATUS_REQUESTED = 'REQUESTED'
    STATUS_AVAILABLE = 'AVAILABLE'
    STATUS_NOT_AVAILABLE = 'NOT_AVAILABLE'

    def __init__(self,
                 description: str = "",
                 unit: pint.Unit = None,
                 ifc_attr_name: str = "",
                 default_ps: Tuple[str, str] = None,
                 default_association: Tuple[str, str] = None,
                 patterns: Iterable = None,
                 ifc_postprocessing: Callable[[Any], Any] = None,
                 functions: Iterable[Callable[[object, str], Any]] = None,
                 default=None,
                 dependant_attributes: Iterable[str] = None,
                 dependant_elements: str = None):
        """

        Args:
            description: Description of attribute
            unit: pint unit of attribute, defaults to dimensionless. Use SI
                units whenever possible.
            ifc_attr_name: Name of attribute in IFC schema.
            default_ps: tuple of propertyset name and property name. These
                follow the IFC schema specifications.
            default_association: tuple of association name and property name.
                These follow the IFC schema specifications.
            patterns: iterable of (compiled) re patterns to find not schema
                conform stored information
            ifc_postprocessing: callable to apply on initial value, returns
                final value
            functions: iterable of callable with signature func(bind, name) ->
                value. First return with no error is used as value.
            default: default value which is used if no other source is
                successful. Use only for attributes which have valid
                defaults.
            dependant_attributes: list of additional attributes necessary to
                calculate the attribute. Will be calculated automatically if
                not provided.
            dependant_elements: list of additional elements necessary to
                calculate the attribute
        """
        self.name = None  # auto set by AutoAttributeNameMeta
        self.description = description
        self.unit = unit

        self.ifc_attr_name = ifc_attr_name
        self.default_ps = default_ps
        self.default_association = default_association
        self.patterns = patterns
        self.functions = functions
        self.default_value = default
        self.dependant_attributes = dependant_attributes
        self.dependant_elements = dependant_elements

        if ifc_postprocessing is not None:
            self.ifc_post_processing = ifc_postprocessing

        # TODO argument for validation function

    def to_aggregation(self, calc=None, **kwargs):
        """Create new Attribute suited for aggregation."""
        options = {
            'description': self.description,
            'unit': self.unit,
            'default': self.default_value
        }
        options.update(kwargs)
        options['functions'] = [calc]
        return Attribute(**options)

    def _get_value(self, bind):
        """"""
        value = None
        if bind.ifc:  # don't bother if there is no ifc
            # default ifc attribute
            if value is None and self.ifc_attr_name:
                if hasattr(bind.ifc, self.ifc_attr_name):
                    raw_value = getattr(bind.ifc, self.ifc_attr_name)
                    value = self.ifc_post_processing(raw_value)
            # default property set
            if value is None and self.default_ps:
                raw_value = self.get_from_default_propertyset(bind,
                                                              self.default_ps)
                value = self.ifc_post_processing(raw_value)

            if value is None and self.default_association:
                raw_value = self.get_from_default_propertyset(
                    bind, self.default_association)
                value = self.ifc_post_processing(raw_value)

            # tool specific properties (finder)
            if value is None:
                raw_value = self.get_from_finder(bind, self.name)
                value = self.ifc_post_processing(raw_value)

            # custom properties by patterns
            if value is None and self.patterns:
                raw_value = self.get_from_patterns(bind, self.patterns,
                                                   self.name)
                value = self.ifc_post_processing(raw_value)

        # custom functions
        if value is None and self.functions:
            value = self.get_from_functions(bind, self.functions, self.name)

        # logger value none
        if value is None:
            quality_logger.warning(
                "Attribute '%s' of %s %s was not found in default PropertySet, "
                "default  Association, finder, patterns or functions",
                self.name, bind.ifc_type, bind.guid)

        # default value
        if value is None and self.default_value is not None:
            value = self.default_value
            if value is not None and self.unit:
                value = value * self.unit

        # check unit
        if isinstance(value, (list, set)):
            # case to calculate values that are list of quantities
            new_value = []
            for item in value:
                if self.unit is not None and item is not None and not \
                        isinstance(item, ureg.Quantity):
                    logger.warning(
                        f"Unit not set for attribute {self} of {bind}")
                    new_value.append(item * self.unit)
            value = new_value if len(new_value) == len(value) else value
        else:
            if self.unit is not None and value is not None and not isinstance(
                    value, ureg.Quantity):
                logger.warning(f"Unit not set for attribute {self} of {bind}")
                value = value * self.unit
        # todo validation of attributes on creation time makes accept_valids
        #  function in base_tasks.py unusable as not valid attributes are never
        #  created
        # if value is not None and bind.conditions:
        #     if not self.check_conditions(bind, value, self.name):
        #         value = None

        return value

    @staticmethod
    def get_from_default_propertyset(bind, default):
        """Get value from default property set"""
        try:
            value = bind.get_exact_property(*default)
        except Exception:
            value = None
        return value

    @staticmethod
    def get_from_finder(bind, name):
        finder = getattr(bind, 'finder', None)
        if finder:  # Aggregations have no finder
            try:
                return bind.finder.find(bind, name)
            except (AttributeError, TypeError):
                pass
        return None

    @staticmethod
    def get_from_patterns(bind, patterns, name):
        """Get value from non default property sets matching patterns"""
        value = bind.select_from_potential_properties(patterns, name, False)
        return value

    @staticmethod
    def get_from_functions(bind, functions, name):
        """Get value from functions.

        First successful function calls return value is used"""
        value = None
        for func in functions:
            try:
                value = func(bind, name)
            except Exception as ex:
                logger.error("Function '%s' of %s.%s raised %s",
                             func.__name__, bind, name, ex)
                pass
            else:
                if value is not None:
                    break
        return value

    @staticmethod
    def get_conditions(bind, name):
        """Get conditions for attribute"""
        conditions = []
        for condition in bind.conditions:
            if condition.key == name:
                conditions.append(partial(condition.check, bind))
        return conditions

    @staticmethod
    def check_conditions(bind, value, name):
        """Check conditions"""
        conditions = Attribute.get_conditions(bind, name)
        for condition_check in conditions:
            if not condition_check(value):
                return False
        return True

    def create_decision(self, bind):
        """Created Decision for this Attribute"""
        # TODO: set state in output dict -> attributemanager
        conditions = [lambda x: True] if not bind.conditions else \
            Attribute.get_conditions(bind, self.name)
        decision = RealDecision(
            question="Enter value for %s of %s" % (self.name, bind),
            console_identifier="Name: %s, GUID: %s"
                               % (bind.name, bind.guid),
            # output=bind.attributes,
            key=self.name,
            global_key="%s_%s.%s" % (bind.ifc_type, bind.guid, self.name),
            allow_skip=False,
            validate_func=conditions,
            unit=self.unit,
        )
        return decision

    @staticmethod
    def ifc_post_processing(value):
        """Function for post processing of ifc property values (e.g. diameter
        list -> diameter)by default this function does nothing"""
        if isinstance(value, str) and value.isnumeric():
            value = float(value)
        return value

    def request(self, bind, external_decision=None):
        """Request attribute via decision.

        Args:
            bind: bound instance of attribute
            external_decision: Decision to use instead of default decision
        """

        # read current value and status
        value, status = self._inner_get(bind)

        if value is None:
            if status == Attribute.STATUS_NOT_AVAILABLE:
                _decision = self.get_dependency_decisions(
                    bind, external_decision)
                return _decision
        elif isinstance(value, list):
            if not all(value):
                _decision = self.get_dependency_decisions(bind,
                                                          external_decision)
                return _decision
            return
        elif isinstance(value, Decision):
            # already a decision stored in value
            return value
        else:
            # already requested or available
            return

    def get_dependency_decisions(self, bind, external_decision=None):
        """Get dependency decisions"""
        if self.functions is not None:
            self.get_attribute_dependency(bind)
            if self.dependant_attributes or self.dependant_elements:
                _decision = {}
                if self.dependant_elements:
                    # case for attributes that depend on the same
                    # attribute in other elements
                    _decision_inst = self.dependant_elements_decision(
                        bind)
                    for inst in _decision_inst:
                        if inst not in _decision:
                            _decision[inst] = _decision_inst[inst]
                        else:
                            _decision[inst].update(_decision_inst[inst])
                        if inst is self:
                            print()
                elif self.dependant_attributes:
                    # case for attributes that depend on others
                    # attributes in the same instance
                    for d_attr in self.dependant_attributes:
                        bind.request(d_attr)
                _decision.update(
                    {self.name: (self.dependant_attributes, self.functions)})
            else:
                _decision = external_decision or self.create_decision(
                    bind)
        else:
            # actual request
            _decision = external_decision or self.create_decision(bind)
        status = Attribute.STATUS_REQUESTED
        self._inner_set(bind, _decision, status)

        return _decision

    def get_attribute_dependency(self, instance):
        """Get attribute dependency.

        When an attribute depends on other attributes in the same instance or
        the same attribute in other elements, this function gets the
        dependencies when they are not stored on the respective dictionaries.
        """
        if not self.dependant_attributes and not self.dependant_elements:
            dependant = []
            for func in self.functions:
                for attr in func.__code__.co_names:
                    if hasattr(instance, attr):
                        dependant.append(attr)

            for dependant_item in dependant:
                # case for attributes that depend on the same attribute in
                # other elements -> dependant_elements
                logger.warning("Attribute \"%s\" from class \"%s\" has no: "
                               % (self.name, type(instance).__name__))
                if 'elements' in dependant_item:
                    self.dependant_elements = dependant_item
                    logger.warning("- dependant elements: \"%s\"" %
                                   dependant_item)
                # case for attributes that depend on the other attributes in
                # the same instance -> dependant_attributes
                else:
                    if self.dependant_attributes is None:
                        self.dependant_attributes = []
                    self.dependant_attributes.append(dependant_item)
                    logger.warning("- dependant attributes: \"%s\"" %
                                   dependant_item)

    def dependant_elements_decision(self, bind) -> dict:
        """Function to request attributes in other elements different to bind,
        that are later on necessary to calculate an attribute in bind (case of
        aggregation)

        Returns:
        _decision: key: is the instance, value: is another dict composed of the
                   attr name and the corresponding decision or function to
                   calculate said attribute
        """
        _decision = {}
        for inst in getattr(bind, self.dependant_elements):
            # request instance attribute
            pre_decisions = inst.attributes.get_decisions()
            inst.request(self.name)
            additional_decisions = inst.attributes.get_decisions()
            inst_decisions = [dec for dec in additional_decisions
                              if dec not in pre_decisions]
            for decision in inst_decisions:
                if decision is not None:
                    if inst not in _decision:
                        _decision[inst] = {}
                    if isinstance(decision, dict):
                        _decision[inst].update(decision)
                    else:
                        _decision[inst][decision.key] = decision
        if self.dependant_attributes:
            for d_attr in self.dependant_attributes:
                requested_decisions = bind.request(d_attr)
                if requested_decisions is not None:
                    for inst, attr in requested_decisions.items():
                        if not isinstance(inst, str):
                            if inst not in _decision:
                                _decision[inst] = {}
                            _decision[inst].update(attr)
        return _decision

    def initialize(self, manager):
        if not self.name:
            print(self)
            raise AttributeError("Attribute.name not set!")

        manager[self.name] = (None, self.STATUS_UNKNOWN)

    def _inner_get(self, bind):
        return bind.attributes[self.name]

    def _inner_set(self, bind, value, status):
        # TODO: validate
        bind.attributes[self.name] = (value, status)

    def __get__(self, bind, owner):
        """This gets called if attribute is accessed via element.attribute.

        The descriptors get function handles the different underlying ways to
        get an attributes value"""
        if bind is None:
            return self

        # read current value and status
        value_or_decision, status = self._inner_get(bind)
        changed = False
        value = None

        if isinstance(value_or_decision, Decision):
            # decision
            if status != self.STATUS_REQUESTED:
                raise AssertionError("Inconsistent status")
            if value_or_decision.valid():
                value = value_or_decision.value
                status = self.STATUS_AVAILABLE
                changed = True
        else:
            value = value_or_decision

        if value is None and status == self.STATUS_UNKNOWN:
            value = self._get_value(bind)
            status = self.STATUS_AVAILABLE if value is not None \
                else self.STATUS_NOT_AVAILABLE  # change for temperature
            changed = True

        if changed:
            # write back new value and status
            self._inner_set(bind, value, status)

        return value

    def __set__(self, bind, value):
        if self.unit:
            if isinstance(value, ureg.Quantity):
                # case for quantity
                _value = value.to(self.unit)
            elif isinstance(value, list):
                # case for list of quantities
                _value = []
                for item in value:
                    if isinstance(item, ureg.Quantity):
                        _value.append(item.to(self.unit))
                    else:
                        _value.append(item * self.unit)
            else:
                _value = value * self.unit
        else:
            _value = value
        self._inner_set(bind, _value, self.STATUS_AVAILABLE)

    def __str__(self):
        return "Attribute %s" % self.name


class AttributeManager(dict):
    """Manages the attributes.

    Every bim2sim element owns an instance of the AttributeManager class which
    manages the corresponding attributes of this element. It as an dict with
        key: name of attribute as string
        value: tuple with (value of attribute, Status of attribute).
    """

    def __init__(self, bind):
        super().__init__()
        self.bind = bind

        for name in self.names:
            attr = self.get_attribute(name)
            attr.initialize(self)

    def __setitem__(self, name, value):
        if name not in self.names:
            raise AttributeError("Invalid Attribute '%s'. Choices are %s" % (
                name, list(self.names)))

        if isinstance(value, tuple) and len(value) == 2:
            super().__setitem__(name, value)
        else:
            super().__setitem__(name, (value, Attribute.STATUS_AVAILABLE))

    def update(self, other):
        # dict.update does not invoke __setitem__
        for k, v in other.items():
            self.__setitem__(k, v)

    def request(self, name: str, external_decision: Decision = None) \
            -> Union[None, Decision]:
        """Request attribute by name.

        Checks the status of the requested attribute and returns

        Args:
            name: name of requested attribute
            external_decision: custom decision to get attribute from

        Returns:
            A Decision to get the requested attributes value.
            """
        try:
            attr = self.get_attribute(name)
        except KeyError:
            raise KeyError("%s has no Attribute '%s'" % (self.bind, name))
        value, status = self[name]
        if status == Attribute.STATUS_UNKNOWN:
            # make sure default methods are tried
            getattr(self.bind, name)
            value, status = self[name]
        if value is None:
            if status == Attribute.STATUS_NOT_AVAILABLE:
                decision = attr.request(self.bind, external_decision)
                return decision
        if isinstance(value, list):
            # case for list of quantities
            if not all(v is not None for v in value):
                decision = attr.request(self.bind, external_decision)
                return decision
        elif isinstance(value, Decision):
            if external_decision and value is not external_decision:
                raise AttributeError("Can't set external decision for an "
                                     "already requested attribute.")
            return value
        else:
            # already requested or available
            return

    def get_attribute(self, name):
        return getattr(type(self.bind), name)

    def get_unit(self, name):
        attr = self.get_attribute(name)
        return attr.unit

    @property
    def names(self):
        """Returns a generator object with all attributes that the corresponding
        bind owns."""
        return (name for name in dir(type(self.bind))
                if isinstance(getattr(type(self.bind), name), Attribute))

    def get_decisions(self) -> DecisionBunch:
        """Return all decision of attributes with status REQUESTED."""
        decisions = DecisionBunch()
        for dec, status in self.values():
            if status == Attribute.STATUS_REQUESTED:
                decisions.append(dec)
        return decisions


def multi_calc(func):
    """Decorator for calculation of multiple Attribute values"""

    def wrapper(bind, name):
        # inner function call
        result = func(bind)
        value = result.pop(name)
        # send all other result values to AttributeManager instance
        bind.attributes.update(result)
        return value

    return wrapper
