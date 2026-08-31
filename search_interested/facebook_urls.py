"""Facebook URL normalization and identity helpers."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .settings import TRACKING_QUERY_PARAMS


def is_facebook_post_url(url):
    parsed = urlparse(url)
    if "facebook.com" not in parsed.netloc:
        return False

    return any(
        marker in url
        for marker in (
            "/posts/",
            "/permalink/",
            "story_fbid=",
            "multi_permalinks=",
        )
    )


def is_facebook_comment_url(url):
    parsed = urlparse(url)
    if "facebook.com" not in parsed.netloc:
        return False

    query_keys = {key for key, _ in parse_qsl(parsed.query, keep_blank_values=True)}
    return "comment_id" in query_keys or "reply_comment_id" in query_keys


def clean_facebook_url(url):
    parsed = urlparse(url)
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key not in TRACKING_QUERY_PARAMS and not key.startswith("__")
    ]
    return urlunparse(parsed._replace(query=urlencode(query), fragment=""))


def extract_parent_post_url(content_url):
    if not content_url or not is_facebook_comment_url(content_url):
        return content_url

    parsed = urlparse(content_url)
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key not in {"comment_id", "reply_comment_id"}
    ]
    return clean_facebook_url(
        urlunparse(parsed._replace(query=urlencode(query), fragment=""))
    )
