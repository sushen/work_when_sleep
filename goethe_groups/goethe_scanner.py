"""Continuous monitoring scanner for Goethe Group Member Requests page."""

from __future__ import annotations

import time

from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)

from Pages.FacebookGroupMemberRequestsPage import FacebookGroupMemberRequestsPage
from goethe_groups.goethe_config import get_enabled_goethe_groups
from search_interested.browser_session import (
    create_driver,
    is_dead_browser_session,
    login_if_needed,
    restart_driver,
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
from search_interested.text_utils import format_age, print_running_time, short_error


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

    raw_ts = raw_request.get("timestamp_info") or {}
    timestamp_info = {
        "raw": raw_ts.get("raw", ""),
        "age_seconds": raw_ts.get("age_seconds"),
        "confidence": raw_ts.get("confidence", "NONE"),
        "freshness": raw_ts.get("freshness", "UNKNOWN"),
        "source": raw_ts.get("source", "unknown"),
        "warning": raw_ts.get("warning"),
    }

    if content_url and content_url != group_url:
        opportunity_key = f"url:{content_url}"
    else:
        opportunity_key = f"fb:member_req:{group_url}:{author}"

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
            print("[GoetheGroups] NEW REQUEST detected.")
            print(f"[GoetheGroups] Request age <= {self.immediate_alert_seconds} seconds.")
            print("[GoetheGroups] BEEP")
            beep()
            print("[GoetheGroups] Request marked as alerted.")
            return True
        return False

    def process_item(self, normalized_item: dict) -> dict | None:
        """Evaluate member request item, check freshness alert, save and dispatch."""
        opportunity_key = normalized_item["opportunity_key"]

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
        """Fetch and process ONLY the newest member request from the target page."""
        target = page_url or self.target_url
        print("[GoetheGroups] Reloading Member Requests page...")

        if self.browser is None:
            return []

        page = FacebookGroupMemberRequestsPage(self.browser)

        try:
            page.navigate_to_member_requests(target)
        except Exception as error:
            print(f"[GoetheGroups] Error navigating to {target}: {short_error(error)}")
            return []

        print("[GoetheGroups] Waiting for newest member request...")
        raw_data = page.get_first_member_request(group_url=target)
        if not raw_data:
            print("[GoetheGroups] No member requests found.")
            return []

        normalized = normalize_member_request(raw_data)
        author = normalized.get("author", "UNKNOWN")
        age_seconds = normalized.get("age_seconds")
        raw_age = normalized.get("timestamp_raw") or ""

        if age_seconds is not None:
            age_display = format_age(age_seconds)
        else:
            age_display = raw_age or "unknown age"

        print(f"[GoetheGroups] Newest request:\nmember={author}\nage={age_display}")

        opportunity_key = normalized.get("opportunity_key")
        is_already_alerted = opportunity_key in self.alerted_keys

        if is_already_alerted:
            print("[GoetheGroups] Request already alerted. No alert.")
        elif age_seconds is None or age_seconds > self.immediate_alert_seconds or age_seconds < 0:
            print(f"[GoetheGroups] Request is older than {self.immediate_alert_seconds} seconds. No alert.")
        else:
            self.check_immediate_freshness_alert(normalized)

        opp = self.process_item(normalized)
        return [opp] if opp else []

    def run_continuous(self, start_time: float | None = None) -> None:
        """Continuous polling loop over Goethe Group member requests page every 30s."""
        if start_time is None:
            start_time = time.time()

        if self.browser is None:
            self.browser = create_driver()

        login_if_needed(self.browser)

        enabled_groups = get_enabled_goethe_groups(self.config_file)
        if enabled_groups:
            target_url = enabled_groups[0].get_member_requests_url()
        else:
            target_url = self.target_url

        print(f"[GoetheGroups] Starting continuous Member Requests monitor:\n{target_url}")

        while True:
            cycle_started = time.time()
            try:
                self.monitor_member_requests(target_url)
            except Exception as error:
                print(f"[GoetheGroups] Error in member request cycle: {short_error(error)}")
                if self.browser and is_dead_browser_session(error):
                    try:
                        self.browser = restart_driver(self.browser)
                    except Exception as restart_err:
                        print(f"[GoetheGroups] Restart browser error: {short_error(restart_err)}")

            cycle_duration = time.time() - cycle_started
            print(f"[GoetheGroups] Scan completed in {cycle_duration:.1f}s")
            print(f"[GoetheGroups] Waiting {self.poll_interval}s...")
            time.sleep(self.poll_interval)


def main():
    scanner = GoetheGroupScanner()
    try:
        scanner.run_continuous()
    except KeyboardInterrupt:
        print("\n[GoetheGroups] Member requests scanner stopped by user.")


if __name__ == "__main__":
    main()
