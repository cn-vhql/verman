"""
VerMan entrypoint.
"""

import argparse
from typing import List, Optional

from gui import VersionManagerGUI


def parse_startup_path(argv: Optional[List[str]] = None) -> Optional[str]:
    parser = argparse.ArgumentParser(description="VerMan local version manager")
    parser.add_argument("path", nargs="?", help="Workspace directory or file path to open")
    args = parser.parse_args(argv)
    return args.path


def main(argv: Optional[List[str]] = None):
    startup_path = parse_startup_path(argv)
    app = VersionManagerGUI(startup_path=startup_path)
    app.run()


if __name__ == "__main__":
    main()
