import hashlib
import os
import pathlib
import re
import time
from datetime import datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from selenium import webdriver
from selenium.common.exceptions import (
    InvalidSessionIdException,
    NoSuchWindowException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

try:
    from .notifier import beep
except ImportError:
    from notifier import beep

try:
    from .signals import (
        find_commercial_signals,
        find_intent_signals,
        find_interested_signals,
        find_negative_signals,
        find_problem_signals,
        find_service_signals,
        find_urgency_signals,
    )
except ImportError:
    from signals import (
        find_commercial_signals,
        find_intent_signals,
        find_interested_signals,
        find_negative_signals,
        find_problem_signals,
        find_service_signals,
        find_urgency_signals,
    )


SCRIPT_DIRECTORY = pathlib.Path(__file__).resolve().parent
PROJECT_DIRECTORY = SCRIPT_DIRECTORY.parent
GROUP_LIST_FILE = SCRIPT_DIRECTORY / "groupList.txt"
INACTIVE_GROUPS_FILE = SCRIPT_DIRECTORY / "inactive_groups.txt"
RESULTS_FILE = SCRIPT_DIRECTORY / "search_results.txt"
USER_DATA_DIRECTORY = SCRIPT_DIRECTORY / "userdata"
CHROME_PROFILE_DIRECTORY = "Profile 8"
CHROME_DRIVER_PATH = PROJECT_DIRECTORY / "driver" / "chromedriver.exe"

FACEBOOK_HOME = "https://facebook.com"

HEADLESS = False
WAIT_SECONDS = 10
LOGIN_WAIT_SECONDS = 8
POST_WAIT_SECONDS = 25
SCROLLS_PER_GROUP = 6
SCROLL_PAUSE_SECONDS = 2
GROUP_RETRY_PAUSE_SECONDS = 30
MAX_GROUP_FAILURES_BEFORE_ROTATE = 3

DEAD_BROWSER_ERROR_MARKERS = (
    "invalid session id",
    "no such window",
    "target window already closed",
    "chrome not reachable",
    "disconnected",
)

VERY_RECENT_MAX_SECONDS = 60
RECENT_MAX_SECONDS = 24 * 60 * 60
OLDER_BUT_RELEVANT_MAX_SECONDS = 6 * 24 * 60 * 60
ACTIVE_GROUP_MAX_AGE_SECONDS = OLDER_BUT_RELEVANT_MAX_SECONDS
MIN_RECENT_POSTS_FOR_ACTIVE = 1
ACTIVITY_POST_SAMPLE_LIMIT = 8
MIN_ACTIVITY_TEXT_CHARS = 8

BEEP_PAUSE_SECONDS = 0.2

MAX_POST_TEXT_DISPLAY_CHARS = 3000
SAVE_QUALITY_LEVELS = {"STRONG", "POSSIBLE"}
ALERT_QUALITY_LEVELS = {"STRONG", "POSSIBLE"}
STRONG_OPPORTUNITY_THRESHOLD = 5
POSSIBLE_OPPORTUNITY_THRESHOLD = 4
TIMESTAMP_CONFLICT_TOLERANCE_SECONDS = 4 * 60 * 60

# Keep Facebook XPath guesses in one place because their DOM changes often.
POST_CONTAINER_XPATHS = [
    "//div[@role='article']",
    "//div[@aria-label='Actions for this post']/ancestor::div[@role='article'][1]",
]
POST_WAIT_XPATH = "//div[@role='article'] | //div[@aria-label='Actions for this post']"
POST_ACTION_XPATH = ".//div[@aria-label='Actions for this post']"

POST_TEXT_XPATHS = [
    ".//div[@data-ad-preview='message']",
    ".//div[@data-ad-comet-preview='message']",
]

POST_URL_XPATHS = [
    ".//a[contains(@href, '/posts/')]",
    ".//a[contains(@href, '/permalink/')]",
    ".//a[contains(@href, 'story_fbid=')]",
    ".//a[contains(@href, 'multi_permalinks=')]",
]

COMMENT_URL_XPATHS = [
    ".//a[contains(@href, 'comment_id=')]",
]

POST_TIMESTAMP_XPATHS = [
    ".//a[contains(@href, '/posts/')]",
    ".//a[contains(@href, '/permalink/')]",
    ".//a[contains(@href, 'story_fbid=')]",
    ".//a[contains(@href, 'multi_permalinks=')]",
]

COMMENT_TIMESTAMP_XPATHS = [
    ".//a[contains(@href, 'comment_id=')]",
    ".//abbr",
]

TRACKING_QUERY_PARAMS = {
    "fbclid",
    "__cft__",
    "__tn__",
    "ref",
    "refid",
    "mibextid",
    "paipv",
}

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


def create_chrome_options():
    USER_DATA_DIRECTORY.mkdir(exist_ok=True)

    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument(f"--user-data-dir={USER_DATA_DIRECTORY}")
    chrome_options.add_argument(f"--profile-directory={CHROME_PROFILE_DIRECTORY}")
    chrome_options.add_argument("--disable-infobars")
    if HEADLESS:
        chrome_options.add_argument("--headless=new")
    chrome_options.add_experimental_option(
        "prefs", {"profile.default_content_setting_values.notifications": 2}
    )
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    return chrome_options


def create_driver():
    chrome_service = Service(str(CHROME_DRIVER_PATH))
    browser = webdriver.Chrome(service=chrome_service, options=create_chrome_options())
    browser.implicitly_wait(3)
    return browser


def restart_driver(browser):
    print("[BROWSER] Selenium session is dead; restarting Chrome.")
    close_driver(browser)
    browser = create_driver()
    login_if_needed(browser)
    print("[BROWSER] Chrome restarted.")
    return browser


def close_driver(browser):
    try:
        browser.quit()
    except WebDriverException:
        pass


def is_dead_browser_session(error):
    if isinstance(error, (InvalidSessionIdException, NoSuchWindowException)):
        return True

    message = str(error).lower()
    return any(marker in message for marker in DEAD_BROWSER_ERROR_MARKERS)


def wait_for_page_ready(browser, timeout=WAIT_SECONDS):
    WebDriverWait(browser, timeout).until(
        lambda active_browser: active_browser.execute_script("return document.readyState")
        in {"interactive", "complete"}
    )


def login_if_needed(browser):
    browser.get(FACEBOOK_HOME)
    wait_for_page_ready(browser)

    try:
        email_input = WebDriverWait(browser, LOGIN_WAIT_SECONDS).until(
            EC.presence_of_element_located((By.NAME, "email"))
        )
    except TimeoutException:
        print("[LOGIN] Existing Facebook session detected.")
        return

    username = os.environ.get("my_facebook_email")
    password = os.environ.get("my_facebook_pass")

    if not username or not password:
        print(
            "[LOGIN] Login form found, but my_facebook_email/my_facebook_pass "
            "environment variables are missing."
        )
        input("[PAUSED] Log in manually in Chrome, then press Enter to continue: ")
        return

    try:
        email_input.clear()
        email_input.send_keys(username)
        browser.find_element(By.NAME, "pass").send_keys(password)
        browser.find_element(By.NAME, "login").click()
        print("[LOGIN] Credentials submitted.")
        input(
            "[PAUSED] Complete any Facebook login checks in Chrome, "
            "then press Enter to continue: "
        )
    except WebDriverException as error:
        print(f"[ERROR] Could not submit login form: {short_error(error)}")
        input("[PAUSED] Log in manually in Chrome, then press Enter to continue: ")


def read_group_queue_lines():
    try:
        with open(GROUP_LIST_FILE, encoding="utf-8") as file:
            return file.read().splitlines()
    except OSError as error:
        print(f"[ERROR] Could not read group list: {error}")
        return []


def is_group_queue_entry(line):
    stripped_line = line.strip()
    return bool(stripped_line) and not stripped_line.startswith("#")


def load_group_urls(log=True):
    group_urls = [
        line.strip()
        for line in read_group_queue_lines()
        if is_group_queue_entry(line)
    ]

    if log:
        print(f"[QUEUE] {len(group_urls)} groups loaded from {GROUP_LIST_FILE}")

    return group_urls


def get_current_group(group_urls=None):
    if group_urls is None:
        group_urls = load_group_urls(log=False)

    if not group_urls:
        return None

    return group_urls[0]


def save_group_queue(queue_lines):
    temp_file = GROUP_LIST_FILE.with_name(f"{GROUP_LIST_FILE.name}.tmp")

    try:
        text = "\n".join(queue_lines)
        if text:
            text += "\n"

        with open(temp_file, "w", encoding="utf-8", newline="\n") as file:
            file.write(text)
            file.flush()
            os.fsync(file.fileno())

        os.replace(temp_file, GROUP_LIST_FILE)
        return True
    except OSError as error:
        print(f"[ERROR] Could not update group queue: {error}")
        return False


def rotate_current_group(completed_group_url):
    queue_lines = read_group_queue_lines()

    for index, line in enumerate(queue_lines):
        if not is_group_queue_entry(line):
            continue

        current_group = line.strip()
        if current_group != completed_group_url:
            print("[ERROR] Group queue changed before rotation.")
            print(f"[QUEUE] Expected current group: {completed_group_url}")
            print(f"[QUEUE] Actual current group: {current_group}")
            return False

        updated_queue = list(queue_lines)
        updated_queue.pop(index)
        updated_queue.append(current_group)

        if save_group_queue(updated_queue):
            print("[QUEUE] Current group moved to bottom")
            print("[QUEUE] Appended to bottom:")
            print(f"    {current_group}")
            return True

        return False

    print("[ERROR] Could not rotate queue because it is empty.")
    return False


def load_inactive_group_urls():
    try:
        with open(INACTIVE_GROUPS_FILE, encoding="utf-8") as file:
            return {
                line.strip()
                for line in file.read().splitlines()
                if is_group_queue_entry(line)
            }
    except FileNotFoundError:
        return set()
    except OSError as error:
        print(f"[ERROR] Could not read inactive group list: {error}")
        return set()


def append_inactive_group(group_url):
    inactive_urls = load_inactive_group_urls()
    if group_url in inactive_urls:
        return True

    try:
        with open(INACTIVE_GROUPS_FILE, "a", encoding="utf-8", newline="\n") as file:
            file.write(group_url + "\n")
            file.flush()
            os.fsync(file.fileno())
        print(f"[QUEUE] Group added to inactive list: {group_url}")
        return True
    except OSError as error:
        print(f"[ERROR] Could not update inactive group list: {error}")
        return False


def move_group_to_inactive(group_url):
    if not append_inactive_group(group_url):
        return False

    queue_lines = read_group_queue_lines()
    for index, line in enumerate(queue_lines):
        if not is_group_queue_entry(line):
            continue

        current_group = line.strip()
        if current_group != group_url:
            print("[ERROR] Group queue changed before inactive move.")
            print(f"[QUEUE] Expected current group: {group_url}")
            print(f"[QUEUE] Actual current group: {current_group}")
            return False

        updated_queue = list(queue_lines)
        updated_queue.pop(index)

        if save_group_queue(updated_queue):
            print("[QUEUE] Inactive group removed from active queue")
            return True

        return False

    print("[ERROR] Could not move inactive group because active queue is empty.")
    return False


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


def build_post_key(group_url, post_url, post_text, timestamp_raw):
    return build_opportunity_key(
        group_url=group_url,
        content_url=post_url,
        content_type="POST",
        content_text=post_text,
        timestamp_raw=timestamp_raw,
    )


def build_opportunity_key(
    group_url,
    content_url,
    content_type,
    content_text,
    timestamp_raw,
):
    if content_url:
        return f"url:{content_url}"

    fallback = "|".join(
        [
            normalize_space(group_url).lower(),
            normalize_space(content_type).lower(),
            normalize_space(timestamp_raw or "").lower(),
            normalize_space(content_text).lower()[:1000],
        ]
    )
    return "hash:" + hashlib.sha1(fallback.encode("utf-8")).hexdigest()


def build_opportunity(
    group_name,
    group_url,
    content_type,
    author,
    content_text,
    content_url,
    timestamp_info,
    opportunity_analysis,
    opportunity_key=None,
):
    if opportunity_key is None:
        opportunity_key = build_opportunity_key(
            group_url=group_url,
            content_url=content_url,
            content_type=content_type,
            content_text=content_text,
            timestamp_raw=timestamp_info["raw"],
        )

    return {
        "detection_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "group_name": group_name,
        "group_url": group_url,
        "content_type": content_type,
        "author": author or "UNKNOWN",
        "content_text": content_text,
        "content_url": content_url,
        "parent_post_url": extract_parent_post_url(content_url),
        "opportunity_key": opportunity_key,
        "matched_signals": opportunity_analysis["matched_signals"],
        "opportunity_score": opportunity_analysis["score"],
        "opportunity_quality": opportunity_analysis["quality"],
        "timestamp_raw": timestamp_info["raw"],
        "timestamp_confidence": timestamp_info["confidence"],
        "timestamp_source": timestamp_info["source"],
        "timestamp_warning": timestamp_info["warning"],
        "content_age_seconds": timestamp_info["age_seconds"],
        "freshness_level": timestamp_info["freshness"],
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


def save_opportunity(opportunity):
    appended_text = format_opportunity_record(opportunity)

    try:
        with open(RESULTS_FILE, "a", encoding="utf-8") as file:
            file.write(appended_text)
            file.flush()
            os.fsync(file.fileno())

        print(f"[SAVE] Saved to {RESULTS_FILE}")
        print("[SAVE] Appended text:")
        print(appended_text.rstrip())
        return True
    except OSError as error:
        print(f"[ERROR] Could not save opportunity: {error}")
        return False


def save_match(match_info):
    return save_opportunity(match_info)


def load_seen_opportunity_keys():
    try:
        text = RESULTS_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        return set()
    except OSError as error:
        print(f"[ERROR] Could not read existing results for duplicate detection: {error}")
        return set()

    seen_keys = set()
    for key in re.findall(r"(?m)^\s*Opportunity Key:\s*\n\s*(\S+)", text):
        seen_keys.add(key.strip())

    for url in re.findall(r"(?m)^\s*(?:Post URL|URL):\s*\n\s*(https?://\S+)", text):
        cleaned_url = clean_facebook_url(url)
        if cleaned_url and cleaned_url.upper() != "UNKNOWN":
            seen_keys.add(f"url:{cleaned_url}")

    if seen_keys:
        print(f"[DUPLICATE] Loaded {len(seen_keys)} saved opportunity keys")

    return seen_keys


def format_opportunity_record(opportunity):
    separator = "=" * 50
    matched_signals = "\n".join(
        f"    {signal}" for signal in opportunity["matched_signals"]
    )

    return (
        f"{separator}\n"
        "OPPORTUNITY FOUND\n"
        f"{separator}\n\n"
        "Detected:\n"
        f"    {opportunity['detection_time']}\n\n"
        "Group:\n"
        f"    {opportunity['group_name']}\n\n"
        "Group URL:\n"
        f"    {opportunity['group_url']}\n\n"
        "Content:\n"
        f"    {opportunity['content_type']}\n\n"
        "Author:\n"
        f"    {opportunity['author']}\n\n"
        "URL:\n"
        f"    {opportunity['content_url'] or 'UNKNOWN'}\n\n"
        "Parent Post URL:\n"
        f"    {opportunity['parent_post_url'] or 'UNKNOWN'}\n\n"
        "Opportunity Key:\n"
        f"    {opportunity['opportunity_key']}\n\n"
        "Signals:\n"
        f"{matched_signals or '    UNKNOWN'}\n\n"
        "Score:\n"
        f"    {opportunity['opportunity_score']}\n\n"
        "Quality:\n"
        f"    {opportunity['opportunity_quality']}\n\n"
        "Facebook Timestamp:\n"
        f"    {opportunity['timestamp_raw'] or 'UNKNOWN'}\n\n"
        "Timestamp Confidence:\n"
        f"    {opportunity['timestamp_confidence']}\n\n"
        "Timestamp Source:\n"
        f"    {opportunity['timestamp_source']}\n\n"
        "Timestamp Warning:\n"
        f"    {opportunity['timestamp_warning'] or 'NONE'}\n\n"
        "Age:\n"
        f"    {format_age(opportunity['content_age_seconds'])}\n\n"
        "Freshness:\n"
        f"    {opportunity['freshness_level']}\n\n"
        "Text:\n"
        f"{indent_text(limit_text(opportunity['content_text'], MAX_POST_TEXT_DISPLAY_CHARS))}\n\n"
        f"{separator}\n\n"
    )


def format_match_record(match_info):
    return format_opportunity_record(match_info)


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
    print("[MATCH] Opportunity found")
    print(f"[MATCH] Group: {opportunity['group_name']}")
    print(f"[MATCH] Content: {opportunity['content_type']}")
    print(f"[MATCH] Author: {opportunity['author']}")
    print(f"[MATCH] Quality: {opportunity['opportunity_quality']}")
    print(f"[MATCH] Score: {opportunity['opportunity_score']}")
    print(f"[MATCH] Signals: {', '.join(opportunity['matched_signals'])}")
    print(f"[TIME] Age: {format_age(opportunity['content_age_seconds'])}")
    print(f"[MATCH] Freshness: {opportunity['freshness_level']}")
    print(f"[MATCH] URL: {opportunity['content_url'] or 'UNKNOWN'}")
    print(f"[MATCH] Text: {first_line(opportunity['content_text'])}")
    print("[SCAN] Continuing...")


def display_match(match_info):
    display_opportunity(match_info)


def check_group_activity(browser, group_name, group_url):
    posts = find_post_containers(browser)
    known_ages = []
    recent_posts = 0
    meaningful_posts = 0
    unknown_timestamps = 0

    for post in posts[:ACTIVITY_POST_SAMPLE_LIMIT]:
        try:
            content_type = extract_content_type(post)
            if content_type != "POST":
                continue

            author = extract_author(post)
            post_text = extract_content_text(post, content_type, author=author)
            if not is_meaningful_activity_text(post_text):
                continue

            meaningful_posts += 1
            timestamp_info = extract_timestamp(post, content_type)
            age_seconds = timestamp_info["age_seconds"]

            if age_seconds is None:
                unknown_timestamps += 1
                continue

            known_ages.append(age_seconds)
            if age_seconds <= ACTIVE_GROUP_MAX_AGE_SECONDS:
                recent_posts += 1
        except StaleElementReferenceException:
            print("[ERROR] Post became stale during activity check.")
        except WebDriverException as error:
            print(f"[ERROR] Could not check group activity: {short_error(error)}")

    latest_age = min(known_ages) if known_ages else None
    if recent_posts >= MIN_RECENT_POSTS_FOR_ACTIVE:
        status = "ACTIVE"
    elif known_ages and unknown_timestamps == 0:
        status = "INACTIVE"
    else:
        status = "UNKNOWN"

    activity_info = {
        "status": status,
        "latest_age_seconds": latest_age,
        "recent_posts": recent_posts,
        "meaningful_posts": meaningful_posts,
        "known_timestamps": len(known_ages),
        "unknown_timestamps": unknown_timestamps,
    }

    print(
        "[ACTIVITY] "
        f"{group_name} -> {status}; "
        f"recent={recent_posts}, "
        f"known_timestamps={len(known_ages)}, "
        f"unknown_timestamps={unknown_timestamps}, "
        f"latest_age={format_age(latest_age)}"
    )
    return activity_info


def is_meaningful_activity_text(text):
    return len(normalize_space(text)) >= MIN_ACTIVITY_TEXT_CHARS


def scan_loaded_posts(browser, group_name, group_url, seen_posts):
    posts = find_post_containers(browser)
    print(f"[SCAN] {len(posts)} posts detected")

    for post in posts:
        try:
            content_type = extract_content_type(post)
            author = extract_author(post)
            content_text = extract_content_text(post, content_type, author=author)
            if not content_text:
                continue

            content_url = extract_content_url(post, content_type)
            timestamp_info = extract_timestamp(post, content_type)
            content_key = build_opportunity_key(
                group_url=group_url,
                content_url=content_url,
                content_type=content_type,
                content_text=content_text,
                timestamp_raw=timestamp_info["raw"],
            )

            if content_key in seen_posts:
                continue
            seen_posts.add(content_key)

            if not is_fresh_opportunity_timestamp(timestamp_info):
                print(
                    "[TIME] Skipping stale/unknown "
                    f"{content_type.lower()} timestamp: "
                    f"{timestamp_info['raw'] or 'UNKNOWN'} "
                    f"({timestamp_info['freshness']})"
                )
                continue

            opportunity_analysis = analyze_opportunity(content_text)
            if not opportunity_analysis["is_opportunity"]:
                continue

            opportunity = build_opportunity(
                group_name=group_name,
                group_url=group_url,
                content_type=content_type,
                author=author,
                content_text=content_text,
                content_url=content_url,
                timestamp_info=timestamp_info,
                opportunity_analysis=opportunity_analysis,
                opportunity_key=content_key,
            )

            save_opportunity(opportunity)
            alert_opportunity(opportunity)
            display_opportunity(opportunity)
        except StaleElementReferenceException:
            print("[ERROR] Post became stale; skipping it.")
        except WebDriverException as error:
            print(f"[ERROR] Could not process post: {short_error(error)}")

    return True


def scan_group(browser, group_url, group_index, group_count, seen_posts):
    print(f"[GROUP {group_index}/{group_count}] Opening group")
    print(f"[GROUP {group_index}/{group_count}] {group_url}")

    browser.get(group_url)
    wait_for_page_ready(browser)
    wait_for_posts(browser)

    group_name = get_group_name(browser, group_url)
    print(f"[GROUP {group_index}/{group_count}] Page loaded: {group_name}")

    page_start(browser)
    activity_info = check_group_activity(browser, group_name, group_url)
    if activity_info["status"] == "INACTIVE":
        print("[GROUP] No meaningful recent activity; moving group to inactive queue.")
        return {
            "success": True,
            "inactive": True,
            "activity": activity_info,
        }

    if activity_info["status"] == "UNKNOWN":
        print("[GROUP] Activity timestamp confidence is unknown; scanning conservatively.")

    if not scan_loaded_posts(browser, group_name, group_url, seen_posts):
        return {
            "success": False,
            "inactive": False,
            "activity": activity_info,
        }

    for scroll_number in range(1, SCROLLS_PER_GROUP + 1):
        print(f"[SCAN] Scroll {scroll_number}/{SCROLLS_PER_GROUP}")
        scroll_down(browser)
        if not scan_loaded_posts(browser, group_name, group_url, seen_posts):
            return {
                "success": False,
                "inactive": False,
                "activity": activity_info,
            }

    return {
        "success": True,
        "inactive": False,
        "activity": activity_info,
    }


def run_continuous_scanner(browser, start_time):
    seen_posts = load_seen_opportunity_keys()
    group_index = 1
    group_failures = {}

    print("[START] Scanner started")

    while True:
        group_urls = load_group_urls()
        current_group = get_current_group(group_urls)

        if not current_group:
            print("[END] No groups to scan.")
            break

        group_count = len(group_urls)
        if group_index > group_count:
            group_index = 1

        scan_result = {
            "success": False,
            "inactive": False,
            "activity": None,
        }
        success = False
        rotated = False
        moved_to_inactive = False

        try:
            scan_result = scan_group(
                browser=browser,
                group_url=current_group,
                group_index=group_index,
                group_count=group_count,
                seen_posts=seen_posts,
            )
            success = scan_result["success"]
        except TimeoutException as error:
            print(f"[ERROR] Could not load group posts: {short_error(error)}")
        except WebDriverException as error:
            print(f"[ERROR] Could not load group: {short_error(error)}")
            if is_dead_browser_session(error):
                try:
                    browser = restart_driver(browser)
                except WebDriverException as restart_error:
                    print(f"[ERROR] Could not restart Chrome: {short_error(restart_error)}")

        if success and scan_result["inactive"]:
            group_failures.pop(current_group, None)
            moved_to_inactive = move_group_to_inactive(current_group)
            if moved_to_inactive:
                next_group = get_current_group()
                if next_group:
                    print("[QUEUE] Next group:")
                    print(f"    {next_group}")
            else:
                print("[QUEUE] Inactive group was not removed; it remains first.")
        elif success:
            group_failures.pop(current_group, None)
            rotated = rotate_current_group(current_group)
            if rotated:
                next_group = get_current_group()
                if next_group:
                    print("[QUEUE] Next group:")
                    print(f"    {next_group}")
            else:
                print("[QUEUE] Current group was not rotated; it remains first.")
        else:
            failure_count = group_failures.get(current_group, 0) + 1
            group_failures[current_group] = failure_count
            print(
                "[GROUP] Scan failed "
                f"({failure_count}/{MAX_GROUP_FAILURES_BEFORE_ROTATE})."
            )

            if failure_count >= MAX_GROUP_FAILURES_BEFORE_ROTATE:
                print("[QUEUE] Too many failures; moving current group to bottom.")
                rotated = rotate_current_group(current_group)
                if rotated:
                    group_failures.pop(current_group, None)
                    next_group = get_current_group()
                    if next_group:
                        print("[QUEUE] Next group:")
                        print(f"    {next_group}")
                else:
                    print("[QUEUE] Current group was not rotated; it remains first.")
            else:
                print("[GROUP] Current group remains first for retry.")
                print(f"[WAIT] Continuing after {GROUP_RETRY_PAUSE_SECONDS} seconds.")
                time.sleep(GROUP_RETRY_PAUSE_SECONDS)

        print_running_time(start_time)
        print("[SCAN] Continuing...")
        if rotated or moved_to_inactive:
            group_index = (group_index % group_count) + 1


def get_group_name(browser, group_url):
    title = normalize_space(browser.title)
    if title and title.lower() != "facebook":
        return title.replace(" | Facebook", "")

    path_parts = [part for part in urlparse(group_url).path.split("/") if part]
    if path_parts:
        return path_parts[-1]

    return group_url


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


def main():
    start_time = time.time()
    print("[START] This script started " + time.ctime())
    beep()

    browser = create_driver()
    login_if_needed(browser)

    try:
        run_continuous_scanner(browser, start_time)
    except KeyboardInterrupt:
        print("\n[STOP] Scanner stopped by user.")

    end_time = time.time()
    print("\n[END] This script ended " + time.ctime())
    total_running_time = end_time - start_time
    print(f"[TIME] This script ran for {int(total_running_time)} seconds.")
    print(f"[TIME] This script ran for {int(total_running_time / 60)} minutes.")


if __name__ == "__main__":
    main()
