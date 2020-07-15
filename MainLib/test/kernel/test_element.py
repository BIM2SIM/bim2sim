"""Testing classes of module element"""

import unittest

from bim2sim.kernel import element
from bim2sim.kernel.attribute import Attribute

from test.kernel.helper import SetupHelper


# IFC_PATH = os.path.abspath(os.path.join(
#     os.path.dirname(bim2sim.__file__), '../..',
#     r'ExampleFiles/KM_DPM_Vereinshaus_Gruppe62_Heizung_DTV_all_elements.ifc'))


class TestElement(element.Element):
    ifc_type = "IfcTest"

    attr1 = Attribute()
    attr2 = Attribute()
    attr3 = Attribute()
    attr4 = Attribute()


@unittest.skip("To be defined")  # TODO: test factory, get_by_guid, discard, Dummy, Ports, connections
class TestElement(unittest.TestCase):
    pass


if __name__ == '__main__':
    unittest.main()
