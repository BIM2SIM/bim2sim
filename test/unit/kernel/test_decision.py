"""Test for decision.py"""
import json
import os
import tempfile
import unittest
from unittest.mock import patch

import pint

from bim2sim.kernel import decision
from bim2sim.kernel.decision import BoolDecision, save, load, RealDecision, \
    DecisionBunch, ListDecision, GuidDecision
from bim2sim.kernel.decision.console import ConsoleDecisionHandler
from bim2sim.elements.mapping.units import ureg


class DecisionTestBase(unittest.TestCase):
    """Base class for Decision tests"""


class TestDecision(DecisionTestBase):
    """General Decision related tests"""

    def test_decision_value(self):
        """test decision value consistency"""

        dec = decision.RealDecision(question="??")

        with self.assertRaises(ValueError):
            value = dec.value
        self.assertFalse(dec.valid())

        dec.value = 5.
        self.assertTrue(dec.valid())
        self.assertEqual(dec.value, 5)
        self.assertIsInstance(dec.value, pint.Quantity)

    def test_invalid_value(self):
        """test float value for IntDecision"""
        dec = RealDecision(question="??")
        self.assertFalse(dec.valid())

        with self.assertRaises(ValueError):
            dec.value = 'five'

    def test_skip(self):
        """test skipping decisions"""
        dec1 = BoolDecision(
            question="??",
            key="key1",
            allow_skip=True)
        self.assertFalse(dec1.valid())
        dec1.skip()
        self.assertTrue(dec1.valid())
        self.assertIsNone(dec1.value)

        dec2 = BoolDecision(
            question="??",
            key="key2",
            allow_skip=False)

        with self.assertRaises(decision.DecisionException):
            dec2.skip()

    def test_freeze_decision(self):
        """Test freezing a decision and change value."""
        dec = BoolDecision('??')
        with self.assertRaises(AssertionError):
            dec.freeze()
        dec.value = True
        dec.freeze()
        with self.assertRaises(AssertionError):
            dec.value = False

    def check(self, value):
        """validation func"""
        return 0 < float(value) < 10

    def test_save_load(self):
        """test saving decisions an loading them"""
        key_bool = "key_bool"
        key_real = "key_real"

        dec_bool = BoolDecision(
            question="??",
            global_key=key_bool)
        dec_bool.value = False
        self.assertFalse(dec_bool.value)

        dec_real = RealDecision(
            question="??",
            validate_func=self.check,
            global_key=key_real)
        dec_real.value = 5.
        self.assertEqual(dec_real.value, 5)

        decisions = DecisionBunch((dec_bool, dec_real))
        with tempfile.TemporaryDirectory(prefix='bim2sim_') as directory:
            path = os.path.join(directory, "mixed")
            save(decisions, path)

            # clear variables to simulate program restart
            dec_real.reset()
            dec_bool.reset()
            del decisions

            loaded_decisions = load(path)

        dec_real.reset_from_deserialized(loaded_decisions[key_real])
        dec_bool.reset_from_deserialized(loaded_decisions[key_bool])
        self.assertEqual(dec_real.value, 5)
        self.assertFalse(dec_bool.value)

    def test_decision_reduce_by_key(self):
        """tests the get_reduced_bunch function with same keys."""
        dec_1 = BoolDecision(key='key1', question="??")
        dec_2 = BoolDecision(key='key1', question="??")
        dec_3 = BoolDecision(key='key2', question="??")
        dec_bunch_orig = DecisionBunch([dec_1, dec_2, dec_3])
        dec_bunch_exp = DecisionBunch([dec_1, dec_3])
        doubled_bunch_exp = DecisionBunch([dec_2])
        red_bunch, doubled_dec = dec_bunch_orig.get_reduced_bunch(criteria='key')
        self.assertListEqual(dec_bunch_exp, red_bunch)
        self.assertListEqual(doubled_dec, doubled_bunch_exp)

    def test_decision_reduce_by_question(self):
        """tests the get_reduced_bunch function with same questions."""
        dec_1 = BoolDecision(key='key1', question="question A ?")
        dec_2 = BoolDecision(key='key2', question="question A ?")
        dec_3 = BoolDecision(key='key3', question="question B ?")
        dec_bunch_orig = DecisionBunch([dec_1, dec_2, dec_3])
        dec_bunch_exp = DecisionBunch([dec_1, dec_3])
        doubled_bunch_exp = DecisionBunch([dec_2])
        red_bunch, doubled_dec = dec_bunch_orig.get_reduced_bunch(
            criteria='question')
        self.assertListEqual(dec_bunch_exp, red_bunch)
        self.assertListEqual(doubled_dec, doubled_bunch_exp)


class TestBoolDecision(DecisionTestBase):
    """test BoolDecisions"""

    def test_decision_value(self):
        """test interpreting input"""

        dec = BoolDecision(question="??")
        dec.value = True
        self.assertTrue(dec.value)

        dec2 = BoolDecision(question="??")
        dec2.value = False
        self.assertFalse(dec2.value)

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
        dec = decision.BoolDecision(question="??", global_key=key)
        dec.value = True
        self.assertTrue(dec.value)

        # check serialize
        serialized = json.dumps(dec.get_serializable())
        deserialized = json.loads(serialized)

        # check reset
        dec.reset()
        self.assertFalse(dec.valid())
        dec.reset_from_deserialized(deserialized)

        self.assertTrue(dec.value)


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
        self.assertTrue(dec.validate(5.))
        self.assertTrue(dec.validate(5))
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
        dec1 = RealDecision(
            question="??",
            global_key=key1)
        dec1.value = 5.
        dec2 = RealDecision(
            question="??",
            unit=unit,
            validate_func=self.check,
            global_key=key2)
        dec2.value = 5.

        self.assertTrue(dec1.value)
        self.assertTrue(dec2.value)

        # check serialize
        serialized1 = json.dumps(dec1.get_serializable())
        serialized2 = json.dumps(dec2.get_serializable())
        deserialized1 = json.loads(serialized1)
        deserialized2 = json.loads(serialized2)

        # check reset
        dec1.reset()
        dec2.reset()
        self.assertFalse(dec1.valid())
        self.assertFalse(dec2.valid())
        dec1.reset_from_deserialized(deserialized1)
        dec2.reset_from_deserialized(deserialized2)

        self.assertTrue(dec1.value)
        self.assertTrue(dec2.value)

        self.assertEqual(dec1.value, 5.)
        self.assertIsInstance(dec1.value, pint.Quantity)

        self.assertEqual(dec2.value.m_as('m'), 5)
        self.assertIsInstance(dec2.value.m, float)


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
        dec = decision.ListDecision(
            question="??",
            choices=self.choices,
            global_key=key)
        dec.value = 'b'
        self.assertTrue(dec.value)

        # check serialize
        serialized = json.dumps(dec.get_serializable())
        deserialized = json.loads(serialized)

        # check reset
        dec.reset()
        self.assertFalse(dec.valid())
        dec.reset_from_deserialized(deserialized)

        self.assertEqual('b', dec.value)
        self.assertIsInstance(dec.value, str)


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
        dec1 = decision.StringDecision(
            question="??",
            global_key=key1)
        dec1.value = 'success'
        dec2 = decision.StringDecision(
            question="??",
            validate_func=self.check,
            global_key=key2)
        dec2.value = 'success'

        self.assertEqual('success', dec1.value)
        self.assertEqual('success', dec2.value)

        # check serialize
        serialized1 = json.dumps(dec1.get_serializable())
        serialized2 = json.dumps(dec2.get_serializable())
        deserialized1 = json.loads(serialized1)
        deserialized2 = json.loads(serialized2)

        # check reset
        dec1.reset()
        dec2.reset()
        self.assertFalse(dec1.valid())
        self.assertFalse(dec2.valid())
        dec1.reset_from_deserialized(deserialized1)
        dec2.reset_from_deserialized(deserialized2)

        self.assertEqual('success', dec1.value)
        self.assertEqual('success', dec2.value)


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

        dec1 = decision.GuidDecision(
            question="??",
            global_key=key1)
        dec1.value = guid1
        dec2 = decision.GuidDecision(
            question="??",
            multi=True,
            validate_func=self.check,
            global_key=key2)
        dec2.value = guid2

        self.assertSetEqual(guid1, dec1.value)
        self.assertSetEqual(guid2, dec2.value)

        # check serialize
        serialized1 = json.dumps(dec1.get_serializable())
        serialized2 = json.dumps(dec2.get_serializable())
        deserialized1 = json.loads(serialized1)
        deserialized2 = json.loads(serialized2)

        # check reset
        dec1.reset()
        dec2.reset()
        self.assertFalse(dec1.valid())
        self.assertFalse(dec2.valid())
        dec1.reset_from_deserialized(deserialized1)
        dec2.reset_from_deserialized(deserialized2)

        self.assertSetEqual(guid1, dec1.value)
        self.assertSetEqual(guid2, dec2.value)


@patch('builtins.print', lambda *args, **kwargs: None)
class TestConsoleHandler(DecisionTestBase):
    handler = ConsoleDecisionHandler()

    def check(self, value):
        return True

    def test_default_value(self):
        """test if default value is used on empty input"""
        real_dec = RealDecision("??", unit=ureg.meter, default=10)
        bool_dec = BoolDecision("??", default=False)
        list_dec = ListDecision("??", choices="ABC", default="C")
        decisions = DecisionBunch((real_dec, bool_dec, list_dec))

        with patch('builtins.input', lambda *args, **kwargs: ''):
            answers = self.handler.get_answers_for_bunch(decisions)

        expected = [10 * ureg.m, False, 'C']
        self.assertListEqual(expected, answers)

    @patch('builtins.input', lambda *args, **kwargs: 'bla bla')
    def test_bad_input(self):
        """test behaviour on bad input"""
        dec = BoolDecision(question="??")
        bunch = DecisionBunch([dec])
        with self.assertRaises(decision.DecisionCancel):
            self.handler.get_answers_for_bunch(bunch)

    def test_skip_all(self):
        """test skipping collected decisions"""
        decisions = DecisionBunch()
        for i in range(3):
            key = "n%d" % i
            decisions.append(BoolDecision(
                question="??",
                key=key,
                allow_skip=True))

        with patch('builtins.input', lambda *args, **kwargs: 'skip all'):
            answers = self.handler.get_answers_for_bunch(decisions)

        self.assertEqual(len(answers), 3)
        self.assertFalse(any(answers))

    def test_real_parsing(self):
        """test input interpretation"""
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
                dec = RealDecision(question="??", unit=unit, validate_func=self.check)
                answer = self.handler.user_input(dec)
                self.assertEqual(res * unit, answer)

    def test_bool_parse(self):
        """test bool value parsing"""

        dec = decision.BoolDecision(question="??")
        self.assertFalse(dec.valid())

        parsed_int1 = self.handler.parse(dec, '1')
        self.assertTrue(parsed_int1)
        self.assertIsInstance(parsed_int1, bool)
        parsed_int0 = self.handler.parse(dec, '0')
        self.assertFalse(parsed_int0)
        self.assertIsInstance(parsed_int0, bool)
        parsed_real = self.handler.parse(dec, '1.1')
        self.assertIsNone(parsed_real)
        parsed_str = self.handler.parse(dec, 'y')
        self.assertTrue(parsed_str)
        self.assertIsInstance(parsed_str, bool)
        parsed_invalid = self.handler.parse(dec, 'foo')
        self.assertIsNone(parsed_invalid)

    def test_real_parse(self):
        """test value parsing"""

        dec = RealDecision(question="??")
        self.assertFalse(dec.valid())

        parsed_int = self.handler.parse(dec, 5)
        self.assertEqual(parsed_int, 5.)
        self.assertIsInstance(parsed_int, pint.Quantity)
        parsed_real = self.handler.parse(dec, 5.)
        self.assertEqual(parsed_real, 5.)
        self.assertIsInstance(parsed_real, pint.Quantity)
        parsed_str = self.handler.parse(dec, '5')
        self.assertEqual(parsed_str, 5.)
        self.assertIsInstance(parsed_str, pint.Quantity)
        parsed_invalid = self.handler.parse(dec, 'five')
        self.assertIsNone(parsed_invalid)

    def test_list_parse(self):
        """test value parsing"""

        choices = [
            ('a', 'option1'),
            ('b', 'option2'),
            ('c', 'option3')
        ]
        dec = ListDecision("??", choices=choices)
        self.assertFalse(dec.valid())

        parsed_int = self.handler.parse(dec, 0)
        self.assertEqual(parsed_int, 'a')

        parsed_real = self.handler.parse(dec, 2)
        self.assertEqual(parsed_real, 'c')

        parsed_str = self.handler.parse(dec, 3)
        self.assertIsNone(parsed_str)

        parsed_str = self.handler.parse(dec, 'a')
        self.assertIsNone(parsed_str)

    def test_string_parse(self):
        """test string input"""
        answers = ('success', 'other')
        for inp in answers:
            with patch('builtins.input', lambda *args: inp):
                dec = decision.StringDecision(question="??")
                answer = self.handler.user_input(dec)
                self.assertEqual(inp, answer)

        with patch('builtins.input', lambda *args: ''):
            with self.assertRaises(decision.DecisionCancel):
                dec = decision.StringDecision(question="??")
                self.handler.user_input(dec)

    def test_guid_parse(self):

        def check(value):
            valids = (
                '2tHa09veL10P9$ol9urWrT',
                '0otlA1TWvCPvzfXTM_RO1R',
                '2GCvzU9J93CxAS3rHyr1a6'
            )
            return all(guid in valids for guid in value)

        def valid_parsed(guid_decision, inp):
            return guid_decision.validate(self.handler.parse_guid_input(inp))

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
        dec1 = GuidDecision(question="??")
        with patch('builtins.input', lambda *args: '2tHa09veL10P9$ol9urWrT'):
            answer = self.handler.user_input(dec1)
            self.assertSetEqual({'2tHa09veL10P9$ol9urWrT'}, answer)

        dec2 = GuidDecision(question="??", validate_func=check, multi=True)
        with patch('builtins.input', lambda *args: '2tHa09veL10P9$ol9urWrT, 0otlA1TWvCPvzfXTM_RO1R'):
            answer2 = self.handler.user_input(dec2)
            self.assertSetEqual({'2tHa09veL10P9$ol9urWrT', '0otlA1TWvCPvzfXTM_RO1R'}, answer2)


if __name__ == '__main__':
    unittest.main()
