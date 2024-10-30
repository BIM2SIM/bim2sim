from pathlib import Path

from bim2sim.utilities.common_functions import download_library


def prepare_regression_tests():
    repo_url = "https://github.com/RWTH-EBC/AixLib.git"
    branch_name = "main"
    repo_name = "AixLib"
    clone_dir = Path(__file__).parent / "library" / f"library_{repo_name}"
    print(f"Cloning AixLib library to {clone_dir}")
    download_library(repo_url, branch_name, clone_dir)


if __name__ == '__main__':
    prepare_regression_tests()
