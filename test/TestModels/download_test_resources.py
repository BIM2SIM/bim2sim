from bim2sim.utilities.common_functions import download_test_models

if __name__ == "__main__":
    download_test_models(domain='hydraulic', with_regression=False)
    download_test_models(domain='arch', with_regression=True)
