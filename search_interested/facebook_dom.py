"""Facebook DOM extraction helpers for posts and comments."""

from __future__ import annotations

import time

from selenium.common.exceptions import StaleElementReferenceException, WebDriverException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .facebook_urls import (
    clean_facebook_url,
    is_facebook_comment_url,
    is_facebook_post_url,
)
from .settings import (
    COMMENT_TIMESTAMP_XPATHS,
    COMMENT_URL_XPATHS,
    POST_CONTAINER_XPATHS,
    POST_TEXT_XPATHS,
    POST_TIMESTAMP_XPATHS,
    POST_URL_XPATHS,
    POST_WAIT_SECONDS,
    POST_WAIT_XPATH,
    SCROLL_PAUSE_SECONDS,
)
from .text_utils import normalize_multiline, normalize_space, short_error
from .timestamps import (
    build_timestamp_info,
    choose_timestamp_from_candidates,
    is_plausible_timestamp_candidate,
    parse_timestamp_age,
)


def page_start(browser):
    ActionChains(browser).send_keys(Keys.HOME).perform()
    time.sleep(1)


def scroll_down(browser):
    ActionChains(browser).send_keys(Keys.PAGE_DOWN).perform()
    time.sleep(SCROLL_PAUSE_SECONDS)


def wait_for_posts(browser):
    WebDriverWait(browser, POST_WAIT_SECONDS).until(
        EC.presence_of_element_located((By.XPATH, POST_WAIT_XPATH))
    )


def find_post_containers(browser, log_errors=True):
    candidates = []

    for xpath in POST_CONTAINER_XPATHS:
        try:
            candidates.extend(browser.find_elements(By.XPATH, xpath))
        except WebDriverException as error:
            if log_errors:
                print(f"[ERROR] Could not locate post containers: {short_error(error)}")

    unique_candidates = []
    seen_element_ids = set()
    for element in candidates:
        if element.id in seen_element_ids:
            continue
        seen_element_ids.add(element.id)

        try:
            if element.is_displayed() and normalize_space(element.text):
                unique_candidates.append(element)
        except StaleElementReferenceException:
            print("[ERROR] Post became stale while collecting containers.")
        except WebDriverException as error:
            if log_errors:
                print(f"[ERROR] Could not inspect post container: {short_error(error)}")

    return remove_nested_containers(browser, unique_candidates)


def remove_nested_containers(browser, containers):
    filtered = []

    for candidate in containers:
        try:
            candidate_is_nested = False
            replacements = []

            for existing in filtered:
                existing_contains_candidate = browser.execute_script(
                    "return arguments[0] !== arguments[1] && arguments[0].contains(arguments[1]);",
                    existing,
                    candidate,
                )
                candidate_contains_existing = browser.execute_script(
                    "return arguments[0] !== arguments[1] && arguments[0].contains(arguments[1]);",
                    candidate,
                    existing,
                )

                if existing_contains_candidate:
                    candidate_is_nested = True
                    replacements.append(existing)
                elif candidate_contains_existing:
                    continue
                else:
                    replacements.append(existing)

            if not candidate_is_nested:
                replacements.append(candidate)

            filtered = replacements
        except StaleElementReferenceException:
            print("[ERROR] Post became stale while removing duplicate containers.")
        except WebDriverException:
            filtered.append(candidate)

    return filtered


def extract_content_type(post):
    try:
        for xpath in POST_TEXT_XPATHS:
            if post.find_elements(By.XPATH, xpath):
                return "POST"
    except StaleElementReferenceException:
        raise
    except WebDriverException:
        pass

    if extract_post_url(post):
        return "POST"

    if extract_comment_url(post):
        return "COMMENT"

    return "POST"


def extract_author(content_element):
    author_xpaths = [
        ".//h2//a[@role='link']",
        ".//h3//a[@role='link']",
        ".//strong//a",
        ".//a[@role='link']",
    ]

    seen_values = set()
    for xpath in author_xpaths:
        try:
            for element in content_element.find_elements(By.XPATH, xpath):
                text = normalize_space(element.text)
                if not text or text in seen_values:
                    continue
                seen_values.add(text)

                href = element.get_attribute("href") or ""
                if is_plausible_author_name(text, href):
                    return text
        except StaleElementReferenceException:
            raise
        except WebDriverException as error:
            print(f"[ERROR] Could not extract author: {short_error(error)}")

    fallback_text = normalize_multiline(content_element.text)
    for line in fallback_text.splitlines():
        candidate = normalize_space(line)
        if is_plausible_author_name(candidate, ""):
            return candidate

    return "UNKNOWN"


def is_plausible_author_name(text, href):
    if not text or len(text) > 80:
        return False

    lowered = text.lower()
    if lowered in {
        "like",
        "comment",
        "share",
        "reply",
        "see more",
        "follow",
        "join group",
        "active",
        "online status indicator",
    }:
        return False

    if parse_timestamp_age(text) is not None or is_plausible_timestamp_candidate(text):
        return False

    if href and (is_facebook_post_url(href) or is_facebook_comment_url(href)):
        return False

    if href and any(marker in href for marker in ("/events/", "/watch/")):
        return False

    if href and "/groups/" in href and "/user/" not in href:
        return False

    return any(character.isalpha() for character in text)


def extract_content_text(content_element, content_type, author=None):
    if content_type == "COMMENT":
        return extract_comment_text(content_element, author=author)
    return extract_post_text(content_element, author=author)


def extract_post_text(post, author=None):
    text_parts = []

    for xpath in POST_TEXT_XPATHS:
        try:
            for element in post.find_elements(By.XPATH, xpath):
                text = normalize_multiline(element.text)
                if text and text not in text_parts:
                    text_parts.append(text)
        except StaleElementReferenceException:
            raise
        except WebDriverException as error:
            print(f"[ERROR] Could not extract post text using XPath: {short_error(error)}")

    if text_parts:
        return "\n\n".join(text_parts)

    # Fallback stays post-level; it avoids the old full-page text scan.
    return clean_fallback_content_text(post.text, author=author)


def extract_comment_text(comment, author=None):
    return clean_fallback_content_text(comment.text, author=author)


def clean_fallback_content_text(raw_text, author=None):
    cleaned_lines = []
    author_normalized = normalize_space(author or "").lower()

    for line in normalize_multiline(raw_text).splitlines():
        normalized_line = normalize_space(line)
        lowered_line = normalized_line.lower()

        if not normalized_line:
            continue
        if author_normalized and lowered_line == author_normalized:
            continue
        if is_noise_content_line(normalized_line):
            continue

        cleaned_lines.append(normalized_line)

    return "\n".join(cleaned_lines)


def is_noise_content_line(line):
    lowered = normalize_space(line).lower()
    if lowered in {
        "like",
        "comment",
        "comments",
        "share",
        "reply",
        "edited",
        "follow",
        "see more",
        "see less",
        "see translation",
        "hide",
        "active",
        "online status indicator",
        "top contributor",
        "admin",
        "author",
    }:
        return True

    if lowered == "." or lowered == "-":
        return True
    if parse_timestamp_age(line) is not None:
        return True

    return False


def extract_post_url(post):
    for xpath in POST_URL_XPATHS:
        try:
            for element in post.find_elements(By.XPATH, xpath):
                href = element.get_attribute("href")
                if (
                    href
                    and is_facebook_post_url(href)
                    and not is_facebook_comment_url(href)
                ):
                    return clean_facebook_url(href)
        except StaleElementReferenceException:
            raise
        except WebDriverException as error:
            print(f"[ERROR] Could not extract post URL: {short_error(error)}")

    return None


def extract_comment_url(comment):
    for xpath in COMMENT_URL_XPATHS:
        try:
            for element in comment.find_elements(By.XPATH, xpath):
                href = element.get_attribute("href")
                if href and is_facebook_comment_url(href):
                    return clean_facebook_url(href)
        except StaleElementReferenceException:
            raise
        except WebDriverException as error:
            print(f"[ERROR] Could not extract comment URL: {short_error(error)}")

    return None


def extract_content_url(content_element, content_type):
    if content_type == "COMMENT":
        return extract_comment_url(content_element) or extract_post_url(content_element)
    return extract_post_url(content_element)


def extract_post_timestamp(post):
    return extract_timestamp(post, "POST")["raw"]


def extract_timestamp(content_element, content_type):
    timestamp_xpaths = (
        COMMENT_TIMESTAMP_XPATHS if content_type == "COMMENT" else POST_TIMESTAMP_XPATHS
    )
    first_unknown_candidate = None

    for xpath in timestamp_xpaths:
        try:
            for element in content_element.find_elements(By.XPATH, xpath):
                href = element.get_attribute("href") or ""
                if content_type == "POST" and is_facebook_comment_url(href):
                    continue
                if content_type == "COMMENT" and href and not is_facebook_comment_url(href):
                    continue

                timestamp_info = timestamp_info_from_element(
                    element,
                    source=f"{content_type.lower()}_timestamp",
                )
                if timestamp_info["age_seconds"] is not None:
                    return timestamp_info

                for candidate in timestamp_info["candidates"]:
                    if (
                        first_unknown_candidate is None
                        and is_plausible_timestamp_candidate(candidate)
                    ):
                        first_unknown_candidate = candidate
        except StaleElementReferenceException:
            raise
        except WebDriverException as error:
            print(f"[ERROR] Could not extract timestamp: {short_error(error)}")

    return build_timestamp_info(
        raw=first_unknown_candidate,
        age_seconds=None,
        confidence="LOW" if first_unknown_candidate else "NONE",
        source=f"{content_type.lower()}_timestamp",
        candidates=[first_unknown_candidate] if first_unknown_candidate else [],
    )


def timestamp_info_from_element(element, source):
    candidates = timestamp_candidates_from_element(element)
    return choose_timestamp_from_candidates(candidates, source=source)


def timestamp_candidates_from_element(element):
    candidates = []

    for attribute_name in ("aria-label", "title", "datetime"):
        value = normalize_space(element.get_attribute(attribute_name))
        if value and value not in candidates:
            candidates.append(value)

    text = normalize_space(element.text)
    if text and text not in candidates:
        candidates.append(text)

    return candidates
