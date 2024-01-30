﻿"""Package for Modelica export"""

import codecs
import logging
import os
from pathlib import Path
from threading import Lock
from typing import Union, Type, Dict, Container, Tuple, Callable, List

import numpy as np
import pint
from mako.template import Template

import bim2sim
from bim2sim.kernel import log
from bim2sim.elements import base_elements as elem
from bim2sim.elements.base_elements import Element

TEMPLATEPATH = Path(bim2sim.__file__).parent / \
               'assets/templates/modelica/tmplModel.txt'
# prevent mako newline bug by reading file seperatly
with open(TEMPLATEPATH) as f:
    templateStr = f.read()
template = Template(templateStr)
lock = Lock()

logger = logging.getLogger(__name__)
user_logger = log.get_user_logger(__name__)


class ModelError(Exception):
    """Error occurring in model"""


class FactoryError(Exception):
    """Error in Model factory"""


def clean_string(string: str) -> str:
    """Replace modelica invalid chars by underscore."""
    return string.replace('$', '_')


def help_package(path: Path, name: str, uses: str = None, within: str = None):
    """Creates a package.mo file.

    Parameters
    ----------

    path : Path
        path of where the package.mo should be placed
    name : string
        name of the Modelica package
    uses :
    within : string
        path of Modelica package containing this package
    """

    template_path_package = Path(bim2sim.__file__).parent / \
                            "assets/templates/modelica/package"
    package_template = Template(filename=str(template_path_package))
    with open(path / 'package.mo', 'w') as out_file:
        out_file.write(package_template.render_unicode(
            name=name,
            within=within,
            uses=uses))
        out_file.close()


def help_package_order(path: Path, package_list: List[str], addition=None,
                       extra=None):
    """Creates a package.order file.

    Parameters
    ----------

    path : Path
        path of where the package.mo should be placed
    package_list : string
        name of all models or packages contained in the package
    addition : string
        if there should be a suffix in front of package_list.string it can
        be specified
    extra : string
        an extra package or model not contained in package_list can be
        specified
    """

    template_package_order_path = Path(bim2sim.__file__).parent / \
                                  "assets/templates/modelica/package_order"
    package_order_template = Template(filename=str(
        template_package_order_path))
    with open(path / 'package.order', 'w') as out_file:
        out_file.write(package_order_template.render_unicode(
            list=package_list,
            addition=addition,
            extra=extra))
        out_file.close()


class Model:
    """Modelica model"""

    def __init__(self, name, comment, elements: list, connections: list):
        self.name = name
        self.comment = comment
        self.elements = elements

        self.size_x = (-100, 100)
        self.size_y = (-100, 100)

        self.connections = self.set_positions(elements, connections)

    def set_positions(self, elements, connections):
        """Sets position of elements

        relative to min/max positions of instance.element.position"""
        instance_dict = {}
        connections_positions = []

        # calculte instance position
        positions = np.array(
            [inst.element.position if inst.element.position is not None else
             (0, 0) for inst in elements])
        pos_min = np.min(positions, axis=0)
        pos_max = np.max(positions, axis=0)
        pos_delta = pos_max - pos_min
        delta_x = self.size_x[1] - self.size_x[0]
        delta_y = self.size_y[1] - self.size_y[0]
        for inst in elements:
            if inst.element.position is not None:
                rel_pos = (inst.element.position - pos_min) / pos_delta
                x = (self.size_x[0] + rel_pos[0] * delta_x).item()
                y = (self.size_y[0] + rel_pos[1] * delta_y).item()
                inst.position = (x, y)
                instance_dict[inst.name] = inst.position
            else:
                instance_dict[inst.name] = (0, 0)

        # add positions to connections
        for inst0, inst1 in connections:
            name0 = inst0.split('.')[0]
            name1 = inst1.split('.')[0]
            connections_positions.append(
                (inst0, inst1, instance_dict[name0], instance_dict[name1])
            )
        return connections_positions

    def code(self):
        """Returns Modelica code."""
        with lock:
            return template.render(model=self, unknowns=self.unknown_params())

    def unknown_params(self):
        unknown = []
        for instance in self.elements:
            un = [f'{instance.name}.{param}'
                  for param, value in instance.modelica_params.items()
                  if value is None]
            unknown.extend(un)
        return unknown

    def save(self, path: str):
        """Save model as Modelica file"""
        _path = os.path.normpath(path)
        if os.path.isdir(_path):
            _path = os.path.join(_path, self.name)

        if not _path.endswith(".mo"):
            _path += ".mo"

        data = self.code()

        user_logger.info("Saving '%s' to '%s'", self.name, _path)
        with codecs.open(_path, "w", "utf-8") as file:
            file.write(data)


class Instance:
    """Modelica model instance"""

    library: str = None
    version = None
    path: str = None
    represents: Union[Element, Container[Element]] = None
    lookup: Dict[Type[Element], Type['Instance']] = {}
    dummy: Type['Instance'] = None
    _initialized = False

    def __init__(self, element: Element):
        self.element = element
        self.position = (80, 80)

        self.params = {}
        self.records = []
        self.requested: Dict[str, Tuple[Callable, str, str]] = {}
        self.connections = []

        self.guid = self._get_clean_guid()
        self.name = self._get_name()
        self.comment = self.get_comment()

        self.request_params()

    def _get_clean_guid(self) -> str:
        return clean_string(getattr(self.element, "guid", ""))

    def _get_name(self) -> str:
        name = self.element.__class__.__name__.lower()
        if self.guid:
            name = name + "_" + self.guid
        return name

    @staticmethod
    def _lookup_add(key, value):
        """Adds key and value to Instance.lookup. Returns conflict"""
        if key in Instance.lookup and value is not Instance.lookup[key]:
            logger.warning("Conflicting representations (%s) in '%s' and '%s. "
                           "Taking the more recent representation of library "
                           "'%s'",
                         key, value.__name__, Instance.lookup[key].__name__, value.library)
        Instance.lookup[key] = value
        return False

    @staticmethod
    def init_factory(libraries: tuple):
        """Initialize lookup for factory"""
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
            for cls in library.__subclasses__():
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
            sorted([" - %s" % (inst.path) for inst in models]))
        logger.debug("Modelica libraries initialized with %d models:\n%s",
                     len(models), models_txt)

    @staticmethod
    def factory(element):
        """Create model depending on ifc_element"""

        if not Instance._initialized:
            raise FactoryError("Factory not initialized.")

        cls = Instance.lookup.get(element.__class__, Instance.dummy)
        return cls(element)

    def request_param(self, name: str, check, export_name: str = None,
                      export_unit: str = ''):
        """Requests a parameter for validation and export.

        Marks the specified parameter as required and performs validation using
            the provided check function.

        Hint: Run collect_params() to collect actual values after making
            requests.

        Args:
            name (str): Name of the parameter to request.
            check: Validation function for the parameter.
            export_name (str, optional): Name of the parameter in export.
                Defaults to name.
            export_unit (str, optional): Unit of the parameter in export.
                Converts to SI units if not specified otherwise.

        Returns:
            None
        """
        self.element.request(name)
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
        special units provided by the request_param function, finally stores
        the parameter on the model instance."""

        for name, (check, export_name, special_units) in self.requested.items():
            param = getattr(self.element, name)
            # check if parameter is a list, to check every value
            if isinstance(param, list):
                new_param = []
                for item in param:
                    if check(item):
                        if special_units or isinstance(item, pint.Quantity):
                            item = self._convert_param(item, special_units)
                        new_param.append(item)
                    else:
                        new_param = None
                        logger.warning("Parameter check failed for '%s' with "
                                       "value: %s", name, param)
                        break
                self.params[export_name] = new_param
            else:
                if check(param):
                    if special_units or isinstance(param, pint.Quantity):
                        param = self._convert_param(param, special_units)
                    self.params[export_name] = param
                else:
                    self.params[export_name] = None
                    logger.warning(
                        "Parameter check failed for '%s' with value: %s",
                        name, param)

    @staticmethod
    def _convert_param(param: pint.Quantity, special_units) -> pint.Quantity:
        """Convert to SI units or special units."""
        if special_units:
            converted = param.m_as(special_units)
        else:
            converted = param.to_base_units()
        return converted

    @property
    def modelica_params(self):
        """Returns param dict converted with to_modelica."""
        mp = {k: self.to_modelica(v) for k, v in self.params.items()}
        return mp

    @staticmethod
    def to_modelica(parameter):
        """converts parameter to modelica readable string"""
        if parameter is None:
            return parameter
        if isinstance(parameter, bool):
            return 'true' if parameter else 'false'
        if isinstance(parameter, pint.Quantity):
            # assumes correct unit is set
            return Instance.to_modelica(parameter.magnitude)
        if isinstance(parameter, (int, float)):
            return str(parameter)
        if isinstance(parameter, str):
            return '%s' % parameter
        if isinstance(parameter, (list, tuple, set)):
            return "{%s}" % (
                ",".join((Instance.to_modelica(par) for par in parameter)))
        if isinstance(parameter, Path):
            return \
                f"Modelica.Utilities.Files.loadResource(\"{str(parameter)}\")"\
                    .replace("\\", "\\\\")
        logger.warning("Unknown class (%s) for conversion", parameter.__class__)
        return str(parameter)

    def get_comment(self):
        """Returns comment string"""
        return self.element.source_info()

    @property
    def path(self):
        """Returns model path in library"""
        return self.__class__.path

    def get_port_name(self, port):
        """Returns name of port"""
        return "port_unknown"

    def get_full_port_name(self, port):
        """Returns name of port including model name"""
        return "%s.%s" % (self.name, self.get_port_name(port))

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

    @staticmethod
    def check_none():
        """Check if value is not None"""
        def inner_check(value):
            return not isinstance(value, type(None))
        return inner_check

    def __repr__(self):
        return "<%s %s>" % (self.path, self.name)


class ModelicaRecord:
    """Mapping for records in Modelica.

    As records have a name and a key, value pair, we need a separate class to
    cover the structure in python.

    Args:
        name: (str) The name of the record in Modelica model
        record_content: (dict, ModelicaRecord) for nested records
    """
    def __init__(
            self,
            name: str,
            record_content:[dict, Type["ModelicaRecord"]]
    ):
        self.name = name
        self.record_content = self.handle_content(record_content)

    def handle_content(self, record_content):
        # handle nested ModelicaRecords
        if isinstance(record_content, ModelicaRecord):
            self.handle_content(record_content.record_content)
            # record_content = record_content.record_content
        return {k: Instance.to_modelica(v) for k, v
                in record_content.items()}


class Dummy(Instance):
    path = "Path.to.Dummy"
    represents = elem.Dummy


if __name__ == "__main__":
    class Radiator(Instance):
        path = "Heating.Consumers.Radiators.Radiator"


    par = {
        "redeclare package Medium": "Modelica.Media.Water.ConstantPropertyLiquidWater",
        "Q_flow_nominal": 4e3,
        "n": 1.3,
        "Type": "HKESim.Heating.Consumers.Radiators.BaseClasses.ThermostaticRadiatorValves.Types.radiatorCalculationTypes.proportional",
        "k": 1.5
    }

    conns = {"radiator1.port_a": "radiator2.port_b"}

    inst1 = Instance("radiator1", {})
    inst2 = Instance("radiator2", par)

    model = Model("System", "Test", [inst1, inst2], conns)

    print(model.code())
    # model.save(r"C:\Entwicklung\temp")
