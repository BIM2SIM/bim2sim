from pathlib import Path

from bim2sim.utilities.common_functions import download_test_resources, \
    download_library


def prepare_regression_tests():
    download_test_resources('arch', True, force_new=True)


if __name__ == '__main__':
    prepare_regression_tests()
