from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import random
from pathlib import Path

from driver.driver import Driver
from login.login import Login


# ----------------------------
# Config
# ----------------------------
GROUPS_FILE = "groups_list.txt"
# How long to wait for a group feed to hydrate before trying to like posts
GROUP_LOAD_WAIT = 25
# Pause between opening groups (helps with lazy/hydrated UIs)
PAUSE_BETWEEN_GROUPS = 6
# Number of posts to like per group
LIKE_COUNT = 5
# Sleep range between likes (human-ish pacing)
LIKE_SLEEP_RANGE = (1.2, 2.4)


# ----------------------------
# Helpers
# ----------------------------
def load_group_urls(path: str | Path) -> list[str]:
    """Read all group URLs from the text file."""
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def rand_sleep(a: float, b: float):
    time.sleep(random.uniform(a, b))


def close_common_overlays(driver):
    """Best-effort close for cookie / notification overlays that can intercept clicks."""
    candidates = [
        # Cookies consent buttons (common variants)
        (By.XPATH, "//div[@role='dialog']//div[@aria-label='Allow all cookies' or @aria-label='Accept all' or @aria-label='Okay' or @aria-label='OK']"),
        (By.XPATH, "//div[@role='dialog']//span[normalize-space()='Allow all cookies' or normalize-space()='Accept all' or normalize-space()='OK']/ancestor::*[@role='button']"),
        # "Turn on notifications" or similar upsells
        (By.XPATH, "//div[@role='dialog']//div[@aria-label='Not now' or @aria-label='Close']"),
        (By.XPATH, "//div[@role='dialog']//span[normalize-space()='Not now' or normalize-space()='Close']/ancestor::*[@role='button']"),
        # Generic dialog close
        (By.XPATH, "//div[@role='dialog']//div[@aria-label='Close']"),
    ]
    for how, sel in candidates:
        try:
            elems = driver.find_elements(how, sel)
            for el in elems:
                if el.is_displayed():
                    el.click()
                    rand_sleep(0.3, 0.6)
        except Exception:
            pass


def like_first_posts(driver, count: int = 5):
    """
    Like the first 'count' posts in a Facebook group.
    Uses resilient selectors and proper waits.
    """
    wait = WebDriverWait(driver, GROUP_LOAD_WAIT)

    # Let the feed render at least one post
    try:
        wait.until(EC.presence_of_element_located((By.XPATH, '//div[@role="article"]')))
    except TimeoutException:
        print("No posts detected on this group page (timeout). Skipping.")
        return

    close_common_overlays(driver)

    # Collect posts; additional small scroll to trigger lazy load
    posts = driver.find_elements(By.XPATH, '//div[@role="article"]')
    if not posts:
        print("No posts found after initial hydrate. Skipping.")
        return

    liked = 0

    # Candidate selectors for the Like control.
    # Keep "Like" for English UI. If your FB language is different, replace the text-based ones.
    like_locators = [
        # Most reliable: role=button with aria-label containing Like and not already pressed
        (By.CSS_SELECTOR, '[role="button"][aria-label*="Like"]:not([aria-pressed="true"])'),
        # Sometimes a span acts as the button
        (By.CSS_SELECTOR, 'span[role="button"][aria-label*="Like"]:not([aria-pressed="true"])'),
        # Action bar variant under the post container
        (By.XPATH, './/*[(@role="button") and contains(@aria-label,"Like") and not(@aria-pressed="true")]'),
        # Fallback: visible text (works on some UIs/locales)
        (By.XPATH, './/span[contains(normalize-space(.), "Like")]/ancestor::*[@role="button" and not(@aria-pressed="true")]'),
    ]

    for idx, post in enumerate(posts, start=1):
        if liked >= count:
            break

        # Bring post into view to ensure its action bar is loaded
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", post)
        except Exception:
            pass
        rand_sleep(0.4, 0.8)

        # Try to locate a like button within this post
        like_el = None
        for how, sel in like_locators:
            try:
                candidates = post.find_elements(how, sel)
                # pick first visible candidate
                like_el = next((el for el in candidates if el.is_displayed()), None)
                if like_el:
                    break
            except Exception:
                continue

        if not like_el:
            print(f"Post {idx}: could not locate an unpressed Like button; skipping.")
            continue

        # Attempt click with fallback to JS (intercepts/overlays are common)
        try:
            like_el.click()
        except Exception:
            try:
                driver.execute_script("arguments[0].click();", like_el)
            except Exception as e2:
                print(f"Post {idx}: click failed ({e2}); retrying after closing overlays.")
                close_common_overlays(driver)
                try:
                    driver.execute_script("arguments[0].click();", like_el)
                except Exception as e3:
                    print(f"Post {idx}: final click failed ({e3}); skipping.")
                    continue

        liked += 1
        print(f"Liked post {idx} (total liked: {liked})")
        rand_sleep(*LIKE_SLEEP_RANGE)

    print(f"Finished this group: liked {liked} post(s).")


# ----------------------------
# Main
# ----------------------------
driver = Driver().driver
driver.get("https://facebook.com")
Login().login(driver)

groups = load_group_urls(GROUPS_FILE)
print(f"Loaded {len(groups)} groups from {GROUPS_FILE}")

for i, url in enumerate(groups, start=1):
    print(f"[{i}/{len(groups)}] Visiting {url}")
    driver.get(url)
    # allow group page to settle a bit before we search for posts
    rand_sleep(PAUSE_BETWEEN_GROUPS, PAUSE_BETWEEN_GROUPS + 2)
    like_first_posts(driver, count=LIKE_COUNT)
    # print(input("Next Group:"))
    time.sleep(10)

print("All groups processed.")
