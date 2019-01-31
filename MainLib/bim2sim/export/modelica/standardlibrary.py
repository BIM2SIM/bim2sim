"""Modul containing model representations from the Modelica Standard Library"""

from bim2sim.export import modelica
from bim2sim.ifc2python import elements, aggregation

class StandardLibrary(modelica.Instance):
    """Base class for Modelica Standard Library"""
    library = "Modelica Standard Library"

class StaticPipe(StandardLibrary):
    path = "Modelica.Fluid.Pipes.StaticPipe"
    represents = [elements.Pipe, aggregation.PipeStrand]

    @classmethod
    def get_params(cls, ele):
        params = {
            "length" : ele.length,
            "diameter" : ele.diameter
            }
        return params
