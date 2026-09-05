"""Goethe Facebook Group Member Requests scanner entrypoint and interface module.

Provides primary interface for discovering new member requests on Facebook groups.
Can be executed directly or imported as a module (`goethe_groups.SearchInterested`).
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from goethe_groups.goethe_config import GoetheGroupConfig, get_enabled_goethe_groups, load_goethe_groups_config
from goethe_groups.goethe_scanner import GoetheGroupScanner, main as scanner_main, normalize_member_request


def scan_member_requests(url: str | None = None, scanner: GoetheGroupScanner | None = None) -> list[dict]:
    """Execute single scan on Goethe Group member requests page."""
    if scanner is None:
        scanner = GoetheGroupScanner()
    return scanner.monitor_member_requests(url)


def run_continuous_scanner(scanner: GoetheGroupScanner | None = None) -> None:
    """Run continuous 30s reload loop over member requests page."""
    if scanner is None:
        scanner = GoetheGroupScanner()
    scanner.run_continuous()


def main() -> None:
    """Main entrypoint for Goethe Group Member Requests scanner."""
    scanner_main()


if __name__ == "__main__":
    main()
