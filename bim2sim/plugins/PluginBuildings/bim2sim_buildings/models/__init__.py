"""Package for Python representations of AixLib models"""
from bim2sim.export import modelica
from bim2sim.elements import hvac_elements as hvac
from bim2sim.elements import bps_elements as bps
from bim2sim.elements.mapping.units import ureg
from bim2sim.export.modelica import Model


class Buildings(modelica.Instance):
    library = "Buildings"


class EPThermalZone(Buildings):
    pass


class SpawnBuilding(Buildings):
    path = "Buildings.ThermalZones.EnergyPlus_9_6_0.Building"
    represents = [bps.SpawnBuilding]

    def request_params(self):
        self.params["idfName"] = self.element.idfName
        self.params["epwName"] = self.element.epwName
        self.params["weaName"] = self.element.weaName
        self.params["printUnits"] = self.element.printUnits
        # self.request_param("idfName", None)
        # self.request_param("epwName", None)
        # self.request_param("weaName", None)
        # self.request_param("printUnits", None)
        # self.params["epwName"] = "D:/Test"
        # self.params["weaName"] = "D:/Test"
        # self.params["printUnits"] = True

    def get_port_name(self, port):
        return "weaBus"


class FreshAirSource(Buildings):
    path = "Buildings.Fluid.Sources.MassFlowSource_WeatherData"
    represents = [bps.FreshAirSource]

    def request_params(self):
        self.params["redeclare package Medium"] = 'Buildings.Media.Air'

# TODO this should be placed in AixLib but currently bim2sim only supports one
#  modelica library for export
class SpawnMultizone(Buildings):
    path = "AixLib.ThermalZones.HighOrder.SpawnOfEP.Multizone"
    represents = [bps.SpawnMultiZone]

    def _get_name(self):
        # TODO #1 maybe find a more generic way via mixins? then lookup needs to
        #  be adjusted
        """For static export elements

        This removes the dynamic name creation for elements which will always
        occur static in later export.
        """
        name = self.element.__class__.__name__.lower()
        return name

    def request_params(self):
        self.params["redeclare package Medium"] = 'Buildings.Media.Air'
        # TODO #1: get names of ep zones in correct order
        self.params["nZones"] = len(self.element.zone_names)
        # TODO: #542 How to export an array of values
        self.params["zoneNames"] = [f'"{ele}"'
                                    for ele in self.element.zone_names]


class SpawnModel(Model):
    def __init__(self, name, comment, elements: list, connections: list):
        super().__init__(name, comment, elements, connections)
        self.building_idf = None
        self.building_wea_epw = None
        self.building_wea_mos = None

        self.n_zones = None
        self.zone_names = []



# class EPMultizone(Buildings):
#     path = "AixLib.Fluid.BoilerCHP.BoilerGeneric"
#     represents = [hvac.Boiler]
#
#     def __init__(self, element):
#         super().__init__(element)
#
#     def request_params(self):
#
#         self.params["redeclare package Medium"] = 'AixLib.Media.Water'
#         self.request_param("dT_water",
#                            self.check_numeric(min_value=0 * ureg.kelvin),
#                            "dTWaterNom")
#         self.request_param("return_temperature",
#                            self.check_numeric(min_value=0 * ureg.celsius),
#                            "TRetNom")
#         self.request_param("rated_power",
#                            self.check_numeric(min_value=0 * ureg.kilowatt),
#                            "QNom")
#         self.request_param("min_PLR",
#                            self.check_numeric(min_value=0 * ureg.dimensionless),
#                            "PLRMin")
#
#     def get_port_name(self, port):
#         try:
#             index = self.element.ports.index(port)
#         except ValueError:
#             # unknown port
#             index = -1
#         if port.verbose_flow_direction == 'SINK':
#             return 'port_a'
#         if port.verbose_flow_direction == 'SOURCE':
#             return 'port_b'
#         else:
#             return super().get_port_name(port)  # ToDo: Gas connection
