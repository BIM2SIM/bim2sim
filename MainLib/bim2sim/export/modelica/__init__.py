"""Package for Modelica export"""

import os
import logging
from pathlib import Path

import codecs
from mako.template import Template
import numpy as np
import pint

import bim2sim
from bim2sim.kernel import element as elem
from bim2sim.decision import RealDecision

TEMPLATEPATH = Path(bim2sim.__file__).parent / 'assets/tmplModel.txt'
# prevent mako newline bug by reading file seperatly
with open(TEMPLATEPATH) as f:
    templateStr = f.read()
templ = Template(templateStr)


class ModelError(Exception):
    """Error occuring in model"""
class FactoryError(Exception):
    """Error in Model factory"""


class Model:
    """Modelica model"""

    def __init__(self, name, comment, instances: list, connections: list):

        self.logger = logging.getLogger(__name__)

        self.name = name
        self.comment = comment
        self.instances = instances

        self.size_x = (-100, 100)
        self.size_y = (-100, 100)

        self.connections, self.connections = self.set_positions(instances, connections)

    def set_positions(self, instances, connections):
        """Sets position of instances

        relative to min/max positions of instance.element.position"""
        instance_dict = {}
        connections_positions = []

        # calculte instance position
        positions = np.array(
            [inst.element.position for inst in instances
             if inst.element.position is not None])
        pos_min = np.min(positions, axis=0)
        pos_max = np.max(positions, axis=0)
        pos_delta = pos_max - pos_min
        delta_x = self.size_x[1] - self.size_x[0]
        delta_y = self.size_y[1] - self.size_y[0]
        for inst in instances:
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
        return list(instances), connections_positions

    def code(self):
        """returns Modelica code"""
        return templ.render(model=self)

    def save(self, path: str):
        """Save model as Modelica file"""
        _path = os.path.normpath(path)
        if os.path.isdir(_path):
            _path = os.path.join(_path, self.name)

        if not _path.endswith(".mo"):
            _path += ".mo"

        data = self.code()

        self.logger.info("Saving '%s' to '%s'", self.name, _path)
        with codecs.open(_path, "w", "utf-8") as file:
            file.write(data)


class Instance:
    """Modelica model instance"""

    library = None
    version = None
    path = None
    represents = None
    lookup = {}
    dummy = None
    _initialized = False

    def __init__(self, element):

        self.element = element
        self.position = (80, 80)

        self.name = element.__class__.__name__.lower()
        self.guid = getattr(element, "guid", "").replace("$", "_")
        if self.guid:
            self.name = self.name + "_" + self.guid
        self.params = {}
        self.validate = {}
        self.get_params()
        self.comment = self.get_comment()
        self.connections = []

    @staticmethod
    def _lookup_add(key, value):
        """Adds key and value to Instance.lookup. Returns conflict"""
        logger = logging.getLogger(__name__)
        if key in Instance.lookup:
            logger.error("Conflicting representations (%s) in '%s' and '%s'",
                         key, value.__name__, Instance.lookup[key].__name__)
            return True
        Instance.lookup[key] = value
        return False

    @staticmethod
    def init_factory(libraries):
        """initialize lookup for factory"""
        logger = logging.getLogger(__name__)
        conflict = False

        Instance.dummy = Dummy

        for library in libraries:
            if Instance not in library.__bases__:
                logger.warning("Got Library not directly inheriting from Instance.")
            if library.library:
                logger.info("Got library '%s'", library.library)
            else:
                logger.error("Attribute library not set for '%s'", library.__name__)
                raise AssertionError("Library not defined")
            for cls in library.__subclasses__():
                if cls.represents is None:
                    logger.warning("'%s' represents no model and can't be used", cls.__name__)
                    continue

                if isinstance(cls.represents, (list, set)):
                    for rep in cls.represents:
                        confl = Instance._lookup_add(rep, cls)
                        if confl:
                            conflict = True
                else:
                    confl = Instance._lookup_add(cls.represents, cls)
                    if confl:
                        conflict = True

        if conflict:
            raise AssertionError("Conflict(s) in Models. (See log for details).")

        Instance._initialized = True

        models = set(Instance.lookup.values())
        models_txt = "\n".join(sorted([" - %s"%(inst.path) for inst in models]))
        logger.debug("Modelica libraries initialized with %d models:\n%s", len(models), models_txt)

    @staticmethod
    def factory(element):
        """Create model depending on ifc_element"""

        if not Instance._initialized:
            raise FactoryError("Factory not initialized.")

        cls = Instance.lookup.get(element.__class__, Instance.dummy)
        return cls(element)

    def manage_params(self):
        """Collect parameters from element and checks them"""
        for name, args in self.validate.items():
            check, export_name = args
            value = self.element.find(name)
            if check(value):
                self.params[export_name] = value
            else:
                RealDecision(
                    question="Please enter parameter for %s"%(self.name + "." + export_name),
                    unit=self.element.attributes.get_unit(name),
                    validate_func=check,
                    output=self.params,
                    output_key=export_name,
                    global_key=self.name + "." + name,
                    collect=True,
                    allow_load=True,
                    allow_save=True,
                    allow_skip=True,
                )

    def register_param(self, name: str, check, export_name: str=None):
        """Parameter gests marked as requiered and will be checked.

        run Element.solve_request() after all parameters are registrated."""
        self.element.request(name)
        self.validate[name] = (check, export_name or name)

    @property
    def modelica_params(self):
        """Returns param dict converted with to_modelica"""
        mp = {k: self.to_modelica(v) for k, v in self.params.items()}
        return mp

    def get_params(self):
        """Returns dictionary of parameters and values"""
        return {}

    def get_comment(self):
        """Returns comment string"""
        return self.element.name
        #return "Autogenerated by BIM2SIM"

    @property
    def path(self):
        """Returns model path in library"""
        return self.__class__.path

    def get_port_name(self, port):
        """Returns name of port"""
        return "port_unknown"

    def get_full_port_name(self, port):
        """Returns name of port including model name"""
        return "%s.%s"%(self.name, self.get_port_name(port))

    @staticmethod
    def to_modelica(parameter):
        """converts parameter to modelica readable string"""
        if parameter is None:
            return parameter
        if isinstance(parameter, bool):
            return 'true' if parameter else 'false'
        if isinstance(parameter, (str, int, float)):
            return str(parameter)
        if isinstance(parameter, str):
            return '"%s"'%parameter
        if isinstance(parameter, (list, tuple, set)):
            return "{%s}"%(",".join((Instance.to_modelica(par) for par in parameter)))
        logger = logging.getLogger(__name__)
        logger.warning("Unknown class (%s) for conversion", parameter.__class__)
        return str(parameter)

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
        return "<%s %s>"%(self.path, self.name)


class Dummy(Instance):
    path = "Path.to.Dummy"
    represents = elem.Dummy


if __name__ == "__main__":

    class Radiator(Instance):
        path = "Heating.Consumers.Radiators.Radiator"

    par = {
        "redeclare package Medium" : "Modelica.Media.Water.ConstantPropertyLiquidWater",
        "Q_flow_nominal" : 4e3,
        "n" : 1.3,
        "Type" : "HKESim.Heating.Consumers.Radiators.BaseClasses.ThermostaticRadiatorValves.Types.radiatorCalculationTypes.proportional",
        "k" : 1.5
    }

    conns = {"radiator1.port_a": "radiator2.port_b"}

    inst1 = Instance("radiator1", {})
    inst2 = Instance("radiator2", par)

    model = Model("System", "Test", [inst1, inst2], conns)

    print(model.code())
    #model.save(r"C:\Entwicklung\temp")
