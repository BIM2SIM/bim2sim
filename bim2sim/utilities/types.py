from enum import Enum, auto


class Domain(Enum):
    """Enumeration for ifc file domains. """
    arch = auto()
    ventilation = auto()
    hydraulic = auto()
    mixed = auto()
    unknown = auto()


class LOD(Enum):
    """Level of detail in form of an enumeration. The different meaning depends
    on the specific WorkflowSetting."""
    ignore = 0
    low = 1
    medium = 2
    full = 3
