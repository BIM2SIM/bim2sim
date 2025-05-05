import re
import inspect
import sys
from bim2sim.elements.mapping.units import ureg
import ifcopenshell.geom
from bim2sim.elements.hvac_elements import HVACProduct
from bim2sim.elements.mapping import attribute
from typing import Set, List, Tuple, Generator, Union, Type

class VentilationProduct(HVACProduct):
    pass


class Duct(VentilationProduct):
    ifc_types = {"IfcDuctSegment": ['*', 'RIGIDSEGMENT', 'FLEXIBLESEGMENT']}

    pattern_ifc_type = [
        re.compile('Duct.?segment', flags=re.IGNORECASE)
    ]

    diameter = attribute.Attribute(
        description='Duct diameter',
        unit=ureg.millimeter,
    )
    length = attribute.Attribute(
        description='Length of Duct',
        unit=ureg.meter,
    )

    def calc_cost_group(self) -> [int]:
        """Default cost group for HVAC elements is 400"""
        return 430

    @property
    def expected_hvac_ports(self):
        return 2


class DuctFitting(VentilationProduct):
    ifc_types = {
        "IfcDuctFitting":
            ['*', 'BEND', 'CONNECTOR', 'ENTRY', 'EXIT', 'JUNCTION',
             'OBSTRUCTION', 'TRANSITION']
    }

    pattern_ifc_type = [
        re.compile('Duct.?fitting', flags=re.IGNORECASE)
    ]

    diameter = attribute.Attribute(
        description='Duct diameter',
        unit=ureg.millimeter,
    )
    length = attribute.Attribute(
        description='Length of Duct',
        unit=ureg.meter,
    )

    def calc_cost_group(self) -> [int]:
        """Default cost group for HVAC elements is 400"""
        return 430

    @property
    def expected_hvac_ports(self):
        return (2, 3)


class FlowController(VentilationProduct):
    ifc_types = {
        "IfcFlowController": ['*']
    }

    def calc_cost_group(self) -> [int]:
        """Default cost group for HVAC elements is 400"""
        return 430

    @property
    def expected_hvac_ports(self):
        return 2


class FireDamper(VentilationProduct):
    ifc_types = {
        "IfcDamper": ['FIREDAMPER', 'FIRESMOKEDAMPER', 'SMOKEDAMPER']
    }
    pattern_ifc_type = [
        re.compile('Brand.?schutz.?klappe', flags=re.IGNORECASE)
    ]

    def calc_cost_group(self) -> [int]:
        """Default cost group for HVAC elements is 400"""
        return 430

    @property
    def expected_hvac_ports(self):
        return 2


class AirTerminal(VentilationProduct):
    ifc_types = {
        "IfcAirTerminal":
            ['*', 'DIFFUSER', 'GRILLE', 'LOUVRE', 'REGISTER']
    }

    pattern_ifc_type = [
        re.compile('Air.?terminal', flags=re.IGNORECASE)
    ]

    diameter = attribute.Attribute(
        description='Terminal diameter',
        unit=ureg.millimeter,
    )

    def calc_cost_group(self) -> [int]:
        """Default cost group for HVAC elements is 400"""
        return 430

    @property
    def expected_hvac_ports(self):
        return 2

    @property
    def shape(self):
        """returns topods shape of the radiator"""
        settings = ifcopenshell.geom.main.settings()
        settings.set(settings.USE_PYTHON_OPENCASCADE, True)
        settings.set(settings.USE_WORLD_COORDS, True)
        settings.set(settings.EXCLUDE_SOLIDS_AND_SURFACES, False)
        settings.set(settings.INCLUDE_CURVES, True)
        return ifcopenshell.geom.create_shape(settings, self.ifc).geometry



# collect all domain classes
items: Set[VentilationProduct] = set()
for name, cls in inspect.getmembers(
        sys.modules[__name__],
        lambda member: inspect.isclass(member)  # class at all
                       and issubclass(member, VentilationProduct)  # domain subclass
                       and member is not VentilationProduct  # but not base class
                       and member.__module__ == __name__):  # declared here
    items.add(cls)
