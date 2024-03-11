import argparse

from bim2sim.utilities.common_functions import download_test_resources


def main():
    parser = argparse.ArgumentParser(
        description="Download script for test resources")
    parser.add_argument(
        "--domain",
        type=str,
        help="Domain for which to download test resources")
    parser.add_argument(
        "--force_new",
        default=False,
        action="store_true",
        help="Download test resources even if a folder already exists")
    parser.add_argument(
        "--with_regression",
        default=False,
        action="store_true",
        help="Download regression results as well")
    args = parser.parse_args()

    if args.domain not in ('hydraulic', 'arch'):
        raise ValueError(f"For the provided domain {args.domain} no additional "
                         f"test resources exist for now.")
    download_test_resources(domain=args.domain,
                            with_regression=args.with_regression,
                            force_new=args.force_new)


if __name__ == "__main__":
    main()
