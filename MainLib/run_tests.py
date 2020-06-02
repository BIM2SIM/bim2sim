"""Run all tests"""

if __name__ == '__main__':
    import unittest

    loader = unittest.TestLoader()
    tests = loader.discover('.')
    testRunner = unittest.runner.TextTestRunner()
    testRunner.run(tests)
