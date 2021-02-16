"""Test for decision.py"""

import unittest
from unittest.mock import patch
import tempfile
import os

import pint

from bim2sim import decision
from bim2sim.decision import Decision
from bim2sim.decision.frontend import FrontEnd
import bim2sim.decision.console
from bim2sim.kernel.units import ureg


class DecisionTestBase(unittest.TestCase):
    """Base class for Decision tests"""
    frontend = FrontEnd()
    _backup = None

    @classmethod
    def setUpClass(cls):
        cls._backup = decision.Decision.frontend
        decision.Decision.set_frontend(cls.frontend)

    @classmethod
    def tearDownClass(cls):
        decision.Decision.set_frontend(cls._backup)

    def tearDown(self):
        decision.Decision.all.clear()
        decision.Decision.stored_decisions.clear()


class TestDecision(DecisionTestBase):
    """General Decision related tests"""

    def test_decision_value(self):
        """test decision value consistency"""

        dec = decision.RealDecision(question="??")

        self.assertIsNone(dec.value)

        with Decision.debug_answer(5., validate=True):
            dec.decide()

        self.assertEqual(dec.value, 5)
        self.assertIsInstance(dec.value, pint.Quantity)

    def test_invalid_value(self):
        """test float value for IntDecision"""
        dec = decision.RealDecision(question="??")
        self.assertIsNone(dec.value)

        with self.assertRaises(ValueError):
            with Decision.debug_answer('five', validate=True):
                dec.decide()

    def test_skip(self):
        """test skipping decisions"""
        target_dict = {}
        dec1 = decision.BoolDecision(
            question="??",
            output=target_dict,
            output_key="key1",
            collect=True,
            allow_skip=True)
        dec2 = decision.BoolDecision(
            question="??",
            output=target_dict,
            output_key="key2",
            collect=True,
            allow_skip=False)

        dec1.skip()
        self.assertIsNone(dec1.value)

        with self.assertRaises(decision.DecisionException):
            dec2.skip()

    def test_collectable(self):
        """test collecting multiple BoolDecisions and decide_collected"""
        target_dict = {}
        dec_list = []
        dec1 = decision.BoolDecision(
            question="??",
            output=target_dict,
            output_key="key1",
            collect=True)
        dec_list.append(dec1)
        dec_list.append(decision.BoolDecision(
            question="??",
            output=target_dict,
            output_key="key2",
            collect=True))

        self.assertIsNone(dec1.value)
        self.assertEqual(len(decision.Decision.all), len(dec_list))

        with Decision.debug_answer(True):
            decision.Decision.decide_collected()

        self.assertTrue(all(target_dict.values()))

        with self.assertRaises(AttributeError, msg="Collect without output_key"):
            decision.BoolDecision(question="??", collect=True)

    def check(self, value):
        """validation func"""
        return 0 < float(value) < 10

    def test_save_load(self):
        """test saving decisions an loading them"""
        key_bool = "key_bool"
        key_real = "key_real"

        with Decision.debug_answer(False):
            dec_bool = decision.BoolDecision(
                question="??",
                global_key=key_bool,
                allow_save=True)
            dec_bool.decide()
        self.assertFalse(dec_bool.value)

        with Decision.debug_answer(5.):
            dec_real = decision.RealDecision(
                question="??",
                validate_func=self.check,
                global_key=key_real,
                allow_save=True)
            dec_real.decide()
        self.assertEqual(dec_real.value, 5)

        with tempfile.TemporaryDirectory(prefix='bim2sim_') as directory:
            path = os.path.join(directory, "mixed")
            decision.Decision.save(path)

            # clear variables to simulate program restart
            del dec_bool
            del dec_real
            decision.Decision.all.clear()
            decision.Decision.stored_decisions.clear()

            with Decision.debug_answer(True):
                decision.Decision.load(path)

        dec_real_loaded = decision.RealDecision(
            question="??",
            validate_func=self.check,
            global_key=key_real,
            allow_load=True)
        self.assertEqual(float(dec_real_loaded.value), 5)
        dec_bool_loaded = decision.BoolDecision(
            question="??",
            global_key=key_bool,
            allow_load=True)
        self.assertFalse(dec_bool_loaded.value)


class TestBoolDecision(DecisionTestBase):
    """test BoolDecisions"""

    def test_decision_value(self):
        """test interpreting input"""

        with Decision.debug_answer(True):
            ans = decision.BoolDecision(question="??").decide()
        self.assertTrue(ans)

        with Decision.debug_answer(False):
            ans = decision.BoolDecision(question="??").decide()
        self.assertFalse(ans)

    def test_validation(self):
        """test value validation"""

        dec = decision.BoolDecision(question="??")

        self.assertTrue(dec.validate(True))
        self.assertTrue(dec.validate(False))
        self.assertFalse(dec.validate(None))
        self.assertFalse(dec.validate(0))
        self.assertFalse(dec.validate(1))
        self.assertFalse(dec.validate('y'))

    def test_save_load(self):
        """test saving decisions an loading them"""
        key = "key1"
        with Decision.debug_answer(True):
            dec = decision.BoolDecision(question="??", global_key=key, allow_save=True)
            dec.decide()

        self.assertTrue(dec.value)

        with tempfile.TemporaryDirectory(prefix='bim2sim_') as directory:
            path = os.path.join(directory, "bool")

            decision.Decision.save(path)

            # clear variables to simulate program restart
            decision.Decision.all.clear()
            decision.Decision.stored_decisions.clear()

            with Decision.debug_answer(True):
                decision.Decision.load(path)

        dec_loaded = decision.BoolDecision(question="??", global_key=key, allow_load=True)
        self.assertTrue(dec_loaded.value)


@patch('builtins.print', lambda *args, **kwargs: None)
class TestRealDecision(DecisionTestBase):
    """test RealDecisions"""

    def check(self, value):
        """validation func"""
        return 0 < float(value.m_as('m')) < 10

    def test_validation(self):
        """test value validation"""
        unit = ureg.meter
        dec = decision.RealDecision(question="??", unit=unit)

        self.assertTrue(dec.validate(5. * unit))
        self.assertTrue(dec.validate(15. * unit))
        self.assertFalse(dec.validate(5.))
        self.assertFalse(dec.validate(5))
        self.assertFalse(dec.validate(False))

        dec_val = decision.RealDecision(question="??", unit=unit, validate_func=self.check)

        self.assertTrue(dec_val.validate(5. * unit))
        self.assertFalse(dec_val.validate(15. * unit))
        self.assertTrue(dec_val.validate(5 * unit))
        self.assertFalse(dec_val.validate(False))

    def test_save_load(self):
        """test saving decisions an loading them"""
        key1 = "key1"
        key2 = "key2"
        unit = ureg.meter
        with Decision.debug_answer(5.):
            dec1 = decision.RealDecision(
                question="??",
                global_key=key1,
                allow_save=True)
            dec1.decide()
            dec2 = decision.RealDecision(
                question="??",
                unit=unit,
                validate_func=self.check,
                global_key=key2,
                allow_save=True)
            dec2.decide()

        self.assertTrue(dec1.value)
        self.assertTrue(dec2.value)

        with tempfile.TemporaryDirectory(prefix='bim2sim_') as directory:
            path = os.path.join(directory, "real")

            decision.Decision.save(path)

            # clear variables to simulate program restart
            decision.Decision.all.clear()
            decision.Decision.stored_decisions.clear()

            with Decision.debug_answer(True):
                decision.Decision.load(path)

        dec1_loaded = decision.RealDecision(
            question="??",
            global_key=key1,
            allow_load=True)
        self.assertEqual(float(dec1_loaded.value), 5.)
        self.assertIsInstance(dec1_loaded.value, pint.Quantity)

        dec2_loaded = decision.RealDecision(
            question="??",
            unit=unit,
            validate_func=self.check,
            global_key=key2,
            allow_load=True)
        self.assertEqual(float(dec2_loaded.value.m_as('m')), 5)
        self.assertIsInstance(dec2_loaded.value.m, float)

# IntDecision not implemented


class TestListDecision(DecisionTestBase):

    def setUp(self) -> None:
        super().setUp()
        self.choices = [
            ('a', 'option1'),
            ('b', 'option2'),
            ('c', 'option3')
        ]

    def test_validation(self):
        """test value validation"""
        dec = decision.ListDecision("??", choices=self.choices)

        self.assertTrue(dec.validate('a'))
        self.assertTrue(dec.validate('c'))
        self.assertFalse(dec.validate('1'))
        self.assertFalse(dec.validate(1))
        self.assertFalse(dec.validate(3))

    def test_save_load(self):
        """test saving decisions an loading them"""
        key = "key1"
        with Decision.debug_answer('b'):
            dec = decision.ListDecision(
                question="??",
                choices=self.choices,
                global_key=key,
                allow_save=True)
            dec.decide()

        self.assertTrue(dec.value)

        with tempfile.TemporaryDirectory(prefix='bim2sim_') as directory:
            path = os.path.join(directory, "real")

            decision.Decision.save(path)

            # clear variables to simulate program restart
            decision.Decision.all.clear()
            decision.Decision.stored_decisions.clear()

            with Decision.debug_answer(True):
                decision.Decision.load(path)

        dec_loaded = decision.ListDecision(
            question="??",
            choices=self.choices,
            global_key=key,
            allow_load=True)
        self.assertEqual(dec_loaded.value, 'b')
        self.assertIsInstance(dec_loaded.value, str)


class TestStringDecision(DecisionTestBase):
    """test RealDecisions"""

    def check(self, value):
        """validation func"""
        return value == 'success'

    def test_validation(self):
        """test value validation"""
        dec = decision.StringDecision(question="??")

        self.assertTrue(dec.validate('1'))
        self.assertTrue(dec.validate('test'))
        self.assertFalse(dec.validate(1))
        self.assertFalse(dec.validate(None))
        self.assertFalse(dec.validate(''))

        dec_val = decision.StringDecision(question="??", validate_func=self.check)

        self.assertTrue(dec_val.validate('success'))
        self.assertFalse(dec_val.validate('other'))

    def test_save_load(self):
        """test saving decisions an loading them"""
        key1 = "key1"
        key2 = "key2"
        with Decision.debug_answer('success'):
            dec1 = decision.StringDecision(
                question="??",
                global_key=key1,
                allow_save=True)
            dec1.decide()
            dec2 = decision.StringDecision(
                question="??",
                validate_func=self.check,
                global_key=key2,
                allow_save=True)
            dec2.decide()

        self.assertEqual('success', dec1.value)
        self.assertEqual('success', dec2.value)

        with tempfile.TemporaryDirectory(prefix='bim2sim_') as directory:
            path = os.path.join(directory, "real")

            decision.Decision.save(path)

            # clear variables to simulate program restart
            decision.Decision.all.clear()
            decision.Decision.stored_decisions.clear()

            with Decision.debug_answer(True):
                decision.Decision.load(path)

        dec1_loaded = decision.StringDecision(
            question="??",
            global_key=key1,
            allow_load=True)
        self.assertEqual('success', dec1_loaded.value)

        dec2_loaded = decision.StringDecision(
            question="??",
            validate_func=self.check,
            global_key=key2,
            allow_load=True)
        self.assertEqual('success', dec2_loaded.value)


@patch('builtins.print', lambda *args, **kwargs: None)
class TestConsoleFrontend(DecisionTestBase):
    frontend = decision.console.ConsoleFrontEnd()

    def check(self, value):
        return True

    @patch('builtins.input', lambda *args, **kwargs: 'bla bla')
    def test_bad_input(self):
        """test behaviour on bad input"""
        dec = decision.BoolDecision(question="??")
        with self.assertRaises(decision.DecisionCancle):
            dec.decide()

    def test_skip_all(self):
        """test skipping collected decisions"""
        target_dict = {}
        for i in range(3):
            key = "n%d" % i
            decision.BoolDecision(
                question="??",
                output=target_dict,
                output_key=key,
                collect=True,
                allow_skip=True)

        with patch('builtins.input', lambda *args, **kwargs: 'skip all'):
            decision.Decision.decide_collected()

        self.assertEqual(len(target_dict), 3)
        self.assertEqual(set(target_dict.values()), {None})

    def test_real_parsing(self):
        """test input interpretaton"""
        expected_valids = {
            '1': 1,
            '1.': 1,
            '1.0': 1,
            '1.1': 1.1,
            '1e0': 1,
            '1e-1': 0.1,
        }
        unit = ureg.meter

        for inp, res in expected_valids.items():
            with patch('builtins.input', lambda *args: inp):
                dec = decision.RealDecision(question="??", unit=unit, validate_func=self.check)
                dec.decide()
                self.assertEqual(dec.value, res * unit)

    def test_bool_parse(self):
        """test bool value parsing"""

        dec = decision.BoolDecision(question="??")
        self.assertIsNone(dec.value)

        parsed_int1 = Decision.frontend.parse(dec, '1')
        self.assertTrue(parsed_int1)
        self.assertIsInstance(parsed_int1, bool)
        parsed_int0 = Decision.frontend.parse(dec, '0')
        self.assertFalse(parsed_int0)
        self.assertIsInstance(parsed_int0, bool)
        parsed_real = Decision.frontend.parse(dec, '1.1')
        self.assertIsNone(parsed_real)
        parsed_str = Decision.frontend.parse(dec, 'y')
        self.assertTrue(parsed_str)
        self.assertIsInstance(parsed_str, bool)
        parsed_invalid = Decision.frontend.parse(dec, 'foo')
        self.assertIsNone(parsed_invalid)

    def test_real_parse(self):
        """test value parsing"""

        dec = decision.RealDecision(question="??")
        self.assertIsNone(dec.value)

        parsed_int = Decision.frontend.parse(dec, 5)
        self.assertEqual(parsed_int, 5.)
        self.assertIsInstance(parsed_int, pint.Quantity)
        parsed_real = Decision.frontend.parse(dec, 5.)
        self.assertEqual(parsed_real, 5.)
        self.assertIsInstance(parsed_real, pint.Quantity)
        parsed_str = Decision.frontend.parse(dec, '5')
        self.assertEqual(parsed_str, 5.)
        self.assertIsInstance(parsed_str, pint.Quantity)
        parsed_invalid = Decision.frontend.parse(dec, 'five')
        self.assertIsNone(parsed_invalid)

    def test_list_parse(self):
        """test value parsing"""

        choices = [
            ('a', 'option1'),
            ('b', 'option2'),
            ('c', 'option3')
        ]
        dec = decision.ListDecision("??", choices=choices)
        self.assertIsNone(dec.value)

        parsed_int = Decision.frontend.parse(dec, 0)
        self.assertEqual(parsed_int, 'a')

        parsed_real = Decision.frontend.parse(dec, 2)
        self.assertEqual(parsed_real, 'c')

        parsed_str = Decision.frontend.parse(dec, 3)
        self.assertIsNone(parsed_str)

        parsed_str = Decision.frontend.parse(dec, 'a')
        self.assertIsNone(parsed_str)

    def test_string_parse(self):
        """test string input"""
        answers = ('success', 'other')
        for inp in answers:
            with patch('builtins.input', lambda *args: inp):
                dec = decision.StringDecision(question="??")
                dec.decide()
                self.assertEqual(inp, dec.value)

        with patch('builtins.input', lambda *args: ''):
            with self.assertRaises(decision.DecisionCancle):
                dec = decision.StringDecision(question="??")
                dec.decide()


if __name__ == '__main__':
    unittest.main()
