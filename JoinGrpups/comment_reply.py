from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import time
import random
import pyautogui
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

# Reply behavior (existing comments)
REPLY_TEXT = "Thanks for the insight!"
# If you want to match a specific comment by substring, set this to a phrase (case-insensitive)
REPLY_BY_TEXT = None  # e.g., "great idea"
# If REPLY_BY_TEXT is None, we'll reply to the N-th visible comment's Reply button
REPLY_INDEX = 0


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


def human_hover(driver, element, duration=0.6):
    """Move the real mouse over an element to trigger hover-only UI."""
    try:
        box = driver.execute_script(
            """
            const r = arguments[0].getBoundingClientRect();
            return {x:r.left, y:r.top, w:r.width, h:r.height};
            """,
            element,
        )
    except Exception:
        return

    win_pos = driver.get_window_position()
    # Adjust for browser chrome height (rough heuristic)
    TITLEBAR_TOOLBAR_OFFSET_Y = 90
    SIDEBORDER_OFFSET_X = 8

    center_x = win_pos['x'] + SIDEBORDER_OFFSET_X + box['x'] + box['w'] / 2
    center_y = win_pos['y'] + TITLEBAR_TOOLBAR_OFFSET_Y + box['y'] + box['h'] / 2

    try:
        pyautogui.moveTo(center_x, center_y, duration=duration)
    except Exception:
        pass


# ----------------------------
# Comment expansion & Reply to EXISTING comments
# ----------------------------

def expand_comments_and_replies(driver, post, max_clicks=6):
    """
    Expand 'View more comments' and 'View more replies' so per-comment 'Reply' exists in the DOM.
    """
    wait = WebDriverWait(driver, 8)

    # Expand "View more comments"
    for _ in range(max_clicks):
        try:
            btns = [
                el for el in post.find_elements(
                    By.XPATH,
                    './/*[@role="button"][.//span[contains(normalize-space(.), "View") and contains(normalize-space(.), "comment")]]',
                ) if el.is_displayed()
            ]
            if not btns:
                break
            driver.execute_script("arguments[0].click();", btns[0])
            wait.until(lambda d: not btns[0].is_displayed() or not btns[0].is_enabled())
            time.sleep(0.3)
        except Exception:
            break

    # Expand "View more replies"
    for _ in range(max_clicks):
        try:
            btns = [
                el for el in post.find_elements(
                    By.XPATH,
                    './/*[@role="button"][.//span[contains(normalize-space(.), "View") and contains(normalize-space(.), "repl")]]',
                ) if el.is_displayed()
            ]
            if not btns:
                break
            driver.execute_script("arguments[0].click();", btns[0])
            wait.until(lambda d: not btns[0].is_displayed() or not btns[0].is_enabled())
            time.sleep(0.3)
        except Exception:
            break


def reply_to_existing_comment(
    driver,
    post,
    reply_text: str,
    comment_index: int = 0,                 # 0 = first visible comment
    comment_text_contains: str | None = None,
) -> bool:
    """
    Click the 'Reply' under an existing comment and submit an inline reply.

    One of `comment_text_contains` or `comment_index` is used to pick which comment to reply to.
    """
    wait = WebDriverWait(driver, 12)
    actions = ActionChains(driver)

    # Ensure the post is fully hydrated and comments visible
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", post)
    except Exception:
        pass
    time.sleep(0.4)
    expand_comments_and_replies(driver, post)

    # Gather visible "Reply" controls scoped to this post
    reply_btn_candidates = post.find_elements(
        By.XPATH,
        (
            './/*[@role="button" and ('
            '   .//span[normalize-space()="Reply"] or '
            '   normalize-space(.)="Reply" or '
            '   contains(@aria-label, "Reply")'
            ')]'
        ),
    )
    reply_btn_candidates = [el for el in reply_btn_candidates if el.is_displayed()]

    if not reply_btn_candidates:
        print("Reply failed: no visible 'Reply' buttons found under this post.")
        return False

    target_btn = None
    if comment_text_contains:
        target_lc = comment_text_contains.strip().lower()
        for btn in reply_btn_candidates:
            try:
                # Heuristic: nearest ancestor that represents the comment container
                container = btn.find_element(
                    By.XPATH,
                    './ancestor::*[contains(@role,"article") or @role="group" or @role="listitem" or @role="region"][1]',
                )
            except Exception:
                container = btn
            txt = (container.text or "").strip().lower()
            if target_lc in txt:
                target_btn = btn
                break

    if target_btn is None:
        # Fallback to index
        if comment_index < 0 or comment_index >= len(reply_btn_candidates):
            print(
                f"Reply failed: comment_index {comment_index} out of range (found {len(reply_btn_candidates)} reply buttons)."
            )
            return False
        target_btn = reply_btn_candidates[comment_index]

    # Some UIs reveal 'Reply' only on hover
    try:
        actions.move_to_element(target_btn).pause(0.2).perform()
    except Exception:
        pass

    # Click the Reply control; fall back to JS if normal click is blocked
    try:
        target_btn.click()
    except Exception:
        try:
            driver.execute_script("arguments[0].click();", target_btn)
        except Exception:
            close_common_overlays(driver)
            try:
                driver.execute_script("arguments[0].click();", target_btn)
            except Exception as e:
                print(f"Reply failed: could not click Reply ({e})")
                return False

    # Find the inline reply editor that appears under that comment
    editor_locators = [
        (By.CSS_SELECTOR, 'div[aria-label="Write a reply"]'),
        (By.XPATH, './/div[@role="textbox" and @contenteditable="true"]'),
        (By.CSS_SELECTOR, 'div[contenteditable="true"][data-lexical-editor]'),
        (By.XPATH, './/div[contains(@aria-label,"reply") and @role="textbox"]'),
    ]

    editor = None
    for how, sel in editor_locators:
        try:
            editor = wait.until(EC.visibility_of_element_located((how, sel)))
            if editor and editor.is_displayed():
                break
        except TimeoutException:
            editor = None

    if not editor:
        print("Reply failed: reply editor did not appear.")
        return False

    # Type and submit
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", editor)
        time.sleep(0.2)
        editor.click()
        editor.send_keys(reply_text)
        time.sleep(0.4)
        editor.send_keys(Keys.ENTER)
        time.sleep(0.8)
        print("Reply posted successfully.")
        return True
    except Exception as e:
        print(f"Reply failed while typing/sending: {e}")
        return False


# ----------------------------
# Like posts, then reply to an EXISTING comment
# ----------------------------

def like_first_posts(driver, count: int = 5):
    """
    Like the first 'count' posts in a Facebook group.
    Then reply to an existing comment under each liked post.
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

        # Keep action bar alive
        try:
            ActionChains(driver).move_to_element(post).perform()
        except Exception:
            pass

        # ---- Reply to an EXISTING comment under this post ----
        reply_ok = reply_to_existing_comment(
            driver,
            post,
            reply_text=REPLY_TEXT,
            comment_index=(REPLY_INDEX if REPLY_BY_TEXT is None else 0),
            comment_text_contains=REPLY_BY_TEXT,
        )
        if not reply_ok:
            print(f"Post {idx}: could not reply to a comment (skipping).")

        rand_sleep(*LIKE_SLEEP_RANGE)

    print(f"Finished this group: liked {liked} post(s).")


# ----------------------------
# Main
# ----------------------------
if __name__ == "__main__":
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
        time.sleep(6)

    print("All groups processed.")
