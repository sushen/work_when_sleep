"""Reddit opportunity scanner entrypoint and interface module.

Provides primary interface for discovering business/service opportunities on Reddit.
Can be executed directly as a script or imported as a module (`reddit_auto.SearchInterested`).
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reddit_auto.reddit_client import RedditClient
from reddit_auto.reddit_parser import normalize_reddit_post
from reddit_auto.reddit_query_queue import RedditQueryQueue, load_reddit_queries, load_reddit_urls, load_subreddit_urls
from reddit_auto.reddit_scanner import RedditScanner, login_if_needed_reddit, main as scanner_main
from reddit_auto.reddit_urls import build_reddit_permalink, clean_reddit_url
from search_interested.browser_session import create_driver
from search_interested.settings import (
    REDDIT_ALERT_QUALITY_LEVELS,
    REDDIT_MAX_OPPORTUNITY_AGE_SECONDS,
    REDDIT_MAX_RESULTS_PER_QUERY,
    REDDIT_POLL_INTERVAL_SECONDS,
    REDDIT_QUERIES_FILE,
    REDDIT_SUBREDDIT_LIST_FILE,
    RESULTS_FILE,
)


def scan_query(query: str, scanner: RedditScanner | None = None) -> list[dict]:
    """Execute single Reddit query or URL scan and return discovered opportunities."""
    if scanner is None:
        scanner = RedditScanner()
    return scanner.process_query(query)


def scan_url(url: str, scanner: RedditScanner | None = None) -> list[dict]:
    """Execute single Reddit target URL scan and return discovered opportunities."""
    if scanner is None:
        scanner = RedditScanner()
    return scanner.scan_url(url)


def run_continuous_scanner(scanner: RedditScanner | None = None) -> None:
    """Run continuous search loop over target Reddit list and queries using Chrome browser."""
    if scanner is None:
        scanner = RedditScanner()
    scanner.run_continuous()


def main() -> None:
    """Main entrypoint for running the Reddit opportunity scanner."""
    scanner_main()


if __name__ == "__main__":
    main()
