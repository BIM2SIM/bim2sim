﻿"""Module containing filters to identify IFC elements of interest"""


class Filter():
    """Base filter"""

    def __init__(self):
        pass

    def matches(self, ifcelement):
        """Check if element matches filter conditions"""
        raise NotImplementedError("Must overwride method 'matches'")

    def __repr__(self):
        return "<%s>"%(self.__class__.__name__)

class TypeFilter(Filter):
    """Filter for subsets of IFC types"""

    def __init__(self, components: list):
        super().__init__()

        self.components = components

    def matches(self, ifcelement):
        __doc__ = super().matches.__doc__
        return ifcelement in self.components #TODO: string based

class GeometricFilter(Filter):
    """Filter based on geometric position"""

    def __init__(self, 
            x_min: float = None, x_max: float = None, 
            y_min: float = None, y_max: float = None, 
            z_min: float = None, z_max: float = None):
        """None = unlimited"""
        super().__init__()

        assert any([not lim is None for lim in [x_min, x_max, y_min, y_max, z_min, z_max]]), \
            "Filter without limits has no effeckt."
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
        raise NotImplementedError("ToDo") # TODO

class ZoneFilter(GeometricFilter):
    """Filter elements within given zone"""

    def __init__(self, zone):
        raise NotImplementedError("ToDo") # TODO
        #super().__init__(x_min, x_max, y_min, y_max, z_min, z_max)
