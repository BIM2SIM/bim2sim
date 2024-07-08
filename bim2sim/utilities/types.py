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
    external = auto()
    usage = auto()
    external_orientation = auto()
    external_orientation_usage = auto()
    all_criteria = auto()
