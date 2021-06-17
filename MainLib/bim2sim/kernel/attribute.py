import logging
from contextlib import contextmanager
from typing import Tuple, Iterable, Callable, Any, Union

import pint
import re

from unicodedata import decimal

from bim2sim.decision import RealDecision, BoolDecision, ListDecision, Decision, \
    DecisionBunch
from bim2sim.kernel.units import ureg
import inspect

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

    value and status of attribute are stored in __dict__ of bound instance"""
    # https://rszalski.github.io/magicmethods/
    STATUS_UNKNOWN = 'UNKNOWN'
    STATUS_REQUESTED = 'REQUESTED'
    STATUS_AVAILABLE = 'AVAILABLE'
    STATUS_NOT_AVAILABLE = 'NOT_AVAILABLE'

    def __init__(self,
                 description: str = "",
                 unit: pint.Unit = None,
                 default_ps: Tuple[str, str] = None,
                 default_association: Tuple[str, str] = None,
                 patterns: Iterable = None,
                 ifc_postprocessing: Callable[[Any], Any] = None,
                 functions: Iterable[Callable[[object, str], Any]] = None,
                 default=None):
        """

        Args:
            description: Description of attribute
            unit: pint unit of attribute, defaults to dimensionless
            default_ps: tuple of propertyset name and property name
            default_association: tuple of association name and property name
            patterns: iterable of (compiled) re patterns
            ifc_postprocessing: callable to apply on initial value, returns final value
            functions: iterable of callable with signature func(bind, name) -> value. First return with no error is used as value.
            default: default value which is used if no other source is successful
        """
        self.name = None  # auto set by AutoAttributeNameMeta
        self.description = description
        self.unit = unit

        self.default_ps = default_ps
        self.default_association = default_association
        self.patterns = patterns
        self.functions = functions
        self.default_value = default

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
        value = None
        if bind.ifc:  # don't bother if there is no ifc
            # default property set
            if value is None and self.default_ps:
                raw_value = self.get_from_default_propertyset(bind, self.default_ps)
                value = self.ifc_post_processing(raw_value)

            if value is None and (self.default_association):
                raw_value = self.get_from_default_assocation(bind, self.default_association)
                value = self.ifc_post_processing(raw_value)

            # tool specific properties (finder)
            if value is None:
                raw_value = self.get_from_finder(bind, self.name)
                value = self.ifc_post_processing(raw_value)

            # custom properties by patterns
            if value is None and self.patterns:
                raw_value = self.get_from_patterns(bind, self.patterns, self.name)
                value = self.ifc_post_processing(raw_value)

        # custom functions
        if value is None and self.functions:
            value = self.get_from_functions(bind, self.functions, self.name)

        # logger value none
        if value is None:
            quality_logger.warning("Attribute '%s' of %s %s was not found in default PropertySet, default  Association,"
                                   " finder, patterns or functions",
                                   self.name, bind.ifc_type, bind.guid)

        # default value
        if value is None and self.default_value is not None:
            value = self.default_value
            if value is not None and self.unit:
                value = value * self.unit

        # check unit
        if self.unit is not None and value is not None and not isinstance(value, ureg.Quantity):
            logger.warning("Unit not set!")
            value = value * self.unit

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
    def get_from_default_assocation(bind, default):
        """Get value from default association"""
        try:
            value = bind.get_exact_association(default[0], default[1])
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
        for i, func in enumerate(functions):
            try:
                value = func(bind, name)
            except Exception as ex:
                logger.error("Function %d of %s.%s raised %s", i, bind, name, ex)
                pass
            else:
                if value is not None:
                    break
        return value

    @staticmethod
    # todo only used for HVAC. Move to own task similar to BPS


    def create_decision(self, bind):
        """Created Decision for this Attribute"""
        # TODO: set state in output dict -> attributemanager
        decision = RealDecision(
            "Enter value for %s of %s" % (self.name, bind),
            # validate_func=lambda x: isinstance(x, float),
            # output=bind.attributes,
            key=self.name,
            global_key="%s_%s.%s" % (bind.ifc_type, bind.guid, self.name),
            allow_skip=False,
            validate_func=lambda x: True,  # TODO meaningful validation
            unit=self.unit,
        )
        return decision

    @staticmethod
    def ifc_post_processing(value):
        """Function for post processing of ifc property values (e.g. diameter list -> diameter)
        by default this function does nothing"""
        return value

    def request(self, bind, external_decision=None):
        """Request attribute
        :param bind: bound instance of attribute
        :param external_decision: Decision to use instead of default decision
        """

        # read current value and status
        value, status = self._inner_get(bind)

        if value is None:
            if status == Attribute.STATUS_NOT_AVAILABLE:
                # actual request
                _decision = external_decision or self.create_decision(bind)
                # bind.related_decisions.append(decision)
                status = Attribute.STATUS_REQUESTED
                self._inner_set(bind, _decision, status)
                return _decision
        elif isinstance(value, Decision):
            # already a decision stored in value
            return value
        else:
            # already requested or available
            return

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
        # this gets called if attribute is accessed
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
            status = self.STATUS_AVAILABLE if value is not None else self.STATUS_NOT_AVAILABLE  # change for temperature
            changed = True

        if changed:
            # write back new value and status
            self._inner_set(bind, value, status)

        return value

    def __set__(self, bind, value):
        if self.unit:
            if isinstance(value, ureg.Quantity):
                _value = value.to(self.unit)
            else:
                _value = value * self.unit
        else:
            _value = value
        self._inner_set(bind, _value, self.STATUS_AVAILABLE)

    def __str__(self):
        return "Attribute %s" % self.name


class AttributeManager(dict):
    """Attribute Manager class"""

    def __init__(self, bind):
        super().__init__()
        self.bind = bind

        for name in self.names:
            attr = self.get_attribute(name)
            attr.initialize(self)

    def __setitem__(self, name, value):
        if name not in self.names:
            raise AttributeError("Invalid Attribute '%s'. Choices are %s" % (name, list(self.names)))

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

        :param name: name of requested attribute
        :param external_decision: custom decision to get attribute from"""
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
        if isinstance(value, Decision):
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
        return (name for name in dir(type(self.bind))
                if isinstance(getattr(type(self.bind), name), Attribute))

    def get_decisions(self) -> DecisionBunch:
        """Return all decision of attributes with status REQUESTED."""
        decisions = DecisionBunch()
        for dec, status in self.items():
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
