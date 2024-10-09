"""Kernel module of bim2sim

Holds central target simulation independent logic.
"""


class IFCDomainError(Exception):
    """Exception raised if IFCDomain of file and element do not fit."""
