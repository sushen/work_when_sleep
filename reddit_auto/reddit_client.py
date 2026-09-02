"""Reddit client for querying public Reddit search API or browser session with rate limiting and retry handling."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

from search_interested.settings import (
    REDDIT_MAX_RESULTS_PER_QUERY,
    REDDIT_REQUEST_TIMEOUT_SECONDS,
    REDDIT_RETRY_DELAY_SECONDS,
    REDDIT_USER_AGENT,
)
from search_interested.text_utils import short_error


def extract_posts_from_json(data: dict) -> list[dict]:
    """Extract list of post dicts from raw Reddit JSON listing."""
    posts = []
    if not isinstance(data, dict):
        return posts

    data_block = data.get("data", {})
    children = data_block.get("children", [])

    for child in children:
        if isinstance(child, dict) and child.get("kind") == "t3":
            post_data = child.get("data")
            if isinstance(post_data, dict):
                posts.append(post_data)

    return posts


class RedditClient:
    """Handles HTTP or browser requests to Reddit search with rate limit backoff."""

    def __init__(
        self,
        user_agent: str = REDDIT_USER_AGENT,
        timeout: int = REDDIT_REQUEST_TIMEOUT_SECONDS,
        retry_delay: int = REDDIT_RETRY_DELAY_SECONDS,
        browser=None,
    ):
        self.user_agent = user_agent
        self.timeout = timeout
        self.retry_delay = retry_delay
        self.browser = browser

    def _extract_posts_from_json(self, data: dict) -> list[dict]:
        return extract_posts_from_json(data)

    def search_newest(
        self,
        query: str,
        limit: int = REDDIT_MAX_RESULTS_PER_QUERY,
    ) -> list[dict]:
        """Search Reddit for newest results matching query. Uses browser if available, else urllib HTTP request."""
        encoded_query = urllib.parse.quote(query)
        url = (
            f"https://www.reddit.com/search.json"
            f"?q={encoded_query}&sort=new&limit={limit}&type=link"
        )

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }
        request = urllib.request.Request(url, headers=headers)

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                status = response.getcode()
                if status == 200:
                    raw_data = response.read().decode("utf-8")
                    parsed_json = json.loads(raw_data)
                    return self._extract_posts_from_json(parsed_json)
                else:
                    print(f"[REDDIT_CLIENT] HTTP {status} for query: '{query}'")
                    return []
        except urllib.error.HTTPError as error:
            if error.code == 429:
                print(
                    f"[REDDIT_CLIENT] Rate limited (HTTP 429). "
                    f"Waiting {self.retry_delay}s before continuing..."
                )
                time.sleep(self.retry_delay)
            else:
                print(f"[REDDIT_CLIENT] HTTP error {error.code}: {short_error(error)}")
            return []
        except urllib.error.URLError as error:
            print(f"[REDDIT_CLIENT] Network error: {short_error(error)}")
            return []
        except json.JSONDecodeError as error:
            print(f"[REDDIT_CLIENT] Invalid JSON response: {short_error(error)}")
            return []
        except Exception as error:
            print(f"[REDDIT_CLIENT] Unexpected error: {short_error(error)}")
            return []
