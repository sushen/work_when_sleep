from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
import time
from pathlib import Path

from driver.driver import Driver
from login.login import Login

GROUPS_FILE = "programmers_groups.txt"
PAUSE_BETWEEN = 5        # seconds to let each group page settle before/after actions
WAIT_SECONDS = 12        # selenium explicit wait timeout


def load_group_urls(path: str | Path) -> list[str]:
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def _looks_like_join(text: str) -> bool:
    """True for join-ish labels, false for already-joined / pending states."""
    t = (text or "").strip().lower()
    if not t:
        return False
    if "join" not in t:
        return False
    blocked = ("joined", "member", "pending", "request sent", "requested", "invited")
    return not any(b in t for b in blocked)


def _first_visible(elements):
    for el in elements:
        try:
            if el.is_displayed() and el.is_enabled():
                yield el
        except StaleElementReferenceException:
            continue


def click_join(driver) -> bool:
    """
    Try to click a 'Join' button on the current group page.
    Returns True if a click was made (and any confirmation submitted), else False.
    """
    wait = WebDriverWait(driver, WAIT_SECONDS)

    # Let the main content mount
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[role='main']")))
    except TimeoutException:
        pass

    # Scopes to search under
    scopes = [
        "[role='main']",
        "header",                  # some group headers render join here
        "body",                    # fallback
    ]
    # Broad button-ish selectors (FB changes often)
    base_selectors = [
        "*[role='button']",
        "a[role='link']",
        "button",
        "div[role='link']",
        "div[tabindex]",
        "span[role='button']",
    ]

    # Try multiple passes with light scrolling to coax lazy content
    for _ in range(3):
        for scope in scopes:
            candidates = []
            for sel in base_selectors:
                candidates.extend(driver.find_elements(By.CSS_SELECTOR, f"{scope} {sel}"))

            # Filter by text
            for el in _first_visible(candidates):
                label = (el.get_attribute("aria-label") or el.text or "").strip()
                if _looks_like_join(label):
                    try:
                        el.click()
                        time.sleep(1.2)  # allow dialog to appear / request to send
                        # If a dialog pops, try to confirm
                        confirm_join(driver)
                        return True
                    except Exception:
                        continue

        # Scroll a bit and retry
        driver.execute_script("window.scrollBy(0, Math.min(600, document.body.scrollHeight));")
        time.sleep(1.0)

    return False


def confirm_join(driver) -> None:
    """
    If Facebook opens a confirmation/request dialog, try to press the confirm button.
    We deliberately avoid filling answers to membership questions here.
    """
    wait = WebDriverWait(driver, 4)
    try:
        # Look for obvious confirm buttons in the dialog
        confirm_xpath = " | ".join([
            "//div[@role='dialog']//button[.//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'request')]]",
            "//div[@role='dialog']//button[.//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'submit')]]",
            "//div[@role='dialog']//button[.//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'join')]]",
            "//div[@role='dialog']//div[@role='button'][.//span[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'request')]]",
        ])
        btn = wait.until(EC.element_to_be_clickable((By.XPATH, confirm_xpath)))
        btn.click()
        time.sleep(0.8)
    except TimeoutException:
        # No dialog or nothing to confirm; that's fine.
        pass


def main():
    driver = Driver().driver
    driver.get("https://facebook.com")
    Login().login(driver)
    time.sleep(3)

    groups = load_group_urls(GROUPS_FILE)
    print(f"Loaded {len(groups)} groups from {GROUPS_FILE}")

    for i, url in enumerate(groups, start=1):
        print(f"[{i}/{len(groups)}] Visiting {url}")
        driver.get(url)
        time.sleep(2.5)  # let header render

        joined = click_join(driver)
        if joined:
            print("→ Clicked Join (or sent request).")
        else:
            print("→ No eligible Join button found (already joined/pending, or UI changed).")

        time.sleep(PAUSE_BETWEEN)


if __name__ == "__main__":
    main()
