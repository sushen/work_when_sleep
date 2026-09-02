"""Normalizes Reddit post items into internal opportunity schema."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from .reddit_urls import build_reddit_permalink, clean_reddit_url
from .timestamps import build_timestamp_info, classify_freshness
from .text_utils import normalize_space


def normalize_reddit_post(post_data: dict, query: str = "", detected_at: float | None = None) -> dict:
    """Transform raw Reddit post JSON dict into normalized internal opportunity structure."""
    if detected_at is None:
        detected_at = time.time()

    post_id = str(post_data.get("id") or "").strip()
    title = normalize_space(post_data.get("title") or "")
    selftext = normalize_space(post_data.get("selftext") or "")
    author = normalize_space(post_data.get("author") or "UNKNOWN")
    subreddit = normalize_space(post_data.get("subreddit") or "")

    if subreddit and not subreddit.startswith("r/"):
        community_name = f"r/{subreddit}"
    else:
        community_name = subreddit or "r/reddit"

    permalink = post_data.get("permalink") or ""
    source_url = build_reddit_permalink(permalink)
    content_url = clean_reddit_url(post_data.get("url") or source_url)

    # Combine title and body text for opportunity analysis
    if title and selftext:
        content_text = f"{title}\n\n{selftext}"
    else:
        content_text = title or selftext

    created_utc = post_data.get("created_utc")
    timestamp_raw = None
    age_seconds = None
    confidence = "NONE"
    warning = None

    if isinstance(created_utc, (int, float)) and created_utc > 0:
        age_seconds = max(0, int(detected_at - created_utc))
        utc_dt = datetime.fromtimestamp(created_utc, tz=timezone.utc)
        timestamp_raw = utc_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        confidence = "HIGH"
    else:
        warning = "missing_or_invalid_created_utc"

    timestamp_info = build_timestamp_info(
        raw=timestamp_raw,
        age_seconds=age_seconds,
        confidence=confidence,
        source="reddit_created_utc",
        candidates=[timestamp_raw] if timestamp_raw else [],
        warning=warning,
    )

    detection_latency_seconds = age_seconds if age_seconds is not None else None

    return {
        "source": "reddit",
        "content_type": "POST",
        "author": author or "UNKNOWN",
        "title": title,
        "body": selftext,
        "content_text": content_text,
        "content_url": content_url or source_url,
        "source_url": source_url,
        "community_name": community_name,
        "subreddit": community_name,
        "timestamp_raw": timestamp_raw,
        "timestamp_info": timestamp_info,
        "source_id": post_id,
        "post_id": post_id,
        "query": query,
        "created_at_utc": timestamp_raw,
        "created_utc": created_utc,
        "detected_at_timestamp": detected_at,
        "age_seconds": age_seconds,
        "detection_latency_seconds": detection_latency_seconds,
    }
