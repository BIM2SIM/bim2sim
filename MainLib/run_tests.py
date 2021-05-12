"""Run all tests"""
from pathlib import Path


unit_dir = Path(__file__).parent.parent

if __name__ == '__main__':
    import unittest

    loader = unittest.TestLoader()
    tests = loader.discover(unit_dir)
    testRunner = unittest.runner.TextTestRunner()
    result = testRunner.run(tests)
    if result.wasSuccessful():
        exit(0)
    else:
        exit(1)
