"""Module contains the unit registry for all params"""

from pint import UnitRegistry

ureg = UnitRegistry()

# Dictionary of the units from IfcUnitAssignment
ifcunits = {}

# TODO:multiple ifc files

ifc_pint_unitmap = {
    'AMPERE': 'ampere',
    'BECQUEREL': 'becquerel',
    'CANDELA': 'candela',
    'COULOMB': 'coulomb',
    'CUBIC_METRE': 'cubic metre',
    'DEGREE_CELSIUS': 'degree_Celsius',
    'FARAD': 'farad',
    'GRAM': 'gram',
    'GRAY': 'gray',
    'HENRY': 'henry',
    'HERTZ': 'hertz',
    'JOULE': 'joule',
    'KELVIN': 'kelvin',
    'LUMEN': 'lumen',
    'LUX': 'lux',
    'METRE': 'metre',
    'MOLE': 'mole',
    'NEWTON': 'newton',
    'OHM': 'ohm',
    'PASCAL': 'pascal',
    'RADIAN': 'radian',
    'SECOND': 'second',
    'SIEMENS': 'siemens',
    'SIEVERT': 'sievert',
    'SQUARE_METRE': 'square metre',
    'STERADIAN': 'steradian',
    'TESLA': 'tesla',
    'VOLT': 'volt',
    'WATT': 'watt',
    'WEBER': 'weber'
}
