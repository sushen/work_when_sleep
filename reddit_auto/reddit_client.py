"""Reddit client for querying public Reddit search API or subreddit feeds with rate limiting and retry handling."""

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


def extract_posts_from_json(data: dict | list) -> list[dict]:
    """Extract list of post dicts (kind 't3') from raw Reddit JSON listing."""
    posts = []
    if isinstance(data, list):
        for item in data:
            posts.extend(extract_posts_from_json(item))
        return posts

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


def extract_comments_from_json(data: dict | list) -> list[dict]:
    """Extract list of comment dicts (kind 't1') from raw Reddit JSON listing."""
    comments = []
    if isinstance(data, list):
        for item in data:
            comments.extend(extract_comments_from_json(item))
        return comments

    if not isinstance(data, dict):
        return comments

    data_block = data.get("data", {})
    children = data_block.get("children", [])

    for child in children:
        if isinstance(child, dict) and child.get("kind") == "t1":
            comment_data = child.get("data")
            if isinstance(comment_data, dict):
                comments.append(comment_data)

    return comments


class RedditClient:
    """Handles HTTP or browser requests to Reddit endpoints with rate limit backoff."""

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

    def _extract_posts_from_json(self, data: dict | list) -> list[dict]:
        return extract_posts_from_json(data)

    def _extract_comments_from_json(self, data: dict | list) -> list[dict]:
        return extract_comments_from_json(data)

    def _fetch_json_endpoint(self, url: str) -> dict | list | None:
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
                    return json.loads(raw_data)
                else:
                    print(f"[REDDIT_CLIENT] HTTP {status} for URL: '{url}'")
                    return None
        except urllib.error.HTTPError as error:
            if error.code == 429:
                print(
                    f"[REDDIT_CLIENT] Rate limited (HTTP 429). "
                    f"Waiting {self.retry_delay}s before continuing..."
                )
                time.sleep(self.retry_delay)
            else:
                print(f"[REDDIT_CLIENT] HTTP error {error.code}: {short_error(error)}")
            return None
        except urllib.error.URLError as error:
            print(f"[REDDIT_CLIENT] Network error: {short_error(error)}")
            return None
        except json.JSONDecodeError as error:
            print(f"[REDDIT_CLIENT] Invalid JSON response: {short_error(error)}")
            return None
        except Exception as error:
            print(f"[REDDIT_CLIENT] Unexpected error: {short_error(error)}")
            return None

    def _clean_subreddit_name(self, subreddit_url_or_name: str) -> str:
        s = subreddit_url_or_name.rstrip("/").strip()
        if "/r/" in s:
            s = s.split("/r/")[-1].split("/")[0]
        elif s.lower().startswith("r/"):
            s = s[2:]
        return s.strip()

    def fetch_subreddit_posts(self, subreddit_url_or_name: str, limit: int = 25) -> list[dict]:
        """Fetch newest posts for a subreddit using /new.json endpoint."""
        sub = self._clean_subreddit_name(subreddit_url_or_name)
        url = f"https://www.reddit.com/r/{sub}/new.json?limit={limit}"
        data = self._fetch_json_endpoint(url)
        return self._extract_posts_from_json(data) if data else []

    def fetch_subreddit_comments(self, subreddit_url_or_name: str, limit: int = 25) -> list[dict]:
        """Fetch newest comments for a subreddit using /comments.json endpoint."""
        sub = self._clean_subreddit_name(subreddit_url_or_name)
        url = f"https://www.reddit.com/r/{sub}/comments.json?limit={limit}"
        data = self._fetch_json_endpoint(url)
        return self._extract_comments_from_json(data) if data else []

    def search_newest(
        self,
        query: str,
        limit: int = REDDIT_MAX_RESULTS_PER_QUERY,
    ) -> list[dict]:
        """Search Reddit for newest results matching query. Uses urllib HTTP request."""
        encoded_query = urllib.parse.quote(query)
        url = (
            f"https://www.reddit.com/search.json"
            f"?q={encoded_query}&sort=new&limit={limit}&type=link"
        )
        data = self._fetch_json_endpoint(url)
        return self._extract_posts_from_json(data) if data else []
