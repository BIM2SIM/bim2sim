"""Testing Elements using Finder

Extracting a property from an ifc class starts the way in 'ment to by' by using the properties implemented in Element classes.
if a not None value is returned -> done
None is retuned -> Finder should provide result (None on Finder AttributeError)
AttributeError is raised -> Finder should provide result
other Exception is raised -> raise

Finder can return not None value -> done
return None -> done (no value found)
raise AttributeError -> attribute does not exist on finder
raise other Exeption -> raise"""

import unittest
import os

import bim2sim
from bim2sim import ifc2python
from bim2sim.ifc2python import finder, element, elements

IFC_PATH = os.path.abspath(os.path.join(
    os.path.dirname(bim2sim.__file__), '../..', 
    r'ExampleFiles/KM_DPM_Vereinshaus_Gruppe62_Heizung_DTV_all_elements.ifc'))

FINDER_RESULT = 'foo'

class DummyFinder(finder.Finder):

    def find(self, element, property_name:str):
        if property_name.startswith('prop'):
            if property_name.endswith('findernone'):
                return None
            return FINDER_RESULT
        else:
            raise AttributeError

class DummyElement(element.Element):
    ifc_type = "IfcPipeFitting"

    @property
    def prop_ok(self):
        return 12.3

    @property
    def prop_none(self):
        return None

    @property
    def prop_findernone(self):
        return None

    @property
    def prop_raise_attributerror(self):
        raise AttributeError

    @property
    def prop_raises_arithmeticerror(self):
        raise ArithmeticError

    @property
    def nofind_prop_none(self):
        return None

    @property
    def nofind_prop_raise_attributerror(self):
        raise AttributeError

    @property
    def nofind_prop_raises_arithmeticerror(self):
        raise ArithmeticError


class Test_ElementProperties(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ifc = ifc2python.load_ifc(IFC_PATH)
        cls.backup = element.Element.finder
        element.Element.finder = DummyFinder()

    @classmethod
    def tearDownClass(cls):
        element.Element.finder = cls.backup

    def setUp(self):
        ifc = self.__class__.ifc.by_type("IfcPipeFitting")[0]
        guid = "123"
        name = "DummyElement_xyz"
        self.ele = DummyElement(ifc=ifc)

    def test_ok(self):
        """default returns value"""
        self.assertEqual(self.ele.prop_ok, 12.3)

    def test_none(self):
        """no default result from element but found by finder"""
        self.assertEqual(self.ele.prop_none, FINDER_RESULT)
        self.assertIsNone(self.ele.prop_findernone)

    def test_invalid(self):
        """getting an invalid attribut will raise"""
        with self.assertRaises(AttributeError):
            self.ele.invalid_attribute

    def test_only_known_by_finder(self):
        """finder can provide results for not default properties"""
        self.assertEqual(self.ele.prop_xyz, FINDER_RESULT)

    def test_prop_raises_attributeerror(self):
        """property raises AttributeError but finder returns result"""
        self.assertEqual(self.ele.prop_raise_attributerror, FINDER_RESULT)

    def test_prop_raises_error(self):
        """property raises != AttributeError will raise"""
        with self.assertRaises(ArithmeticError):
            self.ele.prop_raises_arithmeticerror

    def test_nofind_prop_raises(self):
        """property raises and finder returns None"""

        with self.assertRaises(AttributeError):
            self.ele.nofind_prop_raise_attributerror

        with self.assertRaises(ArithmeticError):
            self.ele.nofind_prop_raises_arithmeticerror


if __name__ == '__main__':
    unittest.main()
