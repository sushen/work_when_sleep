"""Normalizes Reddit post and comment items into internal opportunity schema."""

from __future__ import annotations

import re
import time
from datetime import datetime, timezone

from reddit_auto.reddit_urls import build_reddit_permalink, clean_reddit_url
from search_interested.text_utils import normalize_space
from search_interested.timestamps import build_timestamp_info


def extract_subreddit_name(subreddit_raw: str = "", permalink: str = "", url: str = "") -> str:
    """Extract canonical subreddit name (e.g. r/CryptoTradingBot) from metadata or URL path."""
    clean_raw = normalize_space(subreddit_raw)
    if clean_raw and clean_raw.lower() not in {"reddit", "r/reddit", "unknown"}:
        if clean_raw.startswith("r/"):
            return clean_raw
        return f"r/{clean_raw}"

    for target in (permalink, url):
        if target:
            match = re.search(r"/r/([A-Za-z0-9_]+)", target)
            if match:
                extracted = match.group(1)
                if extracted.lower() != "reddit":
                    return f"r/{extracted}"

    if clean_raw:
        if clean_raw.startswith("r/"):
            return clean_raw
        return f"r/{clean_raw}"

    return "UNKNOWN"


def parse_created_utc_timestamp(created_utc: float | int | None, detected_at: float) -> tuple[str | None, float | None, float | None, str, str | None]:
    """Parse created_utc float into timestamp_raw, age_seconds, detection_latency_seconds, confidence, warning."""
    if isinstance(created_utc, (int, float)) and created_utc > 0:
        source_created_at = float(created_utc)
        # Handle millisecond timestamps if received
        if source_created_at > 1e11:
            source_created_at /= 1000.0

        latency = detected_at - source_created_at
        age_seconds = max(0.0, latency)
        utc_dt = datetime.fromtimestamp(source_created_at, tz=timezone.utc)
        timestamp_raw = utc_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        return timestamp_raw, age_seconds, latency, "HIGH", None

    return None, None, None, "NONE", "missing_or_invalid_created_utc"


def normalize_reddit_post(post_data: dict, query: str = "", detected_at: float | None = None) -> dict:
    """Transform raw Reddit post JSON dict or DOM metadata into normalized internal opportunity structure."""
    if detected_at is None:
        detected_at = time.time()

    raw_id = str(post_data.get("id") or "").strip()
    if raw_id.startswith("t3_"):
        post_id = raw_id[3:]
        canonical_id = raw_id
    else:
        post_id = raw_id
        canonical_id = f"t3_{raw_id}" if raw_id else ""

    title = normalize_space(post_data.get("title") or "")
    selftext = normalize_space(post_data.get("selftext") or post_data.get("body") or "")
    author = normalize_space(post_data.get("author") or "UNKNOWN")
    subreddit_raw = post_data.get("subreddit") or ""

    permalink = post_data.get("permalink") or ""
    source_url = build_reddit_permalink(permalink)
    content_url = clean_reddit_url(post_data.get("url") or source_url)

    community_name = extract_subreddit_name(subreddit_raw, permalink, content_url)

    # Combine title and body text for opportunity analysis
    if title and selftext:
        content_text = f"{title}\n\n{selftext}"
    else:
        content_text = title or selftext

    created_utc = post_data.get("created_utc")
    timestamp_raw, age_seconds, latency, confidence, warning = parse_created_utc_timestamp(created_utc, detected_at)

    timestamp_info = build_timestamp_info(
        raw=timestamp_raw,
        age_seconds=int(age_seconds) if age_seconds is not None else None,
        confidence=confidence,
        source="reddit_created_utc",
        candidates=[timestamp_raw] if timestamp_raw else [],
        warning=warning,
    )

    canonical_key = f"reddit:{canonical_id}" if canonical_id else (content_url or source_url)

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
        "source_id": canonical_id,
        "post_id": post_id,
        "opportunity_key": canonical_key,
        "query": query,
        "created_at_utc": timestamp_raw,
        "source_created_at": created_utc,
        "created_utc": created_utc,
        "detected_at": detected_at,
        "detected_at_timestamp": detected_at,
        "age_seconds": age_seconds,
        "detection_latency_seconds": latency,
        "timestamp_confidence": confidence,
    }


def normalize_reddit_comment(comment_data: dict, query: str = "", detected_at: float | None = None) -> dict:
    """Transform raw Reddit comment JSON dict or DOM metadata into normalized internal opportunity structure."""
    if detected_at is None:
        detected_at = time.time()

    raw_id = str(comment_data.get("id") or "").strip()
    if raw_id.startswith("t1_"):
        comment_id = raw_id[3:]
        canonical_id = raw_id
    else:
        comment_id = raw_id
        canonical_id = f"t1_{raw_id}" if raw_id else ""

    body = normalize_space(comment_data.get("body") or comment_data.get("selftext") or "")
    author = normalize_space(comment_data.get("author") or "UNKNOWN")
    subreddit_raw = comment_data.get("subreddit") or ""
    link_title = normalize_space(comment_data.get("link_title") or comment_data.get("parent_title") or "")

    permalink = comment_data.get("permalink") or ""
    source_url = build_reddit_permalink(permalink)
    content_url = clean_reddit_url(comment_data.get("url") or source_url)

    community_name = extract_subreddit_name(subreddit_raw, permalink, content_url)

    if link_title and body:
        content_text = f"[Parent Post: {link_title}]\n\n{body}"
    else:
        content_text = body

    created_utc = comment_data.get("created_utc")
    timestamp_raw, age_seconds, latency, confidence, warning = parse_created_utc_timestamp(created_utc, detected_at)

    timestamp_info = build_timestamp_info(
        raw=timestamp_raw,
        age_seconds=int(age_seconds) if age_seconds is not None else None,
        confidence=confidence,
        source="reddit_comment_created_utc",
        candidates=[timestamp_raw] if timestamp_raw else [],
        warning=warning,
    )

    canonical_key = f"reddit:{canonical_id}" if canonical_id else (content_url or source_url)

    return {
        "source": "reddit",
        "content_type": "COMMENT",
        "author": author or "UNKNOWN",
        "title": link_title,
        "body": body,
        "content_text": content_text,
        "content_url": content_url or source_url,
        "source_url": source_url,
        "community_name": community_name,
        "subreddit": community_name,
        "timestamp_raw": timestamp_raw,
        "timestamp_info": timestamp_info,
        "source_id": canonical_id,
        "comment_id": comment_id,
        "opportunity_key": canonical_key,
        "query": query,
        "created_at_utc": timestamp_raw,
        "source_created_at": created_utc,
        "created_utc": created_utc,
        "detected_at": detected_at,
        "detected_at_timestamp": detected_at,
        "age_seconds": age_seconds,
        "detection_latency_seconds": latency,
        "timestamp_confidence": confidence,
    }
