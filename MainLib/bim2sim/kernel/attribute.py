
import logging
from contextlib import contextmanager

import pint

from bim2sim.decision import RealDecision

from bim2sim.kernel.units import ureg

logger = logging.getLogger(__name__)
quality_logger = logging.getLogger('bim2sim.QualityReport')


# class AutoAttributeNameMeta(type):
#     """Detect setting on Attributes on class level and set name as given"""
#     def __setattr__(self, name, value):
#         if isinstance(value, Attribute):
#             value.name = name
#         return super().__setattr__(name, value)


class Attribute:
    """Descriptor of element attribute

    value and status of attribute are stored in __dict__ of bound instance"""
    # https://rszalski.github.io/magicmethods/
    STATUS_UNKNOWN = 'UNKNOWN'
    STATUS_REQUESTED = 'REQUESTED'
    STATUS_AVAILABLE = 'AVAILABLE'
    STATUS_NOT_AVAILABLE = 'NOT_AVAILABLE'
    _force = False

    def __init__(self, name=None,
                 description="",
                 unit=None,
                 default_ps=None,
                 patterns=None,
                 ifc_postprocessing=None,
                 functions=None,
                 default=None):
        if name:
            logger.warning("'name' is obsolete. Remove name '%s'" % name)
        self.name = None  # auto set by AutoAttributeNameMeta
        self.description = description
        self.unit = unit

        self.default_ps = default_ps
        self.patterns = patterns
        self.functions = functions
        self.default_value = default

        if ifc_postprocessing:
            self.ifc_post_processing = ifc_postprocessing

        # TODO argument for validation function

    @property
    def value_name(self):
        return '_%s_value_' % self.name

    @property
    def status_name(self):
        return '_%s_status_' % self.name

    def get_value(self, bind):
        return getattr(bind, self.value_name, None)

    def set_value(self, bind, value):
        # TODO: validate
        setattr(bind, self.value_name, value)

    def get_status(self, bind):
        return getattr(bind, self.status_name, self.STATUS_UNKNOWN)

    def set_status(self, bind, status):
        setattr(bind, self.status_name, status)

    def _inner_get(self, bind):

        value = None
        # default property set
        if value is None and self.default_ps:
            raw_value = self.get_from_default(bind, self.default_ps)
            value = self.ifc_post_processing(raw_value)
            if value is None:
                quality_logger.warning("Attribute '%s' of %s %s was not found in default PropertySet",
                                       self.name, bind.ifc_type, bind.guid)

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

        # enrichment
        if value is None:
            value = self.get_from_enrichment(bind, self.name)

        # default value
        if value is None and self.default_value:
            value = self.default_value
            if value and self.unit:
                value = value * self.unit

        # check unit
        if value is not None and not isinstance(value, pint.Quantity):
            logger.warning("Unit not set!")
            value = value * self.unit

        return value

    @staticmethod
    def get_from_default(bind, default):
        try:
            value = bind.get_exact_property(default[0], default[1])
        except Exception:
            value = None
        return value

    @staticmethod
    def get_from_finder(bind, name):
        finder = getattr(bind, 'finder', None)
        if finder:  # Aggregations have no finder
            try:
                return bind.finder.find(bind, name)
            except AttributeError:
                pass
        return None

    @staticmethod
    def get_from_patterns(bind, patterns, name):
        # TODO: prevent decision on call by get()
        value = bind.select_from_potential_properties(patterns, name, False)
        return value

    @staticmethod
    def get_from_functions(bind, functions, name):
        value = None
        for i, func in enumerate(functions):
            try:
                value = func(bind, name)
            except Exception as ex:
                logger.error("Function %d of %s.%s raised %s", i, bind, name, ex)
                pass
            else:
                break
        return value

    @staticmethod
    def get_from_enrichment(bind, name):
        enrichment = getattr(bind, 'enrichment_data', None)
        if enrichment:
            value = enrichment.get(name)
        else:
            value = None
        return value

    @staticmethod
    def get_from_decision(bind, name):
        # TODO: decision
        decision = RealDecision(
            "Enter value for %s of %s" % (name, bind.name),
            # output=self,
            # output_key=name,
            global_key="%s_%s.%s" % (bind.ifc_type, bind.guid, name),
            allow_skip=False, allow_load=True, allow_save=True,
            validate_func=lambda x: True,  # TODO meaningful validation
            collect=False,
            quick_decide=True
        )
        value = decision.value
        return value

    def create_decision(self, bind, collect=True):
        """Created Decision for this Attribute"""
        decision = RealDecision(
            "Enter value for %s of %s" % (self.name, bind.name),
            # validate_func=lambda x: isinstance(x, float),
            output=bind.__dict__,
            output_key=self.name,
            global_key="%s_%s.%s" % (bind.ifc_type, bind.guid, self.name),
            allow_skip=False, allow_load=True, allow_save=True,
            validate_func=lambda x: True,  # TODO meaningful validation
            collect=collect,
            unit=self.unit,
        )
        return decision

    @staticmethod
    @contextmanager
    def force_get():
        """Contextmanager to get missing attributes immediately"""
        Attribute._force = True
        yield
        Attribute._force = False

    @staticmethod
    def ifc_post_processing(value):
        """Function for post processing of ifc property values (e.g. diameter list -> diameter)
        by default this function does nothing"""
        return value

    def request(self, bind):
        """Request attribute"""

        # read current value and status
        value = self.get_value(bind)
        status = self.get_status(bind)

        if value is None:
            if status == Attribute.STATUS_NOT_AVAILABLE:
                # actual request
                decision = self.create_decision(bind)
                bind.related_decisions.append(decision)
                status = Attribute.STATUS_REQUESTED
                self.set_status(bind, status)
                return decision
        else:
            # already requested or available
            return

    def initialize(self, bind):
        if not self.name:
            raise AttributeError("Attribute.name not set!")

        if hasattr(bind, self.value_name) or hasattr(bind, self.status_name):
            raise AttributeError('Can\'t overwrite existing attributes of %s' % bind)

    def __get__(self, bind, owner):
        if bind is None:
            return self

        # read current value and status
        value = self.get_value(bind)
        status = self.get_status(bind)

        if value is None and status == self.STATUS_UNKNOWN:
            value = self._inner_get(bind)
            status = self.STATUS_AVAILABLE if value else self.STATUS_NOT_AVAILABLE

        if self._force and value is None:
            value = self.get_from_decision(bind, self.name)
            status = Attribute.STATUS_AVAILABLE

        # write back new value and status
        self.set_value(bind, value)
        self.set_status(bind, status)

        return value

    def __set__(self, bind, value):
        self.set_value(bind, value)

    def __str__(self):
        return "Attribute %s" % self.name


class AttributeManager(dict):
    """Attribute Manager class"""
    def __init__(self, bind):
        super().__init__()
        self.bind = bind
        
        # search bind class for Attributes
        for name, obj in type(self.bind).__dict__.items():
            if isinstance(obj, Attribute):
                if not obj.name:
                    # auto detect name
                    obj.name = name
                obj.initialize(self.bind)
                self[name] = obj

    def __setitem__(self, name, value):
        if isinstance(value, Attribute):
            return super().__setitem__(name, value)

        if name not in self.names:
            raise AttributeError("Invalid Attribute '%s'. Choices are %s" % (name, list(self.names)))

        # set value of Attribute (used by decisions)
        self.__getitem__(name).__set__(self.bind, value)

    def update(self, other):
        # dict.update does not invoke __setitem__
        for k, v in other.items():
            self.__setitem__(k, v)

    def request(self, name=None):
        """Request attribute by name. (name=None -> all)"""
        if name:
            names = [name]
        else:
            names = self.names

        for n in names:
            try:
                attr = self[n]
            except KeyError:
                raise KeyError("%s has no Attribute '%s'" % (self.bind, n))
            value = attr.get_value(self.bind)
            status = attr.get_status(self.bind)
            if value is None:

                if status == Attribute.STATUS_NOT_AVAILABLE:
                    decision = attr.request(self.bind)
                    self.bind.related_decisions.append(decision)
                    attr.set_status(self.bind, Attribute.STATUS_REQUESTED)
        else:
            # already requested or available
            return

    @property
    def names(self):
        return self.keys()


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
