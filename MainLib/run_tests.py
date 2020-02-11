# """Run all tests"""
#
# if __name__ == '__main__':
#     import unittest
#
#     loader = unittest.TestLoader()
#     tests = loader.discover('./test')
#     testRunner = unittest.runner.TextTestRunner()
#     testRunner.run(tests)


def _get_orientation(bind, name):
    return 32

functions = [_get_orientation]


bind = 23
name = 'asd'

for i, func in enumerate(functions):
    value = func(bind, name)