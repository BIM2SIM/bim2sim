"""Package for Python representations of HKESim models"""
import bim2sim.kernel.elements.all
from bim2sim.export import modelica
from bim2sim.kernel import elements
from bim2sim.kernel.units import ureg
from bim2sim.kernel.aggregation import PipeStrand

from bim2sim.export.modelica import standardlibrary # impor necessary for model detection

class AixLib(modelica.Instance):
    library = "AixLib"


class Boiler(AixLib):
    path = "AixLib.FastHVAC.Components.HeatGenerators.Boiler.Boiler"
    represents = bim2sim.kernel.elements.all.Boiler

    def __init__(self, element):
        self.check_power = self.check_numeric(min_value=0 * ureg.kilowatt) #TODO: Checking System
        super().__init__(element)

    def get_params(self):
        self.manage_param("nominal_power", self.element.rated_power,
                          self.check_power)



