"""Backward-compatible entrypoint for the Facebook opportunity scanner.

The implementation is split across focused modules in this package. This module keeps
legacy imports such as ``from search_interested import SearchInterested as scanner``
working, including tests that patch file-path globals here.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from search_interested import group_queue as _group_queue
from search_interested import results as _results
from search_interested import settings as _settings
from search_interested.facebook_urls import (
    clean_facebook_url,
    extract_parent_post_url,
    is_facebook_comment_url,
    is_facebook_post_url,
)
from search_interested.notifier import beep
from search_interested.opportunity_engine import (
    analyze_opportunity,
    calculate_opportunity_score,
    classify_opportunity,
    flatten_signal_names,
    has_obvious_provider_context,
    has_strong_intent,
    is_fresh_opportunity_timestamp,
    is_interested_only,
    total_signal_weight,
)
from search_interested.results import (
    alert_opportunity,
    alert_user,
    beep_count_for_freshness,
    build_match_info,
    build_opportunity,
    build_opportunity_key,
    build_post_key,
    display_match,
    display_opportunity,
)
from search_interested.text_utils import (
    first_line,
    format_age,
    indent_text,
    limit_text,
    normalize_multiline,
    normalize_space,
    print_running_time,
    short_error,
)
from search_interested.timestamps import (
    RELATIVE_TIME_FULL_PATTERN,
    age_seconds_from_datetime,
    build_timestamp_info,
    choose_timestamp_from_candidates,
    classify_freshness,
    is_plausible_timestamp_candidate,
    normalize_absolute_timestamp,
    parse_absolute_timestamp_age,
    parse_post_age,
    parse_relative_timestamp_age,
    parse_timestamp_age,
    parse_timestamp_candidate,
    parse_today_or_yesterday_age,
    try_parse_datetime,
)

PACKAGE_DIRECTORY = _settings.PACKAGE_DIRECTORY
PROJECT_DIRECTORY = _settings.PROJECT_DIRECTORY
PERSONAL_TOUCH_DIRECTORY = _settings.PERSONAL_TOUCH_DIRECTORY
GROUP_LIST_FILE = _settings.GROUP_LIST_FILE
INACTIVE_GROUPS_FILE = _settings.INACTIVE_GROUPS_FILE
RESULTS_FILE = _settings.RESULTS_FILE
USER_DATA_DIRECTORY = _settings.USER_DATA_DIRECTORY
CHROME_PROFILE_DIRECTORY = _settings.CHROME_PROFILE_DIRECTORY
CHROME_DRIVER_PATH = _settings.CHROME_DRIVER_PATH
FACEBOOK_HOME = _settings.FACEBOOK_HOME
HEADLESS = _settings.HEADLESS
WAIT_SECONDS = _settings.WAIT_SECONDS
LOGIN_WAIT_SECONDS = _settings.LOGIN_WAIT_SECONDS
POST_WAIT_SECONDS = _settings.POST_WAIT_SECONDS
SCROLLS_PER_GROUP = _settings.SCROLLS_PER_GROUP
SCROLL_PAUSE_SECONDS = _settings.SCROLL_PAUSE_SECONDS
GROUP_RETRY_PAUSE_SECONDS = _settings.GROUP_RETRY_PAUSE_SECONDS
MAX_GROUP_FAILURES_BEFORE_ROTATE = _settings.MAX_GROUP_FAILURES_BEFORE_ROTATE
DEAD_BROWSER_ERROR_MARKERS = _settings.DEAD_BROWSER_ERROR_MARKERS
VERY_RECENT_MAX_SECONDS = _settings.VERY_RECENT_MAX_SECONDS
RECENT_MAX_SECONDS = _settings.RECENT_MAX_SECONDS
OLDER_BUT_RELEVANT_MAX_SECONDS = _settings.OLDER_BUT_RELEVANT_MAX_SECONDS
ACTIVE_GROUP_MAX_AGE_SECONDS = _settings.ACTIVE_GROUP_MAX_AGE_SECONDS
MIN_RECENT_POSTS_FOR_ACTIVE = _settings.MIN_RECENT_POSTS_FOR_ACTIVE
ACTIVITY_POST_SAMPLE_LIMIT = _settings.ACTIVITY_POST_SAMPLE_LIMIT
MIN_ACTIVITY_TEXT_CHARS = _settings.MIN_ACTIVITY_TEXT_CHARS
BEEP_PAUSE_SECONDS = _settings.BEEP_PAUSE_SECONDS
MAX_POST_TEXT_DISPLAY_CHARS = _settings.MAX_POST_TEXT_DISPLAY_CHARS
SAVE_QUALITY_LEVELS = _settings.SAVE_QUALITY_LEVELS
ALERT_QUALITY_LEVELS = _settings.ALERT_QUALITY_LEVELS
STRONG_OPPORTUNITY_THRESHOLD = _settings.STRONG_OPPORTUNITY_THRESHOLD
POSSIBLE_OPPORTUNITY_THRESHOLD = _settings.POSSIBLE_OPPORTUNITY_THRESHOLD
TIMESTAMP_CONFLICT_TOLERANCE_SECONDS = _settings.TIMESTAMP_CONFLICT_TOLERANCE_SECONDS
POST_CONTAINER_XPATHS = _settings.POST_CONTAINER_XPATHS
POST_WAIT_XPATH = _settings.POST_WAIT_XPATH
POST_ACTION_XPATH = _settings.POST_ACTION_XPATH
POST_TEXT_XPATHS = _settings.POST_TEXT_XPATHS
POST_URL_XPATHS = _settings.POST_URL_XPATHS
COMMENT_URL_XPATHS = _settings.COMMENT_URL_XPATHS
POST_TIMESTAMP_XPATHS = _settings.POST_TIMESTAMP_XPATHS
COMMENT_TIMESTAMP_XPATHS = _settings.COMMENT_TIMESTAMP_XPATHS
TRACKING_QUERY_PARAMS = _settings.TRACKING_QUERY_PARAMS


def _browser_session():
    from search_interested import browser_session

    return browser_session


def _facebook_dom():
    from search_interested import facebook_dom

    return facebook_dom


def _scanner_engine():
    from search_interested import scanner_engine

    return scanner_engine


def _call(module_factory, function_name, *args, **kwargs):
    return getattr(module_factory(), function_name)(*args, **kwargs)


def close_driver(*args, **kwargs):
    return _call(_browser_session, "close_driver", *args, **kwargs)


def create_chrome_options(*args, **kwargs):
    return _call(_browser_session, "create_chrome_options", *args, **kwargs)


def create_driver(*args, **kwargs):
    return _call(_browser_session, "create_driver", *args, **kwargs)


def is_dead_browser_session(*args, **kwargs):
    return _call(_browser_session, "is_dead_browser_session", *args, **kwargs)


def login_if_needed(*args, **kwargs):
    return _call(_browser_session, "login_if_needed", *args, **kwargs)


def restart_driver(*args, **kwargs):
    return _call(_browser_session, "restart_driver", *args, **kwargs)


def wait_for_page_ready(*args, **kwargs):
    return _call(_browser_session, "wait_for_page_ready", *args, **kwargs)


def page_start(*args, **kwargs):
    return _call(_facebook_dom, "page_start", *args, **kwargs)


def scroll_down(*args, **kwargs):
    return _call(_facebook_dom, "scroll_down", *args, **kwargs)


def wait_for_posts(*args, **kwargs):
    return _call(_facebook_dom, "wait_for_posts", *args, **kwargs)


def find_post_containers(*args, **kwargs):
    return _call(_facebook_dom, "find_post_containers", *args, **kwargs)


def remove_nested_containers(*args, **kwargs):
    return _call(_facebook_dom, "remove_nested_containers", *args, **kwargs)


def extract_content_type(*args, **kwargs):
    return _call(_facebook_dom, "extract_content_type", *args, **kwargs)


def extract_author(*args, **kwargs):
    return _call(_facebook_dom, "extract_author", *args, **kwargs)


def is_plausible_author_name(*args, **kwargs):
    return _call(_facebook_dom, "is_plausible_author_name", *args, **kwargs)


def extract_content_text(*args, **kwargs):
    return _call(_facebook_dom, "extract_content_text", *args, **kwargs)


def extract_post_text(*args, **kwargs):
    return _call(_facebook_dom, "extract_post_text", *args, **kwargs)


def extract_comment_text(*args, **kwargs):
    return _call(_facebook_dom, "extract_comment_text", *args, **kwargs)


def clean_fallback_content_text(*args, **kwargs):
    return _call(_facebook_dom, "clean_fallback_content_text", *args, **kwargs)


def is_noise_content_line(*args, **kwargs):
    return _call(_facebook_dom, "is_noise_content_line", *args, **kwargs)


def extract_post_url(*args, **kwargs):
    return _call(_facebook_dom, "extract_post_url", *args, **kwargs)


def extract_comment_url(*args, **kwargs):
    return _call(_facebook_dom, "extract_comment_url", *args, **kwargs)


def extract_content_url(*args, **kwargs):
    return _call(_facebook_dom, "extract_content_url", *args, **kwargs)


def extract_post_timestamp(*args, **kwargs):
    return _call(_facebook_dom, "extract_post_timestamp", *args, **kwargs)


def extract_timestamp(*args, **kwargs):
    return _call(_facebook_dom, "extract_timestamp", *args, **kwargs)


def timestamp_info_from_element(*args, **kwargs):
    return _call(_facebook_dom, "timestamp_info_from_element", *args, **kwargs)


def timestamp_candidates_from_element(*args, **kwargs):
    return _call(_facebook_dom, "timestamp_candidates_from_element", *args, **kwargs)


def read_group_queue_lines():
    return _group_queue.read_group_queue_lines(GROUP_LIST_FILE)


def is_group_queue_entry(line):
    return _group_queue.is_group_queue_entry(line)


def load_group_urls(log=True):
    return _group_queue.load_group_urls(GROUP_LIST_FILE, log=log)


def get_current_group(group_urls=None):
    return _group_queue.get_current_group(group_urls, group_list_file=GROUP_LIST_FILE)


def save_group_queue(queue_lines):
    return _group_queue.save_group_queue(queue_lines, GROUP_LIST_FILE)


def rotate_current_group(completed_group_url):
    return _group_queue.rotate_current_group(completed_group_url, GROUP_LIST_FILE)


def load_inactive_group_urls():
    return _group_queue.load_inactive_group_urls(INACTIVE_GROUPS_FILE)


def append_inactive_group(group_url):
    return _group_queue.append_inactive_group(group_url, INACTIVE_GROUPS_FILE)


def move_group_to_inactive(group_url):
    return _group_queue.move_group_to_inactive(
        group_url,
        group_list_file=GROUP_LIST_FILE,
        inactive_groups_file=INACTIVE_GROUPS_FILE,
    )


def save_opportunity(opportunity):
    return _results.save_opportunity(opportunity, results_file=RESULTS_FILE)


def save_match(match_info):
    return save_opportunity(match_info)


def load_seen_opportunity_keys():
    return _results.load_seen_opportunity_keys(results_file=RESULTS_FILE)


def format_opportunity_record(opportunity):
    return _results.format_opportunity_record(
        opportunity,
        max_text_chars=MAX_POST_TEXT_DISPLAY_CHARS,
    )


def format_match_record(match_info):
    return format_opportunity_record(match_info)


def check_group_activity(*args, **kwargs):
    return _call(_scanner_engine, "check_group_activity", *args, **kwargs)


def is_meaningful_activity_text(*args, **kwargs):
    return _call(_scanner_engine, "is_meaningful_activity_text", *args, **kwargs)


def scan_loaded_posts(*args, **kwargs):
    return _call(_scanner_engine, "scan_loaded_posts", *args, **kwargs)


def scan_group(*args, **kwargs):
    return _call(_scanner_engine, "scan_group", *args, **kwargs)


def run_continuous_scanner(*args, **kwargs):
    return _call(_scanner_engine, "run_continuous_scanner", *args, **kwargs)


def get_group_name(*args, **kwargs):
    return _call(_scanner_engine, "get_group_name", *args, **kwargs)


def main():
    return _scanner_engine().main()


if __name__ == "__main__":
    main()
