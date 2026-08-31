"""Timestamp parsing and freshness classification."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from .settings import (
    OLDER_BUT_RELEVANT_MAX_SECONDS,
    RECENT_MAX_SECONDS,
    TIMESTAMP_CONFLICT_TOLERANCE_SECONDS,
    VERY_RECENT_MAX_SECONDS,
)
from .text_utils import normalize_space


RELATIVE_TIME_FULL_PATTERN = re.compile(
    r"^(?P<number>\d+|a|an|one)\s*"
    r"(?P<unit>"
    r"seconds?|secs?|s|"
    r"minutes?|mins?|m|"
    r"hours?|hrs?|h|"
    r"days?|d|"
    r"weeks?|w|"
    r"months?|mos?|mo|"
    r"years?|yrs?|y"
    r")\s*(?:ago)?$",
    re.IGNORECASE,
)


def build_timestamp_info(
    raw,
    age_seconds,
    confidence,
    source,
    candidates=None,
    warning=None,
):
    if confidence in {"LOW", "NONE"}:
        age_seconds = None

    return {
        "raw": raw,
        "age_seconds": age_seconds,
        "freshness": classify_freshness(age_seconds),
        "confidence": confidence,
        "source": source,
        "candidates": [candidate for candidate in (candidates or []) if candidate],
        "warning": warning,
    }


def choose_timestamp_from_candidates(candidates, source, now=None):
    unique_candidates = []
    parsed_candidates = []

    for candidate in candidates:
        normalized_candidate = normalize_space(candidate)
        if not normalized_candidate or normalized_candidate in unique_candidates:
            continue
        unique_candidates.append(normalized_candidate)

        parsed = parse_timestamp_candidate(normalized_candidate, now=now)
        if parsed["age_seconds"] is not None:
            parsed_candidates.append(parsed)

    if not parsed_candidates:
        raw = next(
            (
                candidate
                for candidate in unique_candidates
                if is_plausible_timestamp_candidate(candidate)
            ),
            None,
        )
        return build_timestamp_info(
            raw=raw,
            age_seconds=None,
            confidence="LOW" if raw else "NONE",
            source=source,
            candidates=unique_candidates,
        )

    relative_ages = [
        candidate["age_seconds"]
        for candidate in parsed_candidates
        if candidate["kind"] == "relative"
    ]
    absolute_ages = [
        candidate["age_seconds"]
        for candidate in parsed_candidates
        if candidate["kind"] == "absolute"
    ]

    if relative_ages and absolute_ages:
        closest_difference = min(
            abs(relative_age - absolute_age)
            for relative_age in relative_ages
            for absolute_age in absolute_ages
        )
        if closest_difference > TIMESTAMP_CONFLICT_TOLERANCE_SECONDS:
            return build_timestamp_info(
                raw=" | ".join(unique_candidates),
                age_seconds=None,
                confidence="LOW",
                source=source,
                candidates=unique_candidates,
                warning="conflicting_relative_and_absolute_timestamp",
            )

    chosen = parsed_candidates[0]
    return build_timestamp_info(
        raw=chosen["raw"],
        age_seconds=chosen["age_seconds"],
        confidence="HIGH" if source.endswith("_timestamp") else "MEDIUM",
        source=source,
        candidates=unique_candidates,
    )


def parse_timestamp_candidate(timestamp_raw, now=None):
    absolute_age = parse_absolute_timestamp_age(timestamp_raw, now=now)
    if absolute_age is not None:
        return {
            "raw": timestamp_raw,
            "age_seconds": absolute_age,
            "kind": "absolute",
        }

    relative_age = parse_relative_timestamp_age(timestamp_raw)
    if relative_age is not None:
        return {
            "raw": timestamp_raw,
            "age_seconds": relative_age,
            "kind": "relative",
        }

    return {
        "raw": timestamp_raw,
        "age_seconds": None,
        "kind": "unknown",
    }


def parse_post_age(timestamp_raw):
    return parse_timestamp_age(timestamp_raw)


def parse_timestamp_age(timestamp_raw, now=None):
    parsed = parse_timestamp_candidate(timestamp_raw, now=now)
    return parsed["age_seconds"]


def parse_relative_timestamp_age(timestamp_raw):
    if not timestamp_raw:
        return None

    timestamp = normalize_space(timestamp_raw).lower()
    if timestamp in {"now", "just now"}:
        return 0

    if timestamp == "yesterday":
        return int(24 * 60 * 60)

    match = RELATIVE_TIME_FULL_PATTERN.fullmatch(timestamp)
    if not match:
        return None

    number_text = match.group("number").lower()
    amount = 1 if number_text in {"a", "an", "one"} else int(number_text)
    unit = match.group("unit").lower()

    if unit in {"s", "sec", "secs", "second", "seconds"}:
        return amount
    if unit in {"m", "min", "mins", "minute", "minutes"}:
        return amount * 60
    if unit in {"h", "hr", "hrs", "hour", "hours"}:
        return amount * 60 * 60
    if unit in {"d", "day", "days"}:
        return amount * 24 * 60 * 60
    if unit in {"w", "week", "weeks"}:
        return amount * 7 * 24 * 60 * 60
    if unit in {"mo", "mos", "month", "months"}:
        return amount * 30 * 24 * 60 * 60
    if unit in {"y", "yr", "yrs", "year", "years"}:
        return amount * 365 * 24 * 60 * 60

    return None


def parse_absolute_timestamp_age(timestamp_raw, now=None):
    if not timestamp_raw:
        return None

    timestamp = normalize_space(timestamp_raw)
    if not timestamp:
        return None

    now = now or datetime.now()
    cleaned_timestamp = normalize_absolute_timestamp(timestamp)

    if cleaned_timestamp.lower().startswith("today"):
        return parse_today_or_yesterday_age(cleaned_timestamp, now, days_ago=0)
    if cleaned_timestamp.lower().startswith("yesterday"):
        return parse_today_or_yesterday_age(cleaned_timestamp, now, days_ago=1)

    formats_with_year = [
        "%B %d, %Y %I:%M %p",
        "%B %d, %Y",
        "%b %d, %Y %I:%M %p",
        "%b %d, %Y",
        "%m/%d/%Y %I:%M %p",
        "%m/%d/%Y",
    ]
    formats_without_year = [
        "%B %d %I:%M %p",
        "%B %d",
        "%b %d %I:%M %p",
        "%b %d",
    ]

    for timestamp_format in formats_with_year:
        parsed_datetime = try_parse_datetime(cleaned_timestamp, timestamp_format)
        if parsed_datetime is not None:
            return age_seconds_from_datetime(parsed_datetime, now)

    for timestamp_format in formats_without_year:
        parsed_datetime = try_parse_datetime(
            f"{cleaned_timestamp} {now.year}",
            f"{timestamp_format} %Y",
        )
        if parsed_datetime is None:
            continue

        if parsed_datetime > now + timedelta(days=1):
            parsed_datetime = parsed_datetime.replace(year=now.year - 1)
        return age_seconds_from_datetime(parsed_datetime, now)

    return None


def normalize_absolute_timestamp(timestamp):
    cleaned = re.sub(r"^[A-Za-z]+,\s+", "", timestamp)
    cleaned = re.sub(r"\bat\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def parse_today_or_yesterday_age(timestamp, now, days_ago):
    date_part = now.date() - timedelta(days=days_ago)
    time_match = re.search(r"(\d{1,2}:\d{2}\s*(?:AM|PM))", timestamp, re.IGNORECASE)

    if not time_match:
        return days_ago * 24 * 60 * 60

    parsed_time = try_parse_datetime(time_match.group(1).upper(), "%I:%M %p")
    if parsed_time is None:
        return None

    parsed_datetime = datetime.combine(date_part, parsed_time.time())
    return age_seconds_from_datetime(parsed_datetime, now)


def try_parse_datetime(value, timestamp_format):
    try:
        return datetime.strptime(value, timestamp_format)
    except ValueError:
        return None


def age_seconds_from_datetime(parsed_datetime, now):
    age_seconds = int((now - parsed_datetime).total_seconds())
    if age_seconds < -300:
        return None
    return max(0, age_seconds)


def classify_freshness(post_age_seconds):
    if post_age_seconds is None:
        return "UNKNOWN"
    if post_age_seconds <= VERY_RECENT_MAX_SECONDS:
        return "VERY_RECENT"
    if post_age_seconds <= RECENT_MAX_SECONDS:
        return "RECENT"
    if post_age_seconds <= OLDER_BUT_RELEVANT_MAX_SECONDS:
        return "OLDER_BUT_RELEVANT"
    return "IGNORE"


def is_plausible_timestamp_candidate(value):
    if not value or len(value) > 90:
        return False

    normalized_value = normalize_space(value).lower()
    if normalized_value in {"now", "just now", "today", "yesterday"}:
        return True

    if parse_timestamp_age(normalized_value) is not None:
        return True

    return any(
        marker in normalized_value
        for marker in (
            "ago",
            "yesterday",
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        )
    )
