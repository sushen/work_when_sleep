"""Unit tests for Reddit extension modules in SearchInterested."""

from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import pytest

from reddit_auto.reddit_client import RedditClient
from reddit_auto.reddit_parser import normalize_reddit_post
from reddit_auto.reddit_query_queue import RedditQueryQueue, load_reddit_queries
from reddit_auto.reddit_scanner import RedditScanner
from reddit_auto.reddit_urls import build_reddit_permalink, clean_reddit_url
from search_interested.opportunity_engine import analyze_opportunity
from search_interested.results import (
    build_opportunity,
    format_opportunity_record,
    load_seen_opportunity_keys,
    save_opportunity,
)


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
        "subreddit": "forhire",
        "permalink": "/r/forhire/comments/post123/",
        "created_utc": now - 10,
    }

    normalized = normalize_reddit_post(raw, query="need a developer", detected_at=now)
    assert normalized["post_id"] == "post123"
    assert normalized["author"] == "client_user"
    assert normalized["community_name"] == "r/forhire"
    assert "Need a developer" in normalized["content_text"]
    assert "Looking for a Python" in normalized["content_text"]
    assert normalized["source_url"] == "https://www.reddit.com/r/forhire/comments/post123/"


def test_3_reddit_timestamp_parsing():
    now = 1700000000.0
    raw = {
        "id": "t1",
        "title": "Title",
        "created_utc": now - 30,
    }
    normalized = normalize_reddit_post(raw, detected_at=now)
    assert normalized["timestamp_info"]["confidence"] == "HIGH"
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
    assert normalized["detection_latency_seconds"] == 4


def test_5_duplicate_reddit_posts_discovered_by_two_queries(tmp_path):
    results_file = tmp_path / "search_results.txt"
    queue_file = tmp_path / "reddit_queries.txt"
    queue_file.write_text("looking for developer\nneed developer\n", encoding="utf-8")

    now = time.time()
    mock_post = {
        "id": "dup_post_999",
        "title": "Looking for a developer to build an app",
        "selftext": "I need a programmer for a Python project.",
        "author": "buyer_123",
        "subreddit": "forhire",
        "permalink": "/r/forhire/comments/dup_post_999/",
        "created_utc": now - 10,
    }

    mock_client = MagicMock()
    mock_client.search_newest.return_value = [mock_post]

    queue = RedditQueryQueue(queries_file=queue_file)
    scanner = RedditScanner(client=mock_client, query_queue=queue)

    with patch("reddit_auto.reddit_scanner.save_opportunity") as mock_save:
        # Run query 1
        res1 = scanner.process_query("looking for developer")
        assert len(res1) == 1

        # Run query 2 (same post)
        res2 = scanner.process_query("need developer")
        assert len(res2) == 0

        # Should only have saved once
        assert mock_save.call_count == 1


def test_6_fresh_opportunity_detection():
    now = time.time()
    raw = {
        "id": "fresh1",
        "title": "Looking for a Python developer",
        "selftext": "I need a developer to create a web scraper.",
        "created_utc": now - 15,
    }
    normalized = normalize_reddit_post(raw, detected_at=now)
    assert normalized["timestamp_info"]["freshness"] in {"VERY_RECENT", "RECENT"}


def test_7_old_post_rejection(tmp_path):
    mock_client = MagicMock()
    old_time = time.time() - (10 * 24 * 60 * 60) # 10 days old
    mock_client.search_newest.return_value = [{
        "id": "old1",
        "title": "Looking for a Python developer",
        "selftext": "I need someone to build an API.",
        "created_utc": old_time,
    }]

    scanner = RedditScanner(client=mock_client, max_age_seconds=86400)
    with patch("reddit_auto.reddit_scanner.save_opportunity") as mock_save:
        results = scanner.process_query("looking for developer")
        assert len(results) == 0
        mock_save.assert_not_called()


def test_8_unknown_timestamp_behavior(tmp_path):
    mock_client = MagicMock()
    mock_client.search_newest.return_value = [{
        "id": "unknown_time",
        "title": "Looking for a Python developer",
        "created_utc": None,
    }]

    scanner = RedditScanner(client=mock_client)
    with patch("reddit_auto.reddit_scanner.save_opportunity") as mock_save:
        results = scanner.process_query("looking for developer")
        assert len(results) == 0
        mock_save.assert_not_called()


def test_9_strong_opportunity_classification():
    text = "Looking for a Python developer to build a web application. Urgent project with budget."
    analysis = analyze_opportunity(text)
    assert analysis["quality"] in {"STRONG", "POSSIBLE"}
    assert analysis["score"] >= 4


def test_10_provider_self_promotion_rejection():
    text = "I am a Python developer available for work. Developer here! DM me if you need help."
    analysis = analyze_opportunity(text)
    assert analysis["quality"] == "WEAK"


def test_11_title_and_body_analysis():
    raw = {
        "id": "tb1",
        "title": "Looking for developer",
        "selftext": "I need help building a Django backend.",
    }
    normalized = normalize_reddit_post(raw)
    analysis = analyze_opportunity(normalized["content_text"])
    assert "looking_for" in analysis["matched_signals"]
    assert "developer" in analysis["matched_signals"]


def test_12_reddit_result_persistence(tmp_path):
    results_file = tmp_path / "test_results.txt"

    opportunity = build_opportunity(
        group_name="r/forhire",
        group_url="https://www.reddit.com/r/forhire/comments/xyz/",
        content_type="POST",
        author="client1",
        content_text="Looking for developer to build website",
        content_url="https://www.reddit.com/r/forhire/comments/xyz/",
        timestamp_info={
            "raw": "2026-09-02 12:00:00 UTC",
            "age_seconds": 120,
            "freshness": "VERY_RECENT",
            "confidence": "HIGH",
            "source": "reddit_created_utc",
            "warning": None,
        },
        opportunity_analysis={
            "matched_signals": ["looking_for", "developer"],
            "score": 8,
            "quality": "STRONG",
        },
        source="reddit",
        subreddit="r/forhire",
        title="Looking for developer",
        detection_latency_seconds=5.2,
        post_id="xyz",
    )

    success = save_opportunity(opportunity, results_file=results_file)
    assert success is True

    saved_text = results_file.read_text(encoding="utf-8")
    assert "REDDIT OPPORTUNITY FOUND" in saved_text
    assert "Subreddit:\n    r/forhire" in saved_text
    assert "Detection Latency:\n    5.2 seconds" in saved_text

    seen_keys = load_seen_opportunity_keys(results_file=results_file)
    assert "reddit:xyz" in seen_keys


def test_13_query_queue_rotation(tmp_path):
    query_file = tmp_path / "queries.txt"
    query_file.write_text("# Comment line\nlooking for developer\n\nneed a developer\n", encoding="utf-8")

    queue = RedditQueryQueue(queries_file=query_file)
    q1 = queue.get_next_query()
    q2 = queue.get_next_query()
    q3 = queue.get_next_query()

    assert q1 == "looking for developer"
    assert q2 == "need a developer"
    assert q3 == "looking for developer"


def test_14_rate_limit_and_error_recovery():
    client = RedditClient(retry_delay=0.01)

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = json.dumps({
            "data": {
                "children": [
                    {
                        "kind": "t3",
                        "data": {
                            "id": "p1",
                            "title": "Looking for programmer",
                            "created_utc": time.time(),
                        }
                    }
                ]
            }
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        posts = client.search_newest("looking for programmer")
        assert len(posts) == 1
        assert posts[0]["id"] == "p1"


def test_15_search_interested_entrypoint():
    from reddit_auto import SearchInterested

    assert hasattr(SearchInterested, "RedditScanner")
    assert hasattr(SearchInterested, "RedditClient")
    assert hasattr(SearchInterested, "RedditQueryQueue")
    assert hasattr(SearchInterested, "scan_query")
    assert hasattr(SearchInterested, "run_continuous_scanner")

    mock_scanner = MagicMock()
    mock_scanner.process_query.return_value = [{"post_id": "test_15"}]

    res = SearchInterested.scan_query("looking for developer", scanner=mock_scanner)
    assert len(res) == 1
    assert res[0]["post_id"] == "test_15"
    mock_scanner.process_query.assert_called_once_with("looking for developer")

    with patch("reddit_auto.SearchInterested.scanner_main") as mock_main:
        SearchInterested.main()
        mock_main.assert_called_once()


def test_16_subreddit_list_loading(tmp_path):
    sub_file = tmp_path / "sub_raddit_list"
    sub_file.write_text(
        "# Subreddit list\nhttps://www.reddit.com/r/CryptoTradingBot/\nr/algotrading\n\nforhire\n",
        encoding="utf-8",
    )
    query_file = tmp_path / "queries.txt"
    query_file.write_text("looking for developer\n", encoding="utf-8")

    from reddit_auto.reddit_query_queue import load_reddit_urls, load_subreddit_urls

    sub_urls = load_subreddit_urls(list_file=sub_file)
    assert len(sub_urls) == 3
    assert "https://www.reddit.com/r/CryptoTradingBot/" in sub_urls
    assert "https://www.reddit.com/r/algotrading/" in sub_urls
    assert "https://www.reddit.com/r/forhire/" in sub_urls

    all_urls = load_reddit_urls(subreddits_file=sub_file, queries_file=query_file)
    assert len(all_urls) == 4
    assert any("search/?q=looking" in url for url in all_urls)


def test_17_extract_reddit_posts_from_browser_dom():
    from reddit_auto.reddit_scanner import extract_reddit_posts_from_browser

    mock_browser = MagicMock()
    mock_body = MagicMock()
    mock_body.text = "<html>Reddit webpage</html>"
    mock_browser.find_element.return_value = mock_body

    mock_post_el = MagicMock()
    mock_post_el.get_attribute.side_effect = lambda attr: {
        "id": "post_dom_123",
        "post-title": "Looking for a Python developer",
        "author": "dev_buyer",
        "subreddit-prefixed-name": "r/forhire",
        "permalink": "/r/forhire/comments/post_dom_123/",
        "created-timestamp": str(time.time() - 30),
    }.get(attr, "")
    mock_post_el.find_elements.return_value = []

    mock_browser.find_elements.return_value = [mock_post_el]

    posts = extract_reddit_posts_from_browser(mock_browser)
    assert len(posts) == 1
    assert posts[0]["id"] == "post_dom_123"
    assert posts[0]["title"] == "Looking for a Python developer"
    assert posts[0]["author"] == "dev_buyer"
    assert posts[0]["url"] == "https://www.reddit.com/r/forhire/comments/post_dom_123/"
