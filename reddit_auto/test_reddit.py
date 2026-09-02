"""Unit tests for Reddit extension modules in SearchInterested."""

from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from reddit_auto.reddit_client import RedditClient
from reddit_auto.reddit_parser import (
    extract_subreddit_name,
    normalize_reddit_comment,
    normalize_reddit_post,
)
from reddit_auto.reddit_query_queue import RedditQueryQueue, load_reddit_queries
from reddit_auto.reddit_scanner import RedditScanner, login_if_needed_reddit
from reddit_auto.reddit_urls import build_reddit_permalink, clean_reddit_url
from search_interested.opportunity_engine import analyze_opportunity
from search_interested.results import (
    build_opportunity,
    format_opportunity_record,
    load_seen_opportunity_keys,
    save_opportunity,
)
from search_interested.settings import REDDIT_MAX_FRESHNESS_SECONDS, REDDIT_SCAN_INTERVAL_SECONDS


def test_1_reddit_url_normalization():
    raw_url = "https://www.reddit.com/r/forhire/comments/1abc23/post/?utm_source=share&ref=123"
    cleaned = clean_reddit_url(raw_url)
    assert cleaned == "https://www.reddit.com/r/forhire/comments/1abc23/post/"

    permalink = "/r/python/comments/xyz789/looking_for_dev/"
    full = build_reddit_permalink(permalink)
    assert full == "https://www.reddit.com/r/python/comments/xyz789/looking_for_dev/"


def test_2_reddit_post_normalization():
    now = time.time()
    raw = {
        "id": "post123",
        "title": "Need a developer to build website",
        "selftext": "Looking for a Python Django developer.",
        "author": "client_user",
        "subreddit": "CryptoTradingBot",
        "permalink": "/r/CryptoTradingBot/comments/post123/",
        "created_utc": now - 10,
    }

    normalized = normalize_reddit_post(raw, query="need a developer", detected_at=now)
    assert normalized["post_id"] == "post123"
    assert normalized["opportunity_key"] == "reddit:t3_post123"
    assert normalized["author"] == "client_user"
    assert normalized["community_name"] == "r/CryptoTradingBot"
    assert "Need a developer" in normalized["content_text"]
    assert "Looking for a Python" in normalized["content_text"]
    assert normalized["source_url"] == "https://www.reddit.com/r/CryptoTradingBot/comments/post123/"


def test_3_reddit_timestamp_parsing():
    now = 1700000000.0
    raw = {
        "id": "t1",
        "title": "Title",
        "created_utc": now - 30,
    }
    normalized = normalize_reddit_post(raw, detected_at=now)
    assert normalized["timestamp_confidence"] == "HIGH"
    assert normalized["age_seconds"] == 30
    assert normalized["timestamp_info"]["freshness"] == "VERY_RECENT"


def test_4_detection_latency():
    now = 1700000000.0
    raw = {
        "id": "t2",
        "title": "Title",
        "created_utc": now - 4.5,
    }
    normalized = normalize_reddit_post(raw, detected_at=now)
    assert normalized["detection_latency_seconds"] == 4.5


def test_5_duplicate_reddit_posts_discovered_by_two_queries(tmp_path):
    now = time.time()
    mock_post = {
        "id": "dup_post_999",
        "title": "Looking for a developer to build an app",
        "selftext": "I need a programmer for a Python project.",
        "author": "buyer_123",
        "subreddit": "CryptoTradingBot",
        "permalink": "/r/CryptoTradingBot/comments/dup_post_999/",
        "created_utc": now - 10,
    }

    mock_client = MagicMock()
    mock_client.search_newest.return_value = [mock_post]

    scanner = RedditScanner(client=mock_client)

    with patch("reddit_auto.reddit_scanner.save_opportunity") as mock_save, \
         patch("reddit_auto.reddit_scanner.alert_opportunity") as mock_alert:
        # Run 1
        res1 = scanner.process_posts([mock_post])
        assert len(res1) == 1

        # Run 2 (same post)
        res2 = scanner.process_posts([mock_post])
        assert len(res2) == 0

        # Saved and alerted only once
        assert mock_save.call_count == 1
        assert mock_alert.call_count == 1


def test_6_fresh_opportunity_detection():
    now = time.time()
    raw = {
        "id": "fresh1",
        "title": "Looking for a Python developer",
        "selftext": "I need a developer to create a web scraper.",
        "created_utc": now - 15,
    }
    normalized = normalize_reddit_post(raw, detected_at=now)
    assert normalized["timestamp_confidence"] == "HIGH"
    assert normalized["age_seconds"] <= REDDIT_MAX_FRESHNESS_SECONDS


def test_7_old_post_rejection():
    mock_client = MagicMock()
    old_time = time.time() - 601  # 601 seconds old (over 600s max freshness)
    old_post = {
        "id": "old1",
        "title": "Looking for a Python developer",
        "selftext": "I need someone to build an API.",
        "created_utc": old_time,
    }

    scanner = RedditScanner(client=mock_client, max_age_seconds=REDDIT_MAX_FRESHNESS_SECONDS)
    with patch("reddit_auto.reddit_scanner.save_opportunity") as mock_save, \
         patch("reddit_auto.reddit_scanner.alert_opportunity") as mock_alert:
        results = scanner.process_posts([old_post])
        assert len(results) == 0
        mock_save.assert_not_called()
        mock_alert.assert_not_called()


def test_8_unknown_timestamp_behavior():
    mock_client = MagicMock()
    unknown_post = {
        "id": "unknown_time",
        "title": "Looking for a Python developer",
        "created_utc": None,
    }

    scanner = RedditScanner(client=mock_client)
    with patch("reddit_auto.reddit_scanner.save_opportunity") as mock_save, \
         patch("reddit_auto.reddit_scanner.alert_opportunity") as mock_alert:
        results = scanner.process_posts([unknown_post])
        assert len(results) == 0
        mock_save.assert_not_called()
        mock_alert.assert_not_called()


def test_9_fresh_comment_on_old_post():
    now = time.time()
    old_parent_created_utc = now - (3 * 24 * 60 * 60) # 3 days old
    fresh_comment_created_utc = now - 20 # 20 seconds old

    raw_comment = {
        "id": "comm123",
        "link_title": "Looking for a trading bot developer",
        "body": "I need a developer to build a Python crypto trading bot.",
        "author": "commenter_1",
        "subreddit": "CryptoTradingBot",
        "permalink": "/r/CryptoTradingBot/comments/old_post/title/comm123/",
        "created_utc": fresh_comment_created_utc,
    }

    normalized = normalize_reddit_comment(raw_comment, detected_at=now)
    assert normalized["content_type"] == "COMMENT"
    assert normalized["age_seconds"] == 20
    assert normalized["timestamp_confidence"] == "HIGH"
    assert normalized["opportunity_key"] == "reddit:t1_comm123"

    scanner = RedditScanner()
    with patch("reddit_auto.reddit_scanner.save_opportunity") as mock_save, \
         patch("reddit_auto.reddit_scanner.alert_opportunity") as mock_alert:
        results = scanner.process_comments([raw_comment])
        assert len(results) == 1
        assert mock_save.call_count == 1
        assert mock_alert.call_count == 1


def test_10_stale_comment_rejection():
    now = time.time()
    stale_comment_created_utc = now - 601 # 601 seconds old

    raw_comment = {
        "id": "stale_comm",
        "body": "Looking for a Python developer.",
        "created_utc": stale_comment_created_utc,
    }

    scanner = RedditScanner(max_age_seconds=REDDIT_MAX_FRESHNESS_SECONDS)
    with patch("reddit_auto.reddit_scanner.save_opportunity") as mock_save:
        results = scanner.process_comments([raw_comment])
        assert len(results) == 0
        mock_save.assert_not_called()


def test_11_canonical_deduplication():
    now = time.time()
    raw_post = {
        "id": "t3_abc111",
        "title": "Looking for a developer",
        "selftext": "Need python programmer.",
        "created_utc": now - 10,
    }
    raw_comment = {
        "id": "t1_xyz222",
        "body": "I am looking for a developer to hire.",
        "created_utc": now - 15,
    }

    norm_p = normalize_reddit_post(raw_post, detected_at=now)
    norm_c = normalize_reddit_comment(raw_comment, detected_at=now)

    assert norm_p["opportunity_key"] == "reddit:t3_abc111"
    assert norm_c["opportunity_key"] == "reddit:t1_xyz222"


def test_12_subreddit_extraction():
    sub1 = extract_subreddit_name("CryptoTradingBot")
    assert sub1 == "r/CryptoTradingBot"

    sub2 = extract_subreddit_name("r/algotrading")
    assert sub2 == "r/algotrading"

    sub3 = extract_subreddit_name("", permalink="/r/CryptoTradingBot/comments/xyz/")
    assert sub3 == "r/CryptoTradingBot"


def test_13_manual_login_gate():
    mock_browser = MagicMock()
    with patch("builtins.input", return_value=""), \
         patch("reddit_auto.reddit_scanner.wait_for_page_ready") as mock_wait:
        login_if_needed_reddit(mock_browser)
        mock_browser.get.assert_called_once_with("https://www.reddit.com")
        assert mock_wait.call_count >= 1


def test_14_configuration_variables():
    assert REDDIT_MAX_FRESHNESS_SECONDS == 600
    assert REDDIT_SCAN_INTERVAL_SECONDS == 30


def test_15_immediate_alert_behavior():
    now = time.time()
    raw_post = {
        "id": "immediate_1",
        "title": "Looking for a Python developer",
        "selftext": "Urgent need for web scraper developer.",
        "subreddit": "CryptoTradingBot",
        "created_utc": now - 10,
    }

    scanner = RedditScanner()
    with patch("reddit_auto.reddit_scanner.save_opportunity") as mock_save, \
         patch("reddit_auto.reddit_scanner.alert_opportunity") as mock_alert:
        res = scanner.process_posts([raw_post])
        assert len(res) == 1
        mock_save.assert_called_once()
        mock_alert.assert_called_once()
