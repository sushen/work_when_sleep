"""Continuous real-time monitor for Goethe Group Member Requests page."""

from __future__ import annotations

import time
import urllib.request

# Goethe Member Requests Configuration
CHECK_INTERVAL_SECONDS = 60
MEMBER_REQUEST_ALERT_WINDOW_MINUTES = 2
ALERT_WINDOW_SECONDS = MEMBER_REQUEST_ALERT_WINDOW_MINUTES * 60

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
from search_interested.settings import (
    GOETHE_GROUP_POLL_INTERVAL_SECONDS,
    GOETHE_MEMBER_REQUESTS_URL,
)
from search_interested.text_utils import format_age, short_error


def format_runtime(seconds: float) -> str:
    """Format seconds into HH:MM:SS string representation."""
    total_secs = max(0, int(seconds))
    hours, remainder = divmod(total_secs, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def is_internet_connected(timeout: float = 3.0) -> bool:
    """Check whether internet connectivity is available."""
    try:
        urllib.request.urlopen("https://1.1.1.1", timeout=timeout)
        return True
    except Exception:
        try:
            urllib.request.urlopen("https://www.google.com", timeout=timeout)
            return True
        except Exception:
            return False


def normalize_member_request(
    raw_request: dict,
    detected_at: float | None = None,
) -> dict:
    """Normalize raw member request data into standard dictionary."""
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
        request_id = f"url:{content_url}"
    else:
        request_id = f"fb:member_req:{group_url}:{author}"

    return {
        "request_id": request_id,
        "request_key": request_id,
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
        "age_seconds": timestamp_info.get("age_seconds"),
        "timestamp_raw": timestamp_info.get("raw"),
        "discovered_at": detected_at,
    }


class GoetheGroupScanner:
    """Monitors Goethe Group Member Requests page in real-time."""

    def __init__(
        self,
        browser=None,
        poll_interval: int = 60,
        immediate_alert_seconds: int | None = None,
        target_url: str = GOETHE_MEMBER_REQUESTS_URL,
        config_file=None,
    ):
        self.browser = browser
        self.poll_interval = poll_interval
        self.immediate_alert_seconds = (
            immediate_alert_seconds if immediate_alert_seconds is not None else ALERT_WINDOW_SECONDS
        )
        self.target_url = target_url
        self.config_file = config_file
        self.alerted_keys: set[str] = set()
        self.internet_was_down: bool = False

    def monitor_member_requests(self, page_url: str | None = None) -> list[dict]:
        """Fetch and check ONLY the newest member request card from target page."""
        target = page_url or self.target_url
        print("[GoetheGroups] Reloading Member Requests page...")

        if self.browser is None:
            return []

        page = FacebookGroupMemberRequestsPage(self.browser)

        max_error_retries = 3
        for attempt in range(max_error_retries):
            try:
                page.navigate_to_member_requests(target)
                if page.is_technical_error_page():
                    print("[GoetheGroups] Facebook temporary technical error detected.")
                    print("[GoetheGroups] Reloading immediately...")
                    time.sleep(3)
                    continue
                if attempt > 0:
                    print("[GoetheGroups] Member Requests page recovered.")
                break
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
            age_display = raw_age or format_age(age_seconds)
            age_sec_str = f"\nage_seconds={age_seconds}"
        else:
            age_display = raw_age or "unknown age"
            age_sec_str = ""

        print(f"[GoetheGroups] Newest request:\nmember={author}\nage={age_display}{age_sec_str}")
        alert_window_minutes = MEMBER_REQUEST_ALERT_WINDOW_MINUTES
        alert_window_seconds = self.immediate_alert_seconds or ALERT_WINDOW_SECONDS
        print(f"[GoetheGroups] Alert window: {alert_window_minutes} minutes ({alert_window_seconds} seconds)")

        request_id = normalized.get("request_id")
        is_already_alerted = request_id in self.alerted_keys

        if is_already_alerted:
            print("[GoetheGroups] Request already alerted. No alert.")
        elif age_seconds is None or age_seconds > alert_window_seconds or age_seconds < 0:
            print(f"[GoetheGroups] Request older than {alert_window_seconds} seconds.")
            print("[GoetheGroups] Request is outside alert window.")
            print("[GoetheGroups] No alert.")
        else:
            print("[GoetheGroups] Request is within alert window.")
            print("[GoetheGroups] NEW MEMBER REQUEST DETECTED")
            print(f"[GoetheGroups] Request age <= {alert_window_seconds} seconds")
            print("[GoetheGroups] BEEP")
            beep()
            self.alerted_keys.add(request_id)
            print("[GoetheGroups] Request marked as alerted.")

        return [normalized]

    def check_internet_status(self) -> None:
        """Check internet connection, handle outage alert and recovery loop."""
        if not is_internet_connected():
            if not self.internet_was_down:
                print("\n[INTERNET] CONNECTION LOST")
                beep()
                self.internet_was_down = True

            while not is_internet_connected():
                time.sleep(5)

            print("\n[INTERNET] CONNECTION RESTORED")
            print("[GoetheGroups] Resuming Member Requests monitoring...")
            self.internet_was_down = False

    def run_continuous(self, start_time: float | None = None) -> None:
        """Continuous scheduled monitoring loop over Goethe Group Member Requests page."""
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
        print(f"[GoetheGroups] Member request alert window: {MEMBER_REQUEST_ALERT_WINDOW_MINUTES} minutes")
        print(f"[GoetheGroups] Alert threshold: {ALERT_WINDOW_SECONDS} seconds")

        check_counter = 0
        next_check = time.time()

        while True:
            self.check_internet_status()

            check_counter += 1
            cycle_started = time.time()
            print(f"\n[GoetheGroups] CHECK #{check_counter}")

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
            total_runtime = time.time() - start_time
            print(f"[GoetheGroups] Check completed in {cycle_duration:.1f}s")
            print(f"[GoetheGroups] Total runtime: {format_runtime(total_runtime)}")

            next_check += self.poll_interval
            sleep_time = next_check - time.time()
            if sleep_time > 0:
                print("[GoetheGroups] Waiting until next 1-minute check...")
                time.sleep(sleep_time)
            else:
                next_check = time.time()


def main():
    scanner = GoetheGroupScanner()
    try:
        scanner.run_continuous()
    except KeyboardInterrupt:
        print("\n[GoetheGroups] Member requests scanner stopped by user.")


if __name__ == "__main__":
    main()
