"""Modular query queue management for Reddit search queries."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from search_interested.settings import REDDIT_QUERIES_FILE, REDDIT_SUBREDDIT_LIST_FILE
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


def load_subreddit_urls(list_file: Path | str | None = None) -> list[str]:
    """Load, comment-strip, blank-line filter, and deduplicate subreddit URLs from file."""
    if list_file is None:
        list_file = REDDIT_SUBREDDIT_LIST_FILE

    list_path = Path(list_file)
    if not list_path.exists():
        print(f"[REDDIT_QUEUE] Subreddit list file not found: {list_path}")
        return []

    try:
        content = list_path.read_text(encoding="utf-8")
    except OSError as error:
        print(f"[REDDIT_QUEUE] Error reading subreddit list file: {error}")
        return []

    urls = []
    seen = set()

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        normalized = normalize_space(line)
        if not (normalized.startswith("http://") or normalized.startswith("https://")):
            if normalized.startswith("r/"):
                normalized = f"https://www.reddit.com/{normalized}/"
            else:
                normalized = f"https://www.reddit.com/r/{normalized}/"

        lowered = normalized.lower()
        if lowered not in seen:
            seen.add(lowered)
            urls.append(normalized)

    print(f"[REDDIT_QUEUE] Loaded {len(urls)} subreddit URLs from {list_path.name}")
    return urls


def load_reddit_urls(
    subreddits_file: Path | str | None = None,
    queries_file: Path | str | None = None,
) -> list[str]:
    """Load all target Reddit URLs: subreddit list URLs first, followed by query search URLs."""
    subreddit_urls = load_subreddit_urls(subreddits_file)
    queries = load_reddit_queries(queries_file)

    query_urls = []
    for query in queries:
        encoded = quote(query)
        search_url = f"https://www.reddit.com/search/?q={encoded}&sort=new"
        query_urls.append(search_url)

    combined_urls = []
    seen = set()
    for url in subreddit_urls + query_urls:
        lowered = url.lower()
        if lowered not in seen:
            seen.add(lowered)
            combined_urls.append(url)

    print(f"[REDDIT_QUEUE] Total loaded Reddit target URLs: {len(combined_urls)}")
    return combined_urls


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
