"""Module contains the different classes for all HVAC elements"""

import math
import re

import numpy as np

from bim2sim.decorators import cached_property
from bim2sim.ifc2python import element
from bim2sim.decision import BoolDecision
import re
from bim2sim.ifc2python.element import Element
from shapely.geometry import Point
import matplotlib.pyplot as plt

IFC_TYPES_BPS = (
    'IfcBuilding',
    'IfcWall',
    'IfcWallElementedCase',  # necessary?
    'IfcWallStandardCase',  # necessary?
    'IfcRoof',
    'IfcShadingDevice',
    'ifcSlab',
    'IfcPlate',
    'IfcCovering',
    'IfcDoor',
    'IfcWindow',
    'IfcSpace'
)

class Boiler(element.Element):
    """Boiler"""
    ifc_type = 'IfcBoiler'

    # def _add_ports(self):
    #    super()._add_ports()
    #    for port in self.ports:
    #        if port.flow_direction == 1:
    #            port.flow_master = True
    #        elif port.flow_direction == -1:
    #            port.flow_master = True

    def get_inner_connections(self):
        connections = []
        vl_pattern = re.compile('.*vorlauf.*', re.IGNORECASE)  # TODO: extend pattern
        rl_pattern = re.compile('.*rücklauf.*', re.IGNORECASE)
        VL = []
        RL = []
        for port in self.ports:
            if any(filter(vl_pattern.match, port.groups)):
                if port.flow_direction == 1:
                    VL.append(port)
                else:
                    self.logger.warning("Flow direction (%s) of %s does not match %s",
                                        port.verbose_flow_direction, port, port.groups)
                    decision = BoolDecision(
                        "Use %s as VL?" % (port),
                        global_key=port.guid,
                        allow_save=True,
                        allow_load=True)
                    use = decision.decide()
                    if use:
                        VL.append(port)
            elif any(filter(rl_pattern.match, port.groups)):
                if port.flow_direction == -1:
                    RL.append(port)
                else:
                    self.logger.warning("Flow direction (%s) of %s does not match %s",
                                        port.verbose_flow_direction, port, port.groups)
                    decision = BoolDecision(
                        "Use %s as RL?" % (port),
                        global_key=port.guid,
                        allow_save=True,
                        allow_load=True)
                    use = decision.decide()
                    if use:
                        RL.append(port)
        if len(VL) == 1 and len(RL) == 1:
            connections.append((RL[0], VL[0]))
        else:
            self.logger.warning("Unable to solve inner connections for %s", self)

        return connections

    @cached_property
    def water_volume(self):
        """water_volume: float
            Water volume of boiler."""
        return 0.008

    @cached_property
    def min_power(self):
        """min_power: float
            Minimum power that boiler operates at."""
        return None

    @cached_property
    def rated_power(self):
        """rated_power: float
            Rated power of boiler."""
        return None

    @cached_property
    def efficiency(self):
        """efficiency: list
            Efficiency of boiler provided as list with pairs of [
            percentage_of_rated_power,efficiency]"""
        return None


class Pipe(element.Element):
    ifc_type = "IfcPipeSegment"
    default_diameter = ('Pset_PipeSegmentTypeCommon', 'NominalDiameter')
    pattern_diameter = [
        re.compile('.*Durchmesser.*', flags=re.IGNORECASE),
        re.compile('.*Diameter.*', flags=re.IGNORECASE),
    ]
    default_length = ('Qto_PipeSegmentBaseQuantities', 'Length')
    pattern_length = [
        re.compile('.*Länge.*', flags=re.IGNORECASE),
        re.compile('.*Length.*', flags=re.IGNORECASE),
    ]

    @property
    def diameter(self):
        result = self.find('diameter')

        if isinstance(result, list):
            return np.average(result).item()
        return result

    @property
    def length(self):
        try:
            return self.get_lenght_from_shape(self.ifc.Representation)
        except AttributeError:
            return None

    @staticmethod
    def get_lenght_from_shape(ifc_representation):
        """Serach for extruded depth in representations

        Warning: Found extrusion may net be the required length!
        :raises: AttributeError if not exactly one extrusion is found"""
        candidates = []
        try:
            for representation in ifc_representation.Representations:
                for item in representation.Items:
                    if item.is_a() == 'IfcExtrudedAreaSolid':
                        candidates.append(item.Depth)
        except:
            raise AttributeError("Failed to dertermine length.")
        if not candidates:
            raise AttributeError("No representation to dertermine length.")
        if len(candidates) > 1:
            raise AttributeError("Too many representations to dertermine length %s." % candidates)
        return candidates[0]


class PipeFitting(element.Element):
    ifc_type = "IfcPipeFitting"
    default_diameter = ('Pset_PipeFittingTypeCommon', 'NominalDiameter')
    default_pressure_class = ('Pset_PipeFittingTypeCommon', 'PressureClass')

    pattern_diameter = [
        re.compile('.*Durchmesser.*', flags=re.IGNORECASE),
        re.compile('.*Diameter.*', flags=re.IGNORECASE),
    ]

    @property
    def diameter(self):
        result = self.find('diameter')

        if isinstance(result, list):
            return np.average(result).item()
        return result

    @property
    def length(self):
        return self.find('length')

    @property
    def pressure_class(self):
        return self.find('pressure_class')


class SpaceHeater(element.Element):
    ifc_type = 'IfcSpaceHeater'

    @cached_property
    def nominal_power(self):
        return 42.0

    @cached_property
    def length(self):
        return 42.0


class StorageDevice(element.Element):
    ifc_type = "IfcStorageDevice"


class Storage(element.Element):
    ifc_type = "IfcTank"

    @property
    def storage_type(self):
        return None

    @property
    def hight(self):
        return 1

    @property
    def diameter(self):
        return 1

    @property
    def port_positions(self):
        return (0, 0.5, 1)

    @property
    def volume(self):
        return self.hight * self.diameter ** 2 / 4 * math.pi


class Distributor(element.Element):
    ifc_type = "IfcDistributionChamberElement"

    @property
    def volume(self):
        return 100

    @property
    def nominal_power(self):  # TODO Workaround, should come from aggregation of consumer circle
        return 100


class Pump(element.Element):
    ifc_type = "IfcPump"

    @property
    def rated_power(self):
        return 3

    @property
    def rated_hight(self):
        return 8

    @property
    def rated_volume_flow(self):
        return 4.3

    @property
    def diameter(self):
        return 40


class Valve(element.Element):
    ifc_type = "IfcValve"

    @cached_property
    def diameter(self):
        return

    @cached_property
    def length(self):
        return


class Duct(element.Element):
    ifc_type = "IfcDuctSegment"

    @property
    def diameter(self):
        return 1

    @property
    def length(self):
        return 1


class DuctFitting(element.Element):
    ifc_type = "IfcDuctFitting"

    @property
    def diameter(self):
        return 1

    @property
    def length(self):
        return 1


class AirTerminal(element.Element):
    ifc_type = "IfcAirTerminal"

    @property
    def diameter(self):
        return 1


class Medium(element.Element):
    ifc_type = "IfcDistributionSystems"


### BPS


class ThermalSpace(element.Element):
    ifc_type = "IfcSpace"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._space_elements = {}
        self._specific_u_value = None

    def _get_space_elements(self):
        objects = dict(self.objects)
        self._specific_u_value = 0
        # for space_element in self.ifc.Decomposes[0].RelatingObject.ContainsElements[0].RelatedElements:
        #     GUID_element = str(space_element)[str(space_element).find('(')+2:str(space_element).find(',')-1]
        #     if GUID_element in objects:
        #         if hasattr(objects[GUID_element], "orientation"):
        #             if objects[GUID_element].orientation not in self._space_elements:
        #                 self._space_elements[objects[GUID_element].orientation] = []
        #             self._space_elements[objects[GUID_element].orientation].append(objects[GUID_element])


        # u_a = 0
        # for obj in self._space_elements:
        #     if hasattr(obj, "area") and hasattr(obj, "u_value"):
        #         u_a += obj.area * obj.u_value
        # self._specific_u_value = u_a / (self.area*self.height)

    @cached_property
    def Pset_ThermalSpaceCommon(self):
        return self.get_propertysets()

    @property
    def space_elements(self):
        self._get_space_elements()
        return self._space_elements

    @property
    def max_temperature(self):
        temp = '21 °C'
        if "HLS" in self.Pset_PipeFittingTypeCommon:
            temp = self.Pset_PipeFittingTypeCommon['HLS']['Temperature']
        return temp

    @property
    def min_temperature(self):
        return '16 °C'

    @property
    def area(self):
        area = 1
        if "Abmessungen" in self.Pset_PipeFittingTypeCommon:
            area = self.Pset_PipeFittingTypeCommon['Abmessungen']['Fläche']
        return area

    @property
    def height(self):
        return 1


class Wall(element.Element):
    ifc_type = "IfcWall"
    # ifc_type = 'IfcWallStandardCase'

    @cached_property
    def Pset_WallCommon(self):
        return self.get_propertysets()

    @property
    def area(self):
        return self.get_properties()

    @property
    def u_value(self):
        return 1

    @property
    def is_external(self):
        if 'IW' in self.Pset_WallCommon['ID-Daten']['Typname']:
            external = False
        else:
            external = True
        return external

    @property
    def orientation(self):
        if self.is_external is True:
            orientation = self.ifc.Representation.Description
        else:
            orientation = "Intern"
        return orientation


class OuterWall(Wall):
    @property
    def orientation(self):
        return 1


class Window(element.Element):
    ifc_type = "IfcWindow"

    @cached_property
    def Pset_WindowCommon(self):
        return self.get_propertysets()

    @property
    def is_external(self):
        external = False
        if 'Daten' in self.Pset_WindowCommon:
            if 'Lage Bauteil' in self.Pset_WindowCommon['Daten']:
                if 'außen' in self.Pset_WindowCommon['Daten']['Lage Bauteil']:
                    external = True

        return external

    @property
    def area(self):
        return 1

    @property
    def u_value(self):
        return 1

    @property
    def g_value(self):
        return 1

    @property
    def orientation(self):
        if self.is_external is True:
            orientation = self.ifc.Tag
        else:
            orientation = "Intern"
        return orientation


class Door(element.Element):
    ifc_type = "IfcDoor"

    @property
    def area(self):
        return 1

    @property
    def u_value(self):
        return 1

    @property
    def g_value(self):
        return 1


class Roof(element.Element):
    ifc_type = "IfcRoof"

    @property
    def area(self):
        return 1

    @property
    def is_external(self):
        external = True
        return external

    @property
    def u_value(self):
        return 1

    @property
    def g_value(self):
        return 1


class ShadingDevice(element.Element):
    ifc_type = "IfcShadingDevice"

    @property
    def area(self):
        return 1

    @property
    def shading_device_type(self):
        return 1

    @property
    def g_value(self):
        return 1


class Building(element.Element):
    ifc_type = "IfcBuilding"

    @cached_property
    def Pset_BuildingCommon(self):
        return self.get_propertysets()

    @property
    def net_area(self):
        return 1

    @property
    def occupancy_type(self):
        return 1

    @property
    def number_storeys(self):
        return 1

    @property
    def year_construction(self):
        return 1


class Covering(element.Element):
    ifc_type = "IfcCovering"

    @property
    def area(self):
        return 1

    @property
    def u_value(self):
        return 1

    @property
    def g_value(self):
        return 1


class Plate(element.Element):
    ifc_type = "IfcPlate"

    @property
    def area(self):
        return 1

    @property
    def u_value(self):
        return 1

    @property
    def g_value(self):
        return 1


class Slab(element.Element):
    ifc_type = "IfcSlab"

    @cached_property
    def Pset_SlabCommon(self):
        return self.get_propertysets()

    @property
    def area(self):
        if "Abmessungen" in self.Pset_SlabCommon:
            area_value = self.Pset_SlabCommon["Abmessungen"]["Fläche"]
        else:
            area_value = 0
        return area_value

    @property
    def is_external(self):
        if self.ifc.Tag == 'True':
            return True
        else:
            return False


    @property
    def u_value(self):
        return 1

    @property
    def g_value(self):
        return 1


__all__ = [ele for ele in locals().values() if ele in element.Element.__subclasses__()]
