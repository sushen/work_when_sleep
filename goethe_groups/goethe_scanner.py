"""Continuous monitoring scanner for Goethe Facebook groups search interests."""

from __future__ import annotations

import time
from typing import Sequence

from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)

from Pages.FacebookGroupSearchPage import FacebookGroupSearchPage
from goethe_groups.goethe_config import GoetheGroupConfig, get_enabled_goethe_groups
from search_interested.browser_session import (
    create_driver,
    is_dead_browser_session,
    login_if_needed,
    restart_driver,
    wait_for_page_ready,
)
from search_interested.notifier import beep
from search_interested.opportunity_engine import analyze_opportunity, is_fresh_opportunity_timestamp
from search_interested.results import (
    alert_opportunity,
    build_opportunity,
    build_opportunity_key,
    display_opportunity,
    load_seen_opportunity_keys,
    save_opportunity,
)
from search_interested.settings import (
    GOETHE_GROUP_POLL_INTERVAL_SECONDS,
    MAX_SCROLLS_PER_GOETHE_SEARCH,
)
from search_interested.text_utils import print_running_time, short_error


def normalize_goethe_post(raw_post: dict, query: str = "", detected_at: float | None = None) -> dict:
    """Normalize raw Goethe group search result into standard item dictionary."""
    if detected_at is None:
        detected_at = time.time()

    group_url = raw_post.get("group_url", "")
    content_url = raw_post.get("content_url") or raw_post.get("post_url") or group_url
    content_type = raw_post.get("content_type", "POST")
    text = raw_post.get("content_text") or raw_post.get("text", "")
    author = raw_post.get("author") or raw_post.get("author_name", "UNKNOWN")
    timestamp_info = raw_post.get("timestamp_info") or {"raw": "", "age_seconds": None, "confidence": "NONE", "freshness": "UNKNOWN"}

    opportunity_key = build_opportunity_key(
        group_url=group_url,
        content_url=content_url,
        content_type=content_type,
        content_text=text,
        timestamp_raw=timestamp_info.get("raw"),
    )

    post_id = raw_post.get("post_id")
    if not post_id and content_url:
        if "/posts/" in content_url:
            post_id = content_url.split("/posts/")[1].split("/")[0].split("?")[0]
        elif "/permalink/" in content_url:
            post_id = content_url.split("/permalink/")[1].split("/")[0].split("?")[0]
        elif "story_fbid=" in content_url:
            post_id = content_url.split("story_fbid=")[1].split("&")[0]

    return {
        "source": "facebook",
        "source_type": "goethe_group",
        "community_name": raw_post.get("group_name", "Goethe Group"),
        "group_name": raw_post.get("group_name", "Goethe Group"),
        "group_url": group_url,
        "search_interest": query,
        "query": query,
        "post_id": post_id,
        "post_url": raw_post.get("post_url", content_url),
        "author": author,
        "author_name": author,
        "content_type": content_type,
        "content_text": text,
        "text": text,
        "content_url": content_url,
        "timestamp_info": timestamp_info,
        "timestamp_confidence": timestamp_info.get("confidence", "NONE"),
        "age_seconds": timestamp_info.get("age_seconds"),
        "timestamp_raw": timestamp_info.get("raw"),
        "opportunity_key": opportunity_key,
        "discovered_at": detected_at,
    }


class GoetheGroupScanner:
    """Monitors configured Goethe Facebook groups by searching keywords periodically."""

    def __init__(
        self,
        browser=None,
        poll_interval: int = GOETHE_GROUP_POLL_INTERVAL_SECONDS,
        max_scrolls: int = MAX_SCROLLS_PER_GOETHE_SEARCH,
        config_file=None,
    ):
        self.browser = browser
        self.poll_interval = poll_interval
        self.max_scrolls = max_scrolls
        self.config_file = config_file
        self.seen_keys = load_seen_opportunity_keys()

    def process_item(self, normalized_item: dict) -> dict | None:
        """Evaluate normalized Goethe item, save and alert if fresh opportunity."""
        opportunity_key = normalized_item["opportunity_key"]

        if opportunity_key in self.seen_keys:
            return None

        self.seen_keys.add(opportunity_key)

        timestamp_info = normalized_item.get("timestamp_info", {})
        if not is_fresh_opportunity_timestamp(timestamp_info):
            return None

        opportunity_analysis = analyze_opportunity(normalized_item["content_text"])
        quality = opportunity_analysis["quality"]

        if quality in {"WEAK", "REJECT"}:
            return None

        opportunity = build_opportunity(
            group_name=normalized_item["group_name"],
            group_url=normalized_item["group_url"],
            content_type=normalized_item["content_type"],
            author=normalized_item["author"],
            content_text=normalized_item["content_text"],
            content_url=normalized_item["content_url"],
            timestamp_info=timestamp_info,
            opportunity_analysis=opportunity_analysis,
            opportunity_key=opportunity_key,
            source="facebook",
            subreddit="",
            title=f"Goethe Group: {normalized_item['group_name']} - {normalized_item['query']}",
            query=normalized_item.get("query"),
            post_id=normalized_item.get("post_id"),
        )
        opportunity["source_type"] = "goethe_group"
        opportunity["search_interest"] = normalized_item.get("search_interest")

        save_opportunity(opportunity)
        alert_opportunity(opportunity)
        display_opportunity(opportunity)
        return opportunity

    def search_group_query(
        self,
        group: GoetheGroupConfig,
        query: str,
    ) -> list[dict]:
        """Perform search in group for given query and process visible posts."""
        print(f"[GoetheGroups] Opening group: {group.name}")
        print(f"[GoetheGroups] Searching: '{query}' ({group.url})")

        if self.browser is None:
            return []

        search_page = FacebookGroupSearchPage(self.browser)

        try:
            search_page.navigate_to_group_search(group.url, query)
            search_page.wait_for_results()
        except Exception as error:
            print(f"[GoetheGroups] Error navigating/loading search for {group.name} / '{query}': {short_error(error)}")
            return []

        discovered = []

        # Scroll and parse results
        for scroll_num in range(1, self.max_scrolls + 1):
            post_elements = search_page.get_visible_post_elements()
            for elem in post_elements:
                try:
                    raw_data = search_page.extract_post_data(
                        elem,
                        query=query,
                        group_name=group.name,
                        group_url=group.url,
                    )
                    if not raw_data:
                        continue

                    normalized = normalize_goethe_post(raw_data, query=query)
                    opp = self.process_item(normalized)
                    if opp:
                        discovered.append(opp)
                except StaleElementReferenceException:
                    continue
                except Exception as error:
                    print(f"[GoetheGroups] Error extracting post element: {short_error(error)}")

            if scroll_num < self.max_scrolls:
                search_page.scroll_results(1)

        print(f"[GoetheGroups] Search finished for '{query}'. Opportunities found: {len(discovered)}")
        return discovered

    def scan_all_groups(self) -> list[dict]:
        """Scan all enabled Goethe groups across all configured search interests."""
        enabled_groups = get_enabled_goethe_groups(self.config_file)
        if not enabled_groups:
            print("[GoetheGroups] No enabled Goethe groups found in configuration.")
            return []

        all_opportunities = []

        for group in enabled_groups:
            for interest in group.search_interests:
                try:
                    opps = self.search_group_query(group, interest)
                    all_opportunities.extend(opps)
                except Exception as error:
                    print(f"[GoetheGroups] Exception searching {group.name} for '{interest}': {short_error(error)}")
                    if self.browser and is_dead_browser_session(error):
                        try:
                            self.browser = restart_driver(self.browser)
                        except Exception as restart_err:
                            print(f"[GoetheGroups] Could not restart browser: {short_error(restart_err)}")

        return all_opportunities

    def run_continuous(self, start_time: float | None = None) -> None:
        """Continuous polling loop for Goethe groups scanning."""
        if start_time is None:
            start_time = time.time()

        beep()
        if self.browser is None:
            self.browser = create_driver()

        login_if_needed(self.browser)

        print("[GoetheGroups] Continuous scanner started.")

        while True:
            cycle_started = time.time()
            opps = self.scan_all_groups()
            cycle_duration = time.time() - cycle_started

            print(
                f"[GoetheGroups] Cycle completed in {cycle_duration:.1f}s. "
                f"New opportunities: {len(opps)}"
            )
            print_running_time(start_time)
            print(f"[GoetheGroups] Waiting {self.poll_interval}s before next pass...")
            time.sleep(self.poll_interval)


def main():
    scanner = GoetheGroupScanner()
    try:
        scanner.run_continuous()
    except KeyboardInterrupt:
        print("\n[GoetheGroups] Scanner stopped by user.")


if __name__ == "__main__":
    main()
