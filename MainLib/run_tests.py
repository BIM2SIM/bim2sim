"""Run all tests"""
from os import path
this_dir = path.abspath(path.dirname(__file__))

if __name__ == '__main__':
    import unittest

    loader = unittest.TestLoader()
    tests = loader.discover(path.join(this_dir))
    testRunner = unittest.runner.TextTestRunner()
    testRunner.run(tests)
