"""Package for Modelica export"""

import os
import logging

from mako.template import Template

TEMPLATEPATH = os.path.join(os.path.dirname(__file__), 'tmplModel.txt')
# prevent mako newline bug by reading file seperatly
with open(TEMPLATEPATH) as f:
    templateStr = f.read()
templ = Template(templateStr)

def code(model):
    """returns Modelica code"""
    return templ.render(model=model)

def write(model, path:str):
    """Save model as Modelica file"""
    _path = os.path.normpath(path)
    if os.path.isdir(_path):
        _path = os.path.join(_path, model.name)

    if not path.endswith(".mo"):
        _path += ".mo"

    data = code(model)

    logger = logging.getLogger(__name__)
    logger.info("Saving '%s' to '%s'", model.name, _path)
    with open(_path, "w") as file:
        file.write(data)


if __name__ == "__main__":
    class Inst():
        def __init__(self, path, name, params:dict):
            self.path = path
            self.name = name
            self.params = params

    class Model():
        def __init__(self, name, comment, instances:list, connections:dict):
            self.name = name
            self.comment = comment
            self.instances = instances
            self.connections = connections

    par = {
        "redeclare package Medium" : "Modelica.Media.Water.ConstantPropertyLiquidWater",
        "Q_flow_nominal" : 4e3,
        "n" : 1.3,
        "Type" : "HKESim.Heating.Consumers.Radiators.BaseClasses.ThermostaticRadiatorValves.Types.radiatorCalculationTypes.proportional",
        "k" : 1.5
    }

    conns = {"radiator1.port_a": "radiator2.port_b"}

    inst1 = Inst("Heating.Consumers.Radiators.Radiator", "radiator1", par)
    inst2 = Inst("Heating.Consumers.Radiators.Radiator", "radiator2", par)

    model = Model("System", "Test", [inst1, inst2], conns)

    print(code(model))
    write(model, r"C:\Entwicklung\temp")


# -------------------------------------------------------------
#"""Package for Python representations of Modelica models"""

import os
import logging

INDENT = "  "

def indent(to_indent: str):
    """increase indent level by one"""
    return INDENT + to_indent.replace("\n", "\n" + INDENT)

class Interface():
    """Representation of Modelica interface"""

    def __init__(self, name, parent):

        self.name = name
        self.parent = parent

        self.connections = []

    def connect(self, other):
        """Connect this interface to another interface"""
        assert isinstance(other, self.__class__), "Can't connect inerfaces of different classes."
        self.connections.append(other)

    @property
    def full_name(self):
        """Qualifier name"""
        return ".".join([self.parent.name, self.name])

    @property
    def annotation(self):
        """Annotation"""
        return "" # TODO

    def connections_str(self):
        """Returns connections of this interface as modelica code"""
        conns = []
        for con in self.connections:
            conns.append("connect(%s, %s)%s;"%(self.full_name, con.full_name, self.annotation))
        return "\n".join(conns) or ""

    def __repr__(self):
        return "<Interface (%s)>"%(self.full_name)

class Model():
    """Representation of Modelica model instance"""

    model = None

    def __init__(self, params: dict, interfaces: list, name=None, comment=None):
        self.logger = logging.getLogger(__name__)
        self.name = name or self.__class__.__name__ #TODO: make name unique
        self.comment = comment or ""

        self.parameter = params

        self.interfaces = interfaces
        if not self.interfaces:
            self.logger.warning("Model %s has no interfaces!", self.name)

    @property
    def annotation(self):
        """Annotation"""
        return "annotation (Placement(transformation(extent={{-88,16},{-68,36}})))" # TODO

    def param_str(self):
        """Parameter part of modelica model instantiation"""
        param = ",\n".join(["%s=%s"%(k, v) for k, v in self.parameter.items()])
        param = "\n" + param if param else param
        return param

    def model_str(self):
        """Returns Modelica code of model instantiation"""
        anno = self.annotation
        anno = "\n" + indent(anno) if anno else ""
        txt = "%s %s(%s) \"%s\"%s;"% \
            (self.__class__.model, self.name, indent(self.param_str()), self.comment, anno)
        return txt

    def connections_str(self):
        """Returns Modelica code of model's connections"""
        conns = []
        for i in self.interfaces:
            con = i.connections_str()
            if con:
                conns.append(con)
        return "\n\n".join(conns) or ""

    def __repr__(self):
        return "<%s (%s %s)>"%(self.__class__.__name__, self.__class__.model, self.name)

    def __str__(self):
        return self.model_str()

class System():
    """Representation of Modelica Model containing a runnable simulation"""

    def __init__(self, name, comment=None):
        self.logger = logging.getLogger(__name__)

        self.name = name
        self.comment = comment or ""

        self.children = []

    @property
    def head(self):
        """Model name eg."""
        comment = '"%s"'%self.comment if self.comment else ""
        return "model %s %s"%(self.name, comment)

    @property
    def models(self):
        """Userd model instances"""
        return "\n\n".join([c.model_str() for c in self.children])

    @property
    def equation(self):
        """equation part"""
        equa = "equation\n"
        equa += indent("\n".join([child.connections_str() for child in self.children]))
        return equa

    @property
    def foot(self):
        """End model"""
        return "end %s;"%(self.name)

    @property
    def annotation(self):
        """Annotation"""
        return "annotation (uses(Modelica(version=\"3.2.2\")));" # TODO

    def to_modelica(self):
        """Returns full modelica code of this system"""
        blocks = [
            self.head, "",
            indent(self.models), "",
            self.equation,
            indent(self.annotation),
            self.foot
        ]
        return "\n".join(blocks)

    def save(self, path: str):
        """Save System as modelica file"""
        _path = path
        if os.path.isdir(_path):
            _path = os.path.join(_path, self.name)

        if not path.endswith(".mo"):
            _path += ".mo"

        self.logger.info("Saving '%s' to '%s'", self.name, _path)
        with open(_path, "w") as file:
            file.write(self.to_modelica())

    def __repr__(self):
        return "<%s (%s, %d children)>"%(self.__class__.__name__, self.name, len(self.children))

    def __str__(self):
        return self.to_modelica()
