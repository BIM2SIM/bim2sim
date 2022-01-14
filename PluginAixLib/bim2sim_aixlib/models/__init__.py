"""Package for Python representations of HKESim models"""
from bim2sim.kernel.elements import hvac
from bim2sim.export import modelica
from bim2sim.kernel import elements
from bim2sim.kernel.aggregation import PipeStrand, Consumer, \
    ConsumerHeatingDistributorModule, GeneratorOneFluid
from bim2sim.kernel.units import ureg




class AixLib(modelica.Instance):
    library = "AixLib"


# copy paste from hkesim
class Boiler(AixLib):
    path = "AixLib.FastHVAC.Components.HeatGenerators.Boiler.Boiler"
    represents = hvac.Boiler

    def __init__(self, element):
        self.check_power = self.check_numeric(min_value=0 * ureg.kilowatt) #TODO: Checking System
        super().__init__(element)

    def request_params(self):
        self.request_param("rated_power", self.check_power, "nominal_power")


class BoilerModule(AixLib):
    path = "ModularEnergySystems.EnergyModules.BoilerSystem"
    represents = [GeneratorOneFluid]

    def __init__(self, element):
        self.check_temp_tupel = True #TODO: Checking System
        super().__init__(element)

    def request_params(self):
        # self.register_param("Tconsumer", self.check_temp_tupel, "Tconsumer")
        # self.params["Q_nom"] =
        self.params["Tconsumer"] = (self.element.temperature_inlet, self.element.temperature_outlet)
        self.params["Medium_heating"] = 'Modelica.Media.Water.ConstantPropertyLiquidWater'
        self.request_param("useHydraulicSeparator", self.check_temp_tupel, "useHydraulicSeparator")
        self.request_param("hydraulicSeparatorVolume", self.check_temp_tupel, "V")

        index = 0




