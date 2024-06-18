"""Package for Modelica export"""

import codecs
import logging
import os
from enum import Enum
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

    def __init__(self, name, comment, elements: list, connections: list,
                 connections_heat_ports: list):
        self.name = name
        self.comment = comment
        self.elements = elements

        self.size_x = (-100, 100)
        self.size_y = (-100, 100)

        self.connections = self.set_positions(elements, connections)
        # TODO positions for heatports?
        self.connections_heat_ports = connections_heat_ports

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

    def render_modelica_code(self):
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

        data = self.render_modelica_code()

        user_logger.info("Saving '%s' to '%s'", self.name, _path)
        with codecs.open(_path, "w", "utf-8") as file:
            file.write(data)


class Instance:
    """Modelica model instance

    # TODO describe the total process

    """

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

        self.stored_params = {}
        self.export_params = {}
        self.export_records = {}
        self.records = []
        self.requested: Dict[str, Tuple[Callable, bool, Union[None, Callable],
                             str, str]] = {}
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

    def request_param(self, name: str, check, export: bool = True,
                      needed_params: list = None, function: Callable=None,
                      export_name: str = None, export_unit: str = ''):
        """Requests a parameter for validation and export.

        Marks the specified parameter as required and performs validation using
            the provided check function.

        Hint: Run collect_params() to collect actual values after making
            requests.

        Args:
            name (str): Name of the parameter to request.
            check: Validation function for the parameter.
            export (bool): if parameter should be exported or only the value
                should be stored (for not directly mapped parameters)
            needed_params (list): All parameters that are needed to run the
                function to evaluate this parameter
            function (func): Function to evaluate this parameter
            export_name (str, optional): Name of the parameter in export.
                Defaults to name.
            export_unit (str, optional): Unit of the parameter in export.
                Converts to SI units if not specified otherwise.

        Returns:
            None
        """
        if function:
            for needed_param in needed_params:
                self.element.request(needed_param)
                self.requested[needed_param] = \
                    (check, False, None, needed_param, export_unit)
            self.requested[name] = (check, export, function, name, export_unit)
        else:
            self.element.request(name)
            self.requested[name] = (
                check, export, function,
                export_name or name, export_unit)

    def request_params(self):
        """Request all required parameters."""
        # overwrite this in child classes
        pass

    def collect_params(self):
        """Collect all requested parameters.
            # TODO complete docstrings
        """
        # TODO if the check fails for needed_param, there is only a warning
        #  but when trying to check_and_store the primary parameter, the runtime
        #  will fail due to missing parameter from failed check above
        for name, (check, export, function, export_name, special_units) in (
                self.requested.items()):
            if function:
                param = function()
                self._check_and_store_param(name, param, check, export,
                                            export_name, special_units)
            else:
                param = getattr(self.element, name)
                self._check_and_store_param(name, param, check, export,
                                            export_name, special_units)

    def _check_and_store_param(
            self, name, param, check, export, export_name, special_units):
        """

        First checks if the parameter is a list or a quantity, next uses the
        check function provided by the request_param function to check every
        value of the parameter, afterward converts the parameter values to the
        special units provided by the request_param function, finally stores
        the parameter on the model instance.

        # TODO #624 explain difference between export_params and stored_params
        # TODO #624 complete docstrings
        Args:
            name:
            param:
            check:
            export:
            export_name:
            special_units:

        Returns:

        """
        new_param = None
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
        elif isinstance(param, dict):
            # TODO #624 clean check for all values in dict (even nested)
            # TODO handle special units for dicts
            # for item in param.values():
            #     if True:
                # if check(item):
                #     if special_units or isinstance(item, pint.Quantity):
                #         item = self._convert_param(item, special_units)
                #     pass
            if export:
                self.export_records[export_name] = param
            return
        else:
            if check(param):
                if special_units or isinstance(param, pint.Quantity):
                    new_param = self._convert_param(param, special_units)
            else:
                logger.warning(
                    "Parameter check failed for '%s' with value: %s",
                    name, param)
        if export:
            self.export_params[export_name] = new_param
        else:
            self.stored_params[export_name] = new_param


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
        mp = {k: self.to_modelica(v) for k, v in self.export_params.items()}
        return mp

    @property
    def modelica_records(self):
        mr = {k: self.to_modelica(v) for k, v in self.export_records.items()}
        return mr

    @property
    def modelica_export_dict(self):
        return {**self.modelica_params, **self.modelica_records}

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
        # handle modelica records
        if isinstance(parameter, dict):
            record_str = ""
            for index, (key, value) in enumerate(parameter.items(), 1):
                # handle nested dicts
                if isinstance(value, dict):
                    seperator = "("
                else:
                    seperator = "="
                record_str += key
                record_str += seperator
                record_str += Instance.to_modelica(value)
                if index < len(parameter):
                    record_str += ","
                elif isinstance(value, dict):
                    record_str += ")"
            return record_str
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

    def get_heat_port_names(self):
        """Returns names of heat ports if existing"""
        return {}

    def get_full_port_name(self, port):
        """Returns name of port including model name"""
        return "%s.%s" % (self.name, self.get_port_name(port))

    def get_full_heat_port_names(self):
        """Returns names of heat ports including model name"""
        # full_heat_port_names = {}
        # for heat_port_name in self.get_heat_port_names():
        #     full_heat_port_names = "%s.%s" % (self.name, heat_port_name)
        return "%s.%s" % (self.name, self.get_heat_port_names())

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
            record_content: [dict, Type["ModelicaRecord"]]
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


class HeatTransferType(Enum):
    CONVECTIVE = "convective"
    RADIATIVE = "radiative"
    GENERIC = "generic"


class HeatPort:
    """Simplified representation of a heat port in Modelica.

    This does not represent a bim2sim element, as IFC doesn't have the concept
    of heat ports. This class is just for better differentiation between
    radiative, convective and generic heat ports.

   Args:
        heat_transfer_type (HeatTransferType): The type of heat transfer.
        name (str): name of the heat port in the parent modelica element
        parent (Instance): Modelica Instance that holds this heat port
    """

    def __init__(self,
                 heat_transfer_type: Union[HeatTransferType, str],
                 name: str,
                 parent: Instance):
        self.heat_transfer_type = heat_transfer_type
        self.name = name
        self.parent = parent

    @property
    def heat_transfer_type(self):
        return self._heat_transfer_type

    @heat_transfer_type.setter
    def heat_transfer_type(self, value: Union[HeatTransferType, str]):
        if isinstance(value, HeatTransferType):
            self._heat_transfer_type = value
        elif isinstance(value, str):
            try:
                self._heat_transfer_type = HeatTransferType[value.upper()]
            except KeyError:
                raise AttributeError(f'Cannot set heat_transfer_type to {value}, '
                                     f'only "convective", "radiative", and '
                                     f'"generic" are allowed')
        else:
            raise AttributeError(f'Cannot set heat_transfer_type to {value}, '
                                 f'only instances of HeatTransferType or '
                                 f'strings "convective", "radiative", and '
                                 f'"generic" are allowed')


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

    print(model.render_modelica_code())
    # model.save(r"C:\Entwicklung\temp")
