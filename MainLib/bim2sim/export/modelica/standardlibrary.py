"""Modul containing model representations from the Modelica Standard Library"""

from bim2sim.export import modelica
from bim2sim.kernel import elements, aggregation
from bim2sim.kernel.units import ureg

from bim2sim.decision import RealDecision

class StandardLibrary(modelica.Instance):
    """Base class for Modelica Standard Library"""
    library = "Modelica Standard Library"

class StaticPipe(StandardLibrary):
    path = "Modelica.Fluid.Pipes.StaticPipe"
    represents = [elements.Pipe, elements.PipeFitting, aggregation.PipeStrand]

    def __init__(self, element):
        self.check_length = self.check_numeric(min_value=0 * ureg.meter)
        self.check_diameter = self.check_numeric(min_value=0 * ureg.meter)
        super().__init__(element)

    def get_params(self):
        self.register_param("length", self.check_length)
        self.register_param("diameter", self.check_diameter)

    def get_port_name(self, port):
        try:
            index = self.element.ports.index(port)
        except ValueError:
            # unknown port
            index = -1
        if index == 0:
            return "port_a"
        elif index == 1:
            return "port_b"
        else:
            return super().get_port_name(port)


class Valve(StandardLibrary):
    path = "Modelica.Fluid.Valves.ValveIncompressible"
    represents = [elements.Valve]

    def __init__(self, element):
        self.check_length = self.check_numeric(min_value=0 * ureg.meter)
        self.check_diameter = self.check_numeric(min_value=0 * ureg.meter)
        super().__init__(element)

    def get_params(self):
        self.register_param("length", self.check_length)
        self.register_param("diameter", self.check_diameter)

    def get_port_name(self, port):
        try:
            index = self.element.ports.index(port)
        except ValueError:
            # unknown port
            index = -1
        if index == 0:
            return "port_a"
        elif index == 1:
            return "port_b"
        else:
            return super().get_port_name(port)


class ClosedVolume(StandardLibrary):
    path = "Modelica.Fluid.Vessels.ClosedVolume"
    represents = [elements.Storage]

    def __init__(self, element):
        self.check_volume = self.check_numeric(min_value=0 * ureg.meter ** 3)
        super().__init__(element)

    def volume(self):
        self.register_param("volume", self.check_volume)

    def get_port_name(self, port):
        try:
            index = self.element.ports.index(port)
        except ValueError:
            return super().get_port_name(port)
        else:
            return "ports[%d]"%index
