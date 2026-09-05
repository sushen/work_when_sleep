"""Unit and integration tests for Goethe Facebook Group Member Requests scanner."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from selenium.common.exceptions import StaleElementReferenceException

from Pages.FacebookGroupMemberRequestsPage import FacebookGroupMemberRequestsPage
from goethe_groups.goethe_config import (
    GoetheGroupConfig,
    get_enabled_goethe_groups,
    load_goethe_groups_config,
)
from goethe_groups.goethe_scanner import (
    GoetheGroupScanner,
    format_runtime,
    normalize_member_request,
)
from search_interested.settings import ALERT_WINDOW_SECONDS, MEMBER_REQUEST_ALERT_WINDOW_MINUTES
from search_interested.facebook_dom import extract_timestamp
from search_interested.timestamps import parse_relative_timestamp_age


def test_goethe_config_loading_member_requests(tmp_path: Path):
    config_file = tmp_path / "test_goethe.json"
    data = [
        {
            "name": "Goethe Group Bangladesh",
            "url": "https://www.facebook.com/groups/goethebd",
            "member_requests_url": "https://www.facebook.com/groups/goethebd/member-requests",
            "enabled": True,
        }
    ]
    config_file.write_text(json.dumps(data), encoding="utf-8")

    all_configs = load_goethe_groups_config(config_file)
    assert len(all_configs) == 1
    assert all_configs[0].name == "Goethe Group Bangladesh"
    assert (
        all_configs[0].get_member_requests_url()
        == "https://www.facebook.com/groups/goethebd/member-requests"
    )


def test_format_runtime():
    assert format_runtime(0) == "00:00:00"
    assert format_runtime(63) == "00:01:03"
    assert format_runtime(3665) == "01:01:05"


def test_parse_relative_timestamp_a_few_seconds_ago():
    age = parse_relative_timestamp_age("a few seconds ago")
    assert age is not None
    assert 0 <= age <= 60

    about_min_age = parse_relative_timestamp_age("about a minute ago")
    assert about_min_age == 60


def test_member_request_alert_window_default_is_two_minutes():
    assert MEMBER_REQUEST_ALERT_WINDOW_MINUTES == 2
    assert ALERT_WINDOW_SECONDS == 120


def test_normalize_member_request():
    raw_req = {
        "group_name": "Goethe Group Bangladesh",
        "group_url": "https://www.facebook.com/groups/goethebd/member-requests",
        "content_text": "Answers: 1. Preparing for Goethe A1. 2. Yes.",
        "author": "Rahim Khan",
        "content_type": "MEMBER_REQUEST",
        "content_url": "https://www.facebook.com/user/100012345",
        "timestamp_info": {
            "raw": "45 secs ago",
            "age_seconds": 45,
            "confidence": "HIGH",
            "freshness": "VERY_RECENT",
            "source": "dom_post_url",
            "warning": None,
        },
    }

    normalized = normalize_member_request(raw_req, detected_at=1000.0)

    assert normalized["source"] == "facebook"
    assert normalized["source_type"] == "goethe_member_request"
    assert normalized["group_name"] == "Goethe Group Bangladesh"
    assert normalized["author"] == "Rahim Khan"
    assert normalized["age_seconds"] == 45


def test_member_request_timestamp_is_extracted_from_card_text():
    card = MagicMock()
    timestamp_element = MagicMock()
    timestamp_element.text = "Requested\na few seconds ago"
    timestamp_element.get_attribute.return_value = ""
    card.find_elements.return_value = [timestamp_element]

    timestamp_info = extract_timestamp(card, "MEMBER_REQUEST")

    assert timestamp_info["raw"] == "a few seconds ago"
    assert timestamp_info["age_seconds"] == 10


def test_first_request_a_few_seconds_ago_beep():
    mock_browser = MagicMock()
    scanner = GoetheGroupScanner(browser=mock_browser)

    mock_raw_data = {
        "group_name": "Goethe Group Bangladesh",
        "group_url": "https://www.facebook.com/groups/goethebd/member-requests",
        "author": "Siam Ahmed",
        "content_text": "Requested a few seconds ago",
        "content_url": "https://www.facebook.com/user/siam_123",
        "timestamp_info": {
            "raw": "a few seconds ago",
            "age_seconds": 10,
            "confidence": "HIGH",
            "freshness": "VERY_RECENT",
            "source": "dom_timestamp",
        },
    }

    with patch.object(FacebookGroupMemberRequestsPage, "navigate_to_member_requests"), patch.object(
        FacebookGroupMemberRequestsPage, "get_first_member_request", return_value=mock_raw_data
    ), patch.object(
        FacebookGroupMemberRequestsPage, "is_technical_error_page", return_value=False
    ), patch("goethe_groups.goethe_scanner.beep") as mock_beep:
        scanner.monitor_member_requests()
        mock_beep.assert_called_once()


def test_first_request_7_minutes_old_no_beep():
    mock_browser = MagicMock()
    scanner = GoetheGroupScanner(browser=mock_browser)

    mock_raw_data = {
        "group_name": "Goethe Group Bangladesh",
        "group_url": "https://www.facebook.com/groups/goethebd/member-requests",
        "author": "John",
        "content_text": "Need A1 info",
        "content_url": "https://www.facebook.com/user/john_1",
        "timestamp_info": {
            "raw": "7 minutes ago",
            "age_seconds": 420,
            "confidence": "HIGH",
            "freshness": "RECENT",
            "source": "dom_timestamp",
        },
    }

    with patch.object(FacebookGroupMemberRequestsPage, "navigate_to_member_requests"), patch.object(
        FacebookGroupMemberRequestsPage, "get_first_member_request", return_value=mock_raw_data
    ), patch.object(
        FacebookGroupMemberRequestsPage, "is_technical_error_page", return_value=False
    ), patch("goethe_groups.goethe_scanner.beep") as mock_beep:
        scanner.monitor_member_requests()
        mock_beep.assert_not_called()


def test_first_request_30_seconds_old_and_new_beep():
    mock_browser = MagicMock()
    scanner = GoetheGroupScanner(browser=mock_browser)

    mock_raw_data = {
        "group_name": "Goethe Group Bangladesh",
        "group_url": "https://www.facebook.com/groups/goethebd/member-requests",
        "author": "David",
        "content_text": "New request David",
        "content_url": "https://www.facebook.com/user/david_30",
        "timestamp_info": {
            "raw": "30 seconds ago",
            "age_seconds": 30,
            "confidence": "HIGH",
            "freshness": "VERY_RECENT",
            "source": "dom_timestamp",
        },
    }

    with patch.object(FacebookGroupMemberRequestsPage, "navigate_to_member_requests"), patch.object(
        FacebookGroupMemberRequestsPage, "get_first_member_request", return_value=mock_raw_data
    ), patch.object(
        FacebookGroupMemberRequestsPage, "is_technical_error_page", return_value=False
    ), patch("goethe_groups.goethe_scanner.beep") as mock_beep:
        scanner.monitor_member_requests()
        mock_beep.assert_called()


def test_first_request_59_seconds_old_and_new_beep():
    mock_browser = MagicMock()
    scanner = GoetheGroupScanner(browser=mock_browser)

    mock_raw_data = {
        "group_name": "Goethe Group Bangladesh",
        "group_url": "https://www.facebook.com/groups/goethebd/member-requests",
        "author": "Sarah",
        "content_text": "New request Sarah",
        "content_url": "https://www.facebook.com/user/sarah_59",
        "timestamp_info": {
            "raw": "59 seconds ago",
            "age_seconds": 59,
            "confidence": "HIGH",
            "freshness": "VERY_RECENT",
            "source": "dom_timestamp",
        },
    }

    with patch.object(FacebookGroupMemberRequestsPage, "navigate_to_member_requests"), patch.object(
        FacebookGroupMemberRequestsPage, "get_first_member_request", return_value=mock_raw_data
    ), patch.object(
        FacebookGroupMemberRequestsPage, "is_technical_error_page", return_value=False
    ), patch("goethe_groups.goethe_scanner.beep") as mock_beep:
        scanner.monitor_member_requests()
        mock_beep.assert_called()


def test_first_request_61_seconds_old_still_beeps():
    mock_browser = MagicMock()
    scanner = GoetheGroupScanner(browser=mock_browser)

    mock_raw_data = {
        "group_name": "Goethe Group Bangladesh",
        "group_url": "https://www.facebook.com/groups/goethebd/member-requests",
        "author": "Michael",
        "content_text": "Request Michael",
        "content_url": "https://www.facebook.com/user/michael_61",
        "timestamp_info": {
            "raw": "61 seconds ago",
            "age_seconds": 61,
            "confidence": "HIGH",
            "freshness": "VERY_RECENT",
            "source": "dom_timestamp",
        },
    }

    with patch.object(FacebookGroupMemberRequestsPage, "navigate_to_member_requests"), patch.object(
        FacebookGroupMemberRequestsPage, "get_first_member_request", return_value=mock_raw_data
    ), patch.object(
        FacebookGroupMemberRequestsPage, "is_technical_error_page", return_value=False
    ), patch("goethe_groups.goethe_scanner.beep") as mock_beep:
        scanner.monitor_member_requests()
        mock_beep.assert_called_once()


def test_same_request_appears_after_30_seconds_no_second_beep():
    mock_browser = MagicMock()
    scanner = GoetheGroupScanner(browser=mock_browser)

    raw_req_1 = {
        "group_name": "Goethe Group Bangladesh",
        "group_url": "https://www.facebook.com/groups/goethebd/member-requests",
        "author": "David",
        "content_text": "New request David",
        "content_url": "https://www.facebook.com/user/david_30",
        "timestamp_info": {
            "raw": "20 seconds ago",
            "age_seconds": 20,
            "confidence": "HIGH",
            "freshness": "VERY_RECENT",
            "source": "dom_timestamp",
        },
    }

    raw_req_2 = {
        "group_name": "Goethe Group Bangladesh",
        "group_url": "https://www.facebook.com/groups/goethebd/member-requests",
        "author": "David",
        "content_text": "New request David",
        "content_url": "https://www.facebook.com/user/david_30",
        "timestamp_info": {
            "raw": "50 seconds ago",
            "age_seconds": 50,
            "confidence": "HIGH",
            "freshness": "VERY_RECENT",
            "source": "dom_timestamp",
        },
    }

    with patch.object(FacebookGroupMemberRequestsPage, "navigate_to_member_requests"), patch.object(
        FacebookGroupMemberRequestsPage, "is_technical_error_page", return_value=False
    ), patch("goethe_groups.goethe_scanner.beep") as mock_beep:
        with patch.object(
            FacebookGroupMemberRequestsPage, "get_first_member_request", return_value=raw_req_1
        ):
            scanner.monitor_member_requests()
            assert mock_beep.call_count == 1

        with patch.object(
            FacebookGroupMemberRequestsPage, "get_first_member_request", return_value=raw_req_2
        ):
            scanner.monitor_member_requests()
            assert mock_beep.call_count == 1


def test_new_request_appears_after_polling_interval_beep():
    mock_browser = MagicMock()
    scanner = GoetheGroupScanner(browser=mock_browser)

    old_req = {
        "group_name": "Goethe Group Bangladesh",
        "group_url": "https://www.facebook.com/groups/goethebd/member-requests",
        "author": "Old User",
        "content_text": "Old request",
        "content_url": "https://www.facebook.com/user/old_user",
        "timestamp_info": {
            "raw": "10 minutes ago",
            "age_seconds": 600,
            "confidence": "HIGH",
            "freshness": "OLDER",
            "source": "dom_timestamp",
        },
    }

    new_req = {
        "group_name": "Goethe Group Bangladesh",
        "group_url": "https://www.facebook.com/groups/goethebd/member-requests",
        "author": "Brand New User",
        "content_text": "Brand new request",
        "content_url": "https://www.facebook.com/user/brand_new_user",
        "timestamp_info": {
            "raw": "15 seconds ago",
            "age_seconds": 15,
            "confidence": "HIGH",
            "freshness": "VERY_RECENT",
            "source": "dom_timestamp",
        },
    }

    with patch.object(FacebookGroupMemberRequestsPage, "navigate_to_member_requests"), patch.object(
        FacebookGroupMemberRequestsPage, "is_technical_error_page", return_value=False
    ), patch("goethe_groups.goethe_scanner.beep") as mock_beep:
        with patch.object(
            FacebookGroupMemberRequestsPage, "get_first_member_request", return_value=old_req
        ):
            scanner.monitor_member_requests()
            assert mock_beep.call_count == 0

        with patch.object(
            FacebookGroupMemberRequestsPage, "get_first_member_request", return_value=new_req
        ):
            scanner.monitor_member_requests()
            assert mock_beep.call_count == 1


def test_invalid_ui_element_ignored_by_pom():
    driver = MagicMock()
    page = FacebookGroupMemberRequestsPage(driver)

    help_center_card = {
        "author": "Help Center",
        "content_text": "Help Center",
        "timestamp_info": {"raw": "now", "age_seconds": 0},
    }
    real_card = {
        "author": "Siam Ahmed",
        "content_text": "Answers to questions",
        "timestamp_info": {"raw": "10s ago", "age_seconds": 10},
    }

    assert page.is_valid_member_request(help_center_card) is False
    assert page.is_valid_member_request(real_card) is True


def test_member_request_card_xpath_is_valid():
    selector = FacebookGroupMemberRequestsPage.MEMBER_REQUEST_CARDS[1]

    assert ".\\*" not in selector
    assert ".//*" in selector


def test_page_unavailable_at_the_moment_is_detected():
    driver = MagicMock()
    driver.title = ""
    driver.find_element.return_value.text = (
        "This page isn't available at the moment\n"
        "This may be because of a technical error that we're working to fix."
    )
    page = FacebookGroupMemberRequestsPage(driver)

    assert page.is_technical_error_page() is True


def test_facebook_technical_error_page_reloads_immediately():
    mock_browser = MagicMock()
    scanner = GoetheGroupScanner(browser=mock_browser)

    mock_raw_data = {
        "author": "Recovered User",
        "content_text": "Request after recovery",
        "timestamp_info": {"raw": "10s ago", "age_seconds": 10},
    }

    with patch.object(FacebookGroupMemberRequestsPage, "navigate_to_member_requests"), patch.object(
        FacebookGroupMemberRequestsPage,
        "is_technical_error_page",
        side_effect=[True, False],
    ), patch.object(
        FacebookGroupMemberRequestsPage, "get_first_member_request", return_value=mock_raw_data
    ), patch("time.sleep") as mock_sleep, patch("goethe_groups.goethe_scanner.beep"):
        result = scanner.monitor_member_requests()
        assert len(result) == 1
        assert result[0]["author"] == "Recovered User"
        mock_sleep.assert_not_called()


def test_internet_disconnection_and_recovery():
    scanner = GoetheGroupScanner()

    with patch("goethe_groups.goethe_scanner.is_internet_connected", side_effect=[False, True]), patch(
        "goethe_groups.goethe_scanner.beep"
    ) as mock_beep, patch("time.sleep"):
        scanner.check_internet_status()
        mock_beep.assert_called_once()
        assert scanner.internet_was_down is False


def test_empty_request_page_no_crash():
    mock_browser = MagicMock()
    scanner = GoetheGroupScanner(browser=mock_browser)

    with patch.object(FacebookGroupMemberRequestsPage, "navigate_to_member_requests"), patch.object(
        FacebookGroupMemberRequestsPage, "get_first_member_request", return_value=None
    ), patch.object(FacebookGroupMemberRequestsPage, "is_technical_error_page", return_value=False):
        res = scanner.monitor_member_requests()
        assert res == []


def test_scanner_does_not_iterate_hundreds():
    mock_browser = MagicMock()
    scanner = GoetheGroupScanner(browser=mock_browser)

    mock_data = {
        "author": "Single Target",
        "content_text": "Only inspects first request",
        "timestamp_info": {"raw": "5m ago", "age_seconds": 300},
    }

    with patch.object(FacebookGroupMemberRequestsPage, "navigate_to_member_requests"), patch.object(
        FacebookGroupMemberRequestsPage, "get_first_member_request", return_value=mock_data
    ) as mock_get_first, patch.object(
        FacebookGroupMemberRequestsPage, "is_technical_error_page", return_value=False
    ), patch.object(
        FacebookGroupMemberRequestsPage, "get_visible_member_requests"
    ) as mock_get_visible:
        scanner.monitor_member_requests()

        mock_get_first.assert_called_once()
        mock_get_visible.assert_not_called()


def test_normal_scan_completes_fast():
    mock_browser = MagicMock()
    scanner = GoetheGroupScanner(browser=mock_browser)

    mock_data = {
        "author": "Fast User",
        "content_text": "Fast scan test",
        "timestamp_info": {"raw": "30s ago", "age_seconds": 30},
    }

    start_time = time.time()
    with patch.object(FacebookGroupMemberRequestsPage, "navigate_to_member_requests"), patch.object(
        FacebookGroupMemberRequestsPage, "get_first_member_request", return_value=mock_data
    ), patch.object(
        FacebookGroupMemberRequestsPage, "is_technical_error_page", return_value=False
    ), patch("goethe_groups.goethe_scanner.beep"):
        scanner.monitor_member_requests()
    duration = time.time() - start_time

    assert duration < 5.0
