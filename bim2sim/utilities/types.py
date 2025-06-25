from enum import Enum, auto


class IFCDomain(Enum):
    """Enumeration for ifc file domains. """
    arch = auto()
    ventilation = auto()
    hydraulic = auto()
    sanitary = auto()
    mixed = auto()
    unknown = auto()


class LOD(Enum):
    """Level of detail in form of an enumeration. The different meaning depends
    on the specific simulation settings."""
    ignore = 0
    low = 1
    medium = 2
    full = 3


class ZoningCriteria(Enum):
    """Criteria for grouping thermal zones within a building.

    This enum defines different strategies for combining thermal zones based on
    various architectural and functional characteristics.

    Attributes:
        external: Groups zones based on their contact with the building
        exterior. Separates zones with exterior contact from
         interior-only zones.

        usage: Groups zones based on their functional usage/purpose within the
            building.

        external_orientation: Groups zones based on both exterior contact and
            facade orientation (North, East, South, West).

        external_orientation_usage: Combines grouping based on exterior contact
        , orientation, and usage.

        all_criteria: Most comprehensive grouping that considers:
            - Exterior contact
            - Facade orientation
            - Usage
            - Glass percentage
            - Physical adjacency between zones

        individual_spaces: Every space is converted into a thermal zone.

        combined_single_zone: All spaces are converted into a single thermal zone.
    """

    external = auto()
    usage = auto()
    external_orientation = auto()
    external_orientation_usage = auto()
    all_criteria = auto()
    individual_spaces = auto()
    combined_single_zone = auto()


class AttributeDataSource(Enum):
    """Enumerator for data_source of attributes.

    This Enumerator defines various sources from which attribute data can be
    derived. It categorizes the origin of attributes used in a given
    context, allowing for standardized reference and handling of these data
    sources in the application.

    Following enumerations exist:
        ifc_attr: Represents real IFC attributes derived directly from the IFC
         objects attributes.
        default_ps: Indicates attributes sourced from default property sets.
        default_association: Attributes obtained from default associations.
        finder: Attributes found through the finder searching mechanism.
        patterns: Attributes identified through pattern recognition.
        function: Attributes determined through functions of the attribute
         evaluation or calculations.
        default: Represents the default attribute source when no specific
        source is defined.
        decision: Attributes derived from answered decisions.
        manual_overwrite: Attributes that were manually overwritten during the
        process without the definition of a specific data source.
        enrichment: Attributes enriched or supplemented with additional
        information.
        space_boundary: Attributes derived from space boundary definitions.
    """
    ifc_attr = auto()
    default_ps = auto()
    default_association = auto()
    finder = auto()
    patterns = auto()
    function = auto()
    default = auto()
    decision = auto()
    manual_overwrite = auto()
    enrichment = auto()
    space_boundary = auto()


class BoundaryOrientation(Enum):
    """
    Enumeration for boundary orientations.

    top: Ceilings, roofs (normal points upward)
    bottom: Floors, slabs (normal points downward)
    vertical: Walls (normal perpendicular to vertical)
    """
    top = auto()
    bottom = auto()
    vertical = auto()


class FlowDirection(Enum):
    """Used to describe the flow direction of ports."""
    sink_and_source = 0
    sink = -1
    source = 1
    unknown = 2


class FlowSide(Enum):
    supply_flow = 1
    return_flow = -1
    unknown = 0
