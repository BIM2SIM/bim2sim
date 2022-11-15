"""Module contains the unit registry for all params"""

from pint import UnitRegistry

# to avoid temperature problems
ureg = UnitRegistry(autoconvert_offset_to_baseunit=True)
ureg.define('percent = 0.01*count = %')
ureg.define('EUR = currency')
ureg.define('USD = currency')
ureg.define('GBP  = currency')

# TODO:multiple ifc files
# ifc units are up2date to ifc 4.3
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
    'WEBER': 'weber',
}


def parse_ifc(unit_entity):
    unit_type = unit_entity.is_a()
    if unit_type == 'IfcDerivedUnit':
        unit = ureg.dimensionless
        for element in unit_entity.Elements:
            prefix_string = \
                element.Unit.Prefix.lower() if element.Unit.Prefix else ''
            unit_part = ureg.parse_units('{}{}'.format(prefix_string,
                                                       ifc_pint_unitmap[
                                                           element.Unit.Name]))
            if element.Unit.Dimensions:
                unit_part = unit_part ** element.Dimensions
            unit = unit * unit_part ** element.Exponent
        return unit
    elif unit_type == 'IfcSIUnit':
        prefix_string = unit_entity.Prefix.lower() if unit_entity.Prefix else ''
        unit = ureg.parse_units(
            '{}{}'.format(prefix_string, ifc_pint_unitmap[unit_entity.Name]))
        if unit_entity.Dimensions:
            unit = unit ** unit_entity.Dimensions
        return unit
    elif unit_type in [
        'IfcConversionBasedUnit',
        'IfcConversionBasedUnitWithOffset'
    ]:
        # we use pint conversions instead IFC ones (ignoring ConversionOffset &
        # ConversionFactor)
        unit_component = unit_entity.ConversionFactor.UnitComponent
        prefix_string = unit_component.Prefix.lower() if \
            unit_component.Prefix else ''
        unit = ureg.parse_units(
            '{}{}'.format(prefix_string, ifc_pint_unitmap[unit_component.Name]))
        if unit_component.Dimensions:
            unit = unit ** unit_component.Dimensions
        return unit
    elif unit_type == 'IfcMonetaryUnit':
        currency = unit_entity.Currency
        try:
            unit = ureg.parse_units(currency)
        except:
            unit = ureg.dimensionless
        return unit
    elif unit_type == 'IfcDerivedUnitElement':
        unit = ureg.dimensionless
        prefix_string = \
            unit_type.Unit.Prefix.lower() if unit_type.Unit.Prefix else ''
        unit_part = ureg.parse_units('{}{}'.format(prefix_string,
                                                   ifc_pint_unitmap[
                                                       unit_type.Unit.Name]))
        if unit_type.Unit.Dimensions:
            unit_part = unit_part ** unit_type.Dimensions
        unit = unit * unit_part ** unit_type.Exponent
        return unit
    elif unit_type == 'IfcMeasureWithUnit':
        unit_component = unit_entity.UnitComponent
        unit = ureg.parse_units(ifc_pint_unitmap[unit_component.Name])
        if unit_component.Dimensions:
            unit = unit ** unit_component.Dimensions
        return unit
    else:
        raise NotImplementedError(f"Found {unit_type} and can't convert it to"
                                  f"Pint unit in Python.")
    # TODO: IfcDimensionalExponents,IfcContextDependentUnit


def conversion(unit, ufrom, uto):
    if unit is None:
        unit = 0
    if not isinstance(unit, ureg.Quantity):
        unit = ureg.Quantity(unit, getattr(ureg, ufrom))
    unit = unit.to(uto)
    return unit.to(uto)
