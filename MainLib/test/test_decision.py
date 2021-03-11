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

    def test_debug_answers(self):
        """Test implementation of debug answers"""
        with Decision.debug_answer(True):
            dec = decision.BoolDecision(
                question="??")
            dec.decide()
        self.assertTrue(dec.value)

        answers = (True, 3.2, False)

        with Decision.debug_answer(answers, multi=True):
            dec0 = decision.BoolDecision(question="??")
            dec0.decide()
            dec1 = decision.RealDecision(question="??")
            dec1.decide()
            dec2 = decision.BoolDecision(question="??")
            dec2.decide()
        self.assertTupleEqual(answers, (dec0.value, dec1.value, dec2.value))

        output = {}
        with Decision.debug_answer(answers, multi=True):
            dec0 = decision.BoolDecision(question="??", collect=True, output=output, output_key=0)
            dec1 = decision.RealDecision(question="??", collect=True, output=output, output_key=1)
            dec2 = decision.BoolDecision(question="??", collect=True, output=output, output_key=2)
            decision.Decision.decide_collected()
        self.assertTupleEqual(answers, tuple(output[i] for i in range(3)))

    def test_default_value(self):
        """test if default value is used correctly with debug_answer"""
        real_dec = decision.RealDecision("??", unit=ureg.m, default=10)
        bool_dec = decision.BoolDecision("??", default=False)
        list_dec = decision.ListDecision("??", choices="ABC", default="C")

        # use default answer where possible ('x' should be overwritten by defaults)
        with Decision.debug_answer('x', validate=True, overwrite_default=False):
            self.assertEqual(10 * ureg.m, real_dec.decide())
            self.assertFalse(bool_dec.decide())
            self.assertEqual("C", list_dec.decide())

        real_dec2 = decision.RealDecision("??", unit=ureg.m, default=10)
        bool_dec2 = decision.BoolDecision("??", default=False)
        list_dec2 = decision.ListDecision("??", choices="ABC", default="C")

        # default answers are overwritten by debug answers
        answers = (5, True, "A")
        with Decision.debug_answer(answers, validate=True, multi=True):
            self.assertEqual(answers[0] * ureg.m, real_dec2.decide())
            self.assertEqual(answers[1], bool_dec2.decide())
            self.assertEqual(answers[2], list_dec2.decide())


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


class TestGuidDecision(DecisionTestBase):

    def check(self, value):
        """validation func"""
        valids = (
            '2tHa09veL10P9$ol9urWrT',
            '0otlA1TWvCPvzfXTM_RO1R',
            '2GCvzU9J93CxAS3rHyr1a6'
        )
        return all(guid in valids for guid in value)

    def test_validation(self):
        """test value validation"""
        dec = decision.GuidDecision(question="??", multi=False)

        self.assertTrue(dec.validate({'2tHa09veL10P9$ol9urWrT'}))
        self.assertFalse(dec.validate({'2tHa09veL10P9$ol9urWrT, 0otlA1TWvCPvzfXTM_RO1R'}), 'multi not allowed')
        self.assertFalse(dec.validate({'2tHa09veL10P9$ol'}))
        self.assertFalse(dec.validate(''))
        self.assertFalse(dec.validate(1))
        self.assertFalse(dec.validate(None))

        dec_multi = decision.GuidDecision(question="??", validate_func=self.check, multi=True)

        self.assertTrue(dec_multi.validate({'2tHa09veL10P9$ol9urWrT'}))
        self.assertTrue(dec_multi.validate({'2tHa09veL10P9$ol9urWrT', '0otlA1TWvCPvzfXTM_RO1R'}))
        self.assertFalse(dec_multi.validate({'2tHa09veL10P9$ol9urWrT', 'GUID_not_in_valid_list'}))

    def test_save_load(self):
        """test saving decisions an loading them"""
        key1 = "key1"
        key2 = "key2"
        guid1 = {'2tHa09veL10P9$ol9urWrT'}
        guid2 = {'2tHa09veL10P9$ol9urWrT', '2GCvzU9J93CxAS3rHyr1a6'}

        with Decision.debug_answer((guid1, guid2), multi=True):
            dec1 = decision.GuidDecision(
                question="??",
                global_key=key1,
                allow_save=True)
            dec1.decide()
            dec2 = decision.GuidDecision(
                question="??",
                multi=True,
                validate_func=self.check,
                global_key=key2,
                allow_save=True)
            dec2.decide()

        self.assertSetEqual(guid1, dec1.value)
        self.assertSetEqual(guid2, dec2.value)

        with tempfile.TemporaryDirectory(prefix='bim2sim_') as directory:
            path = os.path.join(directory, "real")

            decision.Decision.save(path)

            # clear variables to simulate program restart
            decision.Decision.all.clear()
            decision.Decision.stored_decisions.clear()

            with Decision.debug_answer(True):
                decision.Decision.load(path)

        dec1_loaded = decision.GuidDecision(
            question="??",
            global_key=key1,
            allow_load=True)
        self.assertEqual(guid1, dec1_loaded.value)

        dec2_loaded = decision.GuidDecision(
            question="??",
            multi=True,
            validate_func=self.check,
            global_key=key2,
            allow_load=True)
        self.assertEqual(guid2, dec2_loaded.value)


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

    def test_guid_parse(self):

        def check(value):
            valids = (
                '2tHa09veL10P9$ol9urWrT',
                '0otlA1TWvCPvzfXTM_RO1R',
                '2GCvzU9J93CxAS3rHyr1a6'
            )
            return all(guid in valids for guid in value)

        def valid_parsed(guid_decision, inp):
            return guid_decision.validate(self.frontend.parse_guid_input(inp))

        # test parse + validate
        dec = decision.GuidDecision(question="??", multi=False)
        self.assertTrue(valid_parsed(dec, '2tHa09veL10P9$ol9urWrT'))
        self.assertFalse(valid_parsed(dec, '2tHa09veL10P9$ol9urWrT, 0otlA1TWvCPvzfXTM_RO1R'))  # multi not allowed
        self.assertFalse(valid_parsed(dec, '2tHa09veL10P9$ol'))
        self.assertFalse(valid_parsed(dec, ''))
        self.assertFalse(valid_parsed(dec, 1))
        self.assertFalse(valid_parsed(dec, None))

        # test parse + validate in multi guid decision
        dec_multi = decision.GuidDecision(question="??", validate_func=check, multi=True)
        self.assertTrue(valid_parsed(dec_multi, '2tHa09veL10P9$ol9urWrT'))
        self.assertTrue(valid_parsed(dec_multi, '2tHa09veL10P9$ol9urWrT, 0otlA1TWvCPvzfXTM_RO1R'))
        self.assertTrue(valid_parsed(dec_multi, '2tHa09veL10P9$ol9urWrT 0otlA1TWvCPvzfXTM_RO1R'))
        self.assertTrue(valid_parsed(dec_multi, '2tHa09veL10P9$ol9urWrT,0otlA1TWvCPvzfXTM_RO1R'))
        self.assertFalse(valid_parsed(dec_multi, '2tHa09veL10P9$ol9urWrT, GUID_not_in_valid_list'))
        self.assertFalse(valid_parsed(dec_multi, '2tHa09veL10P9$ol9urWrT; 0otlA1TWvCPvzfXTM_RO1R'))

        # full test
        with patch('builtins.input', lambda *args: '2tHa09veL10P9$ol9urWrT'):
            value = decision.GuidDecision(question="??").decide()
            self.assertSetEqual({'2tHa09veL10P9$ol9urWrT'}, value)
        with patch('builtins.input', lambda *args: '2tHa09veL10P9$ol9urWrT, 0otlA1TWvCPvzfXTM_RO1R'):
            value = decision.GuidDecision(question="??", validate_func=check, multi=True).decide()
            self.assertSetEqual({'2tHa09veL10P9$ol9urWrT', '0otlA1TWvCPvzfXTM_RO1R'}, value)

    def test_default_value(self):
        """test if default value is used on empty input"""
        real_dec = decision.RealDecision("??", unit=ureg.meter, default=10)
        bool_dec = decision.BoolDecision("??", default=False)
        list_dec = decision.ListDecision("??", choices="ABC", default="C")

        with patch('builtins.input', lambda *args, **kwargs: ''):
            self.assertEqual(10 * ureg.meter, real_dec.decide())
            self.assertFalse(bool_dec.decide())
            self.assertEqual("C", list_dec.decide())


if __name__ == '__main__':
    unittest.main()
