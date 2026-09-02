"""Continuous real-time monitoring scanner for Reddit service/business opportunities."""

from __future__ import annotations

import json
import time
from typing import Sequence
from urllib.parse import quote

from selenium.webdriver.common.by import By

from reddit_auto.reddit_client import RedditClient, extract_comments_from_json, extract_posts_from_json
from reddit_auto.reddit_parser import (
    extract_subreddit_name,
    normalize_reddit_comment,
    normalize_reddit_post,
)
from reddit_auto.reddit_query_queue import load_subreddit_urls
from reddit_auto.reddit_urls import build_reddit_permalink
from search_interested.browser_session import (
    create_driver,
    wait_for_page_ready,
)
from search_interested.notifier import beep
from search_interested.opportunity_engine import analyze_opportunity
from search_interested.results import (
    alert_opportunity,
    build_opportunity,
    display_opportunity,
    load_seen_opportunity_keys,
    save_opportunity,
)
from search_interested.settings import (
    REDDIT_HOME,
    REDDIT_IMMEDIATE_ALERT_SECONDS,
    REDDIT_MAX_FRESHNESS_SECONDS,
    REDDIT_MAX_RESULTS_PER_QUERY,
    REDDIT_SCAN_INTERVAL_SECONDS,
)
from search_interested.text_utils import print_running_time, short_error


def login_if_needed_reddit(browser, timeout: int = 8) -> None:
    """Open Reddit and pause for manual user login confirmation."""
    if browser is None:
        return

    try:
        browser.get(REDDIT_HOME)
        wait_for_page_ready(browser, timeout=timeout)
    except Exception as error:
        print(f"[REDDIT_LOGIN] Error loading Reddit homepage: {short_error(error)}")

    print("[REDDIT_LOGIN] Reddit browser window opened.")
    print("[REDDIT_LOGIN] Please log in manually if required.")
    input("[PAUSED] Once manual login is complete, press Enter to continue scanning: ")
    try:
        wait_for_page_ready(browser, timeout=timeout)
    except Exception:
        pass


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
    """Extract raw post dictionaries from active browser page via JSON text or DOM elements."""
    posts = []

    # 1. If browser is displaying a raw JSON response body
    try:
        body_text = browser.find_element(By.TAG_NAME, "body").text.strip()
        if body_text.startswith("{") or body_text.startswith("["):
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
        "//div[contains(@class, 'thing') and contains(@class, 'link')]",
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


def extract_reddit_comments_from_browser(browser, query: str = "", url: str = "") -> list[dict]:
    """Extract raw comment dictionaries from active browser page via JSON text or DOM elements."""
    comments = []

    # 1. If browser is displaying a raw JSON response body
    try:
        body_text = browser.find_element(By.TAG_NAME, "body").text.strip()
        if body_text.startswith("{") or body_text.startswith("["):
            parsed = json.loads(body_text)
            extracted = extract_comments_from_json(parsed)
            if extracted:
                return extracted
    except Exception:
        pass

    # 2. Extract from DOM comment elements
    comment_elements = browser.find_elements(
        By.XPATH,
        "//shreddit-comment | "
        "//div[contains(@class, 'thing') and contains(@class, 'comment')]",
    )

    seen_ids = set()

    for element in comment_elements:
        try:
            comment_id = (
                element.get_attribute("id")
                or element.get_attribute("data-fullname")
                or ""
            ).strip()

            author = (
                element.get_attribute("author")
                or _extract_element_text_by_xpath(element, ".//a[contains(@href, '/user/')]")
                or "UNKNOWN"
            )

            subreddit = element.get_attribute("subreddit-prefixed-name") or ""

            permalink = element.get_attribute("permalink") or ""

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

            body = _extract_element_text_by_xpath(
                element,
                ".//div[@slot='comment'] | .//div[contains(@class, 'usertext-body')] | .//p",
            )
            if not body and element.text:
                body = element.text

            if not body or len(body) < 2:
                continue

            if comment_id in seen_ids:
                continue
            seen_ids.add(comment_id)

            comment_data = {
                "id": comment_id,
                "body": body,
                "author": author,
                "subreddit": subreddit,
                "permalink": permalink,
                "created_utc": created_utc,
                "url": build_reddit_permalink(permalink),
            }
            comments.append(comment_data)
        except Exception as error:
            print(f"[REDDIT] Error parsing DOM comment element: {error}")

    return comments


class RedditScanner:
    """Monitors fixed watchlist of subreddits in real-time for new posts and comments."""

    def __init__(
        self,
        browser=None,
        client: RedditClient | None = None,
        poll_interval: int = REDDIT_SCAN_INTERVAL_SECONDS,
        max_age_seconds: int = REDDIT_MAX_FRESHNESS_SECONDS,
        immediate_alert_seconds: int = REDDIT_IMMEDIATE_ALERT_SECONDS,
    ):
        self.browser = browser
        self.client = client or RedditClient(browser=browser)
        self.poll_interval = poll_interval
        self.max_age_seconds = max_age_seconds
        self.immediate_alert_seconds = immediate_alert_seconds
        self.seen_keys = load_seen_opportunity_keys()
        self.alerted_freshness_keys: set[str] = set()

    def check_immediate_freshness(self, normalized_item: dict) -> bool:
        """Check item age and trigger immediate real-time beep if within REDDIT_IMMEDIATE_ALERT_SECONDS."""
        opportunity_key = normalized_item.get("opportunity_key")
        if not opportunity_key or opportunity_key in self.alerted_freshness_keys:
            return False

        confidence = normalized_item.get("timestamp_confidence", "NONE")
        if confidence in {"NONE", "UNKNOWN"}:
            return False

        age_seconds = normalized_item.get("age_seconds")
        if age_seconds is None or age_seconds < 0:
            return False

        if age_seconds <= self.immediate_alert_seconds:
            self.alerted_freshness_keys.add(opportunity_key)

            content_type = normalized_item.get("content_type", "POST")
            header_tag = "[REDDIT NEW POST]" if content_type == "POST" else "[REDDIT NEW COMMENT]"
            url_label = "Post URL" if content_type == "POST" else "Comment URL"
            author_str = normalized_item.get("author", "UNKNOWN")
            if author_str and not author_str.startswith("u/"):
                author_display = f"u/{author_str}"
            else:
                author_display = author_str or "UNKNOWN"

            latency_sec = normalized_item.get("detection_latency_seconds")
            latency_str = f"{latency_sec:.1f} seconds" if isinstance(latency_sec, (int, float)) else f"{int(age_seconds)} seconds"
            age_str = f"{int(age_seconds)} seconds"

            created_time_str = normalized_item.get("timestamp_raw") or "UNKNOWN"

            print("=" * 50)
            print(header_tag)
            print("=" * 50)
            print(f"Subreddit:\n    {normalized_item.get('community_name', 'UNKNOWN')}")
            print(f"Author:\n    {author_display}")
            if content_type == "POST":
                print(f"Title:\n    {normalized_item.get('title', '')}")
            print(f"Created:\n    {created_time_str}")
            print(f"Age:\n    {age_str}")
            print(f"Detection Latency:\n    {latency_str}")
            print(f"{url_label}:\n    {normalized_item.get('content_url') or normalized_item.get('source_url')}")
            print(f"Text:\n    {normalized_item.get('body') or normalized_item.get('content_text') or ''}")
            print("=" * 50)

            print("[REDDIT] IMMEDIATE FRESH ALERT")
            print(f"[REDDIT] Age: {age_str}")
            print(f"[REDDIT] Detection latency: {latency_str}")
            print("[ALERT] REAL-TIME -> BEEP")

            beep()
            return True

        return False

    def process_item(self, normalized_item: dict) -> dict | None:
        """Evaluate normalized post or comment item, save and alert immediately if fresh opportunity."""
        opportunity_key = normalized_item["opportunity_key"]

        if opportunity_key in self.seen_keys:
            return None

        self.seen_keys.add(opportunity_key)

        timestamp_confidence = normalized_item.get("timestamp_confidence", "NONE")
        age_seconds = normalized_item.get("age_seconds")

        # Strict Freshness Check
        if timestamp_confidence in {"NONE", "UNKNOWN"} or age_seconds is None:
            return None

        if age_seconds > self.max_age_seconds:
            return None

        opportunity_analysis = analyze_opportunity(normalized_item["content_text"])
        quality = opportunity_analysis["quality"]

        if quality in {"WEAK", "REJECT"}:
            return None

        opportunity = build_opportunity(
            group_name=normalized_item["community_name"],
            group_url=normalized_item["source_url"],
            content_type=normalized_item["content_type"],
            author=normalized_item["author"],
            content_text=normalized_item["content_text"],
            content_url=normalized_item["content_url"],
            timestamp_info=normalized_item["timestamp_info"],
            opportunity_analysis=opportunity_analysis,
            opportunity_key=opportunity_key,
            source="reddit",
            subreddit=normalized_item["subreddit"],
            title=normalized_item.get("title"),
            detection_latency_seconds=normalized_item["detection_latency_seconds"],
            query=normalized_item.get("query"),
            post_id=normalized_item.get("post_id") or normalized_item.get("comment_id"),
        )

        save_opportunity(opportunity)
        alert_opportunity(opportunity)
        display_opportunity(opportunity)
        return opportunity

    def process_posts(self, raw_posts: list[dict], query: str = "") -> list[dict]:
        """Process list of raw posts into immediate opportunities."""
        detected_at = time.time()
        discovered = []

        for raw_post in raw_posts:
            normalized = normalize_reddit_post(raw_post, query=query, detected_at=detected_at)
            self.check_immediate_freshness(normalized)
            opportunity = self.process_item(normalized)
            if opportunity:
                discovered.append(opportunity)

        return discovered

    def process_comments(self, raw_comments: list[dict], query: str = "") -> list[dict]:
        """Process list of raw comments into immediate opportunities."""
        detected_at = time.time()
        discovered = []

        for raw_comment in raw_comments:
            normalized = normalize_reddit_comment(raw_comment, query=query, detected_at=detected_at)
            self.check_immediate_freshness(normalized)
            opportunity = self.process_item(normalized)
            if opportunity:
                discovered.append(opportunity)

        return discovered

    def _filter_fresh_items(self, items: list[dict], detected_at: float) -> list[dict]:
        """Return subset of normalized items that meet strict freshness window."""
        fresh = []
        for item in items:
            confidence = item.get("timestamp_confidence", "NONE")
            age = item.get("age_seconds")
            if confidence not in {"NONE", "UNKNOWN"} and age is not None and age <= self.max_age_seconds:
                fresh.append(item)
        return fresh

    def monitor_subreddit(self, subreddit_url: str) -> dict:
        """Fetch posts and comments for a single subreddit, process fresh items immediately, and return stats."""
        detected_at = time.time()
        sub_name = extract_subreddit_name("", permalink=subreddit_url, url=subreddit_url)
        print(f"[REDDIT] Checking {sub_name}")

        if self.browser is not None:
            new_posts_url = f"{subreddit_url.rstrip('/')}/new/"
            try:
                self.browser.get(new_posts_url)
                wait_for_page_ready(self.browser)
                raw_posts = extract_reddit_posts_from_browser(self.browser, url=new_posts_url)
            except Exception as error:
                print(f"[REDDIT] Browser error fetching posts for {sub_name}: {short_error(error)}")
                raw_posts = []

            comments_url = f"{subreddit_url.rstrip('/')}/comments/"
            try:
                self.browser.get(comments_url)
                wait_for_page_ready(self.browser)
                raw_comments = extract_reddit_comments_from_browser(self.browser, url=comments_url)
            except Exception as error:
                print(f"[REDDIT] Browser error fetching comments for {sub_name}: {short_error(error)}")
                raw_comments = []
        else:
            raw_posts = self.client.fetch_subreddit_posts(subreddit_url, limit=25)
            raw_comments = self.client.fetch_subreddit_comments(subreddit_url, limit=25)

        normalized_posts = [normalize_reddit_post(p, query=subreddit_url, detected_at=detected_at) for p in raw_posts]
        normalized_comments = [normalize_reddit_comment(c, query=subreddit_url, detected_at=detected_at) for c in raw_comments]

        fresh_posts = self._filter_fresh_items(normalized_posts, detected_at)
        fresh_comments = self._filter_fresh_items(normalized_comments, detected_at)
        total_fresh_items = len(fresh_posts) + len(fresh_comments)

        opportunities = []

        # Check immediate freshness and process posts
        for norm in normalized_posts:
            self.check_immediate_freshness(norm)
            opp = self.process_item(norm)
            if opp:
                opportunities.append(opp)

        # Check immediate freshness and process comments
        for norm in normalized_comments:
            self.check_immediate_freshness(norm)
            opp = self.process_item(norm)
            if opp:
                opportunities.append(opp)

        latencies = [
            opp["detection_latency_seconds"]
            for opp in opportunities
            if opp.get("detection_latency_seconds") is not None
        ]
        avg_latency_str = f"{sum(latencies)/len(latencies):.1f}s" if latencies else "N/A"

        print(f"[REDDIT] New posts: {len(raw_posts)}")
        print(f"[REDDIT] New comments: {len(raw_comments)}")
        print(f"[REDDIT] Fresh items: {total_fresh_items}")
        print(f"[REDDIT] Opportunities: {len(opportunities)}")
        print(f"[REDDIT] Detection latency: {avg_latency_str}")

        return {
            "subreddit": sub_name,
            "posts_count": len(raw_posts),
            "comments_count": len(raw_comments),
            "fresh_count": total_fresh_items,
            "opportunities_count": len(opportunities),
            "opportunities": opportunities,
        }

    def scan_url(self, url: str) -> list[dict]:
        """Backward compatible URL scanning."""
        stats = self.monitor_subreddit(url)
        return stats["opportunities"]

    def process_query(self, query: str) -> list[dict]:
        """Backward compatible single query process using client API."""
        raw_posts = self.client.search_newest(query, limit=REDDIT_MAX_RESULTS_PER_QUERY)
        return self.process_posts(raw_posts, query=query)

    def run_continuous(self, start_time: float | None = None) -> None:
        """Continuous monitoring loop over fixed subreddit watchlist."""
        if start_time is None:
            start_time = time.time()

        beep()
        if self.browser is None:
            self.browser = create_driver()

        login_if_needed_reddit(self.browser)

        subreddit_urls = load_subreddit_urls()
        print(f"[REDDIT] Real-time scanner started on {len(subreddit_urls)} fixed watchlist subreddits")

        while True:
            cycle_started_at = time.time()
            subreddit_urls = load_subreddit_urls()
            if not subreddit_urls:
                print("[REDDIT] No subreddits in sub_raddit_list. Waiting 30s...")
                time.sleep(30)
                continue

            cycle_opportunities = 0

            for sub_url in subreddit_urls:
                try:
                    stats = self.monitor_subreddit(sub_url)
                    cycle_opportunities += stats["opportunities_count"]
                except Exception as error:
                    print(f"[REDDIT] Error monitoring '{sub_url}': {short_error(error)}")

            cycle_finished_at = time.time()
            cycle_duration_seconds = cycle_finished_at - cycle_started_at

            print(
                f"[REDDIT] Cycle finished: duration={cycle_duration_seconds:.1f}s, "
                f"total_opportunities={cycle_opportunities}"
            )
            print_running_time(start_time)
            print(f"[REDDIT] Waiting {self.poll_interval}s before next monitoring pass...")
            time.sleep(self.poll_interval)


def main():
    scanner = RedditScanner()
    try:
        scanner.run_continuous()
    except KeyboardInterrupt:
        print("\n[REDDIT] Scanner stopped by user.")


if __name__ == "__main__":
    main()
