"""Run all tests"""

if __name__ == '__main__':
    import unittest

    loader = unittest.TestLoader()
    tests = loader.discover('./test')
    testRunner = unittest.runner.TextTestRunner()
    result = testRunner.run(tests)
    if result.wasSuccessful():
        exit(0)
    else:
        exit(1)



