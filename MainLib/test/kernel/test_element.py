"""Testing classes of module element"""

import unittest

from bim2sim.kernel import element
from bim2sim.kernel.attribute import Attribute

from test.kernel.helper import SetupHelper


# IFC_PATH = os.path.abspath(os.path.join(
#     os.path.dirname(bim2sim.__file__), '../..',
#     r'ExampleFiles/KM_DPM_Vereinshaus_Gruppe62_Heizung_DTV_all_elements.ifc'))


class TestElement(element.Element):
    ifc_type = "IfcPipeFitting"

    attr1 = Attribute(
        name='attr1'
    )

    attr2 = Attribute(
        name='attr2'
    )

    attr3 = Attribute(
        name='attr3'
    )

    attr4 = Attribute(
        name='attr4'
    )


@unittest.skip("To be defined")  # TODO: test factory, get_by_guid, discard, Dummy, Ports, connections
class TestElement(unittest.TestCase):
    pass


if __name__ == '__main__':
    unittest.main()
