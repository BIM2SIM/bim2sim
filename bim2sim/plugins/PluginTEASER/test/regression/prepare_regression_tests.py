from pathlib import Path

from bim2sim.utilities.common_functions import download_test_resources, \
    download_library


def prepare_regression_tests():
    download_test_resources('arch', True, force_new=True)
    repo_url = "https://github.com/RWTH-EBC/AixLib.git"
    branch_name = "main"
    repo_name = "AixLib"
    clone_dir = Path(__file__).parent / "library" / f"library_{repo_name}"
    download_library(repo_url, branch_name, clone_dir)


if __name__ == '__main__':
    prepare_regression_tests()
