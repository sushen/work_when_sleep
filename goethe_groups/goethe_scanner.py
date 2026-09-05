"""Continuous monitoring scanner for Goethe Group Member Requests page."""

from __future__ import annotations

import time
from typing import Sequence

from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)

from Pages.FacebookGroupMemberRequestsPage import FacebookGroupMemberRequestsPage
from goethe_groups.goethe_config import GoetheGroupConfig, get_enabled_goethe_groups
from search_interested.browser_session import (
    create_driver,
    is_dead_browser_session,
    login_if_needed,
    restart_driver,
    wait_for_page_ready,
)
from search_interested.notifier import beep
from search_interested.opportunity_engine import analyze_opportunity
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
    GOETHE_IMMEDIATE_ALERT_SECONDS,
    GOETHE_MEMBER_REQUESTS_URL,
)
from search_interested.text_utils import print_running_time, short_error


def normalize_member_request(
    raw_request: dict,
    detected_at: float | None = None,
) -> dict:
    """Normalize raw member request data into standard item dictionary."""
    if detected_at is None:
        detected_at = time.time()

    group_name = raw_request.get("group_name", "Goethe Group Bangladesh")
    group_url = raw_request.get("group_url", GOETHE_MEMBER_REQUESTS_URL)
    author = raw_request.get("author", "UNKNOWN")
    text = raw_request.get("content_text") or raw_request.get("text", "")
    content_url = raw_request.get("content_url", group_url)
    timestamp_info = raw_request.get("timestamp_info") or {
        "raw": "",
        "age_seconds": None,
        "confidence": "NONE",
        "freshness": "UNKNOWN",
        "source": "unknown",
        "warning": None,
    }

    opportunity_key = build_opportunity_key(
        group_url=group_url,
        content_url=content_url,
        content_type="MEMBER_REQUEST",
        content_text=text,
        timestamp_raw=timestamp_info.get("raw"),
    )

    return {
        "source": "facebook",
        "source_type": "goethe_member_request",
        "community_name": group_name,
        "group_name": group_name,
        "group_url": group_url,
        "author": author,
        "author_name": author,
        "content_type": "MEMBER_REQUEST",
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
    """Monitors Goethe Group Member Requests page in real-time."""

    def __init__(
        self,
        browser=None,
        poll_interval: int = GOETHE_GROUP_POLL_INTERVAL_SECONDS,
        immediate_alert_seconds: int = GOETHE_IMMEDIATE_ALERT_SECONDS,
        target_url: str = GOETHE_MEMBER_REQUESTS_URL,
        config_file=None,
    ):
        self.browser = browser
        self.poll_interval = poll_interval
        self.immediate_alert_seconds = immediate_alert_seconds
        self.target_url = target_url
        self.config_file = config_file
        self.seen_keys = load_seen_opportunity_keys()
        self.alerted_keys: set[str] = set()

    def check_immediate_freshness_alert(self, normalized_item: dict) -> bool:
        """Trigger immediate BEEP if request age <= GOETHE_IMMEDIATE_ALERT_SECONDS (60s)."""
        opportunity_key = normalized_item.get("opportunity_key")
        if not opportunity_key or opportunity_key in self.alerted_keys:
            return False

        age_seconds = normalized_item.get("age_seconds")
        if age_seconds is not None and 0 <= age_seconds <= self.immediate_alert_seconds:
            self.alerted_keys.add(opportunity_key)
            print("=" * 50)
            print("[GOETHE NEW MEMBER REQUEST - FRESH ALERT]")
            print("=" * 50)
            print(f"Group: {normalized_item.get('group_name')}")
            print(f"Author: {normalized_item.get('author')}")
            print(f"Age: {int(age_seconds)} seconds")
            print(f"URL: {normalized_item.get('content_url')}")
            print(f"Details: {normalized_item.get('content_text')}")
            print("=" * 50)
            print("[ALERT] NEW MEMBER REQUEST <= 60s -> BEEP")
            beep()
            return True
        return False

    def process_item(self, normalized_item: dict) -> dict | None:
        """Evaluate member request item, check freshness alert, save and dispatch."""
        opportunity_key = normalized_item["opportunity_key"]

        # Real-time alert check for requests <= 60 seconds
        self.check_immediate_freshness_alert(normalized_item)

        if opportunity_key in self.seen_keys:
            return None

        self.seen_keys.add(opportunity_key)

        timestamp_info = normalized_item.get("timestamp_info", {})
        opportunity_analysis = analyze_opportunity(normalized_item["content_text"])

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
            title=f"Member Request: {normalized_item['author']} ({normalized_item['group_name']})",
            post_id=None,
        )
        opportunity["source_type"] = "goethe_member_request"

        save_opportunity(opportunity)
        alert_opportunity(opportunity)
        display_opportunity(opportunity)
        return opportunity

    def monitor_member_requests(self, page_url: str | None = None) -> list[dict]:
        """Fetch and process visible member requests from the target page."""
        target = page_url or self.target_url
        print(f"[GoetheGroups] Opening Member Requests page: {target}")

        if self.browser is None:
            return []

        page = FacebookGroupMemberRequestsPage(self.browser)

        try:
            page.navigate_to_member_requests(target)
        except Exception as error:
            print(f"[GoetheGroups] Error navigating to {target}: {short_error(error)}")
            return []

        discovered = []
        elements = page.get_visible_member_requests()
        print(f"[GoetheGroups] Found {len(elements)} member request elements.")

        for elem in elements:
            try:
                raw_data = page.extract_member_request_data(elem, group_url=target)
                if not raw_data:
                    continue
                normalized = normalize_member_request(raw_data)
                opp = self.process_item(normalized)
                if opp:
                    discovered.append(opp)
            except StaleElementReferenceException:
                continue
            except Exception as error:
                print(f"[GoetheGroups] Error parsing member request card: {short_error(error)}")

        return discovered

    def run_continuous(self, start_time: float | None = None) -> None:
        """Continuous polling loop over Goethe Group member requests page every 30s."""
        if start_time is None:
            start_time = time.time()

        beep()
        if self.browser is None:
            self.browser = create_driver()

        login_if_needed(self.browser)

        enabled_groups = get_enabled_goethe_groups(self.config_file)
        if enabled_groups:
            target_url = enabled_groups[0].get_member_requests_url()
        else:
            target_url = self.target_url

        print(f"[GoetheGroups] Continuous scanner monitoring Member Requests: {target_url}")

        while True:
            cycle_started = time.time()
            try:
                opps = self.monitor_member_requests(target_url)
                cycle_duration = time.time() - cycle_started
                print(
                    f"[GoetheGroups] Pass finished in {cycle_duration:.1f}s. "
                    f"New member requests processed: {len(opps)}"
                )
            except Exception as error:
                print(f"[GoetheGroups] Error in member request cycle: {short_error(error)}")
                if self.browser and is_dead_browser_session(error):
                    try:
                        self.browser = restart_driver(self.browser)
                    except Exception as restart_err:
                        print(f"[GoetheGroups] Restart browser error: {short_error(restart_err)}")

            print_running_time(start_time)
            print(f"[GoetheGroups] Waiting {self.poll_interval}s before reloading member requests page...")
            time.sleep(self.poll_interval)


def main():
    scanner = GoetheGroupScanner()
    try:
        scanner.run_continuous()
    except KeyboardInterrupt:
        print("\n[GoetheGroups] Member requests scanner stopped by user.")


if __name__ == "__main__":
    main()
