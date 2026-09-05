"""Unit and integration tests for Goethe Facebook Groups opportunity scanner."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from goethe_groups.goethe_config import GoetheGroupConfig, get_enabled_goethe_groups, load_goethe_groups_config
from goethe_groups.goethe_scanner import GoetheGroupScanner, normalize_goethe_post


def test_goethe_config_loading(tmp_path: Path):
    config_file = tmp_path / "test_goethe.json"
    data = [
        {
            "name": "Goethe Test Group 1",
            "url": "https://www.facebook.com/groups/test1",
            "enabled": True,
            "search_interests": ["German A1", "exam"],
        },
        {
            "name": "Goethe Test Group 2",
            "url": "https://www.facebook.com/groups/test2",
            "enabled": False,
            "search_interests": ["German B1"],
        },
    ]
    config_file.write_text(json.dumps(data), encoding="utf-8")

    all_configs = load_goethe_groups_config(config_file)
    assert len(all_configs) == 2
    assert all_configs[0].name == "Goethe Test Group 1"
    assert all_configs[0].search_interests == ["German A1", "exam"]

    enabled_configs = get_enabled_goethe_groups(config_file)
    assert len(enabled_configs) == 1
    assert enabled_configs[0].name == "Goethe Test Group 1"


def test_normalize_goethe_post():
    raw_post = {
        "group_name": "Goethe German A1",
        "group_url": "https://www.facebook.com/groups/goethe.a1",
        "content_text": "Need help for Goethe A1 exam preparation!",
        "author": "John Doe",
        "content_type": "POST",
        "content_url": "https://www.facebook.com/groups/goethe.a1/posts/123456789/",
        "timestamp_info": {
            "raw": "2 hrs ago",
            "age_seconds": 7200,
            "confidence": "HIGH",
            "freshness": "VERY_RECENT",
            "source": "dom_post_url",
            "warning": None,
        },
    }

    normalized = normalize_goethe_post(raw_post, query="Goethe A1", detected_at=1000.0)

    assert normalized["source"] == "facebook"
    assert normalized["source_type"] == "goethe_group"
    assert normalized["group_name"] == "Goethe German A1"
    assert normalized["post_id"] == "123456789"
    assert normalized["author"] == "John Doe"
    assert normalized["search_interest"] == "Goethe A1"
    assert "123456789" in normalized["opportunity_key"] or "https://www.facebook.com/groups/goethe.a1/posts/123456789/" in normalized["opportunity_key"]


def test_deduplication_and_opportunity_pipeline():
    scanner = GoetheGroupScanner(browser=None)
    scanner.seen_keys.clear()  # Clear seen keys for isolated test execution

    normalized_item = {
        "source": "facebook",
        "source_type": "goethe_group",
        "group_name": "Goethe A1",
        "group_url": "https://www.facebook.com/groups/goethe.a1",
        "query": "German A1",
        "search_interest": "German A1",
        "post_id": "999",
        "author": "Alice",
        "content_type": "POST",
        "content_text": "Looking to hire a German tutor for Goethe A1 exam prep, paid per hour!",
        "content_url": "https://www.facebook.com/groups/goethe.a1/posts/999/",
        "timestamp_info": {
            "raw": "10 mins ago",
            "age_seconds": 600,
            "confidence": "HIGH",
            "freshness": "VERY_RECENT",
            "source": "dom_post_url",
            "warning": None,
        },
        "opportunity_key": "fb:post:unique_test_key_999",
    }

    with patch("goethe_groups.goethe_scanner.save_opportunity") as mock_save, \
         patch("goethe_groups.goethe_scanner.alert_opportunity") as mock_alert, \
         patch("goethe_groups.goethe_scanner.display_opportunity") as mock_display:

        opp1 = scanner.process_item(normalized_item)
        assert opp1 is not None
        assert opp1["group_name"] == "Goethe A1"
        assert opp1["source_type"] == "goethe_group"
        mock_save.assert_called_once()
        mock_alert.assert_called_once()

        # Second attempt with same key must be deduplicated
        opp2 = scanner.process_item(normalized_item)
        assert opp2 is None


def test_missing_optional_fields_handling():
    raw_minimal = {
        "group_name": "Goethe B1",
        "group_url": "https://www.facebook.com/groups/goethe.b1",
        "text": "Anyone know Goethe exam date?",
    }

    normalized = normalize_goethe_post(raw_minimal, query="exam date")
    assert normalized["author"] == "UNKNOWN"
    assert normalized["timestamp_confidence"] == "NONE"
    assert normalized["post_id"] is None


def test_search_failure_isolation():
    mock_browser = MagicMock()
    scanner = GoetheGroupScanner(browser=mock_browser)

    group1 = GoetheGroupConfig(
        name="Group 1",
        url="https://facebook.com/groups/g1",
        enabled=True,
        search_interests=["query1", "query2"],
    )

    with patch.object(scanner, "search_group_query") as mock_search, \
         patch("goethe_groups.goethe_scanner.get_enabled_goethe_groups", return_value=[group1]):

        # First query fails with exception, second query succeeds
        mock_search.side_effect = [
            RuntimeError("Network error on query1"),
            [{"opportunity_key": "opp2"}],
        ]

        results = scanner.scan_all_groups()
        assert len(results) == 1
        assert mock_search.call_count == 2
