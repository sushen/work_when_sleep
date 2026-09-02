"""Chrome/Selenium session setup and recovery."""

from __future__ import annotations

import os
import shutil

from selenium import webdriver
from selenium.common.exceptions import (
    InvalidSessionIdException,
    NoSuchWindowException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .settings import (
    CHROME_DRIVER_PATH,
    CHROME_PROFILE_DIRECTORY,
    DEAD_BROWSER_ERROR_MARKERS,
    FACEBOOK_HOME,
    HEADLESS,
    LOGIN_WAIT_SECONDS,
    USER_DATA_DIRECTORY,
    WAIT_SECONDS,
)
from .text_utils import short_error


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
    options = create_chrome_options()

    if CHROME_DRIVER_PATH.exists():
        try:
            chrome_service = Service(str(CHROME_DRIVER_PATH))
            browser = webdriver.Chrome(service=chrome_service, options=options)
            browser.implicitly_wait(3)
            return browser
        except Exception:
            pass

    driver_path = shutil.which("chromedriver")
    if driver_path:
        chrome_service = Service(driver_path)
    else:
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            chrome_service = Service(ChromeDriverManager().install())
        except Exception:
            chrome_service = Service()

    browser = webdriver.Chrome(service=chrome_service, options=options)
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
