"""HVACObject

This module contains the Base class for all HVAC elements.
"""

class HVACObject(object):
    """HVACObject class.

    This is the base class for all HVAC elements.

    Parameters
    ----------

    parent : HVACSystem()
        The parent class of this object, the HVACSystem the HVACObject
        belongs to.
        Default is None.

    Attributes
    ----------

    IfcGUID: str
        The GUID of the corresponding IFC element.
    """
    def __init__(self, parent=None):
        """Constructor for HVACObject"""

        self.parent = parent
        self.IfcGUID = None
