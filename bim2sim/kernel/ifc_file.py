from ifcopenshell import file as ifc_file

from bim2sim.kernel.finder import Finder, TemplateFinder
from bim2sim.kernel.units import parse_ifc


class IfcFileClass:
    """Combine IfcOpenShell file instance, finder and units together.

    Especially if we handle multiple IFC files this dataclass helps us to keep
    track which finder and units belong to which ifc file.

    Args:
        file: IfcOpenShell file instance
        finder: Initialized TemplateFinder instance
    """

    def __init__(self, file: ifc_file, finder=TemplateFinder):
        self.file = file
        self.finder = finder
        self.ifc_units = self.get_ifc_units()

    def get_ifc_units(self) -> dict:
        """Returns dict to translate IFC units to pint units

        To use units from IFC we get all unit definitions from the ifc and their
        corresponding measurement instances and map them to pint units.

        Returns:
             dict where key is the IfcMeasurement and value the pint unit
             definition. e.g. 'IfcLengthMeasure': meter
        """
        unit_assignment = self.file.by_type('IfcUnitAssignment')

        results = {}

        for unit_entity in unit_assignment[0].Units:
            try:
                if hasattr(unit_entity, 'UnitType'):
                    key = 'Ifc{}'.format(
                        unit_entity.UnitType.capitalize().replace('unit',
                                                                  'Measure'))
                    pos_key = 'IfcPositive{}'.format(
                        unit_entity.UnitType.capitalize().replace('unit',
                                                                  'Measure'))
                elif hasattr(unit_entity, 'Currency'):
                    key = 'IfcMonetaryMeasure'
                unit = parse_ifc(unit_entity)
                results[key] = unit
                if pos_key:
                    results[pos_key] = unit
            except:
                self.logger.warning(f"Failed to parse {unit_entity}")

        return results
