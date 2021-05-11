"""Testing Attributes on Elements"""

import unittest

from bim2sim.kernel import element
from bim2sim.kernel.attribute import Attribute
from bim2sim.decision import Decision
from bim2sim.kernel.units import ureg

from test.unit.kernel.helper import SetupHelper


class TestElement(element.ProductBased):
    ifc_type = "IfcTest"

    attr1 = Attribute(
        unit=ureg.meter
    )
    attr2 = Attribute()
    attr3 = Attribute()
    attr4 = Attribute()
    attr5 = Attribute(
        functions=[lambda self, attr:42]
    )


class TestAttribute(unittest.TestCase):

    helper = SetupHelper()

    # @classmethod
    # def setUpClass(cls):
    #     # cls.helper = SetupHelper()
    #     Decision.enable_debug(None)
    #
    # @classmethod
    # def tearDownClass(cls):
    #     cls.helper = None
    #     Decision.disable_debug()

    def setUp(self):
        self.subject = self.helper.element_generator(TestElement)

    def tearDown(self):
        self.helper.reset()

    def test_set_get(self):
        """Test setting and getting valid attribute values"""
        self.assertIsNone(self.subject.attr1)

        self.subject.attr1 = 1.23
        self.assertEqual(1.23 * ureg.meter, self.subject.attr1)

    def test_type_consistence(self):
        """Test value of type int remains as int, float as float, etc."""
        self.assertIsNone(self.subject.attr1)

        self.subject.attr1 = 0.2
        self.assertIs(type(0.2), type(self.subject.attr1.magnitude))

        self.subject.attr2 = 42
        self.assertIs(42, self.subject.attr2)

        self.subject.attr3 = True
        self.assertIs(True, self.subject.attr3)

        self.subject.attr4 = 'abc'
        self.assertIs('abc', self.subject.attr4)

    def test_attribute_manager(self):
        """Test attribute manager"""
        self.assertIsNone(self.subject.attr1)

        self.assertEqual(5, len(self.subject.attributes), "All Attributes should be registered in AttributeManager")

        self.assertEqual(5, len(list(self.subject.attributes.names)))

        self.assertIn('attr1', self.subject.attributes)

        # set attribute
        self.subject.attr1 = 1.
        self.assertEqual(1. * ureg.meter, self.subject.attr1)

        # set attribute manager value
        self.subject.attributes['attr2'] = 4
        self.assertEqual(self.subject.attr2, 4)

        self.subject.attributes['attr3'] = True
        self.assertEqual(True, self.subject.attr3)

    def test_attribute_manager_unit(self):
        """test get unit from manager"""
        self.assertEqual(ureg.meter, self.subject.attributes.get_unit('attr1'))

    def test_attribute_manager_names(self):
        """test names of manager"""

        target = {'attr1', 'attr2', 'attr3', 'attr4', 'attr5'}
        found = set(self.subject.attributes.names)
        self.assertEqual(target, found)

    def test_set_invalid_attribute(self):
        """Test setting an invalid attribute"""
        with self.assertRaises(AttributeError):
            self.subject.attributes.set('invalid_attribute', -1)

    def test_get_invalid_attribute(self):
        """Test getting an invalid attribute"""
        with self.assertRaises(KeyError):
            self.subject.attributes['invalid_attribute']

    def test_from_function(self):
        """test getting attribute from function"""
        self.assertEqual(42, self.subject.attr5)


if __name__ == '__main__':
    unittest.main()
