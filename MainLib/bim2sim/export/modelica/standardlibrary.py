"""Modul containing model representations from the Modelica Standard Library"""

from bim2sim.export import modelica
from bim2sim.ifc2python import elements, aggregation

from bim2sim.decision import RealDecision

class StandardLibrary(modelica.Instance):
    """Base class for Modelica Standard Library"""
    library = "Modelica Standard Library"

class StaticPipe(StandardLibrary):
    path = "Modelica.Fluid.Pipes.StaticPipe"
    represents = [elements.Pipe, aggregation.PipeStrand]

    def __init__(self, element):
        self.check_length = self.check_numeric(min_value=0)
        self.check_diameter = self.check_numeric(min_value=0)
        super().__init__(element)

    def get_params(self):
        self.manage_param("length", self.element.length, self.check_length)
        self.manage_param("diameter", self.element.diameter, self.check_diameter)

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
    represents = [elements.Storage, elements.StorageDevice]

    def __init__(self, element):
        self.check_volume = self.check_numeric(min_value=0)
        super().__init__(element)

    def get_params(self):
        self.manage_param("volume" , self.element.volume, self.check_volume)

    def get_port_name(self, port):
        try:
            index = self.element.ports.index(port)
        except ValueError:
            return super().get_port_name(port)
        else:
            return "ports[%d]"%index
