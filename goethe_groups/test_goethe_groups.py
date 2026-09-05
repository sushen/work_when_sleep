"""Unit and integration tests for Goethe Facebook Group Member Requests scanner."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from goethe_groups.goethe_config import GoetheGroupConfig, get_enabled_goethe_groups, load_goethe_groups_config
from goethe_groups.goethe_scanner import GoetheGroupScanner, normalize_member_request


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
    assert all_configs[0].get_member_requests_url() == "https://www.facebook.com/groups/goethebd/member-requests"


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


def test_freshness_beep_alert_60_seconds():
    scanner = GoetheGroupScanner(browser=None)

    fresh_item = {
        "group_name": "Goethe Group Bangladesh",
        "author": "Rahim Khan",
        "age_seconds": 30,  # <= 60 seconds
        "opportunity_key": "fb:member_req:unique_1",
        "content_url": "https://www.facebook.com/groups/goethebd/member-requests",
        "content_text": "Fresh member request",
    }

    with patch("goethe_groups.goethe_scanner.beep") as mock_beep:
        alerted = scanner.check_immediate_freshness_alert(fresh_item)
        assert alerted is True
        mock_beep.assert_called_once()

        # Repeated check must not trigger duplicate alert
        alerted_again = scanner.check_immediate_freshness_alert(fresh_item)
        assert alerted_again is False


def test_old_member_request_no_immediate_beep():
    scanner = GoetheGroupScanner(browser=None)

    old_item = {
        "group_name": "Goethe Group Bangladesh",
        "author": "Old Request User",
        "age_seconds": 180,  # > 60 seconds
        "opportunity_key": "fb:member_req:unique_old",
        "content_url": "https://www.facebook.com/groups/goethebd/member-requests",
        "content_text": "Old member request",
    }

    with patch("goethe_groups.goethe_scanner.beep") as mock_beep:
        alerted = scanner.check_immediate_freshness_alert(old_item)
        assert alerted is False
        mock_beep.assert_not_called()


def test_deduplication_and_pipeline():
    scanner = GoetheGroupScanner(browser=None)
    scanner.seen_keys.clear()

    item = {
        "source": "facebook",
        "source_type": "goethe_member_request",
        "group_name": "Goethe Group Bangladesh",
        "group_url": "https://www.facebook.com/groups/goethebd/member-requests",
        "author": "Karim",
        "content_type": "MEMBER_REQUEST",
        "content_text": "Need help with Goethe A1 exam preparation",
        "content_url": "https://www.facebook.com/user/999",
        "timestamp_info": {
            "raw": "2 mins ago",
            "age_seconds": 120,
            "confidence": "HIGH",
            "freshness": "VERY_RECENT",
            "source": "dom_post_url",
            "warning": None,
        },
        "opportunity_key": "fb:member_req:test_dedup_999",
    }

    with patch("goethe_groups.goethe_scanner.save_opportunity") as mock_save, \
         patch("goethe_groups.goethe_scanner.alert_opportunity") as mock_alert, \
         patch("goethe_groups.goethe_scanner.display_opportunity") as mock_display:

        opp1 = scanner.process_item(item)
        assert opp1 is not None
        assert opp1["source_type"] == "goethe_member_request"
        mock_save.assert_called_once()

        # Second attempt should be deduplicated
        opp2 = scanner.process_item(item)
        assert opp2 is None
