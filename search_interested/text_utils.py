"""Small text, display, and logging helpers."""

from __future__ import annotations

import re
import time


def normalize_space(value):
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_multiline(value):
    lines = [line.strip() for line in (value or "").splitlines() if line.strip()]
    return "\n".join(lines)


def limit_text(value, max_chars):
    if len(value) <= max_chars:
        return value
    return value[:max_chars].rstrip() + "\n...[truncated]"


def indent_text(value, spaces=4):
    prefix = " " * spaces
    return "\n".join(f"{prefix}{line}" for line in (value or "").splitlines())


def first_line(value):
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    return limit_text(lines[0] if lines else "", 160)


def format_age(post_age_seconds):
    if post_age_seconds is None:
        return "UNKNOWN"
    if post_age_seconds < 60:
        return f"{post_age_seconds} seconds"
    if post_age_seconds < 60 * 60:
        return f"{post_age_seconds // 60} minutes"
    if post_age_seconds < 24 * 60 * 60:
        return f"{post_age_seconds // (60 * 60)} hours"
    return f"{post_age_seconds // (24 * 60 * 60)} days"


def short_error(error):
    message = str(error).splitlines()[0] if str(error) else error.__class__.__name__
    return message[:250]


def print_running_time(start_time):
    total_seconds = int(time.time() - start_time)
    print(f"[TIME] This script is running for {total_seconds} seconds.")
    print(f"[TIME] This script is running for {int(total_seconds / 60)} minutes.")
