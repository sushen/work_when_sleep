"""High-level scanner workflow orchestration."""

from __future__ import annotations

import time
from urllib.parse import urlparse

from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)

from .browser_session import (
    create_driver,
    is_dead_browser_session,
    login_if_needed,
    restart_driver,
    wait_for_page_ready,
)
from .facebook_dom import (
    extract_author,
    extract_content_text,
    extract_content_type,
    extract_content_url,
    extract_timestamp,
    find_post_containers,
    page_start,
    scroll_down,
    wait_for_posts,
)
from .group_lifecycle import GroupLifecycleManager
from .group_queue import (
    get_current_group,
    load_group_urls,
    move_group_to_inactive,
    rotate_current_group,
)
from .notifier import beep
from .opportunity_engine import analyze_opportunity, is_fresh_opportunity_timestamp
from .results import (
    alert_opportunity,
    build_opportunity,
    build_opportunity_key,
    display_opportunity,
    load_seen_opportunity_keys,
    save_opportunity,
)
from .settings import (
    ACTIVE_GROUP_MAX_AGE_SECONDS,
    ACTIVITY_POST_SAMPLE_LIMIT,
    GROUP_RETRY_PAUSE_SECONDS,
    MAX_GROUP_FAILURES_BEFORE_ROTATE,
    MIN_ACTIVITY_TEXT_CHARS,
    MIN_RECENT_POSTS_FOR_ACTIVE,
    SCROLLS_PER_GROUP,
)
from .text_utils import format_age, normalize_space, print_running_time, short_error


def check_group_activity(browser, group_name, group_url):
    posts = find_post_containers(browser)
    known_ages = []
    recent_posts = 0
    meaningful_posts = 0
    unknown_timestamps = 0

    for post in posts[:ACTIVITY_POST_SAMPLE_LIMIT]:
        try:
            content_type = extract_content_type(post)
            if content_type != "POST":
                continue

            author = extract_author(post)
            post_text = extract_content_text(post, content_type, author=author)
            if not is_meaningful_activity_text(post_text):
                continue

            meaningful_posts += 1
            timestamp_info = extract_timestamp(post, content_type)
            age_seconds = timestamp_info["age_seconds"]

            if age_seconds is None:
                unknown_timestamps += 1
                continue

            known_ages.append(age_seconds)
            if age_seconds <= ACTIVE_GROUP_MAX_AGE_SECONDS:
                recent_posts += 1
        except StaleElementReferenceException:
            print("[ERROR] Post became stale during activity check.")
        except WebDriverException as error:
            print(f"[ERROR] Could not check group activity: {short_error(error)}")

    latest_age = min(known_ages) if known_ages else None
    if recent_posts >= MIN_RECENT_POSTS_FOR_ACTIVE:
        status = "ACTIVE"
    elif known_ages and unknown_timestamps == 0:
        status = "INACTIVE"
    else:
        status = "UNKNOWN"

    activity_info = {
        "status": status,
        "latest_age_seconds": latest_age,
        "recent_posts": recent_posts,
        "meaningful_posts": meaningful_posts,
        "known_timestamps": len(known_ages),
        "unknown_timestamps": unknown_timestamps,
    }

    print(
        "[ACTIVITY] "
        f"{group_name} -> {status}; "
        f"recent={recent_posts}, "
        f"known_timestamps={len(known_ages)}, "
        f"unknown_timestamps={unknown_timestamps}, "
        f"latest_age={format_age(latest_age)}"
    )
    return activity_info


def is_meaningful_activity_text(text):
    return len(normalize_space(text)) >= MIN_ACTIVITY_TEXT_CHARS


def scan_loaded_posts(browser, group_name, group_url, seen_posts, opportunities_found=None):
    posts = find_post_containers(browser)
    print(f"[SCAN] {len(posts)} posts detected")

    for post in posts:
        try:
            content_type = extract_content_type(post)
            author = extract_author(post)
            content_text = extract_content_text(post, content_type, author=author)
            if not content_text:
                continue

            content_url = extract_content_url(post, content_type)
            timestamp_info = extract_timestamp(post, content_type)
            content_key = build_opportunity_key(
                group_url=group_url,
                content_url=content_url,
                content_type=content_type,
                content_text=content_text,
                timestamp_raw=timestamp_info["raw"],
            )

            if content_key in seen_posts:
                continue
            seen_posts.add(content_key)

            if not is_fresh_opportunity_timestamp(timestamp_info):
                print(
                    "[TIME] Skipping stale/unknown "
                    f"{content_type.lower()} timestamp: "
                    f"{timestamp_info['raw'] or 'UNKNOWN'} "
                    f"({timestamp_info['freshness']})"
                )
                continue

            opportunity_analysis = analyze_opportunity(content_text)
            if not opportunity_analysis["is_opportunity"]:
                continue

            opportunity = build_opportunity(
                group_name=group_name,
                group_url=group_url,
                content_type=content_type,
                author=author,
                content_text=content_text,
                content_url=content_url,
                timestamp_info=timestamp_info,
                opportunity_analysis=opportunity_analysis,
                opportunity_key=content_key,
            )

            save_opportunity(opportunity)
            alert_opportunity(opportunity)
            display_opportunity(opportunity)
            if opportunities_found is not None:
                opportunities_found.append(opportunity)
        except StaleElementReferenceException:
            print("[ERROR] Post became stale; skipping it.")
        except WebDriverException as error:
            print(f"[ERROR] Could not process post: {short_error(error)}")

    return True


def scan_group(browser, group_url, group_index, group_count, seen_posts):
    print(f"[GROUP {group_index}/{group_count}] Opening group")
    print(f"[GROUP {group_index}/{group_count}] {group_url}")

    browser.get(group_url)
    wait_for_page_ready(browser)
    wait_for_posts(browser)

    group_name = get_group_name(browser, group_url)
    print(f"[GROUP {group_index}/{group_count}] Page loaded: {group_name}")

    page_start(browser)
    activity_info = check_group_activity(browser, group_name, group_url)
    if activity_info["status"] == "INACTIVE":
        print("[GROUP] No meaningful recent activity; moving group to inactive queue.")
        return {
            "success": True,
            "inactive": True,
            "activity": activity_info,
        }

    if activity_info["status"] == "UNKNOWN":
        print("[GROUP] Activity timestamp confidence is unknown; scanning conservatively.")

    opportunities_found = []

    if not scan_loaded_posts(browser, group_name, group_url, seen_posts, opportunities_found):
        return {
            "success": False,
            "inactive": False,
            "activity": activity_info,
            "opportunities": opportunities_found,
        }

    for scroll_number in range(1, SCROLLS_PER_GROUP + 1):
        print(f"[SCAN] Scroll {scroll_number}/{SCROLLS_PER_GROUP}")
        scroll_down(browser)
        if not scan_loaded_posts(browser, group_name, group_url, seen_posts, opportunities_found):
            return {
                "success": False,
                "inactive": False,
                "activity": activity_info,
                "opportunities": opportunities_found,
            }

    return {
        "success": True,
        "inactive": False,
        "activity": activity_info,
        "opportunities": opportunities_found,
    }


def run_continuous_scanner(browser, start_time):
    seen_posts = load_seen_opportunity_keys()
    lifecycle_manager = GroupLifecycleManager()
    group_index = 1
    group_failures = {}

    print("[START] Scanner started")

    while True:
        group_urls = load_group_urls()
        current_group = get_current_group(group_urls)

        if not current_group:
            print("[END] No groups to scan.")
            break

        group_count = len(group_urls)
        if group_index > group_count:
            group_index = 1

        scan_result = {
            "success": False,
            "inactive": False,
            "activity": None,
        }
        success = False
        rotated = False
        moved_to_inactive = False

        try:
            scan_result = scan_group(
                browser=browser,
                group_url=current_group,
                group_index=group_index,
                group_count=group_count,
                seen_posts=seen_posts,
            )
            success = scan_result["success"]
        except TimeoutException as error:
            print(f"[ERROR] Could not load group posts: {short_error(error)}")
        except WebDriverException as error:
            print(f"[ERROR] Could not load group: {short_error(error)}")
            if is_dead_browser_session(error):
                try:
                    browser = restart_driver(browser)
                except WebDriverException as restart_error:
                    print(f"[ERROR] Could not restart Chrome: {short_error(restart_error)}")

        # Integration helper call: update group lifecycle stats & prune inactive groups after each scan
        if success:
            opportunities = scan_result.get("opportunities", [])
            lifecycle_manager.on_group_scanned(current_group, opportunities)

        if success and scan_result["inactive"]:
            group_failures.pop(current_group, None)
            moved_to_inactive = move_group_to_inactive(current_group)
            if moved_to_inactive:
                next_group = get_current_group()
                if next_group:
                    print("[QUEUE] Next group:")
                    print(f"    {next_group}")
            else:
                print("[QUEUE] Inactive group was not removed; it remains first.")
        elif success:
            group_failures.pop(current_group, None)
            rotated = rotate_current_group(current_group)
            if rotated:
                next_group = get_current_group()
                if next_group:
                    print("[QUEUE] Next group:")
                    print(f"    {next_group}")
            else:
                print("[QUEUE] Current group was not rotated; it remains first.")
        else:
            failure_count = group_failures.get(current_group, 0) + 1
            group_failures[current_group] = failure_count
            print(
                "[GROUP] Scan failed "
                f"({failure_count}/{MAX_GROUP_FAILURES_BEFORE_ROTATE})."
            )

            if failure_count >= MAX_GROUP_FAILURES_BEFORE_ROTATE:
                print("[QUEUE] Too many failures; moving current group to bottom.")
                rotated = rotate_current_group(current_group)
                if rotated:
                    group_failures.pop(current_group, None)
                    next_group = get_current_group()
                    if next_group:
                        print("[QUEUE] Next group:")
                        print(f"    {next_group}")
                else:
                    print("[QUEUE] Current group was not rotated; it remains first.")
            else:
                print("[GROUP] Current group remains first for retry.")
                print(f"[WAIT] Continuing after {GROUP_RETRY_PAUSE_SECONDS} seconds.")
                time.sleep(GROUP_RETRY_PAUSE_SECONDS)

        print_running_time(start_time)
        print("[SCAN] Continuing...")
        if rotated or moved_to_inactive:
            group_index = (group_index % group_count) + 1


def get_group_name(browser, group_url):
    title = normalize_space(browser.title)
    if title and title.lower() != "facebook":
        return title.replace(" | Facebook", "")

    path_parts = [part for part in urlparse(group_url).path.split("/") if part]
    if path_parts:
        return path_parts[-1]

    return group_url


def main():
    start_time = time.time()
    print("[START] This script started " + time.ctime())
    beep()

    browser = create_driver()
    login_if_needed(browser)

    try:
        run_continuous_scanner(browser, start_time)
    except KeyboardInterrupt:
        print("\n[STOP] Scanner stopped by user.")

    end_time = time.time()
    print("\n[END] This script ended " + time.ctime())
    total_running_time = end_time - start_time
    print(f"[TIME] This script ran for {int(total_running_time)} seconds.")
    print(f"[TIME] This script ran for {int(total_running_time / 60)} minutes.")
