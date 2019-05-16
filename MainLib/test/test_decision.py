"""Test for decision.py"""

import unittest
from unittest.mock import patch
import tempfile
import shutil
import os

from bim2sim import decision


class DecisionTestBase(unittest.TestCase):
    """Base class for Decision tests"""

    def tearDown(self):
        decision.Decision.collection.clear()
        decision.Decision.stored_decisions.clear()

@patch('builtins.print', lambda *args: None)
class TestBoolDecision(DecisionTestBase):
    """test BoolDecisions"""

    def test_bool_decision_value(self):
        """test interpreting input"""
        with patch('builtins.input', lambda *args: 'y'):
            ans = decision.BoolDecision(question="??").decide()
        self.assertTrue(ans)

        with patch('builtins.input', lambda *args: 'n'):
            ans = decision.BoolDecision(question="??").decide()
        self.assertFalse(ans)

    @patch('builtins.input', lambda *args: 'bla bla')
    def test_bad_input(self):
        """test behaviour on bad input"""
        dec = decision.BoolDecision(question="??")
        with self.assertRaises(decision.DecisionCancle):
            dec.decide()

    def test_collectable(self):
        """test collecting multiple BoolDecisions and decide_colledted"""
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

        self.assertEqual(len(decision.Decision.collection), len(dec_list))
        with patch('builtins.input', lambda *args: 'y'):
            decision.Decision.decide_collected()

        for value in target_dict.values():
            self.assertTrue(value)

        with self.assertRaises(AttributeError):
            decision.BoolDecision(question="??", collect=True)

    def test_save_load(self):
        """test saving decisions an loading them"""
        key = "key1"
        with patch('builtins.input', lambda *args: 'y'):
            dec = decision.BoolDecision(question="??", global_key=key, allow_save=True)
            dec.decide()

        self.assertTrue(dec.value)

        with tempfile.TemporaryDirectory(prefix='bim2sim_') as directory:
            path = os.path.join(directory, "bool")

            decision.Decision.save(path)

            # clear variables to simulate program restart
            decision.Decision.collection.clear()
            decision.Decision.stored_decisions.clear()

            with patch('builtins.input', lambda *args: 'y'):
                decision.Decision.load(path)

        dec_loaded = decision.BoolDecision(question="??", global_key=key, allow_load=True)
        self.assertTrue(dec_loaded.value)

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

    def test_skip_all(self):
        """test skipping collected decisions"""
        target_dict = {}
        for i in range(3):
            key = "n%d"%i
            decision.BoolDecision(
                question="??",
                output=target_dict,
                output_key=key,
                collect=True,
                allow_skip=True)

        with patch('builtins.input', lambda *args: 'skip all'):
            decision.Decision.decide_collected()

        self.assertEqual(len(target_dict), 3)
        self.assertEqual(set(target_dict.values()), {None})

@patch('builtins.print', lambda *args: None)
class TestRealDecision(DecisionTestBase):
    """test RealDecisions"""

    def check(self, value):
        """validation func"""
        return 0 < value < 10

    def test_real_decision(self):
        """test input interpretaton"""
        expected_valids = {
            '1': 1,
            '1.': 1,
            '1.0': 1,
            '1.1': 1.1,
            '1e0': 1,
            '1e-1': 0.1,
        }

        for inp, res in expected_valids.items():
            with patch('builtins.input', lambda *args: inp):
                dec = decision.RealDecision(question="??", validate_func=self.check)
                dec.decide()
                self.assertEqual(dec.value, res)

    def test_collectable(self):
        """test collecting multiple RealDecisions and decide_colledted"""
        target_dict = {}
        dec_list = []
        dec1 = decision.RealDecision(
            question="??",
            validate_func=self.check,
            output=target_dict,
            output_key="key1",
            collect=True)
        dec_list.append(dec1)
        dec_list.append(decision.RealDecision(
            question="??",
            validate_func=self.check,
            output=target_dict,
            output_key="key2",
            collect=True))

        self.assertIsNone(dec1.value)

        self.assertEqual(len(decision.Decision.collection), len(dec_list))
        with patch('builtins.input', lambda *args: '5'):
            decision.Decision.decide_collected()

        for value in target_dict.values():
            self.assertEqual(value, 5)

    def test_save_load(self):
        """test saving decisions an loading them"""
        key = "key1"
        with patch('builtins.input', lambda *args: '5'):
            dec = decision.RealDecision(
                question="??",
                validate_func=self.check,
                global_key=key,
                allow_save=True)
            dec.decide()

        self.assertTrue(dec.value)

        with tempfile.TemporaryDirectory(prefix='bim2sim_') as directory:
            path = os.path.join(directory, "real")

            decision.Decision.save(path)

            # clear variables to simulate program restart
            decision.Decision.collection.clear()
            decision.Decision.stored_decisions.clear()

            with patch('builtins.input', lambda *args: 'y'):
                decision.Decision.load(path)

        dec_loaded = decision.RealDecision(
            question="??",
            validate_func=self.check,
            global_key=key,
            allow_load=True)
        self.assertEqual(dec_loaded.value, 5)


@patch('builtins.print', lambda *args: None)
class TestMixedDecision(DecisionTestBase):
    """Test mixed Decisions"""

    def check(self, value):
        """validation func"""
        return 0 < value < 10

    def test_save_load(self):
        """test saving decisions an loading them"""
        key_bool = "key_bool"
        key_real = "key_real"

        with patch('builtins.input', lambda *args: 'n'):
            dec_bool = decision.BoolDecision(
                question="??",
                global_key=key_bool,
                allow_save=True)
            dec_bool.decide()
        self.assertFalse(dec_bool.value)

        with patch('builtins.input', lambda *args: '5'):
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
            decision.Decision.collection.clear()
            decision.Decision.stored_decisions.clear()

            with patch('builtins.input', lambda *args: 'y'):
                decision.Decision.load(path)

        dec_real_loaded = decision.RealDecision(
            question="??",
            validate_func=self.check,
            global_key=key_real,
            allow_load=True)
        self.assertEqual(dec_real_loaded.value, 5)
        dec_bool_loaded = decision.BoolDecision(
            question="??",
            global_key=key_bool,
            allow_load=True)
        self.assertFalse(dec_bool_loaded.value)

if __name__ == '__main__':
    unittest.main()
