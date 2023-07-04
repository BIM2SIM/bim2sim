"""Module for validating an element by a condition"""
import logging

from bim2sim.elements.mapping.units import ureg


class Condition:
    """Class for validating an element by a condition"""

    _logger = None

    def __init__(self, name, critical_for_creation=True):
        self.name = name
        self.critical_for_creation = critical_for_creation

    @property
    def logger(self):
        """logger instance"""
        if not Condition._logger:
            Condition._logger = logging.getLogger(__name__)
        return Condition._logger

    def check(self, element, value):
        pass


class RangeCondition(Condition):
    """"Validate through a simple ValueRange

    Args:
        key: attribute of the element to validate
        value_min: minimum allowed value
        value_max: maximum allowed value
        incl_edges: if True, the value_min and value_max are valid as well
        critical_for_creation: if True, the element will not be created if the
         validation fails
    Return:
        True if valid, False if not valid
    """

    def __init__(self, key: str, value_min, value_max, incl_edges: bool = False,
                 critical_for_creation: bool = True):
        super().__init__(key, critical_for_creation)
        self.key = key
        self.valueMin = value_min
        self.valueMax = value_max
        self.incl_edges = incl_edges
        self.critical_for_creation = critical_for_creation

    def check(self, element, value):
        if value is None:
            return False
        if not isinstance(value, (list, set)):
            value = [value]
        check_list = []
        for v in value:
            if self.incl_edges:
                check_list.append(False if not v or v <= self.valueMin
                                  or v >= self.valueMax else True)
            else:
                check_list.append(False if not v or v < self.valueMin
                              or v > self.valueMax else True)
        return all(check_list)


class ListCondition(Condition):
    """Validate if a list has elements, or a specific number of elements

    Args:
        key: attribute of the element to validate
        values: list of allowed values
        critical_for_creation: if True, the element will not be created if the
         validation fails
    Return:
        True if valid, False if not valid
    """

    def __init__(self, key: str, list_length: int = None,
                 critical_for_creation: bool = True):
        super().__init__(key, critical_for_creation)
        self.key = key
        self.listLength = list_length
        self.critical_for_creation = critical_for_creation

    def check(self, element, value):
        if type(value) is not list:
            return False
        if self.listLength is None:
            return True if len(value) > 0 else False
        else:
            return True if len(value) == self.listLength else False


class ThicknessCondition(Condition):
    def __init__(self, key: str,
                 threshold: ureg.Quantity = 0,
                 critical_for_creation: bool = True):
        super().__init__(key, critical_for_creation)
        self.key = key
        self.threshold = threshold
        self.critical_for_creation = critical_for_creation

    def check(self, element, value):
        if value is None:
            return False
        value_from_layers = sum(layer.thickness for layer in element.layers)
        if not value_from_layers:
            return False
        if not self.threshold:
            return True if value == value_from_layers else False
        discrepancy = abs(value - value_from_layers) / value
        return True if discrepancy <= self.threshold else False


class UValueCondition(Condition):
    def __init__(self, key: str,
                 threshold: ureg.Quantity = 0,
                 critical_for_creation: bool = True):
        super().__init__(key, critical_for_creation)
        self.key = key
        self.threshold = threshold
        self.critical_for_creation = critical_for_creation

    def check(self, element, value):
        if value is None:
            return False
        value_from_layers = self.get_u_value_from_layers(element.layerset)
        if not value_from_layers:
            return False
        if not self.threshold:
            return True if value == value_from_layers else False
        discrepancy = abs(value - value_from_layers) / value
        return True if discrepancy <= self.threshold else False

    @staticmethod
    def get_u_value_from_layers(layer_set):
        layers_r = 0
        for layer in layer_set.layers:
            if layer.thickness:
                if layer.material.thermal_conduc and \
                        layer.material.thermal_conduc > 0:
                    layers_r += layer.thickness / layer.material.thermal_conduc

        if layers_r > 0:
            return 1 / layers_r
        return None
