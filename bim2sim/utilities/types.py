from enum import Enum


class Domain(Enum):
    """Enumeration for ifc file domains. """
    arch = 'arch'
    ventilation = 'ventilation'
    hydraulic = 'hydraulic'
    mixed = 'mixed'
    unknown = 'unknown'
