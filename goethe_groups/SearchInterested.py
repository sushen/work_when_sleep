"""Goethe Facebook Groups opportunity scanner entrypoint and interface module.

Provides primary interface for discovering German-learning/Goethe opportunities in Facebook groups.
Can be executed directly or imported as a module (`goethe_groups.SearchInterested`).
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from goethe_groups.goethe_config import GoetheGroupConfig, get_enabled_goethe_groups, load_goethe_groups_config
from goethe_groups.goethe_scanner import GoetheGroupScanner, main as scanner_main, normalize_goethe_post


def scan_goethe_group(group: GoetheGroupConfig, query: str, scanner: GoetheGroupScanner | None = None) -> list[dict]:
    """Execute single search query scan on a Goethe Facebook group."""
    if scanner is None:
        scanner = GoetheGroupScanner()
    return scanner.search_group_query(group, query)


def run_continuous_scanner(scanner: GoetheGroupScanner | None = None) -> None:
    """Run continuous search loop over configured Goethe groups."""
    if scanner is None:
        scanner = GoetheGroupScanner()
    scanner.run_continuous()


def main() -> None:
    """Main entrypoint for Goethe Groups opportunity scanner."""
    scanner_main()


if __name__ == "__main__":
    main()
