"""Page Object Model class for Facebook Group Member Requests page interactions."""

from __future__ import annotations

import time

from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from Pages.BasePage import BasePage
from search_interested.browser_session import wait_for_page_ready
from search_interested.facebook_dom import (
    extract_author,
    extract_content_text,
    extract_timestamp,
)
from search_interested.facebook_urls import clean_facebook_url
from search_interested.settings import (
    GOETHE_MEMBER_REQUESTS_URL,
    WAIT_SECONDS,
)


class FacebookGroupMemberRequestsPage(BasePage):
    """Page Object for Facebook Group Member Requests page."""

    MEMBER_REQUEST_CARDS = (
        By.XPATH,
        "//div[@role='article'] | "
        "//div[contains(@aria-label, 'Member request')] | "
        "//div[contains(@class, 'x1n2onr6') and .//a[contains(@href, '/user/') or contains(@href, 'facebook.com/')]]",
    )

    def __init__(self, driver):
        super().__init__(driver)

    def navigate_to_member_requests(self, url: str = GOETHE_MEMBER_REQUESTS_URL) -> None:
        """Navigate directly to Goethe Group Member Requests URL."""
        self.driver.get(url)
        wait_for_page_ready(self.driver, timeout=WAIT_SECONDS)

    def reload_page(self) -> None:
        """Reload the member requests page."""
        self.driver.refresh()
        wait_for_page_ready(self.driver, timeout=WAIT_SECONDS)

    def wait_for_first_member_request(self, timeout: int = 10) -> bool:
        """Wait until the first member request card element is present."""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located(self.MEMBER_REQUEST_CARDS)
            )
            return True
        except TimeoutException:
            return False

    def get_first_member_request(
        self,
        group_name: str = "Goethe Group Bangladesh",
        group_url: str = GOETHE_MEMBER_REQUESTS_URL,
        max_retries: int = 3,
        timeout: int = 10,
    ) -> dict | None:
        """Locate ONLY the first/newest member request card and extract its data."""
        for attempt in range(max_retries):
            try:
                if not self.wait_for_first_member_request(timeout=timeout):
                    return None

                elements = self.driver.find_elements(*self.MEMBER_REQUEST_CARDS)
                if not elements:
                    return None

                first_card = elements[0]
                data = self.extract_member_request_data(
                    first_card, group_name=group_name, group_url=group_url
                )
                if data:
                    return data
            except StaleElementReferenceException:
                print(f"[POM] Stale element on attempt {attempt + 1}/{max_retries}, retrying...")
                time.sleep(0.5)
                continue
            except Exception as error:
                print(f"[POM] Error extracting first member request data: {error}")
                return None

        return None

    def get_visible_member_requests(self) -> list:
        """Legacy helper for visible member request elements."""
        try:
            elements = self.driver.find_elements(*self.MEMBER_REQUEST_CARDS)
            return elements
        except Exception as error:
            print(f"[POM] Error finding member request elements: {error}")
            return []

    def extract_member_request_data(
        self,
        element,
        group_name: str = "Goethe Group Bangladesh",
        group_url: str = GOETHE_MEMBER_REQUESTS_URL,
    ) -> dict | None:
        """Extract structured dictionary from single member request DOM element."""
        try:
            author = extract_author(element)
            text = extract_content_text(element, "MEMBER_REQUEST", author=author)

            if not text and hasattr(element, "text") and element.text:
                text = element.text.strip()

            if not text:
                return None

            timestamp_info = extract_timestamp(element, "MEMBER_REQUEST")

            request_url = group_url
            try:
                links = element.find_elements(
                    By.XPATH,
                    ".//a[contains(@href, '/user/') or contains(@href, 'profile.php')]",
                )
                for link in links:
                    href = link.get_attribute("href")
                    if href:
                        request_url = clean_facebook_url(href)
                        break
            except StaleElementReferenceException:
                raise
            except Exception:
                pass

            return {
                "source": "facebook",
                "source_type": "goethe_member_request",
                "group_name": group_name,
                "group_url": group_url,
                "author": author or "UNKNOWN",
                "content_text": text,
                "content_url": request_url,
                "content_type": "MEMBER_REQUEST",
                "timestamp_info": timestamp_info,
            }
        except StaleElementReferenceException:
            raise
        except Exception as error:
            print(f"[POM] Error extracting member request data: {error}")
            return None
