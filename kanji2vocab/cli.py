# file: kanji2vocab/cli.py
from dataclasses import dataclass
from typing import Optional

from .models import CLIArgs


def parse_cli(argv: list[str]) -> CLIArgs:
    """Parse argv into a CLIArgs structure."""
    # Handle config editing option.
    if len(argv) == 2 and argv[1] in ("-c", "--config"):
        return CLIArgs(action="config")

    # Handle help option.
    if len(argv) == 2 and argv[1] in ("-h", "--help"):
        return CLIArgs(action="help")

    # Handle single argument (multi-kanji default run).
    if len(argv) == 2:
        return CLIArgs(action="multi", kanji=argv[1])

    # Handle kanji + total pages.
    if len(argv) == 3:
        return CLIArgs(action="run", kanji=argv[1], total_pages=int(argv[2]))

    # Handle kanji + total pages + method.
    if len(argv) == 4:
        return CLIArgs(action="run", kanji=argv[1], total_pages=int(argv[2]), method=argv[3])

    # Fallback to interactive mode.
    return CLIArgs(action="interactive")