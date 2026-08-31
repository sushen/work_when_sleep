"""Opportunity signal scoring and classification."""

from __future__ import annotations

import re

from .settings import (
    POSSIBLE_OPPORTUNITY_THRESHOLD,
    SAVE_QUALITY_LEVELS,
    STRONG_OPPORTUNITY_THRESHOLD,
)
from .signals import (
    find_commercial_signals,
    find_intent_signals,
    find_interested_signals,
    find_negative_signals,
    find_problem_signals,
    find_service_signals,
    find_urgency_signals,
)
from .text_utils import normalize_space


def analyze_opportunity(text):
    normalized_text = normalize_space(text)
    signal_groups = {
        "intent": find_intent_signals(normalized_text),
        "service": find_service_signals(normalized_text),
        "problem": find_problem_signals(normalized_text),
        "commercial": find_commercial_signals(normalized_text),
        "urgency": find_urgency_signals(normalized_text),
        "negative": find_negative_signals(normalized_text),
        "compatibility": find_interested_signals(normalized_text),
    }
    interested_only = is_interested_only(normalized_text)
    score = calculate_opportunity_score(signal_groups, interested_only)
    quality = classify_opportunity(signal_groups, score, interested_only)

    return {
        "signal_groups": signal_groups,
        "matched_signals": flatten_signal_names(signal_groups),
        "score": score,
        "quality": quality,
        "is_opportunity": quality in SAVE_QUALITY_LEVELS,
    }


def calculate_opportunity_score(signal_groups, interested_only=False):
    if interested_only:
        return 0

    score = 0
    score += min(total_signal_weight(signal_groups["intent"]), 5)
    score += min(total_signal_weight(signal_groups["service"]), 3)
    score += min(total_signal_weight(signal_groups["problem"]), 2)
    score += min(total_signal_weight(signal_groups["commercial"]), 2)
    score += min(total_signal_weight(signal_groups["urgency"]), 1)
    score -= min(total_signal_weight(signal_groups["negative"]), 6)

    return max(score, 0)


def classify_opportunity(signal_groups, score, interested_only=False):
    has_intent = bool(signal_groups["intent"])
    has_service = bool(signal_groups["service"])
    has_problem = bool(signal_groups["problem"])
    has_commercial = bool(signal_groups["commercial"])
    has_negative = bool(signal_groups["negative"])

    if interested_only:
        return "WEAK"

    if has_obvious_provider_context(signal_groups) and not has_intent:
        return "WEAK"

    if has_negative and score < POSSIBLE_OPPORTUNITY_THRESHOLD:
        return "WEAK"

    if (
        has_intent
        and has_service
        and has_strong_intent(signal_groups)
        and score >= STRONG_OPPORTUNITY_THRESHOLD
    ):
        return "STRONG"

    if (
        has_intent
        and has_problem
        and (has_service or has_commercial)
        and (has_strong_intent(signal_groups) or has_commercial)
        and score >= STRONG_OPPORTUNITY_THRESHOLD
    ):
        return "STRONG"

    if (
        has_service
        and has_problem
        and score >= POSSIBLE_OPPORTUNITY_THRESHOLD
    ):
        return "POSSIBLE"

    if (
        has_intent
        and (has_problem or has_commercial)
        and score >= POSSIBLE_OPPORTUNITY_THRESHOLD
    ):
        return "POSSIBLE"

    return "WEAK"


def has_strong_intent(signal_groups):
    strong_intent_signals = {
        "looking_for",
        "looking_to_hire",
        "need_person",
        "hiring",
        "can_anyone_help",
        "anyone_know_someone",
        "who_can",
        "searching_for",
        "role_needed",
    }
    intent_names = {signal["name"] for signal in signal_groups["intent"]}
    return bool(strong_intent_signals & intent_names)


def has_obvious_provider_context(signal_groups):
    provider_signals = {
        "self_promotion",
        "as_a_provider",
        "developer_here",
        "work_as_provider",
        "available_provider",
    }
    negative_names = {signal["name"] for signal in signal_groups["negative"]}
    return bool(provider_signals & negative_names)


def is_interested_only(text):
    lowered = normalize_space(text).lower()
    lowered = re.sub(r"[^a-z0-9\s]", "", lowered)
    return lowered in {"interested", "i am interested", "im interested"}


def total_signal_weight(signals):
    return sum(signal["weight"] for signal in signals)


def flatten_signal_names(signal_groups):
    signal_names = []

    for group_name in (
        "intent",
        "service",
        "problem",
        "commercial",
        "urgency",
        "negative",
        "compatibility",
    ):
        for signal in signal_groups[group_name]:
            name = signal["name"]
            if name not in signal_names:
                signal_names.append(name)

    return signal_names


def is_fresh_opportunity_timestamp(timestamp_info):
    return timestamp_info["freshness"] in {
        "VERY_RECENT",
        "RECENT",
        "OLDER_BUT_RELEVANT",
    }
