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

