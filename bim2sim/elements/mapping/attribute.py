import inspect
import functools
import logging
from functools import partial
from typing import Tuple, Iterable, Callable, Any, Union

import pint

from bim2sim.elements.mapping.units import ureg
from bim2sim.kernel.decision import RealDecision, Decision, \
    DecisionBunch, BoolDecision, StringDecision
from bim2sim.utilities.types import AttributeDataSource

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

    * UNKNOWN: default status at the beginning.
    * REQUESTED: Attribute was already requested via a decision??.
    * AVAILABLE: Attribute exists and is available.
    * NOT_AVAILABLE: No way was found to obtain the attributes value.
    * RESET: The Attribute was reset.

    To find more about Descriptor objects follow the explanations on
    https://rszalski.github.io/magicmethods/#descriptor
    """
    STATUS_UNKNOWN = 'UNKNOWN'
    STATUS_REQUESTED = 'REQUESTED'
    STATUS_AVAILABLE = 'AVAILABLE'
    STATUS_NOT_AVAILABLE = 'NOT_AVAILABLE'
    STATUS_RESET = 'RESET'

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
                 dependant_elements: str = None,
                 attr_type: Union[
                     type(bool), type(str), type(int), type(float)] = float
                 ):
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
            dependant_elements: list of additional elements necessary to
                calculate the attribute
            attr_type: data type of attribute, used to determine decision type
                if decision is needed, float is default
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
        self.dependant_elements = dependant_elements
        # data_source stores where the information was obtained from throughout
        # the bim2sim process
        self.data_source = None
        self.attr_type = attr_type

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
        data_source = None
        if bind.ifc:  # don't bother if there is no ifc
            # default ifc attribute
            if value is None and self.ifc_attr_name:
                if hasattr(bind.ifc, self.ifc_attr_name):
                    raw_value = getattr(bind.ifc, self.ifc_attr_name)
                    value = self.post_process_value(bind, raw_value)
                    if value is not None:
                        data_source = AttributeDataSource.ifc_attr
            # default property set
            if value is None and self.default_ps:
                raw_value = self.get_from_default_propertyset(bind,
                                                              self.default_ps)
                value = self.post_process_value(bind, raw_value)
                if value is not None:
                    data_source = AttributeDataSource.default_ps

            if value is None and self.default_association:
                raw_value = self.get_from_default_propertyset(
                    bind, self.default_association)
                value = self.post_process_value(bind, raw_value)
                if value is not None:
                    data_source = AttributeDataSource.default_association

            # tool specific properties (finder)
            if value is None:
                raw_value = self.get_from_finder(bind, self.name)
                value = self.post_process_value(bind, raw_value)
                if value is not None:
                    data_source = AttributeDataSource.finder

            # custom properties by patterns
            if value is None and self.patterns:
                raw_value = self.get_from_patterns(bind, self.patterns,
                                                   self.name)
                value = self.post_process_value(bind, raw_value)
                if value is not None:
                    data_source = AttributeDataSource.patterns

        # custom functions
        if value is None and self.functions:
            value = self.get_from_functions(bind, self.functions, self.name)
        if value is not None:
            data_source = AttributeDataSource.function

        # logger value none
        if value is None:
            quality_logger.warning(
                "Attribute '%s' of %s %s was not found in default "
                "PropertySet, default  Association, finder, patterns or "
                "functions",
                self.name, bind.ifc_type, bind.guid)

        # default value
        if value is None and self.default_value is not None:
            value = self.default_value
            if value is not None and self.unit:
                value = value * self.unit
                data_source = AttributeDataSource.default

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

        return value, data_source

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
    def get_from_functions(bind, functions: list, name: str):
        """Get value from functions.

        First successful function call's return value is used. Functions can be
        1. Methods from the bind object's class hierarchy (use inheritance)
        2. Methods from external classes (call directly with bind as first arg)

        Args:
            bind: The bind object
            functions: List of function objects
            name: The attribute name to process
        """
        value = None
        for func in functions:
            # Check if the function's class is in the bind object's class
            # hierarchy
            if hasattr(func, '__qualname__') and '.' in func.__qualname__:
                func_class_name = func.__qualname__.split('.')[0]

                # Check if the function's class is in the bind's class
                # hierarchy
                is_in_hierarchy = False
                for cls in bind.__class__.__mro__:
                    if cls.__name__ == func_class_name:
                        is_in_hierarchy = True
                        break

                if is_in_hierarchy:
                    # Function is from bind's class hierarchy,
                    # use inheritance
                    try:
                        func_to_call = getattr(bind, func.__name__)
                        value = func_to_call(name)
                    except Exception as ex:
                        logger.error("Function '%s' of %s.%s raised %s",
                                     func.__name__, bind, name, ex)
                        pass
                else:
                    # Function is from an external class, call directly with
                    # bind as first arg
                    try:
                        value = func(bind, name)
                    except Exception as ex:
                        logger.error("Function '%s' of %s.%s raised %s",
                                     func.__name__, bind, name, ex)
                        pass
            else:
                # Fallback for functions without __qualname__, use inheritance
                try:
                    func_to_call = getattr(bind, func.__name__)
                    value = func_to_call(name)
                except Exception as ex:
                    logger.error("Function '%s' of %s.%s raised %s",
                                 func.__name__, bind, name, ex)
                    pass

            # Break the loop if we got a non-None value
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

        console_identifier = "Name: %s, GUID: %s" % (bind.name, bind.guid)
        related = bind.guid
        key = self.name
        global_key = "%s_%s.%s" % (bind.ifc_type, bind.guid, self.name)
        if self.attr_type == bool:
            question = f"Is the attribute {self.name} of {bind} True/Active?"
            decision = BoolDecision(
                question=question,
                console_identifier=console_identifier,
                key=key,
                global_key=global_key,
                allow_skip=False,
                related=related
            )
        elif self.attr_type == str:
            question = "Enter value for %s of %s" % (self.name, bind)
            decision = StringDecision(
                question=question,
                console_identifier=console_identifier,
                key=key,
                global_key=global_key,
                allow_skip=False,
                related=related
            )
        else:
            question = "Enter value for %s of %s" % (self.name, bind)
            decision = RealDecision(
                question=question,
                console_identifier=console_identifier,
                key=key,
                global_key=global_key,
                allow_skip=False,
                validate_func=conditions,
                unit=self.unit,
                related=related
            )
        return decision

    def post_process_value(self, bind, raw_value):
        """Post-process the raw_value.

        If attribute is given an external ifc_postprocessing entry, this
        function will be used. Otherwise, the pre implemented
        ifc_post_processing of the attribute class will be used.
        If an external ifc_postprocessing is give, this is checked for being
        static or not, because if not static, the bind needs to be forwarded to
        the method.
        """
        if raw_value is not None:
            ifc_post_process_func_name = self.ifc_post_processing.__name__
            # check if external ifc_post_processing method exists:
            if hasattr(bind, ifc_post_process_func_name):
                # check of the method is static or needs the bind
                is_static = isinstance(inspect.getattr_static(
                    bind, ifc_post_process_func_name), staticmethod)
                if is_static:
                    value = self.ifc_post_processing(raw_value)
                else:
                    value = self.ifc_post_processing(bind, raw_value)
            else:
                value = self.ifc_post_processing(raw_value)
        else:
            value = raw_value
        return value

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

        # Read current value, status, and data source
        value, status, _ = self._inner_get(bind)

        # Case 1: Value is None and status is STATUS_NOT_AVAILABLE
        if value is None and status == Attribute.STATUS_NOT_AVAILABLE:
            return self.get_dependency_decisions(bind, external_decision)

        # Case 2: Value is a list and not all elements are truthy
        if isinstance(value, list) and not all(value):
            return self.get_dependency_decisions(bind, external_decision)

        # Case 3: Value is already a Decision instance
        if isinstance(value, Decision):
            return value

        # Case 4: Value is available or already requested (no action needed)
        return

    def reset(self, bind, data_source=AttributeDataSource.manual_overwrite):
        """Reset attribute, set to None and STATUS_NOT_AVAILABLE."""
        self._inner_set(
            bind, None, Attribute.STATUS_RESET, data_source)

    def get_dependency_decisions(self, bind, external_decision=None):
        """Get dependency decisions"""
        status = Attribute.STATUS_REQUESTED
        if self.functions is not None:
            if self.dependant_elements:
                logger.warning(f'Attribute {self.name} of element {bind} uses '
                               f'"dependent_elements" functionality, but this '
                               f'is currently not supported. Please take this'
                               f' into account.')
        #         _decision = {}
        #         # raise NotImplementedError(
        #         #     "The implementation of dependant elements needs to be"
        #         #     " revised.")
        #         # case for attributes that depend on the same
        #         # attribute in other elements
        #         _decision_inst = self.dependant_elements_decision(
        #             bind)
        #         for inst in _decision_inst:
        #             if inst not in _decision:
        #                 _decision[inst] = _decision_inst[inst]
        #             else:
        #                 _decision[inst].update(_decision_inst[inst])
        #         for dec_inst, dec in _decision.items():
        #             self._inner_set(
        #                 dec_inst, dec, status, self.data_source)
        #     else:
        #         _decision = external_decision or self.create_decision(
        #             bind)
        # else:
        #     # actual request
        #     _decision = external_decision or self.create_decision(bind)
        _decision = external_decision or self.create_decision(bind)
        self._inner_set(bind, _decision, status, self.data_source)

        return _decision

    # def get_attribute_dependency(self, instance):
    #     """Get attribute dependency.
    #
    #     When an attribute depends on other attributes in the same instance or
    #     the same attribute in other elements, this function gets the
    #     dependencies when they are not stored on the respective dictionaries.
    #     """
    #     if not self.dependant_attributes and not self.ConsoleDecisionHandler:
    #         dependant = []
    #         for func in self.functions:
    #             for attr in func.__code__.co_names:
    #                 if hasattr(instance, attr):
    #                     dependant.append(attr)
    #
    #         for dependant_item in dependant:
    #             # case for attributes that depend on the same attribute in
    #             # other elements -> dependant_elements
    #             logger.warning("Attribute \"%s\" from class \"%s\" has no: "
    #                            % (self.name, type(instance).__name__))
    #             if 'elements' in dependant_item:
    #                 self.dependant_elements = dependant_item
    #                 logger.warning("- dependant elements: \"%s\"" %
    #                                dependant_item)
    #             # case for attributes that depend on the other attributes in
    #             # the same instance -> dependant_attributes
    #             else:
    #                 if self.dependant_attributes is None:
    #                     self.dependant_attributes = []
    #                 self.dependant_attributes.append(dependant_item)
    #                 logger.warning("- dependant attributes: \"%s\"" %
    #                                dependant_item)

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
        # if self.dependant_attributes:
        #     for d_attr in self.dependant_attributes:
        #         requested_decisions = bind.request(d_attr)
        #         if requested_decisions is not None:
        #             for inst, attr in requested_decisions.items():
        #                 if not isinstance(inst, str):
        #                     if inst not in _decision:
        #                         _decision[inst] = {}
        #                     _decision[inst].update(attr)
        return _decision

    def initialize(self, manager):
        if not self.name:
            print(self)
            raise AttributeError("Attribute.name not set!")

        manager[self.name] = (None, self.STATUS_UNKNOWN, None)

    def _inner_get(self, bind):
        return bind.attributes[self.name]

    def _inner_set(self, bind, value, status, data_source):
        # TODO: validate
        bind.attributes[self.name] = value, status, data_source

    def __get__(self, bind, owner):
        """This gets called if attribute is accessed via element.attribute.

        The descriptors get function handles the different underlying ways to
        get an attributes value"""
        if bind is None:
            return self

        # read current value and status
        value_or_decision, status, data_source = self._inner_get(bind)
        changed = False
        value = None

        if isinstance(value_or_decision, Decision):
            # decision
            if status != self.STATUS_REQUESTED:
                raise AssertionError("Inconsistent status")
            if value_or_decision.valid():
                value = value_or_decision.value
                status = self.STATUS_AVAILABLE
                data_source = AttributeDataSource.decision
                changed = True
        else:
            value = value_or_decision

        if (value is None and status
                in [self.STATUS_UNKNOWN, self.STATUS_RESET]):
            value, data_source = self._get_value(bind)
            status = self.STATUS_AVAILABLE if value is not None \
                else self.STATUS_NOT_AVAILABLE  # change for temperature
            changed = True

        if changed:
            # write back new value and status
            self._inner_set(bind, value, status, data_source)

        return value

    def __set__(self, bind, value):
        if isinstance(value, tuple) and len(value) == 2:
            data_source = value[1]
            value = value[0]
        else:
            # if not data_source is provided, 'manual_overwrite' will be set
            data_source = AttributeDataSource.manual_overwrite
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
        self._inner_set(bind, _value, self.STATUS_AVAILABLE, data_source)

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
        if isinstance(value, tuple) and len(value) == 3:
            if not (isinstance(value[-1], AttributeDataSource)
                    or value[-1] is None):
                try:
                    getattr(AttributeDataSource, value[-1])
                except AttributeError:
                    raise ValueError(
                        f"Non valid DataSource provided for attribute {name} "
                        f"of element {self.bind}")
            super().__setitem__(name, value)
        else:
            if not isinstance(value, tuple):
                super().__setitem__(name, (
                    value,
                    Attribute.STATUS_AVAILABLE,
                    AttributeDataSource.manual_overwrite))
            elif isinstance(value[-1], AttributeDataSource) or value[-1] is None:
                super().__setitem__(name, (value, Attribute.STATUS_AVAILABLE))
            else:
                raise ValueError("datasource")

    def update(self, other):
        # dict.update does not invoke __setitem__
        for k, v in other.items():
            self.__setitem__(k, v)

    def reset(self, name, data_source=AttributeDataSource.manual_overwrite):
        """Reset attribute, set to None and STATUS_NOT_AVAILABLE."""
        # TODO this has limitations when the corresponding attribute uses
        #  functions to calculate the value, see #760 for more information
        try:
            attr = self.get_attribute(name)
        except KeyError:
            raise KeyError("%s has no Attribute '%s'" % (self.bind, name))
        attr.reset(self.bind, data_source)

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
        value, status, data_source = self[name]
        if status in [Attribute.STATUS_UNKNOWN, Attribute.STATUS_RESET]:
            # make sure default methods are tried
            getattr(self.bind, name)
            value, status, data_source = self[name]
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
        for dec, status, data_source in self.values():
            if status == Attribute.STATUS_REQUESTED:
                decisions.append(dec)
        return decisions


def multi_calc(func):
    """Decorator for calculation of multiple Attribute values.

    Decorator functools.wraps is needed to return the real function name
    for get_from_functions method.
    """

    @functools.wraps(func)
    def wrapper(bind, name):
        # inner function call
        result = func(bind)
        value = result.pop(name)
        # send all other result values to AttributeManager instance
        bind.attributes.update(result)
        return value

    return wrapper
