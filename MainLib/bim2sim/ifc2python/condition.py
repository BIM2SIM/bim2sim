"""Module for validating an element by a condition"""
import logging


class Condition():
    """Class for validating an element by a condition"""

    _logger = None

    @property
    def logger(self):
        """logger instance"""
        if not Condition._logger:
            Condition._logger = logging.getLogger(__name__)
        return Condition._logger

    def run(self, element):
        pass


class RangeCondition(Condition):
    """"Validate through a simple ValueRange"""

    def __init__(self, key: str, valueMin: float, valueMax: float):
        self.key = key
        self.valueMin = valueMin
        self.valueMax = valueMax

    def check(self, element):
        value = getattr(element, self.key)
        return False if not value or value < self.valueMin or value > self.valueMax else True
