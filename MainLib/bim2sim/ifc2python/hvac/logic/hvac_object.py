"""HVACObject

This module contains the Base class for all HVAC elements.
"""

class HVACObject(object):
    """HVACObject class.

    This is the base class for all HVAC elements.

    Parameters
    ----------


    parent: HVACSystem()
        The parent class of this object, the HVACSystem the HVACObject
        belongs to.
        Default is None.


    Attributes
    ----------

    IfcGUID: list of strings
        A list with the GUID of the corresponding IFC elements, in general
        only one element, for pipeStrand mostly more than one.
    """
    def __init__(self, parent=None):
        """Constructor for HVACObject"""

        self.parent = parent
        # todo create own id structure or use exising one and only map the ifc
        # todo is existing?
        self.IfcGUID = None


