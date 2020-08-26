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
        # TODO: Test if unit_component ist no IFCSIUnit?!?!
        unit = ureg.dimensionless
        for element in unit_entity.Elements:
            prefix_string = element.Unit.Prefix.lower() if element.Unit.Prefix else ''
            unit_part = ureg.parse_units('{}{}'.format(prefix_string, ifc_pint_unitmap[element.Unit.Name]))
            if element.Unit.Dimensions:
                unit_part = unit_part ** element.Dimensions
            unit = unit * unit_part ** element.Exponent
        return unit
    elif unit_type == 'IfcSIUnit':
        prefix_string = unit_entity.Prefix.lower() if unit_entity.Prefix else ''
        unit = ureg.parse_units('{}{}'.format(prefix_string, ifc_pint_unitmap[unit_entity.Name]))
        if unit_entity.Dimensions:
            unit = unit ** unit_entity.Dimensions
        return unit
    elif unit_type == 'IfcConversionBasedUnit':
        # TODO: Test with multiple components? test if unit_component ist no IFCSIUnit?!?! Conversion?! Seperate
        #  or use in units?!
        unit_component = unit_entity.ConversionFactor.UnitComponent
        prefix_string = unit_component.Prefix.lower() if unit_component.Prefix else ''
        unit = ureg.parse_units('{}{}'.format(prefix_string, ifc_pint_unitmap[unit_component.Name]))
        if unit_component.Dimensions:
            unit = unit ** unit_component.Dimensions
        return unit
    elif unit_type == 'IfcMonetaryUnit':
        # TODO: Need To Be Testet Currency in IFC = Currency in PINT?
        currency = unit_entity.Currency
        try:
            unit = ureg.parse_units(currency)
        except:
            unit = ureg.dimensionless
        return unit
    else:
        pass  # TODO: Implement


def conversion(unit ,ufrom, uto):
    if not isinstance(unit, ureg.Quantity):
        unit = ureg.Quantity(unit, getattr(ureg, ufrom))
    unit = unit.to(uto)
    return unit.to(uto)
