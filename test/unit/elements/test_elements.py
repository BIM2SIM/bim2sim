"""Testing classes of module element"""

import unittest
from pathlib import Path

from bim2sim.elements import hvac_elements as hvac
from bim2sim.elements.base_elements import ProductBased, Factory
from bim2sim.elements.mapping.attribute import Attribute
from bim2sim.elements.mapping.ifc2python import load_ifc
from test.unit.elements.helper import SetupHelperHVAC
from bim2sim.utilities.types import IFCDomain

TEST_MODELS = Path(__file__).parent.parent.parent / 'resources'


# TODO test:
#  Element request attr
#  Element/ProductBased validate
#  Factory
#  Factory/IfcMixin ifc_types
#  ProductBased better subclass

def get_ifc(file: str):
    """Get IfcOpenShell wrapper instance for file"""
    ifc = load_ifc(TEST_MODELS / 'hydraulic/ifc' / file)
    return ifc


class Element1(ProductBased):
    ifc_types = {'IFCPIPESEGMENT': ['*']}
    attr_a = Attribute()


class Element2(ProductBased):
    ifc_types = {'IFCPIPEFITTING': ['*']}
    attr_x = Attribute()


class TestSlap(ProductBased):
    ifc_types = {'IfcSlab': ['*', '-SomethingSpecialWeDontWant', 'BASESLAB']}


class TestRoof(ProductBased):
    ifc_types = {
        'IfcRoof': ['FLAT_ROOF', 'SHED_ROOF'],
        'IfcSlab': ['ROOF']
    }


class TestProductBased(unittest.TestCase):

    def test_init(self):
        item = Element1()
        self.assertIsInstance(item, ProductBased)

        item2 = Element1(attr_a=4)
        self.assertEqual(4, item2.attr_a)

    def test_from_ifc(self):
        ifc = get_ifc('B01_2_HeatExchanger_Pipes.ifc')
        guid = '2aUc0GQrtLYqyOs0qLuQL7'
        ifc_entity = ifc.by_guid(guid)
        item = Element1.from_ifc(ifc_entity)

        self.assertIsInstance(item, ProductBased)
        self.assertEqual(guid, item.guid)

    def test_validate_creation_two_port_pipe(self):
        helper = SetupHelperHVAC()
        two_port_pipe = helper.element_generator(hvac.Pipe,
                                                 diameter=10,
                                                 length=100)
        valid = two_port_pipe.validate_creation()
        self.assertTrue(valid)

    def test_validate_creation_three_port_pipe(self):
        helper = SetupHelperHVAC()
        two_port_pipe = helper.element_generator(hvac.Pipe,
                                                 n_ports=3,
                                                 diameter=10,
                                                 length=100)
        valid = two_port_pipe.validate_creation()
        self.assertFalse(valid)


@unittest.skip("Not implemented")
class TestRelationBased(unittest.TestCase):
    pass


class TestFactory(unittest.TestCase):

    def test_init(self):
        relevant_elements = {
            Element1,
            Element2
        }
        factory = Factory(
            relevant_elements, ifc_units={}, ifc_domain=IFCDomain.arch,
            dummy=None)
        self.assertIsInstance(factory, Factory)

    def test_factory_create(self):
        ifc = get_ifc('B01_2_HeatExchanger_Pipes.ifc')
        entities = ifc.by_type('IFCPIPESEGMENT')
        relevant_elements = {
            Element1,
            Element2
        }
        factory = Factory(
            relevant_elements, ifc_units={}, ifc_domain=IFCDomain.arch,
            dummy=None)
        item = factory(entities[0])

        self.assertIsInstance(item, ProductBased)

    @unittest.skip("Not implemented")
    def test_factory_create_better_cls(self):
        pass

    def test_create_mapping(self):
        """Test if Factory uses ifc_types correctly"""
        factory = Factory(
            {TestRoof, TestSlap}, ifc_units={}, ifc_domain=IFCDomain.arch)

        self.assertIs(factory.get_element('IfcSlab', 'BASESLAB'), TestSlap)
        self.assertIs(factory.get_element('IfcSlab', 'OTHER'), TestSlap)
        self.assertIsNone(factory.get_element('IfcSlab', 'SomethingSpecialWeDontWant'))
        self.assertIs(factory.get_element('IfcSlab', 'ROOF'), TestRoof)


if __name__ == '__main__':
    unittest.main()
