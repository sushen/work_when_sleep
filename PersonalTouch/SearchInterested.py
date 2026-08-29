import hashlib
import os
import pathlib
import re
import time
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from selenium import webdriver
from selenium.common.exceptions import (
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


SCRIPT_DIRECTORY = pathlib.Path(__file__).resolve().parent
PROJECT_DIRECTORY = SCRIPT_DIRECTORY.parent
GROUP_LIST_FILE = SCRIPT_DIRECTORY / "groupList.txt"
RESULTS_FILE = SCRIPT_DIRECTORY / "search_results.txt"
USER_DATA_DIRECTORY = SCRIPT_DIRECTORY / "userdata"
CHROME_PROFILE_DIRECTORY = "Profile 8"
CHROME_DRIVER_PATH = PROJECT_DIRECTORY / "driver" / "chromedriver.exe"

FACEBOOK_HOME = "https://facebook.com"

HEADLESS = False
WAIT_SECONDS = 30
LOGIN_WAIT_SECONDS = 8
POST_WAIT_SECONDS = 25
SCROLLS_PER_GROUP = 6
SCROLL_PAUSE_SECONDS = 2
GROUP_RETRY_PAUSE_SECONDS = 30

VERY_RECENT_MAX_SECONDS = 60
RECENT_MAX_SECONDS = 5 * 60

DOUBLE_BEEP_PAUSE_SECONDS = 0.2
NORMAL_BEEP_ENABLED = True
UNKNOWN_TIME_BEEP_ENABLED = True

MAX_POST_TEXT_DISPLAY_CHARS = 3000

RELEVANCE_PATTERNS = [
    r"\binterested\b",
    r"\blooking\s+for\b",
    r"\bneed(?:s|ed|ing)?\b",
    r"\bwants?\b",
    r"\bhiring\b",
    r"\bhire\b",
    r"\bfreelanc(?:e|er|ing)\b",
    r"\bdeveloper\b",
    r"\bdesigner\b",
    r"\bwebsite\b",
]

COMPILED_RELEVANCE_PATTERNS = [
    (pattern, re.compile(pattern, re.IGNORECASE)) for pattern in RELEVANCE_PATTERNS
]

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

TIMESTAMP_XPATHS = [
    ".//a[contains(@href, '/posts/')]",
    ".//a[contains(@href, '/permalink/')]",
    ".//a[contains(@href, 'story_fbid=')]",
    ".//a[contains(@href, 'multi_permalinks=')]",
    ".//abbr",
    ".//span[@aria-label or @title]",
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

RELATIVE_TIME_PATTERN = re.compile(
    r"\b(?P<number>\d+|a|an|one)\s*"
    r"(?P<unit>"
    r"seconds?|secs?|s|"
    r"minutes?|mins?|m|"
    r"hours?|hrs?|h|"
    r"days?|d|"
    r"weeks?|w"
    r")\b\s*(?:ago)?",
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


def extract_post_text(post):
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
    return normalize_multiline(post.text)


def find_matching_patterns(post_text):
    return [
        pattern
        for pattern, compiled_pattern in COMPILED_RELEVANCE_PATTERNS
        if compiled_pattern.search(post_text)
    ]


def extract_post_url(post):
    for xpath in POST_URL_XPATHS:
        try:
            for element in post.find_elements(By.XPATH, xpath):
                href = element.get_attribute("href")
                if href and is_facebook_post_url(href):
                    return clean_facebook_url(href)
        except StaleElementReferenceException:
            raise
        except WebDriverException as error:
            print(f"[ERROR] Could not extract post URL: {short_error(error)}")

    return None


def extract_post_timestamp(post):
    first_unknown_candidate = None

    for xpath in TIMESTAMP_XPATHS:
        try:
            for element in post.find_elements(By.XPATH, xpath):
                for candidate in timestamp_candidates_from_element(element):
                    if parse_post_age(candidate) is not None:
                        return candidate

                    if (
                        first_unknown_candidate is None
                        and is_plausible_timestamp_candidate(candidate)
                    ):
                        first_unknown_candidate = candidate
        except StaleElementReferenceException:
            raise
        except WebDriverException as error:
            print(f"[ERROR] Could not extract timestamp: {short_error(error)}")

    return first_unknown_candidate


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


def parse_post_age(timestamp_raw):
    if not timestamp_raw:
        return None

    timestamp = normalize_space(timestamp_raw).lower()
    if timestamp in {"now", "just now"}:
        return 0

    match = RELATIVE_TIME_PATTERN.search(timestamp)
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

    return None


def classify_freshness(post_age_seconds):
    if post_age_seconds is None:
        return "UNKNOWN"
    if post_age_seconds <= VERY_RECENT_MAX_SECONDS:
        return "VERY_RECENT"
    if post_age_seconds <= RECENT_MAX_SECONDS:
        return "RECENT"
    return "NORMAL"


def is_plausible_timestamp_candidate(value):
    if not value or len(value) > 90:
        return False

    normalized_value = normalize_space(value).lower()
    if normalized_value in {"now", "just now"}:
        return True

    if RELATIVE_TIME_PATTERN.search(normalized_value):
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


def clean_facebook_url(url):
    parsed = urlparse(url)
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key not in TRACKING_QUERY_PARAMS and not key.startswith("__")
    ]
    return urlunparse(parsed._replace(query=urlencode(query), fragment=""))


def build_post_key(group_url, post_url, post_text, timestamp_raw):
    if post_url:
        return f"url:{post_url}"

    fallback = "|".join(
        [
            normalize_space(group_url).lower(),
            normalize_space(timestamp_raw or "").lower(),
            normalize_space(post_text).lower()[:1000],
        ]
    )
    return "hash:" + hashlib.sha1(fallback.encode("utf-8")).hexdigest()


def build_match_info(
    group_name,
    group_url,
    post_text,
    post_url,
    matched_patterns,
    timestamp_raw,
):
    post_age_seconds = parse_post_age(timestamp_raw)
    freshness_level = classify_freshness(post_age_seconds)

    return {
        "detection_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "group_name": group_name,
        "group_url": group_url,
        "post_text": post_text,
        "post_url": post_url,
        "matched_patterns": matched_patterns,
        "timestamp_raw": timestamp_raw,
        "post_age_seconds": post_age_seconds,
        "freshness_level": freshness_level,
    }


def save_match(match_info):
    appended_text = format_match_record(match_info)

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
        print(f"[ERROR] Could not save match: {error}")
        return False


def format_match_record(match_info):
    separator = "=" * 50
    matched_patterns = "\n".join(
        f"    {pattern}" for pattern in match_info["matched_patterns"]
    )

    return (
        f"{separator}\n"
        "MATCH FOUND\n"
        f"{separator}\n\n"
        "Detected:\n"
        f"{match_info['detection_time']}\n\n"
        "Group:\n"
        f"{match_info['group_name']}\n\n"
        "Group URL:\n"
        f"{match_info['group_url']}\n\n"
        "Post URL:\n"
        f"{match_info['post_url'] or 'UNKNOWN'}\n\n"
        "Matched Patterns:\n"
        f"{matched_patterns or '    UNKNOWN'}\n\n"
        "Facebook Timestamp:\n"
        f"{match_info['timestamp_raw'] or 'UNKNOWN'}\n\n"
        "Post Age:\n"
        f"{format_age(match_info['post_age_seconds'])}\n\n"
        "Freshness:\n"
        f"{match_info['freshness_level']}\n\n"
        "Post Text:\n"
        f"{match_info['post_text']}\n\n"
        f"{separator}\n\n"
    )


def alert_user(freshness_level):
    try:
        if freshness_level == "VERY_RECENT":
            print("[ALERT] VERY_RECENT -> DOUBLE BEEP")
            beep()
            time.sleep(DOUBLE_BEEP_PAUSE_SECONDS)
            beep()
        elif freshness_level == "RECENT":
            print("[ALERT] RECENT -> SINGLE BEEP")
            beep()
        elif freshness_level == "NORMAL" and NORMAL_BEEP_ENABLED:
            print("[ALERT] NORMAL -> SINGLE BEEP")
            beep()
        elif freshness_level == "UNKNOWN" and UNKNOWN_TIME_BEEP_ENABLED:
            print("[ALERT] UNKNOWN TIME -> SINGLE BEEP")
            beep()
        else:
            print(f"[ALERT] {freshness_level} -> CONSOLE ONLY")
    except RuntimeError as error:
        print(f"[ERROR] Could not play alert sound: {error}")


def display_match(match_info):
    print("[MATCH] Relevant post found")
    print(f"[MATCH] Group: {match_info['group_name']}")
    print(f"[MATCH] Pattern: {', '.join(match_info['matched_patterns'])}")
    print(f"[TIME] Post age: {format_age(match_info['post_age_seconds'])}")
    print(f"[MATCH] Freshness: {match_info['freshness_level']}")
    print(f"[MATCH] Post URL: {match_info['post_url'] or 'UNKNOWN'}")
    print(f"[MATCH] Text: {first_line(match_info['post_text'])}")
    print("[SCAN] Continuing...")


def scan_loaded_posts(browser, group_name, group_url, seen_posts):
    posts = find_post_containers(browser)
    print(f"[SCAN] {len(posts)} posts detected")

    for post in posts:
        try:
            post_text = extract_post_text(post)
            if not post_text:
                continue

            matched_patterns = find_matching_patterns(post_text)
            if not matched_patterns:
                continue

            post_url = extract_post_url(post)
            timestamp_raw = extract_post_timestamp(post)
            post_key = build_post_key(group_url, post_url, post_text, timestamp_raw)

            if post_key in seen_posts:
                continue
            seen_posts.add(post_key)

            match_info = build_match_info(
                group_name=group_name,
                group_url=group_url,
                post_text=post_text,
                post_url=post_url,
                matched_patterns=matched_patterns,
                timestamp_raw=timestamp_raw,
            )

            save_match(match_info)
            alert_user(match_info["freshness_level"])
            display_match(match_info)
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
    if not scan_loaded_posts(browser, group_name, group_url, seen_posts):
        return False

    for scroll_number in range(1, SCROLLS_PER_GROUP + 1):
        print(f"[SCAN] Scroll {scroll_number}/{SCROLLS_PER_GROUP}")
        scroll_down(browser)
        if not scan_loaded_posts(browser, group_name, group_url, seen_posts):
            return False

    return True


def run_continuous_scanner(browser, start_time):
    seen_posts = set()
    group_index = 1

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

        success = False
        rotated = False

        try:
            success = scan_group(
                browser=browser,
                group_url=current_group,
                group_index=group_index,
                group_count=group_count,
                seen_posts=seen_posts,
            )
        except TimeoutException as error:
            print(f"[ERROR] Could not load group posts: {short_error(error)}")
        except WebDriverException as error:
            print(f"[ERROR] Could not load group: {short_error(error)}")

        if success:
            rotated = rotate_current_group(current_group)
            if rotated:
                next_group = get_current_group()
                if next_group:
                    print("[QUEUE] Next group:")
                    print(f"    {next_group}")
            else:
                print("[QUEUE] Current group was not rotated; it remains first.")
        else:
            print("[GROUP] Scan failed; moving current group to bottom.")
            rotated = rotate_current_group(current_group)
            if rotated:
                next_group = get_current_group()
                if next_group:
                    print("[QUEUE] Next group:")
                    print(f"    {next_group}")
            else:
                print("[QUEUE] Current group was not rotated; it remains first.")
            print(f"[WAIT] Continuing after {GROUP_RETRY_PAUSE_SECONDS} seconds.")
            time.sleep(GROUP_RETRY_PAUSE_SECONDS)

        print_running_time(start_time)
        print("[SCAN] Continuing...")
        if rotated:
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
