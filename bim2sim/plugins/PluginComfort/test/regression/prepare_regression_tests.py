from bim2sim.utilities.common_functions import download_test_resources


def prepare_regression_tests():
    download_test_resources('arch', True, force_new=True)


if __name__ == '__main__':
    prepare_regression_tests()
