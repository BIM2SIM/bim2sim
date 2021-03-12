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


class NotPredefinedElement(element.RelatedSubElementMixin, element.ProductBased):
    ifc_type = 'IfcSomething'

    def __init__(self, *args, **kwargs):
        self.some_attr = 2
        super().__init__(*args, **kwargs)


class PredefinedElement(NotPredefinedElement):
    predefined_types = ('ITEM_A', 'ITEM_B')

    def __init__(self, *args, **kwargs):
        self.some_other_attr = 3
        super().__init__(*args, **kwargs)


class TestPredefinedTypes(unittest.TestCase):

    def test_instanciate_element_with_predefined_sub_elements(self):
        """"""
        instance = NotPredefinedElement(predefined_type='ITEM_A')
        self.assertIsInstance(instance, PredefinedElement)
        # check successfull init
        self.assertEqual(2, instance.some_attr)
        self.assertEqual(3, instance.some_other_attr)

    def test_instantiate_actual_element(self):
        instance = PredefinedElement()
        self.assertIsInstance(instance, PredefinedElement)
        # check successfull init
        self.assertEqual(2, instance.some_attr)
        self.assertEqual(3, instance.some_other_attr)


if __name__ == '__main__':
    unittest.main()
