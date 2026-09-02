"""Continuous discovery scanner for Reddit service/business opportunities."""

from __future__ import annotations

import json
import time
from urllib.parse import quote

from selenium.webdriver.common.by import By

from reddit_auto.reddit_client import RedditClient, extract_posts_from_json
from reddit_auto.reddit_parser import normalize_reddit_post
from reddit_auto.reddit_query_queue import RedditQueryQueue, load_reddit_urls
from reddit_auto.reddit_urls import build_reddit_permalink
from search_interested.browser_session import (
    create_driver,
    wait_for_page_ready,
)
from search_interested.facebook_dom import scroll_down
from search_interested.notifier import beep
from search_interested.opportunity_engine import analyze_opportunity, is_fresh_opportunity_timestamp
from search_interested.results import (
    alert_opportunity,
    build_opportunity,
    display_opportunity,
    load_seen_opportunity_keys,
    save_opportunity,
)
from search_interested.settings import (
    REDDIT_HOME,
    REDDIT_MAX_OPPORTUNITY_AGE_SECONDS,
    REDDIT_MAX_RESULTS_PER_QUERY,
    REDDIT_POLL_INTERVAL_SECONDS,
)
from search_interested.text_utils import print_running_time, short_error


def login_if_needed_reddit(browser, timeout: int = 8) -> None:
    """Check if Reddit requires login or network verification and pause for user action if needed."""
    try:
        browser.get(REDDIT_HOME)
        wait_for_page_ready(browser, timeout=timeout)
    except Exception as error:
        print(f"[REDDIT_LOGIN] Error loading Reddit homepage: {short_error(error)}")
        return

    page_text = ""
    try:
        body = browser.find_element(By.TAG_NAME, "body")
        page_text = body.text.lower()
    except Exception:
        pass

    if (
        "blocked by network security" in page_text
        or "log in to your reddit account" in page_text
        or "use your developer token" in page_text
    ):
        print("[REDDIT_LOGIN] Reddit requires user login or network security check.")
        print("[REDDIT_LOGIN] Please log in to Reddit in the opened Chrome browser window.")
        input("[PAUSED] Once logged in to Reddit in Chrome, press Enter to continue: ")
        wait_for_page_ready(browser)


def _extract_element_text_by_xpath(element, xpath: str) -> str:
    try:
        sub_elements = element.find_elements(By.XPATH, xpath)
        for sub in sub_elements:
            text = sub.text.strip()
            if text:
                return text
    except Exception:
        pass
    return ""


def _extract_attribute_by_xpath(element, xpath: str, attr: str) -> str:
    try:
        sub_elements = element.find_elements(By.XPATH, xpath)
        for sub in sub_elements:
            val = sub.get_attribute(attr)
            if val:
                return val
    except Exception:
        pass
    return ""


def extract_reddit_posts_from_browser(browser, query: str = "", url: str = "") -> list[dict]:
    """Extract raw post dictionaries from the active browser page via JSON text or DOM elements."""
    posts = []

    # 1. If browser is displaying a raw JSON response body
    try:
        body_text = browser.find_element(By.TAG_NAME, "body").text.strip()
        if body_text.startswith("{") and body_text.endswith("}"):
            parsed = json.loads(body_text)
            extracted = extract_posts_from_json(parsed)
            if extracted:
                return extracted
    except Exception:
        pass

    # 2. Extract from DOM post elements
    post_elements = browser.find_elements(
        By.XPATH,
        "//shreddit-post | "
        "//div[@data-testid='post-container'] | "
        "//article | "
        "//div[contains(@class, 'thing')] | "
        "//a[contains(@href, '/comments/')]/ancestor::div[1]",
    )

    seen_ids = set()

    for element in post_elements:
        try:
            post_id = (
                element.get_attribute("id")
                or element.get_attribute("data-post-id")
                or element.get_attribute("data-fullname")
                or ""
            ).strip()

            title = (
                element.get_attribute("post-title")
                or _extract_element_text_by_xpath(
                    element,
                    ".//a[@data-testid='post-title-text'] | .//h3 | .//h1 | .//a[contains(@class, 'title')]",
                )
            )

            if not title and element.text:
                title = element.text.split("\n")[0]

            if not title or len(title) < 3:
                continue

            author = (
                element.get_attribute("author")
                or element.get_attribute("data-author")
                or _extract_element_text_by_xpath(element, ".//a[contains(@href, '/user/')]")
                or "UNKNOWN"
            )

            subreddit = (
                element.get_attribute("subreddit-prefixed-name")
                or element.get_attribute("community")
                or ""
            )

            permalink = (
                element.get_attribute("permalink")
                or element.get_attribute("content-href")
                or element.get_attribute("data-permalink")
                or _extract_attribute_by_xpath(element, ".//a[contains(@href, '/comments/')]", "href")
                or ""
            )

            created_utc = None
            raw_ts = (
                element.get_attribute("created-timestamp")
                or element.get_attribute("data-timestamp")
            )

            if raw_ts:
                try:
                    val = float(raw_ts)
                    if val > 1e11:
                        val = val / 1000.0
                    created_utc = val
                except ValueError:
                    pass

            if created_utc is None:
                created_utc = time.time()

            if not post_id and permalink:
                post_id = permalink.split("/comments/")[1].split("/")[0] if "/comments/" in permalink else permalink

            if not post_id:
                post_id = str(hash(title))

            if post_id in seen_ids:
                continue
            seen_ids.add(post_id)

            selftext = _extract_element_text_by_xpath(
                element,
                ".//div[@slot='text-body'] | .//div[contains(@class, 'usertext-body')] | .//p",
            )

            post_data = {
                "id": post_id,
                "title": title,
                "selftext": selftext,
                "author": author,
                "subreddit": subreddit,
                "permalink": permalink,
                "created_utc": created_utc,
                "url": build_reddit_permalink(permalink),
            }
            posts.append(post_data)
        except Exception as error:
            print(f"[REDDIT] Error parsing DOM post element: {error}")

    return posts


class RedditScanner:
    """Orchestrates query rotation, browser navigation, fetching, normalization, opportunity scoring, alerting, and persistence."""

    def __init__(
        self,
        browser=None,
        client: RedditClient | None = None,
        query_queue: RedditQueryQueue | None = None,
        poll_interval: int = REDDIT_POLL_INTERVAL_SECONDS,
        max_age_seconds: int = REDDIT_MAX_OPPORTUNITY_AGE_SECONDS,
    ):
        self.browser = browser
        self.client = client or RedditClient(browser=browser)
        self.query_queue = query_queue or RedditQueryQueue()
        self.poll_interval = poll_interval
        self.max_age_seconds = max_age_seconds
        self.seen_keys = load_seen_opportunity_keys()

    def _process_raw_posts(self, raw_posts: list[dict], query: str = "") -> list[dict]:
        discovered_opportunities = []
        new_count = 0
        duplicate_count = 0
        old_count = 0
        unknown_time_count = 0
        weak_count = 0
        possible_count = 0
        strong_count = 0

        for raw_post in raw_posts:
            detected_at = time.time()
            normalized = normalize_reddit_post(raw_post, query=query, detected_at=detected_at)
            opportunity_key = (
                normalized["timestamp_info"] and f"reddit:{normalized['post_id']}"
            ) or normalized["content_url"]

            if opportunity_key in self.seen_keys:
                duplicate_count += 1
                continue

            self.seen_keys.add(opportunity_key)
            new_count += 1

            timestamp_info = normalized["timestamp_info"]
            if not is_fresh_opportunity_timestamp(timestamp_info):
                if timestamp_info["freshness"] == "UNKNOWN":
                    unknown_time_count += 1
                    print(f"[REDDIT] Unknown timestamp for post {normalized['post_id']}; skipping.")
                else:
                    old_count += 1
                    print(
                        f"[REDDIT] Old post ({timestamp_info['freshness']}) "
                        f"age={timestamp_info['age_seconds']}s; skipping."
                    )
                continue

            if (
                timestamp_info["age_seconds"] is not None
                and timestamp_info["age_seconds"] > self.max_age_seconds
            ):
                old_count += 1
                continue

            opportunity_analysis = analyze_opportunity(normalized["content_text"])
            quality = opportunity_analysis["quality"]

            if quality == "WEAK":
                weak_count += 1
                continue
            elif quality == "POSSIBLE":
                possible_count += 1
            elif quality == "STRONG":
                strong_count += 1

            opportunity = build_opportunity(
                group_name=normalized["community_name"],
                group_url=normalized["source_url"],
                content_type="POST",
                author=normalized["author"],
                content_text=normalized["content_text"],
                content_url=normalized["content_url"],
                timestamp_info=timestamp_info,
                opportunity_analysis=opportunity_analysis,
                opportunity_key=opportunity_key,
                source="reddit",
                subreddit=normalized["subreddit"],
                title=normalized["title"],
                detection_latency_seconds=normalized["detection_latency_seconds"],
                query=query,
                post_id=normalized["post_id"],
            )

            save_opportunity(opportunity)
            alert_opportunity(opportunity)
            display_opportunity(opportunity)
            discovered_opportunities.append(opportunity)

        print(
            f"[REDDIT] Summary -> "
            f"New: {new_count}, Dup: {duplicate_count}, Old: {old_count}, "
            f"UnknownTime: {unknown_time_count}, Weak: {weak_count}, "
            f"Possible: {possible_count}, Strong: {strong_count}"
        )
        return discovered_opportunities

    def scan_url(self, url: str) -> list[dict]:
        """Navigate Chrome browser to Reddit target URL, extract posts, and process opportunities."""
        print(f"[REDDIT] Target URL: '{url}'")

        if self.browser is None:
            self.browser = create_driver()

        login_if_needed_reddit(self.browser)

        try:
            self.browser.get(url)
            wait_for_page_ready(self.browser)
            scroll_down(self.browser)
            raw_posts = extract_reddit_posts_from_browser(self.browser, url=url)
        except Exception as error:
            print(f"[REDDIT] Error loading URL '{url}': {short_error(error)}")
            raw_posts = []

        print(f"[REDDIT] Results: {len(raw_posts)} posts retrieved")
        return self._process_raw_posts(raw_posts, query=url)

    def process_query(self, query: str) -> list[dict]:
        """Run single search query against Reddit using browser if available or client fallback."""
        if self.browser is not None:
            encoded = quote(query)
            search_url = f"https://www.reddit.com/search/?q={encoded}&sort=new"
            return self.scan_url(search_url)

        print(f"[REDDIT] Query: '{query}'")
        raw_posts = self.client.search_newest(query, limit=REDDIT_MAX_RESULTS_PER_QUERY)
        print(f"[REDDIT] Results: {len(raw_posts)} posts retrieved")
        return self._process_raw_posts(raw_posts, query=query)

    def run_continuous(self, start_time: float | None = None) -> None:
        """Continuous scanning loop over target Reddit list and search queries using Chrome browser."""
        if start_time is None:
            start_time = time.time()

        beep()
        if self.browser is None:
            self.browser = create_driver()

        login_if_needed_reddit(self.browser)
        target_urls = load_reddit_urls()

        print(f"[REDDIT] Continuous scanner started on {len(target_urls)} target URLs")

        url_index = 0
        while True:
            if not target_urls:
                target_urls = load_reddit_urls()
                if not target_urls:
                    print("[REDDIT] No target URLs available in sub_raddit_list or reddit_queries.txt. Waiting 30s...")
                    time.sleep(30)
                    continue

            url = target_urls[url_index]
            try:
                self.scan_url(url)
            except Exception as error:
                print(f"[REDDIT] Error scanning target URL '{url}': {short_error(error)}")

            print_running_time(start_time)
            print(f"[REDDIT] Waiting {self.poll_interval} seconds before next target...")
            time.sleep(self.poll_interval)
            url_index = (url_index + 1) % len(target_urls)


def main():
    scanner = RedditScanner()
    try:
        scanner.run_continuous()
    except KeyboardInterrupt:
        print("\n[REDDIT] Scanner stopped by user.")


if __name__ == "__main__":
    main()
