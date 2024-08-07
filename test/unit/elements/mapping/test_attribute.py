"""Testing Attributes on Elements"""

import unittest

from bim2sim.kernel.decision import DecisionBunch, RealDecision
from bim2sim.elements.base_elements import ProductBased
from bim2sim.elements.mapping.attribute import Attribute
from bim2sim.elements.mapping.units import ureg
from test.unit.elements.helper import SetupHelperHVAC
from bim2sim.utilities.types import AttributeDataSource


class TestElement(ProductBased):
    ifc_types = {}

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

    helper = SetupHelperHVAC()

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


class TestAttributeDecisions(unittest.TestCase):

    def test_request_attribute(self):
        """Test to set attribute by decision."""
        ele = TestElement()
        self.assertIsNone(ele.attr2)
        ele.attributes['attr2']
        decision = ele.request('attr2')
        self.assertIsNone(ele.attr2)

        decision.value = 1
        self.assertEqual(1, ele.attr2)

    def test_request_requested(self):
        """Test requesting an already requested attribute"""
        ele = TestElement()
        decision1 = ele.request('attr2')
        decision2 = ele.request('attr2')
        self.assertIs(decision1, decision2)
        decision1.value = 5
        self.assertEqual(5, ele.attr2)

    def test_request_available(self):
        """Test requesting an already available attribute"""
        ele = TestElement()
        ele.attr3 = 7
        decision1 = ele.request('attr3')
        decision2 = ele.request('attr5')  # from function

        self.assertIsNone(decision1)
        self.assertIsNone(decision2)

    def test_request_many_attributes(self):
        """Test getting many decisions for elements and answer them together."""
        ele1 = TestElement()
        ele1.attr3 = 3
        ele2 = TestElement()
        attrs = ('attr1', 'attr2', 'attr3')
        bunch = DecisionBunch()
        for attr in attrs:
            for ele in (ele1, ele2):
                decision = ele.request(attr)
                if decision:
                    bunch.append(decision)

        for d in bunch:
            d.value = 42

        self.assertEqual(42 * ureg.meter, ele1.attr1)
        self.assertEqual(42 * ureg.meter, ele2.attr1)
        self.assertEqual(3, ele1.attr3)
        self.assertEqual(42, ele2.attr3)

    def test_external_decision(self):
        """Test to set attribute by external decision."""
        ele = TestElement()
        ext_decision = RealDecision("For attr2")
        decision = ele.request('attr2', ext_decision)
        self.assertIs(ext_decision, decision)

        ext_decision.value = 99
        self.assertEqual(99, ele.attr2)


class TestAttributeDataSource(unittest.TestCase):
    def test_data_source(self):
        ele = TestElement()
        ele.attr3 = 3
        decision = ele.request('attr2')
        decision.value = 10
        data_source_attr1 = ele.attributes['attr1'][-1]
        data_source_attr3 = ele.attributes['attr3'][-1]
        data_source_attr4 = ele.attributes['attr4'][-1]
        # get attribute values to make __get__ function run
        attr2 = ele.attr2
        attr5 = ele.attr5
        data_source_attr2 = ele.attributes['attr2'][-1]
        data_source_attr5 = ele.attributes['attr5'][-1]

        self.assertEqual(data_source_attr1, None)
        self.assertEqual(data_source_attr2, AttributeDataSource.decision)
        self.assertEqual(
            data_source_attr3, AttributeDataSource.manual_overwrite)
        self.assertEqual(data_source_attr4, None)
        self.assertEqual(data_source_attr5, AttributeDataSource.function)


if __name__ == '__main__':
    unittest.main()
