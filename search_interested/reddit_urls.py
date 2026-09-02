"""URL normalization and canonicalization helpers for Reddit."""

from __future__ import annotations

from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

REDDIT_TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ref",
    "ref_source",
    "share_id",
    "st",
    "sh",
}


def clean_reddit_url(url: str | None) -> str:
    """Strip tracking query parameters and return canonical Reddit URL."""
    if not url:
        return ""

    parsed = urlparse(url.strip())
    if not parsed.scheme or not parsed.netloc:
        return url.strip()

    # Normalize netloc to www.reddit.com if domain is reddit.com / old.reddit.com etc.
    netloc = parsed.netloc.lower()
    if "reddit.com" in netloc:
        netloc = "www.reddit.com"

    query_params = parse_qs(parsed.query, keep_blank_values=False)
    cleaned_params = {
        key: val for key, val in query_params.items() if key.lower() not in REDDIT_TRACKING_PARAMS
    }

    new_query = urlencode(cleaned_params, doseq=True)
    path = parsed.path.rstrip("/")
    if path and not path.endswith("/"):
        path += "/"

    cleaned = urlunparse((parsed.scheme, netloc, path, parsed.params, new_query, parsed.fragment))
    return cleaned


def build_reddit_permalink(permalink: str | None) -> str:
    """Construct full canonical Reddit URL from a relative permalink or raw URL."""
    if not permalink:
        return ""

    permalink = permalink.strip()
    if permalink.startswith("http://") or permalink.startswith("https://"):
        return clean_reddit_url(permalink)

    if not permalink.startswith("/"):
        permalink = "/" + permalink

    full_url = f"https://www.reddit.com{permalink}"
    return clean_reddit_url(full_url)
