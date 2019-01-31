"""Package for Python representations of HKESim models"""

from bim2sim.export import modelica
from bim2sim.ifc2python import elements
from bim2sim.ifc2python.aggregation import PipeStrand

from bim2sim.export.modelica import standardlibrary # impor necessary for model detection

class HKESim(modelica.Instance):
    library = "HKESim"


class Boiler(HKESim):
    path = "HKESim.Heating.Boilers.Boiler"
    represents = elements.Boiler

    @classmethod
    def get_params(cls, ele):
        params = {
            "nominal_power" : ele.rated_power,
            }
        return params
