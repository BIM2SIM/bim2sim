"""Package for Python representations of HKESim models"""

from bim2sim.export import modelica
from bim2sim.ifc2python import elements
from bim2sim.ifc2python.aggregation import PipeStrand

from bim2sim.export.modelica import standardlibrary # impor necessary for model detection

class AixLib(modelica.Instance):
    library = "AixLib"


class Boiler(AixLib):
    #path = "HKESim.Heating.Boilers.Boiler"
    represents = elements.Boiler

    @classmethod
    def get_params(cls, ele):
        params = {
            "nominal_power" : ele.rated_power,
            }
        return params
