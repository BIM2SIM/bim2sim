import logging

from pathlib import Path
from ifcopenshell import file

from bim2sim.elements.mapping.finder import TemplateFinder
from bim2sim.elements.mapping.units import parse_ifc
from bim2sim.elements.mapping import ifc2python
from bim2sim.utilities.types import IFCDomain

logger = logging.getLogger(__name__)


class IfcFileClass:
    """Combine IfcOpenShell file instance, finder and units together.

    Especially if we handle multiple IFC files this dataclass helps us to keep
    track which finder and units belong to which ifc file.

    Args:
        ifc_path: Pathlib object that points to ifc file
        reset_guids: Boolean that determine if GUIDs should be reset
        ifc_domain: Domain of the given ifc file if this is known
    """

    def __init__(
            self,
            ifc_path: Path,
            reset_guids: bool = False,
            ifc_domain: IFCDomain = None):
        self.ifc_file_name = ifc_path.name
        self.file = self.load_ifcopenshell_file(ifc_path)
        self.finder = None
        self.ifc_units = self.get_ifc_units()
        self.domain = ifc_domain if ifc_domain else IFCDomain.unknown
        self.schema = self.file.schema
        if reset_guids:
            self.file = ifc2python.reset_guids(self.file)

    def initialize_finder(self, finder_path):
        self.finder = TemplateFinder()
        yield from self.finder.initialize(self.file)
        if finder_path:
            self.finder.load(finder_path)

    @staticmethod
    def load_ifcopenshell_file(ifc_path) -> file:
        """Loads the IfcOpenShell file instance"""
        ifc_file = ifc2python.load_ifc(ifc_path)
        return ifc_file

    def get_ifc_units(self) -> dict:
        """Returns dict to translate IFC units to pint units

        To use units from IFC we get all unit definitions from the ifc and their
        corresponding measurement elements and map them to pint units.

        Returns:
             dict where key is the IfcMeasurement and value the pint unit
             definition. e.g. 'IfcLengthMeasure': meter
        """
        logger.info(f"Initializing units for IFC file: {self.ifc_file_name}")
        unit_assignment = self.file.by_type('IfcUnitAssignment')

        ifc_units = {}

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
                ifc_units[key] = unit
                if pos_key:
                    ifc_units[pos_key] = unit
            except:
                logger.warning(f"Failed to parse {unit_entity}")
        ifc_units = {k.lower(): v for k, v in ifc_units.items()}
        return ifc_units
