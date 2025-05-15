"""Module containing filters to identify IFC elements of interest"""
from typing import Iterable, Tuple, Dict, Any, Type, List
import logging

from bim2sim.elements.base_elements import ProductBased


logger = logging.getLogger(__name__)


class Filter:
    """Base filter"""

    def __init__(self):
        pass

    def matches(self, ifcelement):
        """Check if element matches filter conditions"""
        raise NotImplementedError("Must overwride method 'matches'")

    def run(self):
        """Apply the Filter on IFC File"""
        raise NotImplementedError("Must overwride method 'run'")

    def __repr__(self):
        return "<%s>"%(self.__class__.__name__)


class TypeFilter(Filter):
    """Filter for subsets of IFC types"""

    def __init__(self, ifc_types: Iterable):
        super().__init__()
        self.ifc_types = ifc_types

    def matches(self, ifcelement):
        __doc__ = super().matches.__doc__
        return ifcelement.type in self.ifc_types  #TODO: string based

    def run(self, ifc) -> Tuple[Dict[Any, Type[ProductBased]], List[Any]]:
        """Scan ifc by ifc_types.

        :returns dict of ifc_types and suggested entities, list of unknown entities"""

        unknown_ifc_entities = []
        result = {}

        for ifc_type in self.ifc_types:
            try:
                entities = ifc.by_type(ifc_type)
            except RuntimeError:
                logger.info("No entity of type '%s' found", ifc_type)
                entities = []

            for entity in entities:
                result[entity] = ifc_type

        return result, unknown_ifc_entities


class TextFilter(Filter):
    """Filter for unknown properties by text fragments.

    This class provides functionality to filter IFC entities by analyzing text
    fragments to determine their potential element classes.

    Attributes:
        elements_classes: Collection of ProductBased classes to check for matches.
        ifc_units: Dictionary containing IFC unit information.
        optional_locations: Additional locations to check patterns beyond names.
    """

    def __init__(self, elements_classes: Iterable[ProductBased],
                 ifc_units: dict,
                 optional_locations: list = None):
        """Initialize a TextFilter instance.

        Args:
            elements_classes: Collection of ProductBased classes to check for matches.
            ifc_units: Dictionary containing IFC unit information.
            optional_locations: Additional locations to check patterns. Defaults to None.
        """
        super().__init__()
        self.elements_classes = elements_classes
        self.ifc_units = ifc_units
        self.optional_locations = optional_locations

    def find_matches(self, entity):
        """Find all element classes that match the given entity.

        Args:
            entity: The IFC entity to check.

        Returns:
            dict: Dictionary with matching classes as keys and their match fragments as values.
        """
        matches = {}
        for cls in self.elements_classes:
            fragments = cls.filter_for_text_fragments(
                entity, self.ifc_units, self.optional_locations)
            if fragments:
                matches[cls] = fragments

        return matches

    def run(self, ifc_entities: list):
        """Run the filter on a list of IFC entities.

        Args:
            ifc_entities: List of IFC entities to filter.

        Returns:
            tuple:
                - filter_results: Dictionary mapping IFC entities to matching classes
                  and their fragments.
                - unknown: List of IFC entities that didn't match any class.
        """
        filter_results = {}
        unknown = []

        for entity in ifc_entities:
            matches = self.find_matches(entity)
            if matches:
                # Store both the classes and their matching fragments
                filter_results[entity] = matches
            else:
                unknown.append(entity)

        return filter_results, unknown


class GeometricFilter(Filter):
    """Filter based on geometric position"""

    def __init__(self, 
            x_min: float = None, x_max: float = None, 
            y_min: float = None, y_max: float = None, 
            z_min: float = None, z_max: float = None):
        """None = unlimited"""
        super().__init__()

        assert any([not lim is None for lim in [x_min, x_max, y_min, y_max, z_min, z_max]]), \
            "Filter without limits has no effect."
        assert (x_min is None or x_max is None) or x_min < x_max, \
            "Invalid arguments for x_min and x_max"
        assert (y_min is None or y_max is None) or y_min < y_max, \
            "Invalid arguments for y_min and y_max"
        assert (z_min is None or z_max is None) or z_min < z_max, \
            "Invalid arguments for z_min and z_max"

        self.x_min = x_min
        self.x_max = x_max
        self.y_min = y_min
        self.y_max = y_max
        self.z_min = z_min
        self.z_max = z_max

    def matches(self, ifcelement):
        __doc__ = super().matches.__doc__
        raise NotImplementedError("ToDo")  #TODO


class ZoneFilter(GeometricFilter):
    """Filter elements within given zone"""

    def __init__(self, zone):
        raise NotImplementedError("ToDo")  #TODO
        #super().__init__(x_min, x_max, y_min, y_max, z_min, z_max)
