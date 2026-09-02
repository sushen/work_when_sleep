"""Configuration and selectors for the Facebook opportunity scanner."""

from __future__ import annotations

import pathlib


PACKAGE_DIRECTORY = pathlib.Path(__file__).resolve().parent
PROJECT_DIRECTORY = PACKAGE_DIRECTORY.parent
PERSONAL_TOUCH_DIRECTORY = PROJECT_DIRECTORY / "PersonalTouch"
GROUP_LIST_FILE = PACKAGE_DIRECTORY / "groupList.txt"
INACTIVE_GROUPS_FILE = PACKAGE_DIRECTORY / "inactive_groups.txt"
RESULTS_FILE = PACKAGE_DIRECTORY / "search_results.txt"
USER_DATA_DIRECTORY = PERSONAL_TOUCH_DIRECTORY / "userdata"
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

# Reddit integration configuration
REDDIT_ENABLED = True
REDDIT_QUERIES_FILE = PACKAGE_DIRECTORY / "reddit_queries.txt"
REDDIT_POLL_INTERVAL_SECONDS = 10
REDDIT_MAX_RESULTS_PER_QUERY = 25
REDDIT_MAX_OPPORTUNITY_AGE_SECONDS = 24 * 60 * 60
REDDIT_ALERT_QUALITY_LEVELS = {"STRONG", "POSSIBLE"}
REDDIT_REQUEST_TIMEOUT_SECONDS = 10
REDDIT_RETRY_DELAY_SECONDS = 30
REDDIT_USER_AGENT = "SearchInterested/1.0 (Opportunity Discovery Scanner)"
