"""Entrypoint for python -m repo_language_stats."""

import sys
from repo_language_stats.cli import main

if __name__ == "__main__":
    sys.exit(main())
