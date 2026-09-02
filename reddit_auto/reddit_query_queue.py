"""Modular query queue management for Reddit search queries."""

from __future__ import annotations

from pathlib import Path

from search_interested.settings import REDDIT_QUERIES_FILE
from search_interested.text_utils import normalize_space


def load_reddit_queries(queries_file: Path | str | None = None) -> list[str]:
    """Load, comment-strip, blank-line filter, and deduplicate queries from file."""
    if queries_file is None:
        queries_file = REDDIT_QUERIES_FILE

    queries_path = Path(queries_file)
    if not queries_path.exists():
        print(f"[REDDIT_QUEUE] Query file not found: {queries_path}")
        return []

    try:
        content = queries_path.read_text(encoding="utf-8")
    except OSError as error:
        print(f"[REDDIT_QUEUE] Error reading query file: {error}")
        return []

    queries = []
    seen = set()

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        normalized = normalize_space(line)
        lowered = normalized.lower()
        if lowered not in seen:
            seen.add(lowered)
            queries.append(normalized)

    print(f"[REDDIT_QUEUE] Loaded {len(queries)} active queries from {queries_path.name}")
    return queries


class RedditQueryQueue:
    """Manages active query rotation, status tracking, and current position."""

    def __init__(self, queries_file: Path | str | None = None):
        self.queries_file = queries_file or REDDIT_QUERIES_FILE
        self.queries = load_reddit_queries(self.queries_file)
        self.current_index = 0
        self.query_failures: dict[str, int] = {}

    def reload(self) -> None:
        """Reload queries from file."""
        self.queries = load_reddit_queries(self.queries_file)
        if self.current_index >= len(self.queries):
            self.current_index = 0

    def get_current_query(self) -> str | None:
        """Return current active query without rotating."""
        if not self.queries:
            self.reload()
            if not self.queries:
                return None
        return self.queries[self.current_index]

    def get_next_query(self) -> str | None:
        """Return current active query and rotate index to next query."""
        if not self.queries:
            self.reload()
            if not self.queries:
                return None

        query = self.queries[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.queries)
        return query

    def record_failure(self, query: str) -> None:
        """Track failure count for a specific query."""
        self.query_failures[query] = self.query_failures.get(query, 0) + 1

    def record_success(self, query: str) -> None:
        """Clear failure count on successful query run."""
        self.query_failures.pop(query, None)
