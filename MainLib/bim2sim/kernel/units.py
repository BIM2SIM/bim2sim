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


def parse_ifc(unit_entity):

    unit_type = unit_entity.is_a()
    if unit_type == 'IfcDerivedUnit':
        pass  # TODO: Implement
    elif unit_type == 'IfcSIUnit':
        prefix_string = unit_entity.Prefix.lower() if unit_entity.Prefix else ''
        unit = ureg.parse_units('{}{}'.format(prefix_string, ifc_pint_unitmap[unit_entity.Name]))
        if unit_entity.Dimensions:
            unit = unit ** unit_entity.Dimensions
        return unit
    elif unit_type == 'IfcConversionBasedUnit':
        pass  # TODO: Implement
    elif unit_type == 'IfcMonetaryUnit':
        pass  # TODO: Implement
    else:
        pass  # TODO: Implement
