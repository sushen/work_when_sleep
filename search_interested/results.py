"""Opportunity record construction, persistence, alerts, and console output."""

from __future__ import annotations

import hashlib
import os
import re
import time

from .facebook_urls import clean_facebook_url, extract_parent_post_url
from .notifier import beep
from .settings import (
    ALERT_QUALITY_LEVELS,
    BEEP_PAUSE_SECONDS,
    MAX_POST_TEXT_DISPLAY_CHARS,
    RESULTS_FILE,
)
from .text_utils import first_line, format_age, indent_text, limit_text, normalize_space
from .timestamps import build_timestamp_info, parse_post_age


def build_post_key(group_url, post_url, post_text, timestamp_raw):
    return build_opportunity_key(
        group_url=group_url,
        content_url=post_url,
        content_type="POST",
        content_text=post_text,
        timestamp_raw=timestamp_raw,
    )


def build_opportunity_key(
    group_url=None,
    content_url=None,
    content_type="POST",
    content_text="",
    timestamp_raw=None,
    source="facebook",
    post_id=None,
):
    if source == "reddit" and post_id:
        return f"reddit:{post_id}"

    if content_url:
        return f"url:{content_url}"

    fallback = "|".join(
        [
            normalize_space(source or "facebook").lower(),
            normalize_space(group_url or "").lower(),
            normalize_space(content_type or "").lower(),
            normalize_space(timestamp_raw or "").lower(),
            normalize_space(content_text or "").lower()[:1000],
        ]
    )
    return "hash:" + hashlib.sha1(fallback.encode("utf-8")).hexdigest()


def build_opportunity(
    group_name=None,
    group_url=None,
    content_type="POST",
    author="UNKNOWN",
    content_text="",
    content_url=None,
    timestamp_info=None,
    opportunity_analysis=None,
    opportunity_key=None,
    source="facebook",
    subreddit=None,
    title=None,
    detection_latency_seconds=None,
    query=None,
    post_id=None,
):
    if timestamp_info is None:
        timestamp_info = build_timestamp_info(
            raw=None,
            age_seconds=None,
            confidence="NONE",
            source="unknown",
        )

    if opportunity_analysis is None:
        opportunity_analysis = {
            "matched_signals": [],
            "score": 0,
            "quality": "WEAK",
        }

    if opportunity_key is None:
        opportunity_key = build_opportunity_key(
            group_url=group_url,
            content_url=content_url,
            content_type=content_type,
            content_text=content_text,
            timestamp_raw=timestamp_info["raw"],
            source=source,
            post_id=post_id,
        )

    parent_url = extract_parent_post_url(content_url) if source == "facebook" else None

    return {
        "source": source,
        "detection_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "group_name": group_name or subreddit or "UNKNOWN",
        "group_url": group_url or content_url,
        "subreddit": subreddit,
        "content_type": content_type,
        "author": author or "UNKNOWN",
        "title": title,
        "content_text": content_text,
        "content_url": content_url,
        "parent_post_url": parent_url,
        "opportunity_key": opportunity_key,
        "matched_signals": opportunity_analysis["matched_signals"],
        "opportunity_score": opportunity_analysis["score"],
        "opportunity_quality": opportunity_analysis["quality"],
        "timestamp_raw": timestamp_info["raw"],
        "timestamp_confidence": timestamp_info["confidence"],
        "timestamp_source": timestamp_info["source"],
        "timestamp_warning": timestamp_info["warning"],
        "content_age_seconds": timestamp_info["age_seconds"],
        "detection_latency_seconds": detection_latency_seconds,
        "freshness_level": timestamp_info["freshness"],
        "query": query,
    }


def build_match_info(
    group_name,
    group_url,
    post_text,
    post_url,
    matched_patterns,
    timestamp_raw,
):
    timestamp_info = build_timestamp_info(
        raw=timestamp_raw,
        age_seconds=parse_post_age(timestamp_raw),
        confidence="LEGACY",
        source="legacy_post_timestamp",
        candidates=[timestamp_raw] if timestamp_raw else [],
    )
    opportunity_analysis = {
        "matched_signals": matched_patterns,
        "score": 0,
        "quality": "WEAK",
    }
    return build_opportunity(
        group_name=group_name,
        group_url=group_url,
        content_type="POST",
        author="UNKNOWN",
        content_text=post_text,
        content_url=post_url,
        timestamp_info=timestamp_info,
        opportunity_analysis=opportunity_analysis,
    )


def format_opportunity_record(opportunity, max_text_chars=MAX_POST_TEXT_DISPLAY_CHARS):
    separator = "=" * 50
    matched_signals = "\n".join(
        f"    {signal}" for signal in opportunity["matched_signals"]
    )

    source = opportunity.get("source", "facebook")
    title_section = ""
    if opportunity.get("title"):
        title_section = f"Title:\n    {opportunity['title']}\n\n"

    latency_str = "UNKNOWN"
    if opportunity.get("detection_latency_seconds") is not None:
        latency_str = f"{opportunity['detection_latency_seconds']:.1f} seconds"

    if source == "reddit":
        header_name = "REDDIT OPPORTUNITY FOUND"
        group_label = "Subreddit:"
        group_val = opportunity.get("subreddit") or opportunity.get("group_name") or "UNKNOWN"
        group_url_line = ""
    else:
        header_name = "OPPORTUNITY FOUND"
        group_label = "Group:"
        group_val = opportunity.get("group_name") or "UNKNOWN"
        group_url_line = f"Group URL:\n    {opportunity.get('group_url') or 'UNKNOWN'}\n\n"

    return (
        f"{separator}\n"
        f"{header_name}\n"
        f"{separator}\n\n"
        f"Source:\n    {source}\n\n"
        f"Detected:\n    {opportunity['detection_time']}\n\n"
        f"{group_label}\n    {group_val}\n\n"
        f"{group_url_line}"
        f"Content:\n    {opportunity['content_type']}\n\n"
        f"Author:\n    {opportunity['author']}\n\n"
        f"{title_section}"
        f"URL:\n    {opportunity['content_url'] or 'UNKNOWN'}\n\n"
        f"Opportunity Key:\n    {opportunity['opportunity_key']}\n\n"
        f"Signals:\n{matched_signals or '    UNKNOWN'}\n\n"
        f"Score:\n    {opportunity['opportunity_score']}\n\n"
        f"Quality:\n    {opportunity['opportunity_quality']}\n\n"
        f"Creation Timestamp:\n    {opportunity['timestamp_raw'] or 'UNKNOWN'}\n\n"
        f"Timestamp Confidence:\n    {opportunity['timestamp_confidence']}\n\n"
        f"Age:\n    {format_age(opportunity['content_age_seconds'])}\n\n"
        f"Detection Latency:\n    {latency_str}\n\n"
        f"Freshness:\n    {opportunity['freshness_level']}\n\n"
        f"Text:\n{indent_text(limit_text(opportunity['content_text'], max_text_chars))}\n\n"
        f"{separator}\n\n"
    )


def format_match_record(match_info, max_text_chars=MAX_POST_TEXT_DISPLAY_CHARS):
    return format_opportunity_record(match_info, max_text_chars=max_text_chars)


def alert_opportunity(opportunity):
    if opportunity["opportunity_quality"] not in ALERT_QUALITY_LEVELS:
        print(f"[ALERT] {opportunity['opportunity_quality']} -> CONSOLE ONLY")
        return

    alert_user(opportunity["freshness_level"])


def alert_user(freshness_level):
    beep_count = beep_count_for_freshness(freshness_level)
    if beep_count <= 0:
        print(f"[ALERT] {freshness_level} -> NO BEEP")
        return

    try:
        print(f"[ALERT] {freshness_level} -> {beep_count} BEEP(S)")
        for index in range(beep_count):
            if index:
                time.sleep(BEEP_PAUSE_SECONDS)
            beep()
    except RuntimeError as error:
        print(f"[ERROR] Could not play alert sound: {error}")


def beep_count_for_freshness(freshness_level):
    if freshness_level == "VERY_RECENT":
        return 3
    if freshness_level == "RECENT":
        return 2
    if freshness_level == "OLDER_BUT_RELEVANT":
        return 1
    return 0


def display_opportunity(opportunity):
    source = opportunity.get("source", "facebook").upper()
    print(f"==================================================")
    print(f"{source} OPPORTUNITY")
    print(f"==================================================")
    print(f"Quality: {opportunity['opportunity_quality']}")
    print(f"Score: {opportunity['opportunity_score']}")

    if opportunity.get("source") == "reddit" or opportunity.get("subreddit"):
        print(f"Subreddit: {opportunity.get('subreddit') or opportunity['group_name']}")
    else:
        print(f"Group: {opportunity['group_name']}")

    print(f"Author: {opportunity['author']}")
    print(f"Post age: {format_age(opportunity['content_age_seconds'])}")

    if opportunity.get("detection_latency_seconds") is not None:
        print(f"Detection latency: {opportunity['detection_latency_seconds']:.1f} seconds")

    if opportunity.get("title"):
        print(f"\nTitle:\n{opportunity['title']}")

    print(f"\nMatched signals:\n{', '.join(opportunity['matched_signals'])}")
    print(f"\nURL:\n{opportunity['content_url'] or 'UNKNOWN'}")
    print(f"==================================================\n")


def display_match(match_info):
    display_opportunity(match_info)


def save_opportunity(opportunity, results_file=RESULTS_FILE):
    appended_text = format_opportunity_record(opportunity)

    try:
        with open(results_file, "a", encoding="utf-8") as file:
            file.write(appended_text)
            file.flush()
            os.fsync(file.fileno())

        print(f"[SAVE] Saved to {results_file}")
        print("[SAVE] Appended text:")
        print(appended_text.rstrip())
        return True
    except OSError as error:
        print(f"[ERROR] Could not save opportunity: {error}")
        return False


def save_match(match_info, results_file=RESULTS_FILE):
    return save_opportunity(match_info, results_file=results_file)


def load_seen_opportunity_keys(results_file=RESULTS_FILE):
    try:
        text = results_file.read_text(encoding="utf-8")
    except FileNotFoundError:
        return set()
    except OSError as error:
        print(f"[ERROR] Could not read existing results for duplicate detection: {error}")
        return set()

    seen_keys = set()
    for key in re.findall(r"(?m)^\s*Opportunity Key:\s*\n\s*(\S+)", text):
        seen_keys.add(key.strip())

    for url in re.findall(r"(?m)^\s*(?:Post URL|URL):\s*\n\s*(https?://\S+)", text):
        if "facebook.com" in url:
            cleaned_url = clean_facebook_url(url)
            if cleaned_url and cleaned_url.upper() != "UNKNOWN":
                seen_keys.add(f"url:{cleaned_url}")
        else:
            seen_keys.add(f"url:{url}")

    if seen_keys:
        print(f"[DUPLICATE] Loaded {len(seen_keys)} saved opportunity keys")

    return seen_keys
