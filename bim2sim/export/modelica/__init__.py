"""Package for Modelica export"""
import codecs
import logging
import os
from pathlib import Path
from threading import Lock
from typing import Union, Type, Dict, Container, Callable, List, Any
import numpy as np
import pint
from mako.template import Template
import bim2sim
from bim2sim.kernel import log
from bim2sim.elements import base_elements as elem
from bim2sim.elements.base_elements import Element
from bim2sim.elements.hvac_elements import HVACProduct, HVACPort
from bim2sim.kernel.decision import DecisionBunch, RealDecision

TEMPLATEPATH = (Path(bim2sim.__file__).parent /
                'assets/templates/modelica/tmplModel.txt')
# prevent mako newline bug by reading file separately
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


class Model:
    """Modelica model"""

    def __init__(self, name: str, comment: str, elements: list,
                 connections: list):
        """
        Args:
            name: The name of the model.
            comment: A comment or description of the model.
            elements: A list of elements in the model.
            connections: A list of connections between elements in the model.
        """
        self.name = name
        self.comment = comment
        self.elements = elements

        self.size_x = (-100, 100)
        self.size_y = (-100, 100)

        self.connections = self.set_positions(elements, connections)

    def set_positions(self, elements: list, connections: list) -> list:
        """ Sets the position of elements relative to min/max positions of
            instance.element.position

        Args:
            elements: A list of elements whose positions are to be set.
            connections: A list of connections between the elements.

        Returns:
            A list of connections with positions.
        """
        instance_dict = {}
        connections_positions = []

        # Calculate the instance position
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

        # Add positions to connections
        for inst0, inst1 in connections:
            name0 = inst0.split('.')[0]
            name1 = inst1.split('.')[0]
            connections_positions.append(
                (inst0, inst1, instance_dict[name0], instance_dict[name1])
            )
        return connections_positions

    def code(self) -> str:
        """ Returns the Modelica code for the model.The mako template is used to
            render the Modelica code based on the model's elements, connections,
            and unknown parameters.

        Returns
            str: The Modelica code representation of the model.
        """
        with lock:
            return template.render(model=self, unknowns=self.unknown_params())

    def unknown_params(self) -> list:
        """ Identifies unknown parameters in the model. Unknown parameters are
            parameters with None value and that are required by the model.

        Returns:
            A list of unknown parameters in the model.
        """
        unknown_parameters = []
        for instance in self.elements:
            unknown_parameter = [f'{instance.name}.{parameter.name}'
                                 for parameter in
                                 instance.parameters.values()
                                 if parameter.value is None
                                 and parameter.required is True]
            unknown_parameters.extend(unknown_parameter)
        return unknown_parameters

    def save(self, path: str):
        """ Save the model as Modelica file.

        Args:
            path (str): The path where the Modelica file should be saved.
        """
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
    """ Modelica model instance

        This class represents an instance of a Modelica model, which includes
        elements, parameters, connections, and other metadata.

     Attributes:
        library: The library the instance belongs to.
        version: The version of the library.
        path: The path of the model in the library.
        represents: The element or a container of elements that the instance
            represents.
        lookup: A dictionary mapping element types to instance types.
        dummy: A placeholder for an instance.
        _initialized: Indicates whether the instance has been initialized.

    # TODO describe the total process

    """

    library: str = None
    version = None
    path: str = None
    represents: Union[Element, Container[Element]] = None
    lookup: Dict[Type[Element], Type['Instance']] = {}
    dummy: Type['Instance'] = None
    _initialized = False

    def __init__(self, element: HVACProduct):
        """ Initializes an Instance with the given HVACProduct element.

        Args:
            element (HVACProduct): The HVACProduct element represented by the
                instance.
        """
        self.element = element
        self.position = (80, 80)

        self.parameters = {}
        self.connections = []

        self.guid = self._get_clean_guid()
        self.name = self._get_name()
        self.comment = self.get_comment()

    def _get_clean_guid(self) -> str:
        """ Gets a clean GUID of the element.

        Returns:
            The cleaned GUID of the element.
        """
        return clean_string(getattr(self.element, "guid", ""))

    def _get_name(self) -> str:
        """ Generates and returns a name for the instance based on the element's
            class name and GUID.

        Returns:
            The generated name for the instance.
        """
        name = self.element.__class__.__name__.lower()
        if self.guid:
            name = name + "_" + self.guid
        return name

    @staticmethod
    def _lookup_add(key, value) -> bool:
        """ Adds a key-value pair to the Instance lookup dictionary. Logs a
            warning if there is a conflict.

        Args:
            key: The key to add to the lookup dictionary.
            value: The value to associate with the key.

        Returns:
            bool: False, indicating no conflict.
        """
        """Adds key and value to Instance.lookup. Returns conflict"""
        if key in Instance.lookup and value is not Instance.lookup[key]:
            logger.warning("Conflicting representations (%s) in '%s' and '%s. "
                           "Taking the more recent representation of library "
                           "'%s'",
                           key, value.__name__, Instance.lookup[key].__name__,
                           value.library)
        Instance.lookup[key] = value
        return False

    @staticmethod
    def init_factory(libraries: tuple):
        """ Initializes the lookup dictionary for the factory with the provided
            libraries.

        Args:
            libraries: A tuple of libraries to initialize the factory with.

        Raises:
            AssertionError: If a library is not defined or if there are
                conflicts in models.
        """
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
    def factory(element: HVACProduct):
        """ Create model depending on ifc_element"""

        if not Instance._initialized:
            raise FactoryError("Factory not initialized.")

        cls = Instance.lookup.get(element.__class__, Instance.dummy)
        return cls(element)

    def _set_parameter(self, name, unit, required, **kwargs):
        """ Sets a parameter for the instance.

        Args:
            name: The name of the parameter as in the Modelica model.
            unit: The unit of the parameter as in the Modelica model.
            required: Whether the parameter is required. Raises a decision if a
                required parameter is not available
            **kwargs: Additional keyword arguments.
        """
        self.parameters[name] = ModelicaParameter(name, unit, required,
                                                  self.element, **kwargs)

    def collect_params(self):
        """ Collects the parameters of the instance."""
        for parameter in self.parameters.values():
            parameter.collect()

    @property
    def modelica_parameters(self) -> dict:
        """ Converts and returns the instance parameters to Modelica parameters.

        Returns:
            A dictionary of Modelica parameters with key as name and value as
                the parameter in Modelica code.
        """
        mp = {k: ModelicaParameter.parse_to_modelica(k, v.value)
              for k, v in self.parameters.items() if v.export}
        return mp

    def get_comment(self) -> str:
        """ Returns comment string"""
        return self.element.source_info()

    @property
    def path(self):
        """ Returns the model path in the library"""
        return self.__class__.path

    def get_port_name(self, port: HVACPort) -> str:
        """ Get the name of port. Override this method in a subclass.

         Args:
            port: The HVACPort for which to get the name.

        Returns:
            The name of the port as string.
        """
        return "port_unknown"

    def get_full_port_name(self, port: HVACPort) -> str:
        """ Returns name of port including model name.

        Args:
            port: The HVACPort for which to get the full name.

        Returns:
            The full name of the port as string.
        """
        return "%s.%s" % (self.name, self.get_port_name(port))

    def __repr__(self):
        return "<%s %s>" % (self.path, self.name)


class ModelicaParameter:
    """ Represents a parameter in a Modelica model.

    Attributes:
        _decisions: Collection of decisions related to parameters.
        _answers: Dictionary to store answers for parameter decisions.
    """
    _decisions = DecisionBunch()
    _answers: dict = {}

    def __init__(self, name: str, unit: pint.Unit, required: bool,
                 element: HVACProduct, **kwargs):
        """
        Args:
            name: The name of the parameter as in the modelica model.
            unit: The unit of the parameter as in the modelica model.
            required: Indicates whether the parameter is required. Raises a
                decision if parameter is not available.
            element: The element to which the parameter belongs.
            **kwargs: Additional keyword arguments:
                check:
                export: Whether to export the parameter. Default is True.
                attributes: Element attributes related to the parameter.
                function: Function to compute the parameter value.
                function_inputs: Inputs for the function. Either one or more
                    attributes or another ModelicaParameter
               value (Any): Value of the parameter for a direct allocation.
        """
        self.name: str = name
        self.unit: pint.Unit = unit
        self.required: bool = required
        self.element: Element = element
        self.check: Callable = kwargs.get('check')
        self.export: bool = kwargs.get('export', True)
        self.attributes: Union[List[str], str] = kwargs.get('attributes', [])
        self.function: Callable = kwargs.get('function')
        self.function_inputs: dict = kwargs.get('function_inputs', {})
        self._value: Any = kwargs.get('value')
        self.register()

    def register(self):
        """ Registers the parameter, requesting necessary attributes or
            creating decisions if necessary.

        This method performs the following steps:
        1. Checks if the parameter is required and if it does not have a
            function assigned.
            - If attributes are specified, it requests these attributes from the
                element.
            - If no attributes are specified, it creates a decision for the
                parameter.
        2. If the parameter has a function assigned:
            - If the function input is a ModelicaParameter, it is processed
                further.
            - If the function input is an attribute of the element, it requests
                this attribute.
            - If the function input is neither, it raises an AttributeError.
        """
        #
        if self.required and not self.function:
            if self.attributes:
                for attribute in self.attributes:
                    self.element.request(attribute)
            else:
                self._decisions.append(
                    self._create_parameter_decision(self.name, self.unit))
        elif self.function:
            for function_input in self.function_inputs.values():
                # If the function inputs contains attributes, all attributes are
                # requested
                if isinstance(function_input, ModelicaParameter):
                    pass
                elif function_input in self.element.attributes:
                    self.attributes.append(function_input)
                    self.element.request(str(function_input))
                else:
                    raise AttributeError(
                        f"The provided function input{function_input} "
                        f"is not an attribute of {self.element}")

    def _create_parameter_decision(self, name: str, unit: pint.Unit):
        """ Creates a decision for the parameter.

        Args:
            name: The name of the parameter.
            unit: The unit of the parameter.

        Returns:
            The decision object for the parameter.
        """
        decision = RealDecision(
            question="Enter value for %s of %s" % (name, self.element),
            console_identifier="Name: %s, GUID: %s"
                               % (self.name, self.element.guid),
            key=name,
            allow_skip=False,
            unit=unit)
        return decision

    @classmethod
    def get_pending_parameter_decisions(cls):
        """ Yields pending parameter decisions.

        Yields:
            The decisions related to the parameters.
        """
        decisions = cls._decisions
        decisions.sort(key=lambda d: d.key)
        yield decisions
        cls._answers.update(decisions.to_answer_dict())

    def collect(self):
        """ Collects the value of the parameter based on its source.

        This method performs the following steps:
        1. Checks if the parameter has a function assigned:
            - Collects all function inputs, either as ModelicaParameter values
                or attribute values.
            - Calls the function with the collected inputs and converts the
                function output to the parameter's value.
        2. If the parameter is required and has no attributes:
            - Sets the parameter value from the collected answers.
        3. If the parameter has attributes:
            - Retrieves the attribute value(s) and converts them to the
                parameter's value.
        4. If the parameter already has a value, it retains the existing value.
        5. If none of the above conditions are met, sets the parameter value to
            None and logs a warning.
        """
        if self.function:
            collected_function_input = []
            for function_input in self.function_inputs.values():
                if isinstance(function_input, ModelicaParameter):
                    collected_function_input.append(function_input.value)
                else:
                    collected_function_input.append(self.get_attribute_value())
            function_output = self.function(*collected_function_input)
            self.value = self.convert_parameter(function_output)
        elif self.required and not self.attributes:
            self.value = self._answers[self.name]
        elif self.attributes:
            attribute_value = self.get_attribute_value()
            self.value = self.convert_parameter(attribute_value)
        elif self.value:
            pass
        else:
            self.value = None
            logger.warning(f'Parameter {self.name} could not be collected.')

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        if self.check:
            if self.check(value):
                self._value = value
            else:
                logger.warning("Parameter check failed for '%s' with value: "
                               "%s", self.name, self._value)
                self._value = None
        else:
            self._value = value

    def get_attribute_value(self) \
            -> Union[List[pint.Quantity], pint.Quantity]:
        """ Retrieves the value(s) of the parameter's attributes from the
            associated element.

        Returns:
            The attribute value(s) as a list of `pint.Quantity` objects if there
            are multiple attributes, or a single `pint.Quantity` object if there
            is only one attribute.
        """
        attribute_value = [getattr(self.element, attribute)
                           for attribute in self.attributes]
        if len(attribute_value) > 1:
            return attribute_value
        else:
            return attribute_value[0]

    def convert_parameter(self, parameter: Union[pint.Quantity, list]) \
            -> Union[pint.Quantity, list]:
        """ Converts a parameter to its appropriate unit.

        Args:
            parameter: The parameter to convert.

        Returns:
            The converted parameter.
        """
        if not self.unit:
            return parameter
        elif isinstance(parameter, pint.Quantity):
            return parameter.to(self.unit)
        elif isinstance(parameter, list):
            return [self.convert_parameter(param) for param in parameter]

    @staticmethod
    def parse_to_modelica(name: Union[str, None], value: Any) \
            -> Union[str, None]:
        """ Converts a parameter to a Modelica-readable string.

        Args:
            name: The name of the parameter.
            value: The value of the parameter.

        Returns:
            The Modelica-readable string representation of the parameter.
        """
        if name:
            prefix = f'{name}='
        else:
            prefix = ''
        if value is None:
            return value
        elif isinstance(value, bool):
            return f'{prefix}{str(value).lower()}'
        elif isinstance(value, pint.Quantity):
            return ModelicaParameter.parse_to_modelica(name, value.magnitude)
        elif isinstance(value, (int, float)):
            return f'{prefix}{str(value)}'
        elif isinstance(value, str):
            return f'{prefix}{value}'
        elif isinstance(value, (list, tuple, set)):
            return (prefix + "{%s}"
                    % (",".join((ModelicaParameter.parse_to_modelica(None, par)
                                 for par in value))))
        # Handle modelica records
        elif isinstance(value, dict):
            record_str = f'{name}('
            for index, (var_name, var_value) in enumerate(value.items(), 1):
                record_str += ModelicaParameter.parse_to_modelica(var_name,
                                                                  var_value)
                if index < len(value):
                    record_str += ','
                else:
                    record_str += ')'
            return record_str
        elif isinstance(value, Path):
            return \
                (f"Modelica.Utilities.Files.loadResource(\"{str(value)}\")"
                 .replace("\\", "\\\\"))
        logger.warning("Unknown class (%s) for conversion", value.__class__)
        return str(value)

    def __repr__(self):
        return (f"value={self.value}, required={self.required}, "
                f"export={self.export}")


def check_numeric(min_value: Union[pint.Quantity, None] = None,
                  max_value: Union[pint.Quantity, None] = None):
    """ Generates a function to check if a given value falls within specified
        numeric bounds.

    This function creates and returns a checker function (`inner_check`) that
    validates whether a given `value` (a `pint.Quantity`) falls within the range
    defined by `min_value` and `max_value`.

    Args:
        min_value: The minimum value for the range check.
        max_value: The maximum value for the range check.

    Raises:
        AssertionError: If `min_value` or `max_value` is not a `pint.Quantity`
            or `None`.

    Returns:
        A function (`inner_check`) that takes a single argument value` and
            returns `True` if the value is within the specified bounds,
            otherwise `False`.
    """
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


def check_none():
    """ Generates a function to check if a given value is not None."""

    def inner_check(value):
        return not isinstance(value, type(None))
    return inner_check


class Dummy(Instance):
    path = "Path.to.Dummy"
    represents = elem.Dummy
