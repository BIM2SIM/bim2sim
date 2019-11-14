
import logging

from bim2sim.decision import RealDecision

logger = logging.getLogger(__name__)
quality_logger = logging.getLogger('bim2sim.QualityReport')


class Attribute:
    """Descriptor of element attribute"""
    # https://rszalski.github.io/magicmethods/
    STATUS_UNKNOWN = 'UNKNOWN'
    STATUS_REQUESTED = 'REQUESTED'
    STATUS_AVAILABLE = 'AVAILABLE'
    STATUS_NOT_AVAILABLE = 'NOT_AVAILABLE'

    def __init__(self, name,
                 description="",
                 default_ps=None,
                 patterns=None,
                 ifc_postprocessing=None,
                 functions=None,
                 default=None):
        self.name = name
        self.description = description

        self.default_ps = default_ps
        self.patterns = patterns
        self.functions = functions
        self.default_value = default

        if ifc_postprocessing:
            self.ifc_post_processing = ifc_postprocessing

    def _inner_get(self, bind, value):

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
            return bind.finder.find(bind, name)
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
        raise NotImplementedError()
        value = None
        return value

    def get(self, bind, status, value):
        """Try to get value. Returns None if no method was successful.
        use this method, if None is an acceptable value."""
        if status != Attribute.STATUS_UNKNOWN:
            return value, status

        value = self._inner_get(bind, value)
        if value is None:
            new_status = Attribute.STATUS_NOT_AVAILABLE
        else:
            new_status = Attribute.STATUS_AVAILABLE
        return value, new_status

    def set(self, bind, status, value):
        bind.attributes.set(self.name, value, status)

    # def request(self):
    #     # TODO: decision
    #     self._status = Attribute.STATUS_REQUESTED

    def request_get(self, bind, status, value):
        """Try to get value including collectible decision if no other method was successful.
        use this method, if an actual value is required but not immediately. Value is set by solving decisions."""
        raise NotImplementedError()
        if self._status in (Attribute.STATUS_REQUESTED, Attribute.STATUS_AVAILABLE):
            return self._value

        value = self.get()
        if value is None:
            self.request()

        return self._value

    def force_get(self, bind):
        """Try to get value including non collectible decision if no other method was successful.
        use this method, if an actual value is required immediately."""
        raise NotImplementedError()
        value = self.get()

        if value is None:
            value =self.get_from_decision(bind, self.name)

        return self._value

    # def solve_request(self, value):
    #     """Set value by external source like decision"""
    #     self._value = value
    #     self._status = Attribute.STATUS_AVAILABLE

    @staticmethod
    def ifc_post_processing(value):
        """Function for post processing of ifc property values (e.g. diameter list -> diameter)
        by default this function does nothing"""
        return value

    def __get__(self, instance, owner):
        if instance is None:
            return self
        _value, _status = instance.attributes.get(self.name, (None, Attribute.STATUS_UNKNOWN))

        value, status = self.get(instance, _status, _value)

        self.set(instance, status, value)
        return value

    def __str__(self):
        return "Attribute %s" % self.name


class AttributeManager(dict):
    """Attribute Manager class"""
    def __init__(self, bind):
        super().__init__()
        self.bind = bind

    def set(self, name, value, status=None):
        self.__setitem__(name, value, status)

    def __setitem__(self, name, value, status=None):
        if status is None:
            if value is None:
                status = Attribute.STATUS_NOT_AVAILABLE
            else:
                status = Attribute.STATUS_AVAILABLE

        super().__setitem__(name, (value, status))

    def update(self, other):
        # dict.update does not invoke __setitem__
        for k, v in other.items():
            self.__setitem__(k, v)

    def request(self, name):
        """"""
        value = getattr(self.bind, name)
        if value is None:
            value, status = self.__getitem__(name)

            if status == Attribute.STATUS_NOT_AVAILABLE:
                # actual request
                decision = RealDecision(
                    "Enter value for %s of %s" % (name, self.bind.name),
                    # validate_func=lambda x: isinstance(x, float),
                    output=self,
                    output_key=name,
                    global_key="%s_%s.%s" % (self.bind.ifc_type, self.bind.guid, self.name),
                    allow_skip=False, allow_load=True, allow_save=True,
                    collect=True
                )
        else:
            # already requested or available
            return


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
