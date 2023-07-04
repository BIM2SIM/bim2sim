"""Package for TEASER export"""

import logging
from threading import Lock
from typing import Union, Type, Dict, Container, Tuple, Callable, List

import pint

from bim2sim.kernel import log
from bim2sim.elements.base_elements import Element
from bim2sim.elements.base_elements import Dummy as ElementDummy

lock = Lock()

logger = logging.getLogger(__name__)
user_logger = log.get_user_logger(__name__)


class FactoryError(Exception):
    """Error in Model factory"""


class Instance:
    """TEASER model instance"""

    library: str = None
    represents: Union[Element, Container[Element]] = None
    lookup: Dict[Type[Element], Type['Instance']] = {}
    dummy: Type['Instance'] = None
    _initialized = False
    export_instances: List[object] = []
    requested_instances: List[Element] = []

    def __init__(self, element: Element):
        self.element = element
        self.export_instances.append(self)
        if element not in self.requested_instances:
            self.requested_instances.append(element)
        self.requested: Dict[str, Tuple[Callable, str, str]] = {}
        self.request_params()

    @staticmethod
    def _lookup_add(key, value):
        """Adds key and value to Instance.lookup. Returns conflict"""
        if key in Instance.lookup and value is not Instance.lookup[key]:
            logger.error("Conflicting representations (%s) in '%s' and '%s'",
                         key, value.__name__, Instance.lookup[key].__name__)
            return True
        Instance.lookup[key] = value
        return False

    @staticmethod
    def init_factory(libraries):
        """initialize lookup for factory"""
        conflict = False
        Instance.dummy = Dummy
        for library in libraries:
            if Instance not in library.__bases__:
                logger.warning(
                    "Got Library not directly inheriting from Instance.")
            if library.library:
                logger.info("Got library '%s'", library.library)
            else:
                logger.error("Attribute library not set for '%s'",
                             library.__name__)
                raise AssertionError("Library not defined")
            for cls in library.get_library_classes(library):
                if cls.represents is None:
                    logger.warning("'%s' represents no model and can't be used",
                                   cls.__name__)
                    continue

                if isinstance(cls.represents, Container):
                    for rep in cls.represents:
                        confl = Instance._lookup_add(rep, cls)
                        if confl:
                            conflict = True
                else:
                    confl = Instance._lookup_add(cls.represents, cls)
                    if confl:
                        conflict = True

        if conflict:
            raise AssertionError(
                "Conflict(s) in Models. (See log for details).")

        Instance._initialized = True

        models = set(Instance.lookup.values())
        models_txt = "\n".join(
            sorted([" - %s" % inst.__name__ for inst in models]))
        logger.debug("Modelica libraries initialized with %d models:\n%s",
                     len(models), models_txt)

    @staticmethod
    def get_library_classes(library) -> List[Type['Instance']]:
        classes = []
        for cls in library.__subclasses__():
            sub_cls = cls.__subclasses__()
            if sub_cls:
                classes.extend(sub_cls)
            else:
                classes.append(cls)
        return classes

    @staticmethod
    def factory(element, parent):
        """Create model depending on ifc_element"""

        if not Instance._initialized:
            raise FactoryError("Factory not initialized.")

        cls = Instance.lookup.get(type(element), Instance.dummy)

        return cls(element, parent)

    def request_param(self, name: str, check=None, export_name: str = None,
                      export_unit: str = ''):
        """Parameter gets marked as required and will be checked.

        Hint: run collect_params() to collect actual values after requests.

        :param name: name of parameter to request
        :param check: validation function for parameter
        :param export_name: name of parameter in export. Defaults to name
        :param export_unit: unit of parameter in export. Converts to SI units if not specified otherwise"""
        self.element.request(name)
        if export_name is None:
            export_name = name
        self.requested[name] = (check, export_name or name, export_unit)

    def request_params(self):
        """Request all required parameters."""
        # overwrite this in child classes
        pass

    def collect_params(self):
        """Collect all requested parameters.

        First checks if the parameter is a list or a quantity, next uses the
        check function provided by the request_param function to check every
        value of the parameter, afterwards converts the parameter values to the
        special units provided by the request_param function, finally stores the
        parameter on the model instance."""

        for name, (check, export_name, special_units) in self.requested.items():
            param = getattr(self.element, name)
            # check if parameter is a list, to check every value
            if isinstance(param, list):
                new_param = []
                for item in param:
                    if self.check_param(item, check):
                        if special_units or isinstance(item, pint.Quantity):
                            item = self._convert_param(item, special_units).m
                        new_param.append(item)
                    else:
                        new_param = None
                        logger.warning("Parameter check failed for '%s' with "
                                       "value: %s", name, param)
                        break
                setattr(self, export_name, new_param)
            else:
                if self.check_param(param, check):
                    if special_units or isinstance(param, pint.Quantity):
                        param = self._convert_param(param, special_units).m
                    setattr(self, export_name, param)
                else:
                    setattr(self, export_name, None)
                    logger.warning(
                        "Parameter check failed for '%s' with value: %s",
                        name, param)

    @staticmethod
    def check_param(param, check):
        """Check if parameter is valid.

        :param param: parameter to check
        :param check: validation function for parameter"""
        if check is not None:
            if not check(param):
                return False
        return True

    @staticmethod
    def _convert_param(param: pint.Quantity, special_units) -> pint.Quantity:
        """Convert to SI units or special units."""
        if special_units:
            if special_units != param.u:
                converted = param.m_as(special_units)
            else:
                converted = param
        else:
            converted = param.to_base_units()
        return converted

    @staticmethod
    def check_numeric(min_value=None, max_value=None):
        """Generic check function generator
        returns check function"""
        if not isinstance(min_value, (pint.Quantity, type(None))):
            raise AssertionError("min_value is no pint quantity with unit")
        if not isinstance(max_value, (pint.Quantity, type(None))):
            raise AssertionError("max_value is no pint quantity with unit")

        def inner_check(value):
            if not isinstance(value, pint.Quantity):
                return False
            if min_value is None and max_value is None:
                return True
            if min_value is not None and max_value is None:
                return min_value <= value
            if max_value is not None:
                return value <= max_value
            return min_value <= value <= max_value

        return inner_check

    def __repr__(self):
        return "<%s_%s>" % (type(self).__name__, self.name)


class Dummy(Instance):
    represents = ElementDummy
